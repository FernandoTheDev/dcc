# Relatório de Auditoria Técnica — DCC (Ciclo III)

Este documento registra a auditoria completa da base inicial `v0.1.0` do **DCC (Delégua C Compiler)** (10.067 linhas distribuídas em 13 arquivos `.delegua`) e da biblioteca padrão do CGD (`~/.delegua/cgd`), servindo de guia técnico para a refatoração, endurecimento de segurança, correção de defeitos e ampliação de testes.

Baseline verificado em build limpo antes das modificações:
- `./bootstrap/build.sh` (CGD `v0.9.0`): sucesso.
- `make check-format`: 13/13 arquivos conformes.
- `./bootstrap/verify.sh` / `tests/run_tests.py`: 35/35 verificações aprovadas.

---

## 1. Problemas Críticos

### [CRIT-01] Leitor ELF64 do Linker sem validação de limites em entradas não confiáveis (`src/linker/linker.delegua`)
- **Causa provável**: `lerObjetoELF64` e `linkarObjetosELF64` confiam diretamente nos campos `e_shoff`, `e_shentsize`, `e_shnum`, `e_shstrndx`, `sh_offset`, `sh_size`, `sh_align`, `sh_link`, `sh_info`, `symIdx` e `r_offset` de arquivos `.o` externos, além de não validar `EI_CLASS == ELFCLASS64` e `EI_DATA == ELFDATA2LSB`.
- **Impacto**: Objetos `.o` truncados ou maliciosos provocam leitura/escrita fora dos limites (crash do processo compilador) ou exaustão de memória (OOM) via `sh_align` extremo (ex.: `0x40000000` em laço de preenchimento). Relocações com `r_offset` inválido corrompem seções ou falham sem diagnóstico.
- **Reprodução**: Fornecer ao `dcc` um arquivo `.o` de 64 bytes com magic ELF válido e `e_shoff = 999999` ou `sh_align = 1 << 30`.
- **Estratégia de correção**: Extrair `src/linker/elf_leitor.delegua` com validação estrita de cabeçalho ELF64, limites de arquivo, limites de tabela de seções/símbolos/strings, alinhamentos razoáveis (potência de 2 ≤ 65536), limites de `r_offset` e estouro de relocações de 32 bits, emitindo `ErroDCC` controlado.

### [CRIT-02] Comparações de ponto flutuante IEEE-754 incorretas com `NaN` (`src/backend/x86_64/codegen.delegua`, `asm.delegua`)
- **Causa provável**: `ucomisd xmm0, xmm1` ativa `ZF=1, PF=1, CF=1` quando qualquer operando é `NaN`. O backend emitia `sete` (`FEq`), `setne` (`FNeq`), `setb` (`FLt`) e `setbe` (`FLe`) sem tratar `PF` nem inverter operandos.
- **Impacto**: `NaN == NaN` avaliava para `1` (deveria ser `0`), `NaN != NaN` avaliava para `0` (deveria ser `1`), `NaN < 1.0` e `NaN <= 1.0` avaliavam para `1` (deveriam ser `0`), violando IEEE-754 e ISO C99.
- **Reprodução**: Compilar `double n = 0.0 / 0.0; return (n == n) || !(n != n) || (n < 1.0) || (n <= 1.0);` e comparar com GCC/Clang.
- **Estratégia de correção**: Usar `sete al; setnp dl; and al, dl` para `==`; `setne al; setp dl; or al, dl` para `!=`; `ucomisd xmm1, xmm0; seta al` para `<` e `setae al` para `<=` (em ambos `codegen.delegua` e `asm.delegua`).

