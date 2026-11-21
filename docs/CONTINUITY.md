# Continuidade Técnica — DCC (Delégua C Compiler)

Data: 21/11/2026 — Versão inicial `0.1.0`

## Decisões Arquiteturais Consolidadas

1. **Extração independente para `/home/fernandodev/dcc/`**: zero dependência dos diretórios ou exemplos do CGD; o CGD é usado apenas como compilador de bootstrap dos fontes `.delegua`.
2. **Headers reais do sistema (`/usr/include` + diretório freestanding descoberto dinamicamente)**: nenhum cabeçalho da libc foi recriado ou simulado. A descoberta automática seleciona exatamente um diretório freestanding (`gcc` ou `clang`) antes de `/usr/local/include` e `/usr/include`, garantindo funcionamento correto de `#include_next <stdint.h>`.
3. **Desempenho O(N) no pré-processador e lexer**: `fasesIniciaisELimpezaPP` opera sobre vetores de bytes `inteiro[]` (`cgd:bytes`) e `LexerDCC` tokeniza linha a linha, eliminando o gargalo O(N²) de indexação UTF-8 sobre headers grandes da glibc (`<stdio.h>` + `<stdlib.h>` + `<string.h>` = 50 headers reais compilados em ~1,7s).
4. **Pipeline unificado via objetos ELF64 (`ET_REL`) + Linker nativo (`ET_EXEC`)**: todo código de máquina x86-64 gerado por `src/backend/x86_64/codegen.delegua` é PIC-compatível (`R_X86_64_PC32`, `R_X86_64_PLT32`, `R_X86_64_GOTPCREL`), serializado em `.o` padrão por `src/object/elf/elf_obj.delegua` e linkado pelo linker nativo `src/linker/linker.delegua`. Isso permite interoperabilidade nos dois sentidos com `gcc -c` e `clang -c`.
5. **Diagnósticos em `stderr` + saída limpa**: erros e avisos vão para `stderr` via `Primitivas.sistemaEscrever(..., verdadeiro)` com formato `arquivo:linha:coluna: error:` + trecho + `^`, encerrando com `_exit(codigo)` sem stacktrace do runtime Delégua.

## Testes Realmente Executados

- `./bootstrap/build.sh` — compilou `build/dcc` com `cgd -o` sem erros nem avisos.
- `./bootstrap/verify.sh` — executou smoke independente a partir de `/tmp`, auditou `ldd build/dcc` e rodou `tests/run_tests.py`.
- `python3 tests/run_tests.py` — **35/35 verificações aprovadas, 0 falhas**:
  - 11 programas diferenciais × `-O0` e `-O2` comparados contra **GCC 16** e **Clang 22** usando headers reais de `/usr/include/` (`stdio.h`, `stdlib.h`, `string.h`, `stdint.h`, `stdbool.h`, `limits.h`, `iso646.h`, `float.h`, `inttypes.h`, `ctype.h`, `assert.h`, `errno.h`, `signal.h`, `math.h`, `time.h`, `stdarg.h`).
  - 4 combinações de linkagem ELF64 (`DCC+DCC → DCC`, `DCC .o → GCC PIE`, `GCC .o + DCC .o → DCC`, `Clang .o + DCC .o → DCC`) + auditoria `readelf`/`ldd`.
  - 7 testes negativos (diagnósticos com `^`, GNU Cat C `vector_size` e inline `__asm__`, `#error`, `-Werror`, rejeição de `-g` e flags desconhecidas) + teste `-S` a partir de `/tmp`.
- `make check-format` — todos os 12 arquivos `.delegua` em `src/` verificados com `cgd --verificar-formatacao`.

## Próximos Passos Prioritários

1. Passagem e retorno por valor de `struct`/`union` maiores que 8 bytes (9–16B em `rax:rdx` e > 16B via ponteiro oculto `sret` conforme System V AMD64 ABI).
2. Inicializadores globais com endereços simbólicos (emissão de `.rela.data` no `.o` para `const char *g = "texto";` e ponteiros globais para funções/variáveis).
3. Suporte a `_Complex`, `long double` 80-bit x87, literais hex-float (`0x1.fp+3`) e strings largas (`L"..."`).
4. Checagem estrita de qualificadores (`const`), compatibilidade rigorosa de ponteiros com diagnósticos dedicados e `typedef` com shadowing completo por bloco.
5. Otimizações SSA adicionais (`mem2reg` com nós `phi`, alocação de registradores linear scan / grafo de interferência).
6. Leitura de arquivos estáticos `.a` (`ar`), suporte a `-shared` e emissão DWARF básica para habilitar `-g`.
