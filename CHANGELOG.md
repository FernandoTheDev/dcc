# Changelog

Todas as mudanças notáveis do **DCC — Delégua C Compiler** são documentadas neste arquivo seguindo versionamento semântico (`MAJOR.MINOR.PATCH`).

## [0.3.0] - 2026-11-21

### Paralelismo Adaptativo e CLI
- Novas opções de paralelismo com política conservadora baseada em afinidade de CPU (`sched_getaffinity`), quotas cgroup v2/v1, memória disponível e pressão de memória: `-j <N|auto>`, `-j<N>`, `--parallel=off`, `--parallel=auto` e variável `DCC_JOBS`.
- Compilação concorrente Multi-TU via pool limitado de subprocessos isolados (`cgd:processo.Processo.executarLote`), com ordenação determinística de diagnósticos/erros, limpeza garantida de temporários e aceleração de **1,85× (`-j4`) a 2,36× (`-j8`)** em 17 arquivos `.c` preservando SHA-256 bit a bit idêntico.

### Memória, Streaming e Otimização Profunda
- Pipeline streaming função-a-função (`verificarCorpoFuncao` → `construirFuncaoSSA` → `otimizarFuncaoSSA` → `verificarFuncaoSSA` → `emitirFuncaoStreaming`), liberação progressiva de `TokenC99` no parser com `Memoria.coletarSeAcima()` mid-parse e resolução imediata de labels locais no emissor (`resolverPatchesFuncao`).
- Otimizador e verificador SSA (`ir_opt.delegua`, `ir_verify.delegua`) migrados para `cgd:memoria.Arena` (`FatiaBytes`/`FatiaInt64`, zero churn GC), DCE reversa por contagem de usos e despacho $O(1)$ de `OpIR` por faixa inteira (`opt+verify` **4,31× mais rápido** em `frozen_dcc.c`).
- Emissor x86-64 e ELF64 operando diretamente sobre `cgd:bytes.Bytes` (`GC_MALLOC_ATOMIC`), removendo subprocessos `base64` e adicionando `CallInfoSSA` preguiçoso, rastreamento intra-bloco de `RAX` e telemetria `-fmem-report`.
- Em `frozen_dcc.c` (`clang -O2`, `-j1`): tempo mediano reduzido para **`8,66 s`** (`-28,5%` vs Ciclo IV nos mesmos headers) e pico RSS para **`572.960 KB` (`559,5 MiB`, `-42,4%`)**, mantendo determinismo bit a bit entre Clang, GCC e TinyCC (`0.9.28rc`).

### Linker Nativo ELF64 em `Bytes` e Paralelo
- Migração integral de `elf_leitor.delegua`, `linker.delegua` e `elf_comum.delegua` de `inteiro[]` para `cgd:bytes.Bytes` com pré-alocação por prefix-sum (`300 .o`: **`0,20 s / 154,6 MB → 0,03 s / 22,1 MB`**, `6,7×` mais rápido e `-85,7%` RSS).
- Leitura/validação paralela de `.o`/`.a` (`validarESerializarElfWorker`) e preparação paralela de patches de relocação (`prepararPatchesRelocWorker`) via `rotina` CGD + `Bytes` congelado *zero-copy*, com detecção de sobreposição de patches e rejeição de ELFs hostis.
- Nova suíte `tests/test_paralelismo.py`, benchmark `scripts/bench_paralelismo.py` e relatórios técnicos dos Ciclos IV e V.

## [0.2.0] - 2026-11-21

### Arquitetura e Refatoração
- Reorganização modular de 13 para **23 módulos Delégua** (`src/`): pré-processador separado em `preproc.delegua`, `pp_macros.delegua` e `pp_expr.delegua`; IR separada em `ir_tipos.delegua`, `ir_builder.delegua`, `ir_opt.delegua`, `ir_verify.delegua` e `ir_ssa.delegua`; utilitários comuns extraídos para `lexer/literais.delegua`, `object/elf/elf_comum.delegua` e `linker/elf_leitor.delegua`.
- Adoção sistemática de 10 módulos reais da biblioteca padrão do CGD (`cgd:ambiente`, `cgd:arquivos`, `cgd:bytes`, `cgd:caminhos`, `cgd:io`, `cgd:json`, `cgd:nativo`, `cgd:processo`, `cgd:tempo`, `cgd:textos`) + FFI POSIX direta (`chmod`, `isatty`).