### [CRIT-03] ABI incorreta para `float` (32 bits) em chamadas e retornos (`src/backend/x86_64/codegen.delegua`, `src/ir/ir_ssa.delegua`)
- **Causa provável**: A IR trata todos os registradores flutuantes como `double` (64 bits), e tanto a passagem de argumentos (`movsd`) quanto o retorno (`FRet`) e o prólogo (`cvtsd2ss` sobre argumento de entrada) assumiam `double` na fronteira ABI.
- **Impacto**: Incompatibilidade binária com GCC/Clang e `libm.so.6` em funções não-variádicas com parâmetros ou retorno `float` (ex.: `sinf(float)`, `float soma(float a, float b)`).
- **Reprodução**: Linkar objeto GCC contendo `float soma_f(float a, float b)` com chamada do DCC ou chamar `sinf(1.0f)`.
- **Estratégia de correção**: Rastrear largura flutuante (`4` vs `8`) em `FuncaoSSA` e `InstSSA` (argumentos/retorno): converter `double -> float` (`cvtsd2ss`) apenas ao passar argumento `float` não-variádico ou retornar `float`, e `cvtss2sd` no prólogo/retorno do chamador; preservar promoção `float -> double` em chamadas variádicas conforme C99.

### [CRIT-04] Aritmética inteira de 32 bits (`unsigned int` / `int`) sem truncamento de largura (`src/ir/ir_ssa.delegua`, `codegen.delegua`)
- **Causa provável**: Todas as instruções binárias/unárias inteiras na IR e no codegen operam em 64 bits (`REX.W`) sem normalizar resultados de operações de 32 bits (`int` / `unsigned int`).
- **Impacto**: Expressões como `unsigned int a = 0x80000000u; (a << 1) == 0`, `unsigned int x = 0xFFFFFFFFu; (~x) == 0` ou `unsigned long r = (0u - 1u);` produzem resultados incorretos de 64 bits divergindo de ISO C99, GCC e Clang.
- **Reprodução**: Compilar `unsigned int x = 0xFFFFFFFFu; return (~x == 0u) ? 0 : 1;` — retorna `1` em vez de `0`.
- **Estratégia de correção**: Carregar `largura` (`4` ou `8`) e `ehSemSinal` nas operações inteiras da IR e truncar/estender ou emitir instruções 32-bit x86-64 adequadas (respeitando também o constant folding no otimizador).

### [CRIT-05] Comentário de bloco `/*` não fechado aceito silenciosamente + bombas de expansão no pré-processador (`src/preprocessor/preproc.delegua`)
- **Causa provável**: Em `fasesIniciaisELimpezaPP`, o laço `enquanto (k + 1 < p)` para `/* ... */` termina sem verificar se `*/` foi encontrado e sem avançar o último byte. Além disso, `expandirTokens` não impõe limite de profundidade ou total de tokens expandidos.
- **Impacto**: Comentários `/*` não terminados são aceitos silenciosamente (vazando o último byte do arquivo). Macros exponenciais (`#define A B B`, `#define B C C`, ...) causam negação de serviço (CPU/RAM infinita).
- **Reprodução**: Compilar `int main(void) { return 0; } /* aberto` ou macro exponencial de 25 níveis.
- **Estratégia de correção**: Emitir diagnóstico controlado para `/*` não fechado; adicionar limites configuráveis de profundidade de macro, profundidade de `#if`, profundidade de expressão `#if`, total de includes e orçamento máximo de tokens expandidos.

### [CRIT-06] Estouro de pilha (DoS) por recursão ilimitada no parser e acesso fora dos limites em `avancar()` (`src/parser/parser.delegua`)
- **Causa provável**: Nenhuma regra recursiva (`parseExpr`, `parseStmt`, `parseBloco`, `parseCorpoAgregado`, `parseInicializador`, `lerDeclarador`) controla profundidade de aninhamento; `avancar()` incrementa `pos` sem limitar ao sentinela `Fim`.
- **Impacto**: Entradas maliciosas com milhares de `(` ou `{` aninhados derrubam o processo por stack overflow; erros de sincronização podem causar indexação fora do vetor de tokens.
- **Estratégia de correção**: Introduzir guarda de profundidade explícita (`entrarProfundidade`/`sairProfundidade`, limite padrão 256) e limitar `avancar()` ao último índice `Fim`.

---

## 2. Problemas Importantes

