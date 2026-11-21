# Continuidade Técnica — DCC (Delégua C Compiler)

Data: 21/11/2026 — Versão atual `0.2.0` (Ciclo III concluído)

---

## 1. Resumo das Mudanças do Ciclo III (`0.1.0` → `0.2.0`)

1. **Auditoria completa pré-modificação**: toda a base original (13 arquivos, 10.067 LOC) e a biblioteca padrão do CGD (`~/.delegua/cgd`, v0.9.0) foram auditadas integralmente em [AUDIT_REPORT.md](AUDIT_REPORT.md).
2. **Refatoração modular sem quebrar comportamento**: o código passou de 13 arquivos monolíticos para **23 módulos coesos** (12.838 LOC):
   - Pré-processador dividido em `preproc.delegua`, `pp_macros.delegua` e `pp_expr.delegua`;
   - IR dividida em `ir_tipos.delegua`, `ir_builder.delegua`, `ir_opt.delegua`, `ir_verify.delegua` e fachada `ir_ssa.delegua`;
   - Utilitários compartilhados extraídos para `lexer/literais.delegua` (`ClassificadorChar`, escapes C99, literais u64 sem overflow, hex-float) e `object/elf/elf_comum.delegua` (constantes/helpers ELF64);
   - Leitor endurecido de `.o`/`.a` extraído para `linker/elf_leitor.delegua`.
3. **Adoção inteligente da biblioteca padrão CGD (`cgd:*`)**: 10 módulos padrão (`cgd:ambiente`, `cgd:arquivos`, `cgd:bytes`, `cgd:caminhos`, `cgd:io`, `cgd:json`, `cgd:nativo`, `cgd:processo`, `cgd:tempo`, `cgd:textos`) + FFI POSIX direta (`chmod`, `isatty`), documentados em [CGD_STDLIB.md](CGD_STDLIB.md).
4. **Endurecimento de segurança em todas as fases**: limites anti-DoS no pré-processador (incluindo proteção contra macro bombs exponenciais em `<0,3s`), Precedence Climbing + guarda de profundidade `96` no parser, verificador estrutural da IR SSA, guarda de frame/`rel32` no backend, validação rigorosa de ELF64/`.a` no leitor e eliminação de interpolação de caminhos em comandos shell.
5. **Correções reais de C99, ABI e Linker**:
   - Comparações IEEE-754 seguras para `NaN` (`ucomisd` + `PF`), `float` 32-bit real na ABI (`cvtsd2ss`/`cvtss2sd`), literais hex-float (`0x1.fp+3`), conversões `uint64_t <-> double`, e parse sem overflow de literais até `UINT64_MAX`;
   - Operações inteiras 32-bit reais (`eax`/`ecx`) com wraparound `unsigned` e truncamento correto de retornos estreitos;
   - Structs por valor `9..16B` (`rax:rdx`) e `>16B` (`sret` oculto), `offsetof` aninhado e inicialização/atribuição composta de bit-fields;
   - Emissão de `.rela.data` para ponteiros globais inicializados, `STB_WEAK` real (Cat B + relocação na própria TU), archives estáticos `.a` (`-L`, `-l`, extração iterativa), `SHN_COMMON`, `argc`/`argv` em `_start`;
   - `sizeof("str")`, escapes C99 com bytes exatos (`\0`, octal, `\xNN`), aritmética comutativa (`2[arr]`, `1+arr`, `p+=n`), `typedef` com escopo léxico, shadowing de enumeradores, rejeição de escrita em `const`, structs recursivas e duplicatas;
   - Diagnósticos com códigos estáveis `E1xxx`–`E9xxx`/`W1xxx`–`W2xxx`, pilha de inclusão, sublinhado `^~~~`, cores ANSI (`NO_COLOR`/`isatty`), saída JSON (`-fdiagnostics-format=json`), `-Wno-*` e `-ftime-report`.