### Segurança e Estabilidade
- Pré-processador endurecido contra *macro bombs* exponenciais (`E1011`), entradas acima do orçamento de tokens/bytes (`E1018`/`E1019`), `#include` cíclico (`E1002`), aninhamento excessivo de `#if`/`#if`-expr (`E1003`/`E1005`), divisão por zero e `INT64_MIN / -1` (`E1006`), `##` inválido (`E1014`) e comentários `/*` não fechados (`E1001`).
- Parser refatorado para Precedence Climbing (`parseBinaria`) com limite de profundidade recursiva (`96`, `E2010`) e proteção contra colisão de literais string/char (`"\055"`) com tabelas de operadores.
- Leitor ELF64/`.a` endurecido (`src/linker/elf_leitor.delegua`) com validação completa de cabeçalhos, alinhamentos, offsets e relocações; verificação de bounds/overflow de relocação no linker e remoção de interpolação de caminhos em comandos shell.
- Verificador estrutural da IR SSA ampliado (`ir_verify.delegua`) executado antes do backend.

### Conformidade ISO C99, GNU99, ABI e Linker
- Comparações IEEE-754 compatíveis com `NaN` (`ucomisd` + `PF`), `float` 32-bit real na ABI (`cvtsd2ss`/`cvtss2sd`), promoção `float→double` em variádicos, literais hex-float (`0x1.fp+3`), conversões `uint64_t <-> double` e parse sem overflow de inteiros até `UINT64_MAX`.
- Operações inteiras 32-bit reais (`eax`/`ecx`) com wraparound `unsigned` e truncamento/extensão explícita de retornos estreitos (`bool`/`char`/`short`/`int`) pós-chamada conforme System V AMD64 ABI.
- Structs por valor `9..16B` (`rax:rdx`) e `>16B` (`sret` oculto), `offsetof` aninhado, inicializadores designados aninhados (`.a.b = x`, `[i].c = y`), expressões vírgula/atribuição/cast retornando agregados, inicialização e atribuição composta de bit-fields.
- Emissão de `.rela.data` para ponteiros globais inicializados (`"str"`, `&var`, `&arr[k]`, ponteiros de função).
- `sizeof("str")`, escapes C99 exatos em bytes (`\0`, octal `\NNN`, `\xNN`), aritmética comutativa (`2[arr]`, `1 + arr`, `p += n`), `typedef` com escopo por bloco, shadowing de enumeradores, checagem de escrita em `const` (`E3010`), rejeição de structs recursivas (`E3005`) e duplicatas (`E3001`/`E3002`/`E3006`/`E3007`).
- Extensões GNU: `__attribute__((weak))` promovido para Categoria B com emissão `STB_WEAK` e relocação na própria TU; validação de potência de 2 em `aligned(N)`; suporte a `__builtin_expect(exp, c)` e variáveis externas TLS (`__thread` / `_Thread_local` via `R_X86_64_GOTTPOFF` e `STT_TLS`); erros explícitos Categoria C para `({...})` (`E2101`) e `&&label`/`goto *` (`E2102`).
- Linker nativo com suporte a arquivos estáticos `.a` (GNU `ar`, `-L`, `-l`, extração iterativa), `SHN_COMMON`, `SHN_ABS`, relocações em `.rodata` e passagem de `argc`/`argv` em `_start`.