### [IMP-01] `sizeof("literal")` retorna `8` em vez de `tamanho + 1` (`src/semantic/sema.delegua`)
- **Causa provável**: `ExprStr` recebe tipo `char *` em vez de `char[N]`.
- **Impacto**: `sizeof("abc")` resulta em `8` em vez de `4`, violando ISO C99 6.4.5.
- **Estratégia de correção**: Tipar `ExprStr` como `TipoC.arrayDe(char, lenBytes + 1)` (preservando decaimento para ponteiro em expressões e mantendo o tamanho exato em `sizeof`).

### [IMP-02] Escapes em literais string e caractere incompletos; `\0` descartado em strings (`src/lexer/lexer.delegua`)
- **Causa provável**: O lexer descarta `\0` em strings em vez de gravar o byte `0` e não processa `\a`, `\b`, `\f`, `\v`, `\?`, `\xNN` ou octais `\NNN`.
- **Impacto**: `"a\0b"` vira `"ab"` com tamanho 2; `"\x41"` vira `"x41"`. Literais float malformados como `1e+` causam exceção não tratada em `real(...)`.
- **Estratégia de correção**: Armazenar literais de string como vetor de bytes (`inteiro[]`) além da representação textual, suportar escapes C99 completos (octal, hex, `\a\b\f\v\?`, `\0`), suportar literais hex-float `0x1.fp+3` e capturar falhas de conversão com `ErroDCC`.

### [IMP-03] `_start` não passa `argc` e `argv` para `main(int argc, char **argv)` (`src/linker/linker.delegua`)
- **Causa provável**: O stub `_start` sintetizado chama `main` diretamente sem carregar `rdi = [rsp]` e `rsi = rsp + 8`.
- **Impacto**: Qualquer programa C real que leia argumentos de linha de comando (`main(int argc, char **argv)`) recebe registradores não inicializados e falha com SIGSEGV.
- **Estratégia de correção**: Emitir `mov rdi, [rsp]; lea rsi, [rsp + 8]` antes de `call main` em `_start`.

### [IMP-04] Retorno de função não converte para o tipo real de retorno (`src/ir/ir_ssa.delegua`)
- **Causa provável**: `StmtReturn` sempre converte inteiros para `long` em vez de `fn.tipoRet`.
- **Impacto**: `char f(void) { return 300; }` ou `_Bool f(void) { return 5; }` retornam `300` e `5` em vez de `44` e `1`.
- **Estratégia de correção**: Armazenar `tipoRet` em `FuncaoSSA` e converter explicitamente para `tipoRet` no `StmtReturn`.

### [IMP-05] Atribuição composta (`+=`, `-=`) não escala ponteiros e ignora bit-fields (`src/ir/ir_ssa.delegua`)
- **Causa provável**: O ramo composto de `ExprAtrib` aplica `Add`/`Sub` bruto sem multiplicar pelo tamanho do elemento apontado e só trata bit-fields em `OpB.Assign`.
- **Impacto**: `int *p = arr; p += 2;` avança 2 bytes em vez de 8 bytes; `s.bf += 1;` corrompe o campo inteiro da unidade de armazenamento.
- **Estratégia de correção**: Aplicar escala de ponteiro em `+=`/`-=` e ciclo read-modify-write para bit-fields compostos (além de sign-extension no valor retornado por atribuição a bit-field com sinal).

### [IMP-06] Erros e avisos do driver vazam para `stdout` (`src/driver/cli.delegua`)
- **Causa provável**: Linhas 270, 276, 291, 297 e 324 usam `escreva(...)` em vez de `stderr`.
- **Impacto**: Em `-E`, avisos corrompem o código pré-processado em `stdout`; erros de arquivo ausente não vão para `stderr`.
- **Estratégia de correção**: Roteamento unificado via `cgd:io.IO.erroLinha(...)` para todos os diagnósticos e avisos.