6. **Otimização guiada por profiling (`-ftime-report`)**: `ClassificadorChar` com tabelas ASCII em memória, `fatiar()` no tokenizador/lexer, cache de headers limpos e MI-OPT reduziram o tempo de 24 compilações paralelas de `8.76s` para `6.62–6.76s` (~23% mais rápido).
7. **Transparência sobre desenvolvimento por IA e política de segurança**: adicionadas seção explícita no `README.md`, `docs/AI_DEVELOPMENT.md` e `SECURITY.md`.

---

## 2. Evidências Reais Executadas (v0.2.0)

Todos os comandos abaixo foram executados e validados sobre o build limpo atual:

- `make check-format` — **23/23 arquivos `.delegua` aprovados** sem desvios.
- `./bootstrap/build.sh` — compilou `build/dcc` (`0.2.0`) com `CGD v0.9.0`.
- `python3 tests/run_tests.py` — **86/86 verificações aprovadas, 0 falhas**:
  - 18 programas diferenciais × 3 níveis (`-O0`, `-O1`, `-O2`) = 54 execuções idênticas a GCC e Clang usando headers reais de `/usr/include`;
  - 5 verificações de interoperabilidade ABI bidirecional (`DCC↔GCC`, `DCC↔Clang`, incluindo retorno estreito `bool`);
  - 9 testes de linker, archives `.a`, `STB_WEAK`, duplicatas e auditoria ELF64 (`readelf`/`ldd`);
  - 18 testes de diagnósticos negativos, JSON, ANSI, `-Wno-*`, `-S`, `-ftime-report` e execução fora da árvore.
- `python3 tests/test_security_fuzz.py` — **APROVADO** (17 verificações adversariais e de escalabilidade de pré-processador/pipeline, 50 entradas fuzzing lexer/parser, 15 ELF64/`.a` hostis rejeitados controladamente).
- `python3 tests/test_stress.py` — **APROVADO** (multi-arquivo + `libutil.a` em `-O0/-O1/-O2`, 24 compilações paralelas 4× em `2,61s`, benchmark `-ftime-report` `-O2` em `872ms`).

---

## 3. Próximos Passos Prioritários (Ciclo IV)

1. **Classificação completa de `eightbytes` SSE na ABI**: suportar structs ≤ 16 bytes contendo campos `float`/`double` em `xmm0`/`xmm1` conforme System V AMD64 ABI §3.2.3.
2. **Alocação de registradores e `mem2reg` SSA**: reduzir tráfego de memória em slots de pilha com `phi`, análise de vivacidade e alocação *linear scan* sobre registradores reais x86-64.
3. **Desempenho do pré-processador**: reduzir os ~2,0s gastos na limpeza/expansão dos grandes cabeçalhos da `glibc` (ex.: fast-path para linhas sem identificadores presentes na tabela de macros).
4. **C99 restante**: `long double` 80-bit x87, `_Complex`, strings largas (`L"..."`), UCNs e VLAs multidimensionais.
5. **Toolchain & ELF**: geração de bibliotecas compartilhadas (`-shared` / `ET_DYN`), executáveis PIE, relocações TLS (`_Thread_local`) e emissão DWARF inicial (`-g`).
6. **I/O binário nativo sem `base64`**: migrar assim que o runtime CGD expuser leitura/escrita binária direta de `Bytes` em arquivo.


---

## 4. Escalabilidade, Memória e Bootstrap Self-Hosting (`build/dcc.c` → `build/dcc-self.o` → `build/dcc-self`)

Após a conclusão da base v0.2.0, o compilador foi submetido ao teste real de **auto-compilação** sobre `build/dcc.c` (5,5 MiB, 53.009 linhas, ~1 milhão de tokens, 1.074 funções, com a linha 36 contendo 366.154 caracteres de `cgd_source_sites[]`), gerado pelo CGD v0.9.0.

### Obstáculos Encontrados e Correções Reais Implementadas