### Escalabilidade, Self-Hosting, Diagnósticos e Documentação
- **Bootstrap Self-Hosting validado**: o DCC compila seu próprio código C gerado pelo CGD (`build/dcc.c`, 5,5 MiB, 53.009 linhas, ~1 milhão de tokens, 1.074 funções) para `build/dcc-self.o` (23,89 MiB, zero avisos do GC), gerando um executável `build/dcc-self` funcional capaz de compilar programas C reais com `/usr/include`.
- Diagnósticos com códigos estáveis (`E1xxx`–`E9xxx`, `W1xxx`–`W2xxx`), pilha de inclusão (`In file included from ...`), sublinhado `^~~~`, cores ANSI (`-fdiagnostics-color=auto|always|never` + `NO_COLOR`), formato JSON (`-fdiagnostics-format=json`), `-Wno-<categoria>` e `-ftime-report`.
- Otimização O(N) de escalabilidade e memória em todo o pipeline: limpeza/tokenização por bytes no pré-processador e lexer (`ClassificadorChar`, fast-path para linhas sem macros ativas), emissão de objetos ELF64 diretamente sobre `cgd:bytes.Bytes` (18,8× mais rápido em TUs grandes), reduzindo 24 compilações paralelas de `8,76s` para `2,61s` (**3,35× mais rápido**) e o benchmark `-O2` de `3.005ms` para `872ms` (**3,45× mais rápido**).
- Suíte expandida para **86 verificações** em `tests/run_tests.py` (incluindo ABI bidirecional nas 4 direções `DCC↔GCC` e `DCC↔Clang`), além das suítes `tests/test_security_fuzz.py` (com regressões de escalabilidade) e `tests/test_stress.py`.
- Documentação ampliada e transparência explícita sobre desenvolvimento assistido por IA (`README.md`, `SECURITY.md`, `docs/AI_DEVELOPMENT.md`, `docs/AUDIT_REPORT.md`, `docs/ABI.md`, `docs/LINKER.md`, `docs/DIAGNOSTICS.md`, `docs/CGD_STDLIB.md`, `docs/TESTING.md`).

## [0.1.0] - 2026-11-21

### Adicionado
- Extração e reestruturação do compilador C99 nativo em projeto independente `dcc`.
- Pré-processador C99/GNU99 real operando diretamente sobre `/usr/include` e cabeçalhos *freestanding* do sistema, com `#include_next`, `__has_include`, `__has_builtin`, `-I`, `-D`, `-U`, `#warning`, expansão multilinha de macros funcionais e mapeamento de linhas originais (`MapaFonte`).
- Camada formal de compatibilidade GNU (`-std=c99` e `-std=gnu99`) com classificação explícita em Categorias A, B (`packed`, `aligned`, `__asm__("simbolo")`, `typeof`) e C (rejeição explícita de atributos/extensões não suportados).
- Suporte a bit-fields C99 em `struct`, structs/unions anônimos embutidos, globais externas via GOT (`stdout`, `stderr`), `<stdarg.h>` binariamente compatível com System V AMD64 (`vsnprintf` da `libc.so.6`), VLAs com `sizeof` dinâmico, literais compostos, `static` locais, `__func__` e passagem/retorno de structs ≤ 8 bytes por valor.
- Emissor nativo de objetos relocáveis ELF64 (`-c` → `.o` `ET_REL`) com código PIC-compatível (`R_X86_64_PC32`, `R_X86_64_PLT32`, `R_X86_64_GOTPCREL`).
- Linker nativo ELF64 (`src/linker/linker.delegua`) capaz de linkar múltiplos `.o` (gerados por DCC, GCC ou Clang) em executáveis ELF64 dinâmicos (`PT_LOAD` `R E` + `R W`, 13 Section Headers, stubs PLT/GOT).
- Driver CLI completo (`-o`, `-c`, `-S`, `-E`, `-I`, `-D`, `-U`, `-L`, `-l`, `-std=`, `-O0..-O3`, `-Wall`, `-Wextra`, `-Werror`, `-v`, `--version`, `--help`) com rejeição explícita de flags não implementadas (`-g`).
- Sistema de build (`bootstrap/build.sh`, `bootstrap/verify.sh`, `Makefile`, CI em `.github/workflows/ci.yml`) e suíte diferencial independente contra GCC e Clang (`tests/run_tests.py`).