### [IMP-07] Passagem/retorno por valor de `struct`/`union` > 8 bytes e inicializadores globais de ponteiros (`.rela.data`)
- **Causa provável**: Limitações conhecidas da v0.1.0: agregados > 8 bytes passados/retornados por valor tinham seu endereço passado incorretamente; ponteiros globais inicializados (`const char *g = "abc";`, `int *p = &x;`, `fn_t fp = foo;`) gravavam `0` sem relocação `.rela.data`.
- **Impacto**: Quebra interoperabilidade ABI System V AMD64 para structs 9–16B e >16B e impede construções C99 comuns em variáveis globais.
- **Estratégia de correção**: Implementar emissão de `.rela.data` em `ir_builder`/`codegen`/`elf_obj` (e suporte no linker) e implementar classificação ABI System V AMD64 para agregados (≤ 8B, 9–16B em dois registradores, > 16B via pilha/`sret`).

### [IMP-08] Semântica incompleta: structs recursivos/incompletos, shadowing de enum, `const`, `int + ptr`, `idx[arr]`, bit-fields inválidos, `case` duplicado
- **Causa provável**: `sema.delegua` omitia validações estruturais de tipos incompletos, tamanhos negativos/overflow de array, redefinição de campos/structs/globais, escrita em `const` e checagem de shadowing (`constantesEnum` tinha precedência sobre variáveis locais!).
- **Impacto**: Programas inválidos passam silenciosamente ou causam crash interno na fase de IR; programas válidos usando `2 + ptr`, `2[arr]` ou variável local com mesmo nome de enumerador geram código errado.
- **Estratégia de correção**: Corrigir precedência de escopo, adicionar checagens semânticas completas com diagnósticos precisos e suportar `int + ptr` e `idx[arr]`.

### [IMP-09] Otimizador e Verificador de IR com lacunas de segurança (`src/ir/ir_ssa.delegua`)
- **Causa provável**: `otimizarModuloSSA` dobra `SDiv`/`SMod` sem proteger `INT64_MIN / -1` e dobra shifts sem validar `0 <= shift < 64`; `verificarModuloSSA` não valida se operandos (`a`, `b`, `callArgs`) estão definidos, nem índices de strings/globais, nem instruções após terminador.
- **Impacto**: Constant folding pode causar SIGFPE no compilador; invariantes violadas de registradores podem escapar para o backend.
- **Estratégia de correção**: Endurecer `ir_opt.delegua` e ampliar `ir_verify.delegua` para validar todas as invariantes estruturais da IR.

### [IMP-10] `doubleParaBitsIEEE754` / `floatParaBitsIEEE754` incorretos para `Inf`, `NaN`, `-0.0` e subnormais (`src/types/tipos.delegua`)
- **Causa provável**: `val == 0.0` perde o sinal de `-0.0`, e valores não finitos (`Inf`/`NaN`) entram no laço de normalização gerando padrão de bits errado.
- **Estratégia de correção**: Tratar `NaN`, `+Inf`, `-Inf`, `-0.0` (detectável via `1.0 / val < 0.0`), subnormais e arredondamento tie-to-even usando `Primitivas.numeroFinito`.

---

## 3. Problemas Moderados e de Manutenção

### [MOD-01] Arquivos monolíticos com responsabilidades misturadas
- `src/ir/ir_ssa.delegua` (1.966 linhas): mistura tipos IR, lowering AST→IR, inicializadores globais, otimizador e verificador.
- `src/preprocessor/preproc.delegua` (1.403 linhas): mistura fases 1–3, tokenizador/expansão de macros, avaliador `#if` e gerenciador de includes.
- `src/backend/x86_64/codegen.delegua` (1.048 linhas): mistura estruturas de objeto, emissor de opcodes x86-64 com números mágicos e lowering de módulo/ABI.
- `src/linker/linker.delegua` (801 linhas): mistura leitor ELF64, mesclagem/resolução e emissor `ET_EXEC`.

