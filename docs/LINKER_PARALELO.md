# Linker Nativo ELF64 em `Bytes` e Paralelismo Determinístico — DCC 0.2.0 (Ciclo V)

Data: 21/11/2026  
Arquivos: `src/linker/linker.delegua`, `src/linker/elf_leitor.delegua`, `src/object/elf/elf_comum.delegua`, `tests/test_paralelismo.py`.

---

## 1. Transformação Arquitetural do Linker (Ciclo IV → Ciclo V)

### 1.1. Eliminação de `inteiro[]` (24 B/byte) por `cgd:bytes.Bytes` (1 B/byte em `GC_MALLOC_ATOMIC`)
No Ciclo IV, `cli.delegua`, `elf_leitor.delegua` e `linker.delegua` convertiam todos os arquivos `.o` e `.a` em vetores `inteiro[]` (24 bytes por byte no heap GC, escaneados pelo Boehm GC a cada coleta) e construíam o executável final concatenando `inteiro[]` byte a byte.

No Ciclo V:
- `cli.delegua` lê `.o`/`.a` diretamente com `Bytes.lerArquivo()` e recebe `.o` compilados via `elfObjMod.emitirObjetoELF64Bytes()`.
- `elf_leitor.delegua` lê cabeçalhos, seções, `.symtab`, `.strtab`, `.rela.*` e membros de archives `.a` diretamente sobre `Bytes` via `lerU16LE`/`lerU32LE`/`lerU64LE`/`lerCString`.
- `linker.delegua` calcula prefix-sums de `.text`, `.rodata`, `.data` e `.bss`, pré-aloca exatamente os buffers `userText`, `mergedRodata`, `mergedData`, `corpoPreText`, `finalText`, `segRW` e o ELF64 executável final com `Bytes.criarReservado(...)`, copiando seções via `anexarBytesFatia` (`memcpy` nativo em C) e liberando buffers intermediários imediatamente (`liberar()`).

### 1.2. Fases Paralelizáveis via `rotina` CGD (`Bytes` Congelado *Zero-Copy*)

| Etapa do Linker | Execução | Mecanismo | Determinismo |
|---|---|---|---|
| **1. Leitura/Validação de `.o` e membros `.a`** | Paralela acima do limiar | `rotina leitor.validarESerializarElfWorker(bCong.recursoInterno())` em janelas de até 128 tarefas (backpressure) | Resultados materializados estritamente na ordem `0..N-1` da CLI |
| **2. Extração iterativa de `.a` (ponto fixo)** | Sequencial | Depende do conjunto acumulado de símbolos indefinidos | Ordem determinística exata da CLI |
| **3. Resolução de símbolos globais/fracos/COMMON/ABS** | Sequencial | Detecta duplicatas fortes (`E5001`), prevalência forte > fraco, alocação `SHN_COMMON` em `.bss` | 100% determinístico |
| **4. Layout de segmentos (W^X RX/RW), PLT/GOT, `.dynsym`/`.hash`** | Sequencial | Prefix-sums determinísticos | 100% determinístico |
| **5. Cálculo e validação de patches de relocação x86-64** | Paralela acima do limiar | `rotina prepararPatchesRelocWorker(loteCong.recursoInterno())` em `nLotes` balanceados (`80 B`/entrada → `18 B`/patch) | Aplicação ordenada verificando limites de seção e **ausência de sobreposição** (`vistosPatch`) |
| **6. Emissão do binário ELF64 executável** | Sequencial | Alocação única `Bytes.criarReservado(tamFinalElf)` + `anexarBytes` | 100% determinístico |

### 1.3. Segurança Mantida e Reforçada
- Todos os limites anti-DoS e validações ELF64/ar do Ciclo III/IV foram preservados dentro de `validarESerializarElfWorker` (magic, 64-bit LE, `ET_REL`, `EM_X86_64`, `shoff`/`shnum`/`shentsize`/`shstrndx`, `shAlign` anti-bomba, `shOffset + shSize`, índices `symIdx` em `.rela.*`).
- Patches paralelos de relocação validam estouro de 32 bits (`E5014`), tipos não suportados (`E5013`), limites da seção alvo (`E5015`), limites do segmento final e **detecção explícita de sobreposição de patches** (`E5015`).
- Validado em `tests/test_paralelismo.py::linker_paralelo_rejeita_elf_hostil` (ELF truncado misturado com 6 `.o` válidos em `-j4` sob `DCC_FORCE_PAR_LINKER=1` rejeitado controladamente com exit 1).

---

## 2. Benchmarks Reais: 1, 10, 100 e 300 Objetos ELF64 (`~5.400+` Relocações)

Dados de `build/audit_ciclo5/bench_paralelismo.json` (mediana de 3 repetições em 100 e 300 `.o`):

| Quantidade `.o` | Ciclo IV (`inteiro[]` seq) | Ciclo V (`Bytes` `-j1`) | Ganho Tempo | Ganho RSS | Ciclo V Paralelo (limiar antigo `>=4 / >=2k`) | SHA-256 (`-j1/-j2/-j4/-j8/-j auto`) |
|---:|---:|---:|---:|---:|---:|---|
| **1 `.o`** | `<0,01 s` (`10,3 MB`) | `<0,01 s` (`11,1 MB`) | — | estável | `<0,01 s` | `60a8fdbe5d08...` (MATCH) |
| **10 `.o`** | `0,01 s` (`14,3 MB`) | **`<0,01 s`** (`11,6 MB`) | — | `-18,9%` | `<0,01 s` | `82ad0d4a623b...` (MATCH) |
| **100 `.o`** | `0,07 s` (`51,9 MB`) | **`0,01 s`** (**`15,0 MB`**) | **`7,0×`** | **`-71,1%`** | `0,01 s` (`16,6 MB`) | `d73ee234a313...` (MATCH) |
| **300 `.o`** | `0,20 s` (`154,6 MB`) | **`0,03 s`** (**`22,1 MB`**) | **`6,7×`** | **`-85,7%`** | `0,07 s` (`27,8 MB`) | `019c4eb6a715...` (MATCH) |

### 2.1. Calibração Empírica dos Limiares de Ativação Paralela
O benchmark de 300 `.o` revelou um achado importante e honesto: após a migração para `Bytes`, o linker sequencial ficou **tão rápido (`30 ms` para 300 `.o`, `22 MiB` RSS)** que ativar o pool de rotinas em 300 `.o` pequenos (~1,5 MiB totais) adicionou ~40 ms de overhead de empacotamento/acordamento (`0,03 s → 0,07 s`).

Por isso, calibramos os limiares automáticos em `src/linker/linker.delegua`:
- **Leitura paralela (`validarESerializarElfWorker`)**: ativa automaticamente quando `workers > 1 && itens >= 16 && totalBytesEntrada >= 16 MiB` (onde cada worker processa múltiplos MiB de tabelas ELF).
- **Relocações paralelas (`prepararPatchesRelocWorker`)**: ativa automaticamente quando `workers > 1 && totalRelocsLink >= 20.000`.
- **Cobertura contínua em CI**: `DCC_FORCE_PAR_LINKER=1` exercita ambos os caminhos paralelos em `tests/test_paralelismo.py` (22 `.o` + `.a` encadeado + `STB_WEAK` + >2.600 relocações + ELF hostil), provando **SHA-256 100% idêntico** entre `-j1`, `-j2`, `-j4` e `-j8` sem penalizar links rápidos de `< 30 ms`.
