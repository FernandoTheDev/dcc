# DCC — Delégua C Compiler

**DCC** (*Delégua C Compiler*) é um compilador C nativo para **Linux x86-64** (System V AMD64 ABI), escrito integralmente em **Delégua** e compilado para executável nativo pelo **CGD** (*Compilador Geral Delégua*).

O DCC possui pré-processador, lexer, parser, analisador semântico, IR SSA tipada, otimizador, gerador de código de máquina x86-64, emissor de objetos relocáveis ELF64 (`.o` / `ET_REL`), emissor de Assembly x86-64 e linker nativo ELF64 (`ET_EXEC`) próprios — sem invocar GCC, Clang, NASM ou `ld` como backend oculto.

## Características Principais

- **Processamento real de headers do sistema**: consome diretamente os cabeçalhos originais de `/usr/include` e do diretório *freestanding* do sistema (sem headers falsos e sem registro manual de funções da libc).
- **Pré-processador C99/GNU99 real**: fases 1–4, trigraphs, *line splicing*, `#include`, `#include_next`, `-I`, `-D`, `-U`, macros de objeto/função/variádicas (`__VA_ARGS__`), `#`, `##`, *hide-set* contra recursão infinita, `#if`/`#elif`/`#else`/`#endif`/`defined`/`__has_include`, `#line`, `#error`, `#warning`, `#pragma once`, `_Pragma`.
- **Camada formal de compatibilidade GNU** (`-std=c99` vs `-std=gnu99`): classificação explícita em Categorias A (metadados), B (semântica/layout/ABI, como `packed`, `aligned(N)` e `__asm__("simbolo")`) e C (diagnóstico explícito de erro para recursos não suportados).
- **Backend x86-64 e Linker ELF64 nativos**: gera código PIC-compatível, objetos `.o` (`ET_REL`) interoperáveis com GCC/Clang e executáveis ELF64 dinâmicos com segmentos separados `PT_LOAD` (`R E` e `R W`), Section Headers completos e vínculo dinâmico à `libc.so.6` e `libm.so.6` (`-lm`).
- **Diagnósticos estruturados**: arquivo, linha, coluna, trecho de código original e marcador `^`, respeitando `-Wall`, `-Wextra` e `-Werror`.

## Requisitos de Build

- **CGD** ≥ `0.9.0` disponível no `PATH` (ou via `CGD=/caminho/para/cgd`) e seu runtime/bibliotecas nativas (usado exclusivamente para compilar os fontes `.delegua` do DCC).
- Linux x86-64 com headers de desenvolvimento da `glibc` (`/usr/include`) e `coreutils` (`base64`).
- Para executar a suíte diferencial (`tests/run_tests.py`): Python 3, `gcc`, `clang`, `binutils` (`readelf`) e `ldd`.

## Build e Instalação

```sh
./bootstrap/build.sh
./bootstrap/verify.sh
```

Instalação com prefixo configurável (padrão `/usr/local`):

```sh
sudo make install
# ou em diretório local:
make install PREFIX="$HOME/.local"
```

Empacotamento para distribuição Linux x86-64:

```sh
make dist
```

## Uso

```sh
# Compilar e linkar diretamente para executável ELF64
./build/dcc examples/hello_libc.c -o hello
./hello

# Compilar com otimização e biblioteca matemática (libm.so.6)
./build/dcc -O2 prog.c -lm -o prog

# Compilação separada para objeto relocável ELF64 (.o) + linkagem nativa
./build/dcc -c modulo_a.c -o modulo_a.o
./build/dcc -c modulo_b.c -o modulo_b.o
./build/dcc modulo_a.o modulo_b.o -o programa

# Interoperabilidade de objetos .o com GCC/Clang
gcc -std=c99 -c helper.c -o helper.o
./build/dcc -c main.c -o main.o
./build/dcc main.o helper.o -o programa

# Emissão de Assembly x86-64 (-S) e apenas pré-processador (-E)
./build/dcc -S prog.c -o prog.s
./build/dcc -E -DFOO=42 prog.c

# Modos ISO C99 e GNU99
./build/dcc -std=c99 prog.c -o prog
./build/dcc -std=gnu99 prog.c -o prog
```

## Estrutura do Projeto

```text
dcc/
├── bootstrap/          # Scripts de build e verificação independente
├── src/
│   ├── main.delegua    # Ponto de entrada do executável dcc
│   ├── driver/         # Interface CLI e orquestração do pipeline
│   ├── diagnostics/    # Formatação de diagnósticos e mapa de origem
│   ├── types/          # Enums, sistema de tipos LP64 e IEEE-754 puro
│   ├── preprocessor/   # Pré-processador C99/GNU99 real
│   ├── lexer/          # Analisador léxico com dicionários O(1)
│   ├── parser/         # Parser C99/GNU99 + classificador __attribute__
│   ├── semantic/       # Análise semântica, layout LP64 e bit-fields
│   ├── ir/             # Lowering AST -> IR SSA, otimizador e verificador
│   ├── backend/x86_64/ # Emissor Assembly (-S) e codegen x86-64 PIC
│   ├── object/elf/     # Emissor ELF64 relocável (.o / ET_REL)
│   └── linker/         # Linker nativo ELF64 (ET_REL -> ET_EXEC)
├── examples/           # Exemplos C reais
├── tests/              # Suíte diferencial (GCC + Clang), linker e CLI
└── docs/               # Arquitetura, matriz C99, GNU e continuidade
```

## Documentação

- [Arquitetura interna](docs/ARCHITECTURE.md)
- [Matriz de conformidade ISO C99](docs/C99_CONFORMANCE.md)
- [Camada de compatibilidade GNU](docs/GNU_COMPATIBILITY.md)
- [Registro de continuidade](docs/CONTINUITY.md)
- [Como contribuir](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Licença e Atribuição

Distribuído sob a licença **Apache-2.0** (ver [LICENSE](LICENSE)).
O DCC nasceu a partir do compilador C nativo desenvolvido no projeto **CGD — Compilador Geral Delégua**, utilizando a linguagem Delégua inspirada no projeto [Design Líquido / Delégua](https://github.com/DesignLiquido/delegua).