### [MOD-02] Duplicação de lógica e subutilização da biblioteca padrão CGD (`~/.delegua/cgd`)
- Funções duplicadas que já existem na stdlib CGD:
  - `subtextoCli`, `terminaCom`, `trocarExtensao` (`cli.delegua`) e `comecaComL` (`linker.delegua`) → substituir por `cgd:textos` (`Textos.comecaCom`, `Textos.terminaCom`), `cgd:caminhos` (`Caminhos.diretorio`, `Caminhos.juntar`, `Caminhos.semExtensao`, `Caminhos.nome`) e `.fatiar()`.
  - `diretorioDe`, `juntarCaminho`, `subtextoPP` (`preproc.delegua`) → substituir por `cgd:caminhos` e `.fatiar()`.
  - `escreverErro` via `cgd:nativo.Primitivas` (`cli.delegua`) → usar `cgd:io.IO.erroLinha`.
  - `repetirEspacos` (`diag.delegua`) → usar `cgd:textos.Textos.repetir`.
  - `codigoAsciiChar` / `codigoCharPP` (varredura linear de 95 caracteres) → usar `Primitivas.codigoUnicode`.
- Duplicação interna entre módulos do DCC:
  - Serialização ELF (`anexarU16/32/64`, `alinhar`, `preencherAlinh`, `anexarCString`, `anexarShdr`) duplicada entre `elf_obj.delegua` e `linker.delegua` → centralizar em `src/object/elf/elf_comum.delegua` com constantes ELF nomeadas.
  - `parseInteiroPP` / `parseInteiroLit` duplicados entre `preproc.delegua` e `lexer.delegua` → centralizar em utilitário compartilhado.
  - `importar(...)` repetido dentro de métodos/funções quentes (ex.: `TabelaTipos.buscarCampo`, `baixarInicializador`, `preencherBytesGlobal`).

### [MOD-03] Uso de `/bin/sh` na descoberta de diretórios do sistema (`preproc.delegua`)
- `descobrirDirsSistema` invoca `/bin/sh -c "..."`. Pode ser substituído por `Processo.executar("find", ...)` sem shell + verificação direta via `cgd:arquivos`.
- Em `cli.delegua`, `chmod` pode ser executado via FFI `LibC` (`chmod`) sem shell, e `base64` recebe caminho apenas como argumento posicional `$1` (nunca interpolado em string de comando).

### [MOD-04] Sistema de diagnósticos básico (`src/diagnostics/diag.delegua`)
- Faltam códigos estáveis (`E1xxx`/`W2xxx`), sublinhado de intervalo (`^~~~`), histórico de inclusão (`In file included from ...`), diferenciação de ICE (erro interno do compilador), `-Wno-<categoria>`, `-fdiagnostics-color=auto|always|never` (com detecção `isatty(2)`), e formato estruturado `-fdiagnostics-format=json` (via `cgd:json`).
- `#warning` usa `saidaGlobal.tamanho() + 1` ainda não registrado em `MapaFonte`, imprimindo `<entrada>:N` em vez do arquivo/linha reais.

### [MOD-05] Defeitos específicos no Parser e Pré-processador
- `resTipo.alinhamentoExplicito = alinhAttr` muta instâncias compartilhadas de `TipoC` armazenadas em `typedefs`.
- `typedefs` plano sem pilha de escopos (impede shadowing por bloco).
- `sizeof((int)5)` colidia com o ramo de literal composto em `parsePrimario`.
- `AvaliadorExprPP` não rejeita `#if` vazio nem tokens residuais (`#if 1 2`), não protege `INT64_MIN / -1` e ignora aritmética unsigned (`#if -1 < 0U`).
- Extensões GNU Categoria C `({ ... })` (statement expression) e `&&label` (computed goto) não emitiam erro específico de Categoria C.
- `__attribute__((weak))` estava listado na Categoria A mesmo tendo efeito em binding ELF (`STB_WEAK`).

### [MOD-06] Limitações do Linker e Suíte de Testes
- Linker não lê bibliotecas estáticas `.a` (`ar`), não suporta símbolos `SHN_COMMON` nem relocações em `.rodata`.
- Suíte atual (`tests/run_tests.py`) tem 35 verificações, sem testes adversariais/fuzzing para pré-processador, lexer, parser ou arquivos ELF malformados, sem testes bidirecionais completos de ABI (`float`, structs 9–16B e >16B, variádicos cruzados), sem benchmarks de fases e sem testes prolongados de estabilidade/concorrência.

