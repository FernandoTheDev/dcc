# Sistema de Diagnósticos — DCC

O módulo [`src/diagnostics/diag.delegua`](../src/diagnostics/diag.delegua) centraliza o relatório de erros, avisos, notas, erros internos (ICE), mapeamento de origem (`MapaFonte`) e pilha de inclusão (`In file included from ...`).

---

## 1. Formato de Saída

### Formato textual padrão (`-fdiagnostics-format=text`)

Todos os diagnósticos são emitidos em **`stderr`** (via `cgd:io.IO.erroLinha`), preservando `stdout` limpo (fundamental para `-E` e pipes):

```text
In file included from main.c:1:
inc.h:4:5: error: atribuicao a objeto qualificado como 'const' [E3010]
    x = 2;
    ^
```

Com suporte a:
- **Pilha de inclusão completa** quando o erro ocorre em cabeçalho incluído;
- **Trecho de linha original** recuperado via `MapaFonte` e sublinhado proporcional ao comprimento do token (`^~~~`);
- **Cores ANSI** (`-fdiagnostics-color=auto|always|never`): em modo `auto`, detecta TTY em `stderr` via `isatty(2)` (FFI `libc`) e respeita a variável de ambiente padrão `NO_COLOR` (via `cgd:ambiente`);
- **Notas contextuais** opcionais (`note: ...`).

### Formato estruturado JSON (`-fdiagnostics-format=json`)

Serializado com `cgd:json.Json.formatar` em `stderr`, emitindo um objeto JSON por linha (JSON Lines) contendo:

```json
{"severity":"error","code":"E3010","category":"","file":"main.c","line":4,"column":5,"length":1,"message":"atribuicao a objeto qualificado como 'const'","note":"","snippet":"    x = 2;","include_stack":[]}
```

---

## 2. Controle de Avisos

| Flag | Comportamento |
| :--- | :--- |
| `-Wall` | Ativa avisos gerais (ex.: incompatibilidade de ponteiros `W2002`) |
| `-Wextra` | Ativa avisos extras |
| `-Werror` | Promove todos os avisos ativos para erro fatal |
| `-Wno-<categoria>` | Suprime avisos da categoria indicada (ex.: `-Wno-cpp`, `-Wno-incompatible-pointer-types`, `-Wno-all`) |

---

## 3. Catálogo de Códigos Estáveis

| Faixa | Fase | Exemplos |
| :--- | :--- | :--- |
| `E1000`–`E1020` | Pré-processador | `E1001` comentário `/*` aberto, `E1002` limite `#include`, `E1003` `#if`/`#endif`, `E1004`–`E1008` expressão `#if`, `E1011` limite de expansão de macro (anti-DoS), `E1014` `##` inválido, `E1016` header ausente, `E1020` `#error` |
| `W1001` | Pré-processador | `#warning` (categoria `cpp`) |
| `E2000`–`E2102` | Lexer / Parser | `E2001`–`E2005` erro léxico, `E2010` limite de recursão do parser, `E2100` atributo/inline `asm` GNU Cat C, `E2101` statement expression `({...})` Cat C, `E2102` computed goto `&&label` Cat C |
| `E3000`–`E3011` | Semântica / Tipos | `E3001` símbolo/struct duplicado, `E3002` campo duplicado, `E3003` bit-field inválido, `E3004` array negativo/overflow, `E3005` struct recursiva/incompleta, `E3006`/`E3007` `case`/`default` duplicado, `E3010` escrita em `const`, `E3011` tipos incompatíveis |
| `W2002` | Semântica | Ponteiros incompatíveis (`incompatible-pointer-types`, sob `-Wall`) |
| `E4001` | IR SSA / Verificador | Invariante estrutural SSA violada antes do backend |
| `E5000`–`E5015` | Backend / ELF / Linker | `E5001` frame/rel32 fora de alcance, `E5002` ELF64/`.a` malformado, `E5010` símbolo global duplicado, `E5011` símbolo indefinido, `E5012` relocação inválida/overflow |
| `E9000`–`E9999` | Driver / CLI / ICE | `E9001` flag desconhecida ou não suportada (`-g`), `E9999` erro interno do compilador (ICE) |