1. **Falso positivo `E1011` e aviso do GC (`Repeated allocation of very large block 49156 KiB`)**:
   - **Causa**: `expandirTokens` somava tokens normais de entrada ao orçamento de expansão de macros (`400.000`), e `fasesIniciaisELimpezaPP` alocava múltiplos vetores `inteiro[]` de 5,73M elementos (~48 MiB cada) para o arquivo inteiro.
   - **Correção**: orçamentos separados entre entrada (`E1018` 20M tokens, `E1019` 64 MiB/arquivo) e expansão real de macros (`E1011` 50k/linha e 500k/TU de expansões, 50k/linha e 2M/TU de tokens gerados por macros); `fasesIniciaisELimpezaLinhasPP` reescrita linha-a-linha em bytes com fast-path O(1); `linhaContemMacroAtiva` O(N) em bytes sem alocação de `PPToken[]` para linhas sem macros ativas; `hideSet` preguiçoso (`nulo`) em `PPToken`; cache de headers restrito a arquivos `#include` ≤ 512 KiB; truncamento de snippets em `MapaFonte` para 512 chars.
2. **Complexidade O(L²) no lexer em linhas de 366 KiB e O(N²) por parâmetros `T[]` tipados no CGD**:
   - **Causa**: `fonte[pos]` sobre strings UTF-8 no CGD é O(pos), e parâmetros tipados `inteiro[]`/`TokenC99[]`/`NoAST[]` passados em loops quentes validam o vetor inteiro a cada chamada (`tokenizarLinha`, `drenarPendentes`, `parseDeclVarLocal`, `gravarIntLE`, `anexarU64`/`elf_comum`).
   - **Correção**: `LexerDCC.tokenizarLinha` migrado para varredura O(L) sobre bytes com tabela ASCII O(1) para operadores; remoção de validação O(N²) em parâmetros de buffer/vetor nos loops quentes; inicialização preguiçosa (`nulo`) de `TokenC99.bytesStr`, `NoAST.bytesLit` e `InstSSA.callArgs*`; liberação explícita entre fases no driver (`cli.delegua`), em `ir_builder` e em `codegen`.
3. **Alocação de 786 MiB no GC em `elf_obj.delegua`**:
   - **Correção**: `emitirObjetoELF64Bytes` monta as 11 seções diretamente via `cgd:bytes.Bytes` (1 byte/byte em C) — tempo de `elf_obj` em `build/dcc-self.o` caiu de **19.506 ms → 1.038 ms (18,8× mais rápido)** com **zero avisos do GC**.
4. **Inicializadores designados aninhados (ISO C99 6.7.8)** em `delegua_rt.h:183` (`.value.num = num`):
   - **Correção**: encadeamento de `ExprInicDesignado` no parser, semântica, `baixarInicializador` e `preencherBytesGlobal`.
5. **Builtin GNU `__builtin_expect(exp, c)`** em `delegua_rt.h:482`:
   - **Correção**: suportado em `sema.delegua` e `ir_builder.delegua` (avalia `exp` e retorna `long`).
6. **Colisão de string literal `"\055"` (`"-"`) com mapas de operadores no parser** (`build/dcc.c:4199`):
   - **Correção**: checagem `tag != StrLit e tag != CharLit` antes de consultar `mapaUnario`, `mapaBinPrec` e `mapaAtrib`.
7. **Profundidade sintática em cadeias longas `else { if }` geradas pelo CGD**:
   - **Correção**: `parseStmt` delega `{` diretamente para `parseBloco` sem contagem dupla, mantendo o limite anti-DoS em `96` (`E2010` preservado em `parens_profundos`).
8. **Expressão vírgula retornando agregado** `(a, fn_ret_struct()).campo` (`build/dcc.c` linha 4805):
   - **Correção**: `NoKind.ExprComma`, `ExprAtrib` e `ExprCast` de agregados suportados em `baixarEndereco`.
