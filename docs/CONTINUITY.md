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
