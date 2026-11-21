# DCC — Delégua C Compiler

**DCC** (*Delégua C Compiler*) é um compilador C99/GNU99 nativo e independente para **Linux x86-64** (System V AMD64 ABI), escrito integralmente em **Delégua** e compilado para executável nativo pelo **CGD** (*Compilador Geral Delégua*).

O DCC possui pré-processador, lexer, parser, analisador semântico, IR SSA tipada, otimizador, verificador de invariantes, gerador de código de máquina x86-64, emissor de objetos relocáveis ELF64 (`.o` / `ET_REL`), emissor de Assembly x86-64 (`-S`), leitor de arquivos `.o`/`.a` e linker nativo ELF64 (`ET_EXEC`) próprios — sem delegar pré-processamento, compilação, montagem ou linkagem a GCC, Clang, NASM ou `ld`.

> **Aviso de maturidade**: o DCC é um compilador **experimental / educacional / em desenvolvimento ativo** (v0.2.0). Ele **não** é certificado para uso em produção crítica nem oferece cobertura completa de 100% do padrão ISO C99 ou de extensões GNU.

---

## AI-Generated and AI-Assisted Project

Este projeto (**DCC — Delégua C Compiler**) foi desenvolvido de forma **amplamente assistida e gerada por inteligência artificial** (engenharia, arquitetura modular, implementação em Delégua, auditoria de segurança, suítes de testes diferenciais/fuzzing e documentação), sob direção e definição de requisitos por mantenedores humanos.

O que isso significa na prática para usuários e contribuidores:

- **Transparência explícita**: não há qualquer afirmação de revisão humana linha a linha nem de auditoria formal independente de segurança.
- **Evidência reproduzível acima de promessas**: o comportamento validado do DCC é respaldado por testes automatizados executados localmente (testes diferenciais contra `gcc` e `clang` em `-O0/-O1/-O2`, interoperabilidade ABI bidirecional, auditoria ELF64 com `readelf`/`ldd`, suíte adversarial de pré-processador/parser/ELF e testes de estresse/concorrência), e **não** por declarações abstratas de corretude.
- **Limitações conhecidas**: recursos ausentes ou parciais estão registrados explicitamente em [docs/C99_CONFORMANCE.md](docs/C99_CONFORMANCE.md), [docs/GNU_COMPATIBILITY.md](docs/GNU_COMPATIBILITY.md) e [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md).
- **Recomendações de uso responsável**: revise cuidadosamente o código gerado e os artefatos produzidos antes de qualquer uso sensível, e isole a execução ao compilar entradas não confiáveis (veja [SECURITY.md](SECURITY.md)).

Mais detalhes sobre a metodologia, histórico de ciclos e critérios de verificação constam em [docs/AI_DEVELOPMENT.md](docs/AI_DEVELOPMENT.md).

---

## Características Principais