### [MOD-07] Transparência de IA e Política de Segurança ausentes
- `README.md` ainda não contém a seção obrigatória **AI-Generated and AI-Assisted Project**.
- Faltam `docs/AI_DEVELOPMENT.md` e `SECURITY.md`.

---

## 4. Auditoria da Biblioteca Padrão CGD (`~/.delegua/cgd`)

Versão instalada e verificada: **CGD v0.9.0** (`~/.delegua/cgd/`).

| Módulo `cgd:` | APIs Verificadas | Uso no DCC |
| ------------- | ---------------- | ---------- |
| `cgd:arquivos` | `Arquivo(caminho).existe()`, `.ler()`, `.escrever()`, `.informacoes()` | Leitura de `.c`/`.h`, escrita de `.s`/pré-processado |
| `cgd:caminhos` | `Caminhos.absoluto()`, `.normalizar()`, `.juntar()`, `.nome()`, `.diretorio()`, `.extensao()`, `.semExtensao()` | Resolução de `#include` e nomes de saída `.o`/`.s` |
| `cgd:bytes` | `Bytes.deTexto()`, `.deVetor()`, `.deBase64()`, `.paraVetor()`, `.paraTexto()`, `.paraBase64()`, `.tamanho()` | Fases 1–3 O(N), strings, buffers binários ELF |
| `cgd:textos` | `Textos.comecaCom()`, `.terminaCom()`, `.repetir()` | CLI, linker, formatação de diagnósticos |
| `cgd:io` | `IO.escrever()`, `.escreverLinha()`, `.erro()`, `.erroLinha()` | Saída padrão e diagnósticos em `stderr` |
| `cgd:processo` | `Processo.argumentos()`, `Processo.executar(...)` | Argumentos CLI, `base64`, `find` sem shell |
| `cgd:tempo` | `Cronometro` (`.segundos()`, `.milisegundos()`, `.reiniciar()`) | Medição de fases (`-ftime-report`) |
| `cgd:json` | `JSON.serializar(...)` | Diagnósticos estruturados (`-fdiagnostics-format=json`) |
| `cgd:ambiente` | `Ambiente.obter(...)` | `NO_COLOR` / variáveis de ambiente |
| `cgd:nativo` | `Primitivas.codigoUnicode()`, `.numeroFinito()` | Código ASCII/Unicode O(1) e checagem IEEE-754 |

---

## 5. Plano de Execução Incremental

