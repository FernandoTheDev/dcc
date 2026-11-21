# Arquitetura Interna do DCC

## 1. Visão Geral do Pipeline

```text
  arquivos .c / .o
         │
         ▼
  src/driver/cli.delegua          (CLI: -o, -c, -S, -E, -I, -D, -U, -L, -l, -std=, -O0..3, -W*)
         │
         ├──► (.c) src/preprocessor/preproc.delegua
         │         Fases 1–4 em O(N) sobre bytes, descoberta dinâmica de /usr/include e
         │         diretório freestanding, #include / #include_next, macros objeto/função/
         │         variádicas, #, ##, hide-set, #if/defined/__has_include, MapaFonte
         │         │
         │         ▼
         │    src/lexer/lexer.delegua           (Dicionários O(1), linha/coluna exatas, Fase 6)
         │         │
         │         ▼
         │    src/parser/parser.delegua         (AST C99/GNU99 + classificador __attribute__ A/B/C)
         │         │
         │         ▼
         │    src/semantic/sema.delegua         (Tipos LP64, padding, bit-fields, __asm__ link sym)
         │         │
         │         ▼
         │    src/ir/ir_ssa.delegua             (CFG + IR SSA tipada + otimizador + verificador)
         │         │
         │         ├──► (-S) src/backend/x86_64/asm.delegua      ──► arquivo .s (Intel x86-64)
         │         └──► src/backend/x86_64/codegen.delegua       ──► CodigoObjeto PIC-compatível
         │                     │
         │                     ▼
         │              src/object/elf/elf_obj.delegua           ──► arquivo objeto ELF64 (.o ET_REL)
         │                     │
         ▼                     ▼
  src/linker/linker.delegua  (Lê .o do DCC/GCC/Clang, mescla seções, resolve símbolos,
                              sintetiza _start + stubs PLT/GOT, aplica relocações x86-64)
         │
         ▼
  Executável ELF64 Dinâmico (ET_EXEC: PT_LOAD R E + PT_LOAD R W + 13 Section Headers)
```

## 2. ABI System V AMD64 (LP64)

- **Larguras e alinhamentos**: `_Bool`/`char`=1, `short`=2, `int`/`float`=4, `long`/`long long`/`double`/ponteiro=8.
- **Passagem de parâmetros**: 6 registradores GP (`rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`) e 8 SSE (`xmm0`..`xmm7`) com contadores independentes; argumentos excedentes empilhados da direita para a esquerda mantendo `rsp` alinhado em 16 bytes antes de `call`, lidos pelo callee em `[rbp + 16 + k*8]`.
- **Retornos**: `rax` (inteiros, ponteiros, `struct`/`union` ≤ 8 bytes), `xmm0` (`float`/`double`).
- **`va_list` (`__builtin_va_list`)**: layout binário System V AMD64 (`gp_offset`, `fp_offset`, `overflow_arg_area`, `reg_save_area`) com área de salvamento de 176 bytes (6 GP + 8 XMM × 16B), compatível diretamente com `vprintf`/`vsnprintf` da `libc.so.6`.
- **VLAs (`Alloca`)**: alocação dinâmica alinhada em 16 bytes na pilha via `sub rsp, rax`, restaurada automaticamente por `mov rsp, rbp` no epílogo.

## 3. Formato ELF64 e Linker Nativo

### Objeto Relocável (`-c` → `ET_REL`, `src/object/elf/elf_obj.delegua`)

Emite 10 seções padrão: `NULL`, `.text`, `.rela.text`, `.rodata`, `.data`, `.bss`, `.symtab` (todos `STB_LOCAL` antes de `STB_GLOBAL`), `.strtab`, `.shstrtab` e `.note.GNU-stack`.

Todo código gerado usa endereçamento relativo a RIP (`lea rax, [rip+disp32]` com `R_X86_64_PC32`, `mov rax, [rip+disp32]` com `R_X86_64_GOTPCREL`, `call rel32` com `R_X86_64_PLT32`), garantindo compatibilidade direta tanto com o linker nativo do DCC quanto com `gcc`/`ld` em modo PIE padrão do Linux.

### Linker Nativo e Executável Dinâmico (`src/linker/linker.delegua`)

- Lê múltiplos `.o` (`ET_REL` x86-64), mesclando seções alocáveis por permissões (`AX` → `.text`, `A` → `.rodata`, `WA PROGBITS` → `.data`, `WA NOBITS` → `.bss`).
- Resolve símbolos globais/fracos (`STB_GLOBAL`/`STB_WEAK`), detecta redefinições e ausência de `main`.
- Sintetiza `_start` (`call main; mov rdi, rax; xor eax, eax; call exit@plt`) e stubs PLT de 6 bytes (`jmp qword ptr [rip + got_disp32]`).
- Aplica relocações `R_X86_64_64` (1), `R_X86_64_PC32` (2), `R_X86_64_PLT32` (4), `R_X86_64_GOTPCREL` (9), `R_X86_64_32` (10), `R_X86_64_32S` (11), `R_X86_64_GOTPCRELX` (41) e `R_X86_64_REX_GOTPCRELX` (42).
- Produz executável W^X com 5 Program Headers (`PT_PHDR`, `PT_INTERP`, `PT_LOAD` `R E`, `PT_LOAD` `R W` alinhado em página 4096, `PT_DYNAMIC`) e 13 Section Headers.

### Limitações Atuais do Linker

- Não lê arquivos estáticos `.a` (`ar`) nem gera bibliotecas compartilhadas (`-shared`).
- Não suporta relocações TLS (`R_X86_64_TPOFF32` / `__thread`) nem tabelas `.init_array`/`.fini_array` (`__attribute__((constructor))`).
- Objetos externos produzidos por GCC/Clang com seções de código/dados padrão e relocações listadas acima linkam normalmente; construções que exijam símbolos internos da `libgcc` ou `crt1.o` ainda não são fornecidas.
