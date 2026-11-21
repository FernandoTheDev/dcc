# Quarta Etapa de Engenharia e Auditoria Profunda do DCC (Ciclo IV)

**Data:** 21/11/2026  
**Versão do DCC:** `0.2.0` (branch `master`, commit base `686efc3` + melhorias do Ciclo IV)  
**Toolchain CGD integrada:** CGD `0.9.0` (Ciclo III, `vendor/delegua-runtime` com slots inline, `-O2` e inline caching)  
**Ambiente:** Linux `7.2.5-200.fc44.x86_64`, Intel Core i5-11300H (8 threads), 15 GiB RAM; GCC `16.2.1`, Clang `22.1.8`, TinyCC `0.9.28rc`.

---

## 1. Sumário Executivo

O Ciclo IV do **DCC (Delégua C Compiler)** foi conduzido em engenharia cruzada com o Ciclo III do CGD tendo como alvo principal a **eficiência extrema de memória e velocidade na auto-compilação real (`build/dcc.c` → `build/dcc-self.o` → `build/dcc-self`)**, sem sacrificar nenhuma garantia de conformidade C99/GNU99, ABI System V AMD64, limites anti-DoS ou determinismo ELF64.

### Avanços Alcançados (Entrada Congelada `frozen_dcc.c`, 5,05 MiB, ~865k tokens)

| Métrica (`clang -O2`, Modo A) | Baseline Pós-Bootstrap | Final Ciclo IV (Mediana 3 reps) | Melhoria |
| --- | ---: | ---: | ---: |
| **Pico RSS (Memória)** | `6.715.172 KB` (**6,40 GiB**) | **`955.216 KB` (0,91 GiB)** | **7,03× menor (-85,8%)** |
| **Alocação GC cumulativa** | `12.150 MiB` | **`3.863 MiB`** | **3,15× menor (-68,2%)** |
| **Tempo total de auto-compilação** | `29,94 s` | **`8,56 s`** (min `8,54` / max `9,05`) | **3,50× mais rápido** |
| **Tamanho `.text` emitido** | `17.811.065 B` | **`17.051.123 B`** | **-760 KB (-4,3%)** |
| **Tamanho `dcc-self.o` emitido** | `20.950.672 B` | **`20.190.680 B`** | **-760 KB (-3,6%)** |
| **Emissão ELF64 (`elf_obj`)** | `311 ms` | **`53 ms`** | **5,87× mais rápido** |
| **Stress 24 compilações paralelas** | `2,61 s` (era `8,76 s` v0.1) | **`1,35 s`** | **1,93× mais rápido** |
| **Benchmark `-O2` (`test_stress.py`)** | `872 ms` (era `3.005 ms` v0.1) | **`250 ms`** | **3,49× mais rápido** |

Todas as 12 execuções do Modo A (GCC `-O0`, Clang `-O0`, TinyCC `-O0` e Clang `-O2`) produziram objetos ELF64 **bit-a-bit idênticos** (`sha256: 6144e0665d578e7da0d78b6db63f236150f777d1941ab5548f5d0a6647e5f9ba`), e o **Modo B** (pipeline completo com o `build/dcc.c` atual de 955.348 tokens e 894 funções) completou em **9,53 s** (mediana) com **1,01 GiB de RSS**, gerando `build/dcc-self` funcional capaz de compilar `examples/hello_libc.c` em **290 ms** e imprimir `DCC`.

---

## 2. Catálogo de Melhorias Implementadas no DCC (12 Arquivos em `src/`)

### DCC-IV-01 — Instrumentação Forense de Memória (`-fmem-report`, `src/driver/cli.delegua`)
- Adicionada flag `-fmem-report` (e variável `DCC_MEM_REPORT=1`) invocando `Sistema.memoria()` no início e fim de cada uma das 8 fases (`PREPROCESS`, `LEX`, `PARSE`, `SEMA`, `IR`, `OPT`, `CODEGEN`, `ELF`), registrando `rss`, `hwm`, `pss`, `gc_heap`, `gc_free`, `gc_unmap`, `gc_use`, `gc_total`, `gc_cyc` e contadores estruturais reais (`tokens`, `astNodes`, `astLeaves`, `insts`, `calls`, `relaText`, `elfBytes`).