- **Processamento real de cabeçalhos do sistema**: consome diretamente `/usr/include` e o diretório *freestanding* descoberto dinamicamente (sem headers simulados nem cadastro manual de funções da libc).
- **Pré-processador C99/GNU99 real com limites anti-DoS**: fases 1–4, trigraphs, *line splicing*, `#include`, `#include_next`, `-I`, `-D`, `-U`, macros de objeto/função/variádicas (`__VA_ARGS__`, `, ##__VA_ARGS__`), `#`, `##`, *hide-set* de Prosser, `#if`/`#elif`/`#else`/`#endif`/`defined`/`__has_include`/`__has_builtin`, `#line`, `#error`, `#warning`, `#pragma once`, `_Pragma`, cache de headers + otimização de include-guards (MI-OPT) e limites configurados contra macro-bombs e recursão infinita.
- **Camada formal de compatibilidade GNU** (`-std=c99` vs `-std=gnu99`): classificação explícita em Categorias A (metadados), B (semântica/layout/ABI: `packed`, `aligned(N)` potência de 2, `weak`, `__asm__("simbolo")`, `typeof`, `__builtin_expect`, `__thread` / `_Thread_local` TLS externo) e C (erro explícito para extensões não suportadas como inline `asm`, statement expressions `({...})` e computed goto `&&label`).
- **Frontend e Semântica C99 endurecidos**: literais hex-float (`0x1.fp+3`), escapes C99 exatos em bytes (`\0`, octal `\NNN`, `\xNN`), inteiros até `UINT64_MAX`, `sizeof("str")`, inicializadores designados aninhados (`.a.b = x`), `typedef` com escopo por bloco, rejeição de escrita em `const`, structs recursivas/incompletas, duplicatas de campos/`case`/`default`/símbolos globais e proteção contra recursão profunda.
- **IR SSA tipada, otimizador e verificador estrutural**: operações inteiras com largura 32/64 bits, truncamento de retornos estreitos (`bool`/`char`/`short`/`int`) na fronteira ABI, conversões `uint64_t <-> double`, `float` 32-bit vs `double` 64-bit, structs por valor (`<=8B` em `rax`, `9..16B` em `rax:rdx`, `>16B` via `sret` oculto), `.rela.data` para ponteiros globais, respeito a `volatile` e verificação de invariantes SSA antes do backend.
- **Backend x86-64, ELF64 `.o`, Self-Hosting e Linker nativo com suporte a `.a`**: comparações IEEE-754 compatíveis com `NaN`, emissão de `.o` via `cgd:bytes.Bytes` capaz de auto-compilar `build/dcc.c` (53 mil linhas, 1.074 funções → `build/dcc-self`), objetos relocáveis `ET_REL` interoperáveis bidirecionalmente com GCC e Clang, símbolos `STB_WEAK` e `STT_TLS` (`R_X86_64_GOTTPOFF`), leitura endurecida de `.o` e archives estáticos GNU `ar` (`.a`, `-L`, `-l`), resolução iterativa de archives, `SHN_COMMON`, `argc`/`argv` em `_start`, segmentos `PT_LOAD` separados (`R E` e `R W`) e vínculo dinâmico a `libc.so.6` / `libm.so.6`.
- **Diagnósticos estruturados**: códigos estáveis (`E1xxx`–`E9xxx`, `W1xxx`–`W2xxx`), arquivo/linha/coluna, pilha de inclusão (`In file included from ...`), sublinhado de trecho (`^~~~`), cores ANSI automáticas (`-fdiagnostics-color=auto|always|never` + `NO_COLOR`), saída JSON (`-fdiagnostics-format=json`), `-Wall`, `-Wextra`, `-Werror`, `-Wno-<categoria>` e `-ftime-report`.

---

## Requisitos de Build e Execução

- **CGD** ≥ `0.9.0` disponível no `PATH` (ou via `CGD=/caminho/para/cgd`) e sua biblioteca padrão em `~/.delegua/cgd` (detalhes em [docs/CGD_STDLIB.md](docs/CGD_STDLIB.md)).
- Linux x86-64 com cabeçalhos de desenvolvimento da `glibc` (`/usr/include`), `coreutils` (`base64`) e `findutils` (`find`).
- Para executar as suítes de verificação (`tests/`): Python 3, `gcc`, `clang`, `binutils` (`readelf`, `ar`) e `ldd`.

## Build e Verificação

```sh
./bootstrap/build.sh
make check-format
./bootstrap/verify.sh
```

Para executar também as suítes de segurança/fuzzing e estresse/benchmark:

```sh
make test-security
make test-stress
# ou tudo de uma vez:
make test-all
```

Instalação e empacotamento:

```sh
make install PREFIX="$HOME/.local"
make dist
```

## Exemplos de Uso