1. **Etapa 1 — Diagnósticos Profissionais + Utilitários Compartilhados + ELF Comum**: atualizar `diag.delegua`, criar `src/object/elf/elf_comum.delegua` e `src/lexer/literais.delegua`, corrigir `tipos.delegua` (qualificadores, `clonar()`, IEEE-754 exato, proteção de overflow em `tamanhoDe`).
2. **Etapa 2 — Pré-processador Modular e Endurecido**: dividir em `pp_expr.delegua`, `pp_macros.delegua`, `preproc.delegua`; corrigir `/*` não fechado, `#warning`, `AvaliadorExprPP` (unsigned/div0/overflow/trailing), adicionar limites anti-DoS, rastreamento de includes e remover `/bin/sh` de `descobrirDirsSistema`.
3. **Etapa 3 — Lexer e Parser Endurecidos**: literais string como `inteiro[]` com escapes C99 completos (`\0`, octal, `\x`, etc.), hex-floats, guarda de profundidade no parser, `pilhaTypedefs`, `avancar()` seguro, Cat C explícita para `({ ... })` e `&&label`, `const`/`volatile`, `sizeof((int)5)`, `offsetof` aninhado.
4. **Etapa 4 — Análise Semântica Completa**: corrigir `sizeof("str")`, shadowing de enum, structs recursivos/incompletos, arrays negativos/overflow, validação de bit-fields, `int + ptr`, `idx[arr]`, escrita em `const`, duplicação de `case`/campos/globais, avisos `-Wall`/`-Wextra`.
5. **Etapa 5 — IR Modularizada, Otimizador Seguro e Verificador Expandido**: dividir em `ir_tipos.delegua`, `ir_builder.delegua`, `ir_opt.delegua`, `ir_verify.delegua`, `ir_ssa.delegua`; corrigir retorno `tipoRet`, aritmética 32/64-bit, `ptr += n`, bit-fields compostos, `.rela.data` para ponteiros globais, structs > 8B (9–16B e `sret`), `float` 32-bit ABI, otimizador seguro e verificador estrito.
6. **Etapa 6 — Backend x86-64 e Emissor ELF64**: dividir `emissor.delegua`, `abi.delegua`, `codegen.delegua`; corrigir comparações `NaN`, `float` 32-bit ABI, unsigned `ItoF`/`FtoI`, ops 32-bit, structs 9–16B / `sret`, checagens de overflow, `.rela.data` em `elf_obj.delegua`, melhorar `asm.delegua`.
7. **Etapa 7 — Linker Seguro + `.a` + `argc/argv`**: extrair `elf_leitor.delegua` (validação completa + suporte a arquivos estáticos `.a` `ar`), passar `argc`/`argv` no `_start`, suportar `.rela.data`, `.rodata` relocs e `SHN_COMMON`.
8. **Etapa 8 — Driver CLI Limpo + `-ftime-report` + Flags de Diagnóstico**: adotar `cgd:io`, `cgd:caminhos`, `cgd:textos`, `cgd:tempo`, `cgd:json`, `cgd:ambiente`, `isatty`/`chmod` via FFI, suporte a `.a`, `-Wno-*`, `-fdiagnostics-color=*`, `-fdiagnostics-format=*`, `-ftime-report`.
9. **Etapa 9 — Suíte Ampliada (Diferencial, ABI Bidirecional, Linker/Archives, Segurança/Fuzzing, Estresse e Benchmarks)** e correção de quaisquer bugs descobertos.
10. **Etapa 10 — Documentação Completa, Transparência de IA (`README.md`, `docs/AI_DEVELOPMENT.md`, `SECURITY.md`, etc.), CI e Validação Final Limpa**.


---

## 9. Status de Resolução ao Final do Ciclo III (v0.2.0)

Todos os itens críticos e importantes priorizados nesta rodada foram corrigidos e verificados por testes automatizados; itens fora de escopo do Ciclo III permanecem registrados com transparência para o Ciclo IV.

