# Integração Cruzada CGD 0.9.0 (Ciclo IV) × DCC 0.2.0 (Ciclo V)

Data: 21/11/2026

---

## 1. Mapa de Integração Entre Camadas (CGD → DCC)

A evolução coordenada dos dois projetos demonstrou como primitivas de sistema bem desenhadas no compilador/runtime base (`CGD`) desbloqueiam saltos imediatos de memória, velocidade e paralelismo seguro no compilador hospedado (`DCC`):

| Recurso Entregue no CGD (Ciclo IV) | Consumo no DCC (Ciclo V) | Benefício Mensurado |
|---|---|---|
| `cgd:memoria.Arena` (`FatiaBytes`, `FatiaInt64`, geração 64-bit) | `ir_opt.delegua` (propagação de constantes/cópias + DCE por contagem de usos) e `ir_verify.delegua` | `opt+verify` em `frozen_dcc.c`: **`3.611 ms → 838 ms` (`4,31×`)** com **~6.147× menos churn GC** em arrays temporários |
| `cgd:memoria.Memoria.coletarSeAcima()` + `Memoria.estatisticas()` | `parser.delegua` (reclamação mid-parse a cada 120k tokens consumidos) + `cli.delegua` (streaming a cada 128 funções + `-fmem-report`) | Pico RSS em `frozen_dcc.c`: **`995.100 KB → 572.960 KB` (`-42,4%`, `-422 MB`!)** |
| `cgd:memoria.Memoria.sistema()` + `Rotinas.workersRecomendados()` | `cli.delegua` (`-j auto`, `--parallel=off/auto`, `DCC_JOBS`, `taskset`/cgroup) | `taskset -c 0,1 -j auto` → `cpusEff=2, workers=1`; 8 threads → `4` workers conservadores |
| `cgd:bytes.Bytes.congelar()` (*zero-copy* fora do GC) + `lerU16LE/U32LE/U64LE/lerCString/anexarBytesFatia` | `elf_leitor.delegua` + `linker.delegua` (`validarESerializarElfWorker`, `prepararPatchesRelocWorker`) | Linker 300 `.o`: **`0,20 s / 154,6 MB → 0,03 s / 22,1 MB`** (`6,7×` mais rápido, `-85,7%` RSS); transferência *zero-copy* de 16 MiB em `0,011 ms` |
| `cgd:processo.Processo.executarLote()` (`posix_spawnp` + `poll`) | `cli.delegua` (compilação concorrente multi-TU com backpressure de CPU e RAM) | 17 arquivos `.c`: **`1,96 s → 1,06 s` (`-j4`) / `0,83 s` (`-j8`)** com SHA-256 bit a bit idêntico |
| `objetos.c` IC monomórfico para classes fechadas com campos `privado` | Todas as chamadas de método em `Bytes`, `Arena`, `FatiaBytes`, `FatiaInt64` | `codegen` em `frozen_dcc.c`: **`1.420 ms → 928 ms` (`-34,6%`)**; `Arena`/`Bytes` `3,7×` mais rápidos |
| `objetos.c` (`func_cache_mutex`) + `modulos.c` (`delegua_mod_lock`) + `routine_validation.d` (`paralelo = verdadeiro`) | Execução concorrente segura de workers ELF/relocação sob `rotina` | **0 data races em TSan**; **0 erros em ASan/UBSan**; `E3402`/`E3403` intactos |

---

## 2. Bootstrap Indireto Completo do DCC Ciclo V