### DCC-IV-02 — Emissor x86-64 e Seções ELF64 em `cgd:bytes.Bytes` (`emissor.delegua`, `codegen.delegua`, `elf_obj.delegua`, `cli.delegua`)
- **Problema**: `EmissorX86_64.code` e `CodigoObjeto.{textBytes,rodataBytes,dataBytes}` eram armazenados como `inteiro[]` (24 B/byte no runtime CGD, dobrando em realocações e sendo varridos pelo Boehm GC como ponteiros — consumindo **1,66 GiB** de alocação em `CODEGEN`). Além disso, `elf_obj.delegua` encadeava 14 chamadas a `Bytes.concatenar`, gerando **472 MiB** extras, e `cli.delegua` gravava binários invocando `/bin/sh -c "exec base64 -d"`.
- **Correção**:
  - `EmissorX86_64.code` migrado para `Bytes.criarReservado(4096)` (memória `GC_MALLOC_ATOMIC`, 1 B/byte) com `anexarByte`, `anexarU32LE`, `anexarU64LE`, `definirU32LE`.
  - `elf_obj.delegua` pré-calcula o tamanho exato do arquivo ELF64 e monta todas as 11 seções diretamente em um único `Bytes.criarReservado(tamTotal)` via `anexarBytes`/`anexarZeros`.
  - `cli.delegua` usa `Bytes.gravarArquivo()` e `Bytes.lerArquivo()`, eliminando completamente a codificação Base64 e o subprocesso shell.
- **Resultado**: alocações em `CODEGEN` caíram de **1.663 → 176 MiB (-89,4%)**, em `ELF` de **471 → 34 MiB (-92,8%)**, e o tempo de `elf_obj` caiu de **311 ms → 53 ms**.

### DCC-IV-03 — `CallInfoSSA` Preguiçoso na IR (`ir_tipos.delegua`, `ir_builder.delegua`, `ir_opt.delegua`, `ir_verify.delegua`, `codegen.delegua`, `asm.delegua`, `cli.delegua`)
- **Problema**: `InstSSA` possuía 19 campos (488 B/instância), dos quais 7 eram exclusivos de chamadas de função (`callAlvo`, `callArgs`, `callArgsEhFlt`, `callArgsEhF32`, `callArgsStructTam`, `callIndireta`, `callEhVariadica`), embora apenas 42.631 das 803.990 instruções (5,3%) sejam `Call`.
- **Correção**: os 7 campos foram movidos para a classe `CallInfoSSA`, referenciada por um único campo `InstSSA.callInfo` (`nulo` nas 94,7% das instruções não-`Call`), reduzindo `InstSSA` de 19 para 13 campos (-144 B por instrução, economizando ~115 MiB na IR).

### DCC-IV-04 — Bitsets Densos em `Bytes` no Verificador e Otimizador de IR (`ir_verify.delegua`, `ir_opt.delegua`)
- **Problema**: `ir_verify.delegua` e `ir_opt.delegua` rastreavam registradores virtuais SSA usando `dicionario` indexado por `texto(reg)`, alocando centenas de milhares de strings e entradas hash (~330 MiB em `OPT` mesmo em `-O0`!).
- **Correção**: substituição por `Bytes.criar(fn.numRegs)` (1 byte por registrador virtual em `GC_MALLOC_ATOMIC`).
- **Resultado**: alocações de `OPT` em `-O0` caíram de **330 MiB → 2 MiB (-99,4%)**.

### DCC-IV-05 — Pré-processador e Lexer em `Bytes` + Interning de Identificadores (`preproc.delegua`, `lexer.delegua`, `literais.delegua`)
- **Problema**:
  1. `preproc.delegua:80` verificava `lin.contem("\\")` para decidir se uma linha precisava de *line-splicing*; como o código C gerado pelo CGD contém milhares de escapes octais (`"\141..."`), quase todas as linhas perdiam o fast-path $O(1)$!
  2. `linhaContemMacroAtiva` e `LexerDCC.tokenizarLinha` chamavam `Bytes.deTexto(lin).paraVetor()`, convertendo cada linha em `inteiro[]` (24× amplificação).
  3. Identificadores repetidos (`delegua_value`, `cgd_tmp_0`, `args`) geravam strings duplicadas.
- **Correção**:
  - `lin.contem("\\")` substituído por `texMod.Textos.terminaCom(lin, "\\")` (correto conforme fase 2 do C99).
  - Varredura direta sobre `Bytes.obter(i)` + `Bytes.fatiarTexto(ini, fim)` sem `paraVetor()` em `preproc.delegua`, `lexer.delegua` e `literais.delegua`.
  - Tabela `internIds` no lexer deduplicando lexemas de identificadores (até 64 caracteres).
- **Resultado**: alocações de `PREPROCESS` caíram de **3.502 → 2.081 MiB (-40,6%)** e de `LEX` de **1.880 → 494 MiB (-73,7%)**; tempo de `PREPROCESS` caiu de **2.215 → 1.000 ms** e `LEX` de **3.745 → 1.344 ms**.