| Grupo / Achado da Auditoria | Status v0.2.0 | Evidência de Validação |
| :--- | :---: | :--- |
| **CRIT-01** Injeção de shell em I/O binário e descoberta de headers | **Resolvido** | `descobrirDirsSistema` usa `Processo.executar("find", ...)` sem `/bin/sh`; `chmod` migrado para FFI `libc`; ponte `base64` usa comando estático com caminho em argumento posicional `$1` |
| **CRIT-02** Comparações IEEE-754 incorretas para `NaN` | **Resolvido** | `ucomisd` + teste de `PF` (`jp`/`jnp`) em `emissor.delegua` e `asm.delegua`; validado em `c99_ieee754_nan_inf_float32_hexfloat_u64` (`-O0/-O1/-O2`) |
| **CRIT-03** Operações inteiras 32-bit em 64-bit e truncamento de retorno | **Resolvido** | Largura `4` vs `8` em `ir_builder`/`emissor`/`asm` + conversão para `fn.tipoRet`; validado em `c99_int32_unsigned_wraparound_bitops_ret_trunc` |
| **CRIT-04** Conversão `uint64_t <-> double` tratada como signed + overflow de literais u64 | **Resolvido** | `OpIR.UItoF`/`FtoUI` + `parseInteiroC99` em duas metades de 32 bits; validado em `c99_ieee754_nan_inf_float32_hexfloat_u64` |
| **CRIT-05** Leitor ELF64/`.a` vulnerável a entradas malformadas | **Resolvido** | `src/linker/elf_leitor.delegua` + validação de bounds/overflow de relocação em `linker.delegua`; 15/15 binários hostis rejeitados em `tests/test_security_fuzz.py` |
| **CRIT-06** Pré-processador vulnerável a macro-bombs, `#include` cíclico e comentários abertos | **Resolvido** | Limites anti-DoS (`E1001`–`E1014`) + avaliador `#if` 64-bit seguro; 12/12 adversariais aprovados em `tests/test_security_fuzz.py` |
| **CRIT-07** Parser sujeito a stack overflow (`R0001`) em aninhamento profundo | **Resolvido** | Precedence Climbing (`parseBinaria`) + guarda de profundidade `96` (`E2010`); 50/50 entradas fuzz aprovadas em `tests/test_security_fuzz.py` |
| **IMP-01** `float` 32-bit na ABI System V AMD64 | **Resolvido** | `cvtsd2ss`/`cvtss2sd` na borda ABI e promoção variádica; validado em `abi_*` (4 direções) e `sqrtf` |
| **IMP-02** Structs `9..16B` (`rax:rdx`) e `>16B` (`sret`) por valor | **Resolvido** | `RetPair` + `sret` oculto em `ir_builder`/`codegen`; validado em `c99_structs_9_16_e_sret_*` e `abi_*` (4 direções) |
| **IMP-03** Inicializadores de ponteiros globais (`.rela.data`) | **Resolvido** | Emissão `.rela.data` em `codegen`/`elf_obj` + resolução em `linker`; validado em `c99_globais_ponteiros_rela_data_*` |
| **IMP-04** `sizeof("str")`, escapes C99 exatos (`\0`, octal, `\xNN`) e hex-float | **Resolvido** | `bytesStr` exatos no lexer + `literais.delegua`; validado em `c99_strings_escapes_sizeof_ptr_arith` e `c99_ieee754_*` |
| **IMP-05** `typedef` com escopo por bloco, shadowing de `enum`, `const`, duplicatas, structs recursivas | **Resolvido** | `pilhaTypedefs`, `.clonar()`, `E3001`–`E3011`, `W2002`; validado em `run_tests.py` |
| **IMP-06** Archives estáticos `.a` (`-L`/`-l`), `STB_WEAK` (Cat B), `SHN_COMMON`, `argc`/`argv` | **Resolvido** | Extração iterativa `.a`, `STB_WEAK` com relocação na própria TU, `argc`/`argv` em `_start`; validado em `linker_*` e `c99_argc_argv_*` |
| **IMP-07** Bit-fields: inicialização em `{...}`, atribuição composta e retorno com sinal | **Resolvido** | `gravarBitField` em `baixarInicializador` e `ExprAtrib`; validado em `c99_globais_ponteiros_*` |
| **IMP-08** Divisão modular e adoção da stdlib `cgd:*` | **Resolvido** | 13 → 23 módulos (`preproc/pp_macros/pp_expr`, `ir_*`, `literais`, `elf_comum`, `elf_leitor`), 10 módulos `cgd:*` integrados |
| **IMP-09** Diagnósticos profissionais (códigos, include stack, ANSI, JSON, `-Wno-*`, `-ftime-report`) | **Resolvido** | Validado em `diagnostico_formato_json`, `diagnostico_cores_ansi`, `diagnostico_wno_cpp_e_stderr_limpo`, `diag_include_stack`, `benchmark_fases` |
| **PEND-01** Classificação `eightbytes` SSE em structs ≤16B puramente float/double | **Pendente (Ciclo IV)** | Documentado em `docs/ABI.md` e `docs/C99_CONFORMANCE.md` |
| **PEND-02** `long double` 80-bit x87, `_Complex`, `L"..."`, UCNs, VLAs N-D | **Pendente (Ciclo IV)** | Documentado em `docs/C99_CONFORMANCE.md` |
| **PEND-03** Alocação real de registradores (`mem2reg` + linear scan) | **Pendente (Ciclo IV)** | Documentado em `docs/CONTINUITY.md` |
| **PEND-04** `-shared` (`ET_DYN`), PIE, TLS e DWARF (`-g`) | **Pendente (Ciclo IV)** | Documentado em `docs/LINKER.md` e `docs/CONTINUITY.md` |