```sh
# Compilar e linkar diretamente para executável ELF64
./build/dcc examples/hello_libc.c -o hello
./hello

# Compilar com otimização, libm e relatório de tempo por fase
./build/dcc -O2 -ftime-report prog.c -lm -o prog

# Compilação separada (.o) + arquivo estático (.a) + linkagem nativa
./build/dcc -c mod_a.c -o mod_a.o
./build/dcc -c mod_b.c -o mod_b.o
ar rcs libmod.a mod_b.o
./build/dcc mod_a.o -L. -lmod -o programa

# Interoperabilidade bidirecional com GCC/Clang
gcc -std=c99 -c helper.c -o helper.o
./build/dcc -c main.c -o main.o
./build/dcc main.o helper.o -o programa

# Emissão de Assembly x86-64 (-S) e pré-processamento (-E)
./build/dcc -S prog.c -o prog.s
./build/dcc -E -DFOO=42 prog.c

# Diagnósticos em JSON e controle de cores/avisos
./build/dcc -fdiagnostics-format=json prog.c -o prog
./build/dcc -fdiagnostics-color=never -Wno-cpp prog.c -o prog
```

## Estrutura do Projeto

```text
dcc/
├── bootstrap/                 # Scripts de build e verificação independente
├── src/
│   ├── main.delegua           # Ponto de entrada do executável dcc
│   ├── driver/                # Driver CLI, I/O, flags, -ftime-report e resolução -L/-l
│   ├── diagnostics/           # Códigos estáveis, cores ANSI, JSON, include stack e MapaFonte
│   ├── types/                 # Enums, sistema de tipos LP64, qualificadores e IEEE-754 puro
│   ├── preprocessor/          # preproc.delegua, pp_macros.delegua, pp_expr.delegua
│   ├── lexer/                 # lexer.delegua e literais.delegua (escapes/números/ClassificadorChar)
│   ├── parser/                # Parser C99/GNU99 com Precedence Climbing e escopo de typedef
│   ├── semantic/              # Análise semântica, layout LP64, bit-fields e verificações de tipo
│   ├── ir/                    # ir_tipos, ir_builder, ir_opt, ir_verify, ir_ssa
│   ├── backend/x86_64/        # emissor.delegua, codegen.delegua, asm.delegua
│   ├── object/elf/            # elf_comum.delegua (constantes/helpers) e elf_obj.delegua
│   └── linker/                # elf_leitor.delegua (.o/.a endurecido) e linker.delegua
├── examples/                  # Exemplos C reais
├── tests/                     # run_tests.py, test_security_fuzz.py, test_stress.py
└── docs/                      # Documentação técnica, auditoria, conformidade e transparência IA
```

## Documentação

- [Transparência sobre desenvolvimento por IA](docs/AI_DEVELOPMENT.md)
- [Política de segurança e modelo de ameaça](SECURITY.md)
- [Relatório de auditoria técnica (Ciclo III)](docs/AUDIT_REPORT.md)
- [Arquitetura interna](docs/ARCHITECTURE.md)
- [Matriz de conformidade ISO C99](docs/C99_CONFORMANCE.md)
- [Camada de compatibilidade GNU](docs/GNU_COMPATIBILITY.md)
- [ABI System V AMD64 no DCC](docs/ABI.md)
- [Formato ELF64 e Linker nativo](docs/LINKER.md)
- [Sistema de diagnósticos](docs/DIAGNOSTICS.md)
- [Uso da biblioteca padrão CGD](docs/CGD_STDLIB.md)
- [Estratégia de testes e benchmarks](docs/TESTING.md)
- [Registro de continuidade](docs/CONTINUITY.md)
- [Como contribuir](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Licença e Atribuição

Distribuído sob a licença **Apache-2.0** (ver [LICENSE](LICENSE)).
O DCC originou-se do compilador C nativo desenvolvido no projeto **CGD — Compilador Geral Delégua**, utilizando a linguagem Delégua inspirada no projeto [Design Líquido / Delégua](https://github.com/DesignLiquido/delegua).
