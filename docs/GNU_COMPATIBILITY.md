# Camada Formal de Compatibilidade GNU — DCC

Os cabeçalhos oficiais da `glibc` em sistemas Linux utilizam extensões GNU além do ISO C99. O DCC separa estritamente a semântica ISO C99 (`-std=c99`, padrão) do modo com extensões GNU delimitadas (`-std=gnu99`) e classifica cada construção em três categorias formais.

## Modos de Compilação

- **`-std=c99` (padrão)**: define `__STRICT_ANSI__=1` e não define `__GNUC__`, permitindo que os cabeçalhos da glibc selecionem seus caminhos portáteis ISO C99.
- **`-std=gnu99`**: ativa palavras-chave GNU adicionais (`asm`, `typeof`), preserva `__attribute__` como palavra-chave real da linguagem (impedindo que cabeçalhos a redefinam como vazia) e habilita elisão `, ##__VA_ARGS__`.

## Classificação Formal

### Categoria A — Metadados Ignoráveis (sem efeito em layout, semântica ou ABI)

Aceitos e descartados de forma documentada:

- Palavras-chave/prefixos: `__extension__`, `__inline`, `__inline__`, `__restrict`, `__restrict__`, `__const`, `__const__`, `__volatile`, `__volatile__`.
- Atributos `__attribute__((...))`: `nonnull`, `format`, `format_arg`, `noreturn`, `pure`, `const`, `malloc`, `nothrow`, `leaf`, `deprecated`, `unused`, `used`, `warn_unused_result`, `always_inline`, `noinline`, `cold`, `hot`, `visibility`, `access`, `alloc_size`, `returns_twice`, `returns_nonnull`, `sentinel`, `artificial`, `gnu_inline`, `may_alias`, `weak`, `fd_arg`, `fd_arg_read`, `fd_arg_write`, `null_terminated_string_arg`, `externally_visible`, `no_sanitize`, `fallthrough`, `error`, `warning`.

### Categoria B — Extensões Semanticamente / ABI Relevantes (Implementadas)

Interpretadas com efeito real sobre tipos, layout ou símbolos de linkagem:

- `__attribute__((packed))`: define alinhamento de campos da `struct`/`union` para 1 byte (validado diferencialmente contra GCC e Clang).
- `__attribute__((aligned(N)))`: aplica alinhamento explícito `N` a tipos, campos e agregados (validado diferencialmente contra GCC e Clang).
- `__asm__("simbolo")` em declarações/protótipos externos: redireciona o nome do símbolo ELF emitido em `.symtab`/`.dynsym` (usado pela glibc para símbolos versionados como `__isoc99_scanf`).
- `__signed` / `__signed__`: sinalização explícita de tipos inteiros.
- `__builtin_va_list`, `__builtin_va_start`, `__builtin_va_arg`, `__builtin_va_end`, `__builtin_va_copy`: implementação ABI System V AMD64 de 176 bytes.
- `__builtin_offsetof(Tipo, campo)`: avaliado pelo layout LP64 real da tabela de tipos.
- `_Float32`, `_Float64`, `_Float32x`, `_Float64x`: tipos flutuantes usados nos headers da glibc.
- Structs/unions anônimos embutidos em agregados e `#include_next`, `__has_include`, `__has_builtin`, `__has_attribute`.
- `__typeof__` / `typeof` (suporte básico em `-std=gnu99`).

### Categoria C — Extensões Não Suportadas (Erro Explícito Obrigatório)

Nunca são ignoradas silenciosamente; o DCC emite erro explícito com arquivo, linha, coluna e marcador `^`:

- Inline assembly (`__asm__` / `asm`) dentro de corpos de função.
- Atributos `__attribute__((...))` fora das Categorias A e B (por exemplo, `vector_size`, `regparm`, `stdcall`, `fastcall`, `ms_abi`, `naked`, `interrupt`, `constructor`, `destructor`, `section`, `cleanup`).
- *Statement expressions* (`({ ... })`), labels computados (`&&label`) e extensões de memória atômica (`__atomic_*`).