9. **TLS externo (`__thread` / `_Thread_local`)** para `delegua_local_atual` em `libdelegua_rt.o`:
   - **Correção**: suporte a `KwThreadLocal`, `OpIR.AddrExternTls`, `R_X86_64_GOTTPOFF` (22) e `STT_TLS` (6) em `emissor.delegua`/`codegen.delegua`.
10. **Bug real de ABI System V AMD64 em retornos inteiros estreitos (`bool`/`char`/`short`/`int`)**:
    - **Causa**: `delegua_is_truthy()` (compilada pelo GCC) retorna `bool` em `AL` deixando bits 8..63 de `RAX` indefinidos; o caller testava todos os 64 bits de `RAX`.
    - **Correção**: truncamento/extensão explícito pós-chamada (`TruncZext`/`TruncSext`) em `baixarChamada` (`src/ir/ir_builder.delegua`).

### Evidências Reais do Bootstrap e Regressões

- **Auto-compilação completa de `build/dcc.c` (sem alterar `build/dcc.c` nem `delegua_rt.h`)**:
  - `./build/dcc -std=gnu99 -O0 -D__GNUC__=4 -DDELEGUA_OPERADORES_C -I "$HOME/.local/share/cgd" -c build/dcc.c -o build/dcc-self.o -ftime-report`
  - Resultado: **exit 0**, `build/dcc-self.o` = **23.895.480 bytes** (`readelf -h -S` válido, 11 seções, 1.074 funções, >113 mil relocações, **zero avisos do GC**).
  - Tempos (em baixa prioridade `nice -n 15 GC_NPROCS=1`): `preprocess=6650ms lex=46126ms parse=74963ms sema=11571ms ir=66394ms opt+verify=5656ms codegen=13568ms elf_obj=1038ms total=225970ms`.
- **Linkagem e execução do compilador auto-compilado (`build/dcc-self`)**:
  - `gcc build/dcc-self.o "$HOME/.local/share/cgd/lib/libdelegua_rt.o" -lgc -lcurl -lm -lpthread -ldl -o build/dcc-self` → **exit 0**.
  - `./build/dcc-self --version` → imprimiu `dcc (Delegua C Compiler) 0.2.0`.
  - `./build/dcc-self examples/hello_libc.c -o /tmp/hello_from_dcc_self && /tmp/hello_from_dcc_self` → compilou com headers reais de `/usr/include` e imprimiu **`DCC`**!
- **Suítes completas pós-correções**:
  - `make check-format`: 23/23 arquivos aprovados.
  - `tests/run_tests.py`: **86/86 verificações aprovadas, 0 falhas** (incluindo inicializadores designados aninhados, `__builtin_expect`, string `"-"`, vírgula agregada, `__thread` TLS e retorno `bool` estreito contra GCC).
  - `tests/test_security_fuzz.py`: **APROVADO** (incluindo 5 novas regressões de escalabilidade: ~480k tokens sem macros, linha de 260 KiB, inicializador de 1.000 structs com `.rela.data`, header com 1.500 macros legítimas e 200 `#include`s repetidos).
  - `tests/test_stress.py`: **APROVADO** — 24 compilações paralelas 4× em **2,61 s** (antes 8,76 s → **3,35× mais rápido**); benchmark `-O2` total **872 ms** (antes 3.005 ms → **3,45× mais rápido**).

---

## 5. Ciclo IV — Engenharia Cruzada CGD × DCC, Otimização Extrema de Memória e Performance (21/11/2026)

Em trabalho unificado com o Ciclo III do CGD (`0.9.0`), o DCC passou por auditoria forense completa de memória e desempenho na auto-compilação real (`build/dcc.c` → `build/dcc-self.o` → `build/dcc-self`).

