# Camada Formal de Compatibilidade GNU — DCC (v0.2.0)

Os cabeçalhos oficiais da `glibc` em sistemas Linux utilizam extensões GNU além do ISO C99. O DCC separa estritamente a semântica ISO C99 (`-std=c99`, padrão) do modo com extensões GNU delimitadas (`-std=gnu99`) e classifica explicitamente cada construção em três categorias formais — nunca ignorando silenciosamente extensões que alterem layout, semântica ou ABI.

## Modos de Compilação

- **`-std=c99` (padrão)**: define `__STRICT_ANSI__=1` e não define `__GNUC__`, permitindo que os cabeçalhos da glibc selecionem caminhos ISO C99.
- **`-std=gnu99`**: ativa palavras-chave GNU adicionais (`asm`, `typeof`), preserva `__attribute__` como palavra-chave real da linguagem e habilita elisão `, ##__VA_ARGS__`.

## Classificação Formal

### Categoria A — Metadados Ignoráveis (sem efeito em layout, semântica ou ABI)

Aceitos e descartados de forma documentada:

- Palavras-chave/prefixos: `__extension__`, `__inline`, `__inline__`, `__restrict`, `__restrict__`, `__const`, `__const__`, `__volatile`, `__volatile__`.
- Atributos `__attribute__((...))`: `nonnull`, `format`, `format_arg`, `noreturn`, `pure`, `const`, `malloc`, `nothrow`, `leaf`, `deprecated`, `unused`, `used`, `warn_unused_result`, `always_inline`, `noinline`, `cold`, `hot`, `visibility`, `access`, `alloc_size`, `returns_twice`, `returns_nonnull`, `sentinel`, `artificial`, `gnu_inline`, `may_alias`, `fd_arg`, `fd_arg_read`, `fd_arg_write`, `null_terminated_string_arg`, `externally_visible`, `no_sanitize`, `fallthrough`, `error`, `warning`.

### Categoria B — Extensões Semanticamente / ABI Relevantes (Implementadas)

Interpretadas com efeito real sobre tipos, layout ou símbolos ELF:

- `__attribute__((packed))`: define alinhamento de campos da `struct`/`union` para 1 byte (validado diferencialmente contra GCC e Clang).
- `__attribute__((aligned(N)))`: aplica alinhamento explícito `N` a tipos, campos e agregados, com validação obrigatória de `N > 0` potência de 2 (validado diferencialmente contra GCC e Clang).
- `__attribute__((weak))` *(promovido de Cat A para Cat B na v0.2.0)*: emite símbolo `STB_WEAK` em `.symtab` e força relocação simbólica em chamadas/endereços da própria TU, permitindo sobrescrita por definição forte em outro `.o` (validado em `linker_weak_override_strong`).
- `__asm__("simbolo")` em declarações/protótipos externos: redireciona o nome do símbolo ELF emitido em `.symtab`/`.dynsym` (usado pela glibc para símbolos como `__isoc99_scanf`).
- `__signed` / `__signed__`: sinalização explícita de tipos inteiros.
- `__builtin_va_list`, `__builtin_va_start`, `__builtin_va_arg`, `__builtin_va_end`, `__builtin_va_copy`: implementação ABI System V AMD64 de 176 bytes.
- `__builtin_offsetof(Tipo, campo.subcampo)`: suporta acesso a campos aninhados avaliado pelo layout LP64 real.
- `_Float32`, `_Float64`, `_Float32x`, `_Float64x`: tipos flutuantes usados nos headers da glibc.
- Structs/unions anônimos embutidos em agregados e `#include_next`, `__has_include`, `__has_include_next`, `__has_builtin`, `__has_attribute`.
- `__typeof__` / `typeof` (suporte em `-std=gnu99`).

### Categoria C — Extensões Não Suportadas (Erro Explícito Obrigatório)

Nunca são ignoradas silenciosamente; o DCC emite erro explícito com código estável, arquivo, linha, coluna e sublinhado:

- Inline assembly (`__asm__` / `asm`) dentro de corpos de função (`E2100`, testado em `diag_inline_asm_cat_c`).
- Atributos `__attribute__((...))` fora das Categorias A e B — por exemplo `vector_size`, `regparm`, `stdcall`, `fastcall`, `ms_abi`, `naked`, `interrupt`, `constructor`, `destructor`, `section`, `cleanup`, `alias`, `transparent_union` (`E2100`, testado em `diag_gnu_cat_c`).
- *Statement expressions* GNU (`({ ... })`) (`E2101`, testado em `diag_gnu_stmt_expr_cat_c`).
- *Computed goto* / endereço de rótulo (`&&label`, `goto *expr`) (`E2102`, testado em `diag_gnu_computed_goto_cat_c`).
- Extensões de memória atômica (`__atomic_*`) e extensões vetoriais SIMD.