### DCC-IV-06 — Isolamento de Frames e Liberação Explícita Entre Fases (`cli.delegua`)
- **Problema**: sob Boehm GC conservador, `executarDriverDCC` (com `tente/pegue`, gerando variáveis `volatile` e temporários `cgd_tmp_*`) retinha ponteiros residuais para `tokens` e `ast` durante `IR`, `CODEGEN` e `ELF`.
- **Correção**:
  - Extração de `executarPreprocLexParse` e `executarSemaEIR` em subfunções dedicadas.
  - Chamada explícita de `tokens.limpar()`, `ast.filhos.limpar()` e `moduloSSA.funcoes.limpar()` ao encerrar cada fase, combinada com `Sistema.coletarGC(verdadeiro)` em unidades de tradução grandes (`nTokensTU > 20000`).
- **Resultado**: pico RSS caiu de **1.299 → 955 MiB (abaixo de 1 GiB!)**, quebrando o teto simbólico de 1 GiB na auto-compilação.

### DCC-IV-07 — Rastreamento Intra-Bloco do Registrador `RAX` no Backend x86-64 (`src/backend/x86_64/codegen.delegua`)
- **Problema**: o codegen SSA-para-pilha do DCC carregava sistematicamente `mov rax, [rbp - off]` mesmo quando a instrução imediatamente anterior no mesmo bloco básico acabara de calcular exatamente esse registrador virtual em `rax`.
- **Correção**:
  - Adicionado estado intra-bloco `regEmRax: inteiro` com helpers `carregarRegEmRax(reg)` e `definirRegEmRax(reg)` em `GeradorX86_64`.
  - `regEmRax` é invalidado (`-1`) no início de cada bloco básico e em toda instrução que clobbera `rax` (chamadas, `div`/`idiv`, `cmp`/`setcc`, `memcpy`, etc.).
- **Resultado**: redução de **760 KB (-4,3%)** no `.text` de `frozen_dcc.c` (`17.811.065 → 17.051.123 B`) e aceleração do próprio `dcc-self` executando `hello_libc.c` (`322 ms → 237–290 ms`), com 100% dos 86 testes diferenciais aprovados em `-O0`, `-O1` e `-O2`.

---

## 3. Validação Executada

- `make check-format`: **23/23 arquivos `.delegua` aprovados**.
- `python3 tests/run_tests.py`: **86/86 verificações aprovadas, 0 falhas** (54 diferenciais vs. GCC 16 e Clang 22 em `-O0/-O1/-O2`, 5 ABI bidirecionais incluindo TLS e `bool` estreito, 9 linker/`.a`/`STB_WEAK`/ELF64, 18 diagnósticos/CLI/JSON/ANSI).
- `python3 tests/test_security_fuzz.py`: **APROVADO** (macro bombs, escalabilidade, 50 fuzz lexer/parser, 15 ELF64/`.a` hostis).
- `python3 tests/test_stress.py`: **APROVADO** (`stress_concorrencia` 24× em **1,35 s**; `benchmark_fases` `-O2` em **250 ms**).
- `./bootstrap/verify.sh`: **APROVADO** (smoke fora da árvore em `/tmp`, auditoria `ldd`, 86/86 testes).
- **Bootstrap indireto completo**: `build/dcc` → `build/dcc.c` → `build/dcc-self.o` (`22.130.832 B`) → `build/dcc-self` (`20.097.112 B`) → `examples/hello_libc.c` → imprime **`DCC`**.

---

## 4. Limitações Honestas Mantidas e Próximos Passos (Ciclo V)

1. **Alocação completa de registradores (Linear Scan) e `mem2reg` SSA**: o rastreamento intra-bloco de `RAX` reduziu o `.text` em 4,3%, mas a maior parte dos registradores virtuais ainda faz *spill* em `[rbp - off]`, explicando por que `dcc-self.o` (`20,19 MB`) ainda é 2,3× maior que `tcc -c` (`8,75 MB`). Um alocador *linear scan* sobre registradores callee/caller-saved (`rbx`, `r12`–`r15`, `rdi`, `rsi`, `r8`–`r11`, `xmm0`–`xmm7`) é o próximo salto estrutural.
2. **Classificação completa de *eightbytes* SSE na ABI System V AMD64**: structs ≤ 16 B contendo `float`/`double` em `xmm0`/`xmm1` ainda aguardam suporte completo (§3.2.3).
3. **Recursos C99/ELF pendentes**: `long double` 80-bit x87, `_Complex`, strings largas `L"..."`, UCNs, VLAs multidimensionais, `-shared`/`ET_DYN`, PIE e DWARF `-g`.
4. **Independência de bootstrap**: o bootstrap permanece *indireto* (o código-fonte do DCC é escrito em Delégua e transpilado para C pelo CGD; o DCC compila esse C para objeto ELF64 e linka com `libdelegua_rt.o`).