### Melhorias Implementadas no DCC (12 arquivos em `src/`)
1. **Telemetria `-fmem-report`** (`src/driver/cli.delegua`): medição fase-a-fase de RSS/HWM/PSS e Boehm GC via `Sistema.memoria()` + contadores estruturais (`tokens`, `astNodes`, `insts`, `calls`, `relaText`, `elfBytes`).
2. **Emissor x86-64 e ELF64 em `cgd:bytes.Bytes` (`GC_MALLOC_ATOMIC`)** (`emissor.delegua`, `codegen.delegua`, `elf_obj.delegua`, `cli.delegua`): eliminou `EmissorX86_64.code: inteiro[]` (24 B/byte), encadeamento `Bytes.concatenar` e o subprocesso `base64 -d`, substituindo por `Bytes.criarReservado`, `anexarU32LE/U64LE`, `gravarArquivo`/`lerArquivo`.
3. **IR e Verificador/Otimizador compactos** (`ir_tipos.delegua`, `ir_builder.delegua`, `ir_opt.delegua`, `ir_verify.delegua`, `asm.delegua`): extração dos 7 campos de chamada de `InstSSA` para `CallInfoSSA` preguiçoso (`nulo` em 94,7% das instruções) e substituição de dicionários `texto(reg)` por bitsets `Bytes.criar(fn.numRegs)` (`OPT` alloc `330 → 2 MiB`).
4. **Pré-processador e Lexer sem `paraVetor()` + interning** (`preproc.delegua`, `lexer.delegua`, `literais.delegua`): correção do fast-path de line-splicing (`terminaCom("\\")` no lugar de `contem("\\")`, antes quebrado por escapes octais do CGD), leitura direta via `Bytes.obter`/`fatiarTexto` e interning de identificadores (`internIds`).
5. **Isolamento de frames e liberação explícita entre fases** (`cli.delegua`): subfunções `executarPreprocLexParse`/`executarSemaEIR` + `tokens.limpar()`, `ast.filhos.limpar()`, `moduloSSA.funcoes.limpar()` + `Sistema.coletarGC(verdadeiro)` em TUs >20k tokens.
6. **Backend x86-64: rastreamento intra-bloco de `RAX`** (`src/backend/x86_64/codegen.delegua`): elide loads redundantes `[rbp - off]` quando `RAX` já contém o registrador SSA, encolhendo `.text` em `-760 KB` (-4,3%).

### Resultados Medidos (Script [`scripts/bench_ciclo4.py`](../scripts/bench_ciclo4.py), 3 repetições sequenciais)
- **Modo A (Entrada congelada `frozen_dcc.c`, `clang -O2`)**:
  - Tempo total: **29,94 s → 8,56 s** (min `8,54 s` / max `9,05 s` — **3,50× mais rápido**).
  - Pico RSS: **6.715.172 KB (6,40 GiB) → 955.216 KB (0,91 GiB)** (**7,03× menor, -85,8%**).
  - Alocação GC total: **12.150 MiB → 3.863 MiB (-68,2%)**; `elf_obj`: **311 ms → 53 ms**.
  - Determinismo: GCC `-O0` (`12,86 s`, `1,12 GiB`), Clang `-O0` (`13,15 s`, `0,89 GiB`), TinyCC `-O0` (`23,26 s`, `0,91 GiB`) e Clang `-O2` (`8,56 s`, `0,91 GiB`) emitiram exatamente o mesmo `.o` (`20.190.680 B`, `sha256: 6144e0665d578e7da0d78b6db63f236150f777d1941ab5548f5d0a6647e5f9ba`).
- **Modo B (Pipeline atual `build/dcc.c`, 955.348 tokens, 894 funções, `clang -O2`)**:
  - Mediana **9,53 s**, pico RSS **1.038.188 KB (0,99 GiB)**, `build/dcc-self.o` = `22.130.832 B` → `build/dcc-self` compilou `examples/hello_libc.c` em **290 ms** imprimindo **`DCC`**.
- **Suítes completas pós-Ciclo IV**:
  - `make check-format`: **23/23** aprovados.
  - `tests/run_tests.py`: **86/86** verificações aprovadas, 0 falhas.
  - `tests/test_security_fuzz.py`: **APROVADO**.
  - `tests/test_stress.py`: **APROVADO** — 24 compilações paralelas em **1,35 s**; benchmark `-O2` em **250 ms**.
  - `./bootstrap/verify.sh`: **APROVADO**.
