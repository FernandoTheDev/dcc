# Matriz de Conformidade ISO/IEC 9899:1999 (C99) — DCC

Este documento registra com transparência o estado real de cada área do padrão ISO C99 no DCC. **O DCC ainda não declara conformidade integral 100% com ISO C99**; lacunas conhecidas estão explicitamente listadas abaixo.

| Área do Padrão ISO C99 | Status | Validado (GCC + Clang) | Casos de Teste (`tests/run_tests.py`) | Observações / Problemas Conhecidos |
| ---------------------- | ------ | ---------------------- | ------------------------------------- | ---------------------------------- |
| Pré-processador (Fases 1–4): trigraphs, *line splicing*, comentários | Implementado | Sim | `pp_c99_trigraphs_macros_variadicas_defined_undef` | O(N) sobre bytes |
| Pré-processador: `#include`, `#include_next`, `-I`, `-D`, `-U` | Implementado | Sim | Todos os testes com `/usr/include/*` | Consome headers reais do sistema |
| Macros objeto, função, variádicas (`__VA_ARGS__`), `#`, `##`, *hide-set* | Implementado | Sim | `pp_c99_trigraphs_macros_variadicas_defined_undef` | Expansão multilinha suportada |
| `#if`/`#elif`/`#else`/`#endif`/`defined`, `#line`, `#error`, `_Pragma` | Implementado | Sim | `pp_c99_*`, `diag_pp_error`, `diag_werror_warning` | Curto-circuito seguro em `#if` |
| Tipos inteiros LP64 (`_Bool`, `char`, `short`, `int`, `long`, `long long`, `signed`/`unsigned`) | Implementado | Sim | `sys_headers_stdint_stdbool_limits_iso646_float` | Promoções e conversões usuais implementadas |
| Ponto flutuante IEEE-754 (`float`, `double`) | Implementado | Sim | `sys_headers_math_time_libm`, `sys_headers_stdarg_vsnprintf_glibc` | SSE2 escalar; `long double` mapeado para 64-bit IEEE-754 (80-bit x87 pendente) |
| `_Complex` e `_Imaginary` | Não implementado | Não | — | Pendente |
| Literais hexadecimais de ponto flutuante (`0x1.fp+3`), strings largas (`L"..."`), UCNs | Não implementado | Não | — | Pendente |
| Ponteiros multinível, aritmética/diferença, ponteiros de função e callbacks | Implementado | Sim | `abi_qsort_callback_e_10_args_pilha` | Interopera com `qsort` da `libc.so.6` |
| Arrays multidimensionais e tamanho inferido (`int a[] = ...`, `char s[] = "..."`) | Implementado | Sim | `sys_headers_ctype_assert_errno_signal` | Local e global |
| VLAs (Arrays de Tamanho Variável) e `sizeof` em tempo de execução | Implementado | Sim | `c99_vla_literais_compostos_static_func_struct_valor` | 1D via `Alloca` 16B; VLAs multidimensionais pendentes |
| `struct` e `union` (padding LP64, `offsetof`, cópia, anônimos) | Implementado | Sim | `tipos_lp64_padding_offsetof_bitfields` | Passagem/retorno por valor suportados até 8 bytes; > 8 bytes (`rax:rdx` / `sret`) pendente |
| Bit-fields em `struct` (`unsigned : N`, `signed : N`, `: 0`) | Implementado | Sim | `tipos_lp64_padding_offsetof_bitfields` | Empacotamento em unidades de armazenamento |
| `enum` (expressões constantes completas, vírgula final) | Implementado | Sim | `sys_headers_ctype_assert_errno_signal` | Valida enums complexos de `/usr/include/ctype.h` |
| `typedef` | Parcial | Sim | Todos os testes com headers glibc | `typedef` em escopo de arquivo e bloco; shadowing complexo de typedef em sub-blocos ainda limitado |
| Inicializadores designados (`.campo`, `[idx]`) e literais compostos (`(T){...}`) | Implementado | Sim | `c99_vla_literais_compostos_static_func_struct_valor` | Local e composto; relocação de ponteiros em `.data` global (ex. `const char *g = "abc";`) pendente |
| Storage classes (`extern`, `static` global/local, `auto`, `register`) | Implementado | Sim | `c99_vla_literais_compostos_static_func_struct_valor`, `linker_*` | `static` local persistente em `.data`/`.bss` |
| Qualificadores (`const`, `volatile`, `restrict`) e `inline` | Parcial | Sim | Todos os testes com headers glibc | Aceitos sintaticamente; checagem estrita de escrita em `const` e semântica `volatile` pendentes |
| Controle de fluxo (`if`, `while`, `do-while`, `for` C99, `switch`, `goto`/labels) | Implementado | Sim | Suíte completa | Inclui fallthrough em `switch` e curto-circuito `&&`/`||` |
| Funções variádicas (`<stdarg.h>`: `va_start`, `va_arg`, `va_copy`, `va_end`) | Implementado | Sim | `sys_headers_stdarg_vsnprintf_glibc` | Compatível binariamente com `vsnprintf` da `libc.so.6` |
| Identificador predefinido `__func__` | Implementado | Sim | `c99_vla_literais_compostos_static_func_struct_valor` | Internado em `.rodata` |
| Headers reais do sistema (`stdio`, `stdlib`, `string`, `stdint`, `stdbool`, `limits`, `ctype`, `stddef`, `stdarg`, `assert`, `math`, `time`, `errno`, `signal`, `inttypes`, `float`, `iso646`) | Implementado | Sim | `sys_headers_*` | Processados diretamente de `/usr/include` + diretório freestanding |
| Objetos relocáveis (`-c`) e Linker nativo multi-TU | Implementado | Sim | `linker_dcc_dcc`, `linker_gcc_sobre_dcc_o`, `linker_dcc_com_gcc_o`, `linker_dcc_com_clang_o` | Interoperável com GCC e Clang; arquivos `.a` e `-shared` pendentes |
