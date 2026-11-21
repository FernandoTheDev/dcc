# Changelog

Todas as mudanças notáveis do **DCC — Delégua C Compiler** são documentadas neste arquivo seguindo versionamento semântico (`MAJOR.MINOR.PATCH`).

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