- **Relatórios gerados**: [AUDITORIA_CICLO_IV.md](AUDITORIA_CICLO_IV.md), [PERFORMANCE_CICLO_IV.md](PERFORMANCE_CICLO_IV.md), [MEMORIA_BOOTSTRAP.md](MEMORIA_BOOTSTRAP.md), [INTEGRACAO_CGD_DCC.md](INTEGRACAO_CGD_DCC.md) e dados em `build/audit_ciclo4/`.

---

## 6. Ciclo V — Paralelismo Adaptativo, Streaming, `cgd:memoria` e Linker `Bytes`/Paralelo (21/11/2026)

Em engenharia integrada com o Ciclo IV do CGD (`0.9.0`), o DCC incorporou paralelismo adaptativo com respeito rigoroso aos recursos da máquina, migração completa do linker para `cgd:bytes.Bytes`, pipeline streaming por função e uso intensivo de `cgd:memoria`.

### Melhorias Implementadas no DCC
1. **CLI e Política Adaptativa de Recursos (`src/driver/cli.delegua`, `src/main.delegua`)**:
   - Flags `-j <N|auto>`, `-j<N>`, `--parallel=off`, `--parallel=auto` e fallback `DCC_JOBS`, com validação estrita de entradas inválidas.
   - Modo padrão `auto` consultando `Memoria.sistema()` e `Rotinas.workersRecomendados(134217728)` (afinidade `sched_getaffinity`, quotas cgroup v2/v1, RAM disponível e pressão de memória; em `taskset -c 0,1` escolhe `workers=1`).
2. **Compilação Paralela Multi-TU (`src/driver/cli.delegua`)**:
   - Para `>= 2` arquivos `.c` com `workers > 1`, dispara compilações isoladas via `Processo.executarLote` (`maxProc <= min(workers, TUs, RAM/256MiB)`), preservando ordem exata de diagnósticos/erros, limpeza garantida de temporários e ordem exata dos `.o` para o linker.
3. **Pipeline Streaming + `cgd:memoria.Arena` + O(1) SSA (`parser.delegua`, `sema.delegua`, `ir_builder.delegua`, `ir_opt.delegua`, `ir_verify.delegua`, `codegen.delegua`, `emissor.delegua`)**:
   - `parser.delegua`: liberação progressiva de `TokenC99` consumidos (via `tokSentinela`) + `Memoria.coletarSeAcima(192 MiB)` mid-parse a cada 120k tokens em arquivos `>100k` tokens.
   - `sema.delegua` / `ir_builder.delegua` / `codegen.delegua`: streaming função-a-função (`verificarCorpoFuncao` → `construirFuncaoSSA` → `otimizarFuncaoSSA` → `verificarFuncaoSSA` → `emitirFuncaoStreaming`), liberando AST e IR imediatamente e preservando ordem exata de `.rodata`/`.data`/`.symtab`.
   - `emissor.delegua`: resolução imediata de labels/patches intra-função (`labelsLocais` + `resolverPatchesFuncao`).
   - `ir_opt.delegua` / `ir_verify.delegua`: mapas de constantes/cópias/usos em `cgd:memoria.Arena` (`FatiaBytes`/`FatiaInt64`, zero churn GC), DCE por contagem de usos em varredura reversa e despacho $O(1)$ de `OpIR` por faixa inteira.