Fluxo executado de ponta a ponta sobre o estado final dos dois repositórios:
1. `cgd -o --emitir-c src/main.delegua -s build/dcc_c5_current` → gerou `build/dcc_c5_current.c` em `1,31 s` (**`70.988 linhas`**, `6.895.147 bytes`).
2. `dcc -std=gnu99 -O1 -c -j auto -I ~/.local/share/cgd build/dcc_c5_current.c -o build/dcc-self.o` → **exit 0** em **`12,83 s`** (mediana), pico RSS **`849.800 KB` (`829,9 MiB`)**, objeto `build/dcc-self.o` = **`25.292.392 bytes`** (`1.048 funções`, `127.559` relocações `.rela.text`, `17.622` `.rela.data`).
3. `gcc -no-pie build/dcc-self.o ~/.local/share/cgd/lib/libdelegua_rt.o -lgc -lcurl -lm -lpthread -ldl -o build/dcc-self` → executável **`22.970.480 bytes`**.
4. `./build/dcc-self --version` → `dcc (Delegua C Compiler) 0.2.0`.
5. `./build/dcc-self -j auto examples/hello_libc.c -o /tmp/hello_bootstrap_c5 && /tmp/hello_bootstrap_c5` → compilou com headers reais de `/usr/include` e imprimiu **`DCC`**.

---

## 3. Portabilidade GCC / Clang / TinyCC Validada

Todos os quatro compiladores C geradores compilaram o DCC Ciclo V completo e produziram o **exato mesmo `.o` bit a bit** (`sha256 = 9b3c0d377d05a831e309977ef4287f595bad4ee07bf238dc4f345da8d44a1d39`, `18.951.128 B`) na entrada congelada `frozen_dcc.c`:
- **Clang 22.1.8 `-O2`**: build `24,56 s`, Modo A `8,66 s`, RSS `572.960 KB`.
- **GCC 16.2.1 `-O0`**: build `8,29 s`, Modo A `13,33 s`, RSS `843.348 KB`.
- **Clang 22.1.8 `-O0`**: build `3,11 s`, Modo A `13,87 s`, RSS `575.564 KB`.
- **TinyCC `0.9.28rc` `-O0`**: build **`1,36 s`**, Modo A `24,45 s`, RSS **`572.424 KB`**.

---

## 4. Achados Honestos e Próximos Passos para Próximos Ciclos

1. **Crescimento do C gerado pelo modo `assincrona` no `main.delegua` (`42.915 → 70.988` linhas)**:
   - Ao tornar `executarDriverDCCAsync` e `linkarObjetosELF64BytesAsync` funções `assincrona` (para suportar `aguardar Promessa.todas(...)` do linker paralelo), o CGD passou a incluir `bibliotecas/assincrono.delegua` (HTTP/TCP/Canal) e a emitir máquinas de estado assíncronas extensas para `executarDriverDCCAsync`.
   - **Oportunidade CGD Ciclo V**: (a) podar classes não usadas dentro de `cgd:assincrono` (como `HTTP`/`ConexaoTCP`/`OuvinteTCP` quando apenas `Rotinas` é referenciado) e (b) isolar o bloco `aguardar` em wrappers menores no DCC para reduzir em ~35% o volume de C gerado no Modo B.
2. **Tipos qualificados por módulo no CGD (pré-requisito para paralelismo intra-TU sem duplicação)**:
   - Atualmente em Delégua, parâmetros e campos entre módulos precisam ser anotados como `qualquer` (ex.: `emissor: qualquer` em `codegen.delegua`), o que impede o auditor estático `E3402` de provar pureza em chamadas sobre esses objetos dentro de `rotina`.
   - Adicionar suporte a tipos qualificados por módulo no CGD (ou `importar tipo`) permitirá auditar passes cross-módulo nativamente sem enfraquecer `E3402`.
3. **Redução adicional de RSS em `PARSE` (`559 MiB` → `< 400 MiB`)**:
   - Hoje `100%` do pico RSS em `frozen_dcc.c` ocorre na coexistência temporária de `TokenC99` (`~415 MiB` para 961k tokens) + `NoAST` (`26 campos` por nó).
   - Compactar `NoAST` (separando metadados raros como `bitWidth`/`alinhamentoExplicito`/`valorReal` sob demanda, similar a `CallInfoSSA`) ou fazer *pull-parsing* direto sobre o lexer sob demanda (eliminando o vetor completo de 961k `TokenC99`) tem potencial de cortar o pico RSS de `559 MiB` para **`< 300 MiB`**.