4. **Linker Nativo ELF64 em `Bytes` + Workers Paralelos (`linker.delegua`, `elf_leitor.delegua`, `elf_comum.delegua`)**:
   - Eliminação completa de `inteiro[]` (24 B/byte) em favor de `Bytes` (1 B/byte em `GC_MALLOC_ATOMIC`) com pré-alocação por prefix-sum e `anexarBytesFatia`.
   - Leitura/validação paralela de `.o`/`.a` (`validarESerializarElfWorker`) e preparação paralela de patches de relocação (`prepararPatchesRelocWorker`) via `rotina` + `Bytes` congelado *zero-copy*, com checagem de limites/estouro/sobreposição e limiares empíricos calibrados (`>= 16 itens && >= 16 MiB`; `>= 20.000` relocs; exercitável via `DCC_FORCE_PAR_LINKER=1`).

### Resultados Medidos (`scripts/bench_paralelismo.py 3`, `build/audit_ciclo5/bench_paralelismo.json`)
- **Modo A (`frozen_dcc.c`, `clang -O2`, mesmos headers)**:
  - Tempo mediano (`-j1`): **`12,11 s → 8,66 s` (`-28,5%`, `1,40×` mais rápido)**; `opt+verify`: **`3.611 ms → 838 ms` (`4,31×`)**; `codegen`: **`1.420 ms → 928 ms` (`1,53×`)**.
  - Pico RSS mediano: **`995.100 KB (971,8 MiB) → 572.960 KB (559,5 MiB)` (`-42,4%`, `-422 MB`!)**.
  - Determinismo bit a bit: SHA-256 `9b3c0d377d05a831e309977ef4287f595bad4ee07bf238dc4f345da8d44a1d39` (`18.951.128 B`) idêntico entre Ciclo IV, Ciclo V (`clang -O2`, `gcc -O0`, `clang -O0`, `tcc -O0`) e `-j1/-j2/-j4/-j8/-j auto`.
- **Modo B (Pipeline atual `dcc_c5_current.c`, `70.988` linhas, `1.320.946` tokens, `1.048` funções)**:
  - Mediana **`12,83 s`**, pico RSS **`849.800 KB` (`829,9 MiB`)** (`-18,1%` RSS vs Ciclo IV apesar de `+65%` linhas C); bootstrap indireto `build/dcc-self` validado compilando `examples/hello_libc.c` → **`DCC`**.
- **Multi-TU (17 `.c` → executável ELF64)**:
  - `-j1`: `1,96 s` → `-j2`: `1,64 s` (`1,20×`) → **`-j4`: `1,06 s` (`1,85×`)** → **`-j8`: `0,83 s` (`2,36×`)** → **`-j auto`: `1,09 s` (`1,80×`)**; SHA-256 bit a bit idêntico em todos os modos.
- **Linker (300 `.o`)**:
  - Ciclo IV (`inteiro[]`): `0,20 s` / `154.572 KB` → Ciclo V (`Bytes` `-j1`): **`0,03 s` (`6,7×`) / `22.104 KB` (`-85,7%` RSS)**; SHA-256 idêntico em `-j1/-j2/-j4/-j8/-j auto`.

### Suítes Executadas Pós-Ciclo V
- `make check-format`: **100% aprovado**.
- `python3 tests/run_tests.py`: **86/86 aprovados, 0 falhas**.
- `python3 tests/test_security_fuzz.py`: **APROVADO**.
- `python3 tests/test_stress.py`: **APROVADO** (24 compilações paralelas em **`1,22 s`**, benchmark `-O2` em **`225 ms`**).
- `python3 tests/test_paralelismo.py`: **6/6 aprovados** (flags inválidos, `taskset -c 0,1`, determinismo 17 TUs, erros ordenados sem vazamento `/tmp`, linker paralelo 2.600+ relocs + `.a` + `weak` + rejeição de ELF hostil).
- `./bootstrap/verify.sh`: **APROVADO**.
- **Relatórios gerados**: [PARALELISMO_CICLO_V.md](PARALELISMO_CICLO_V.md), [PERFORMANCE_CICLO_V.md](PERFORMANCE_CICLO_V.md), [LINKER_PARALELO.md](LINKER_PARALELO.md), [INTEGRACAO_CGD_DCC_CICLO_V.md](INTEGRACAO_CGD_DCC_CICLO_V.md).
