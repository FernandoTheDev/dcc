# ABI System V AMD64 no DCC

Este documento descreve exatamente o que está implementado, verificado e o que ainda é pendente na implementação da **System V AMD64 ABI** (Linux x86-64 LP64) no DCC v0.2.0.

---

## 1. Modelo de Dados (LP64)

| Tipo C | Tamanho (bytes) | Alinhamento (bytes) | Implementação no DCC |
| :--- | :---: | :---: | :--- |
| `_Bool` / `bool` | 1 | 1 | Normalizado para `0`/`1` via `OpIR.ToBool` |
| `char` / `signed char` / `unsigned char` | 1 | 1 | `char` com sinal; `TruncSext`/`TruncZext` 1B |
| `short` / `unsigned short` | 2 | 2 | `TruncSext`/`TruncZext` 2B |
| `int` / `unsigned int` | 4 | 4 | Operações 32-bit reais (`eax`/`ecx`) com wraparound C99 |
| `long` / `unsigned long` / `long long` | 8 | 8 | Operações 64-bit (`rax`/`rcx`) |
| Ponteiros (`T *`, funções) | 8 | 8 | Endereçamento RIP-relative / GOT |
| `float` (`_Float32`) | 4 | 4 | Conversão `cvtsd2ss`/`cvtss2sd` na borda ABI e memória |
| `double` (`_Float64`) | 8 | 8 | `movsd` em registradores `xmm0`–`xmm7` |
| `long double` | 8 *(limitação)* | 8 | Mapeado para `double` 64-bit (x87 80-bit não implementado) |

Alinhamento de `struct` segue padding natural LP64, suportando `__attribute__((packed))` (alinhamento 1) e `__attribute__((aligned(N)))` (com validação de potência de 2), além de bit-fields C99 em unidades de armazenamento inteiras.

---

## 2. Convenção de Chamada (Registradores e Pilha)

### Argumentos escalares

- **Inteiros e ponteiros**: primeiros 6 em `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`; excedentes na pilha em ordem reversa, com alinhamento de 16 bytes em `rsp` antes de `call`.
- **Ponto flutuante**: primeiros 8 em `xmm0`–`xmm7`; excedentes na pilha.
  - `float` (32 bits) é convertido para *single precision* (`cvtsd2ss`) ao passar para parâmetro `float` e reconvertido (`cvtss2sd`) no callee e no retorno `float`.
  - Em posições variádicas (`...`), aplica-se a promoção padrão ISO C99 (`float` → `double`).
- **Funções variádicas**: `al` recebe o número de registradores `xmm` usados (0–8) antes de `call`; o prólogo de função variádica salva `rdi..r9` e `xmm0..xmm7` na *register save area* compatível com `va_list` de 24 bytes da `glibc` (`gp_offset`, `fp_offset`, `overflow_arg_area`, `reg_save_area`).

### Structs por valor

Classificação por tamanho (`classificarStructModo` em `src/ir/ir_builder.delegua`):

| Tamanho da `struct` | Passagem de argumento | Retorno de função |
| :--- | :--- | :--- |
| `1..8` bytes | 1 registrador GP (`rdi..r9`) se disponível, senão pilha | `rax` |
| `9..16` bytes | 2 registradores GP consecutivos se houver 2 disponíveis, senão pilha | `rax` + `rdx` (`OpIR.RetPair`) |
| `> 16` bytes | Cópia direta na pilha (múltiplos de 8 bytes) | Ponteiro oculto `sret` em `rdi` (deslocando o primeiro argumento inteiro explícito para `rsi`); retorna o ponteiro em `rax` |

### Retornos escalares e truncamento

- Retornos inteiros estreitos (`char`, `short`, `int`, `_Bool`) aplicam conversão explícita para `fn.tipoRet` antes de `Ret`.
- Retornos `float` retornam em `xmm0` no formato `binary32` (`cvtsd2ss`); `double` retorna em `xmm0` no formato `binary64`.

### Inicialização de processo (`_start`)

O stub `_start` emitido pelo linker nativo lê `argc` em `[rsp]` para `rdi` e `argv` em `[rsp+8]` para `rsi` antes de chamar `main(argc, argv)`, encaminhando o retorno de `main` para `exit`.

---

## 3. Validação Bidirecional Executada

Em `tests/run_tests.py` (`rodar_testes_abi_bidirecional`), o mesmo conjunto de funções (`abi_f32`, `abi_f64`, `abi_s8`, `abi_s16`, `abi_s32`, `abi_cb` com ponteiro de função e `abi_var` variádica) é compilado separadamente e linkado nas **4 direções**:

1. `DCC` chama objeto compilado por `GCC` (linkado pelo DCC) — **APROVADO**;
2. `GCC` chama objeto compilado por `DCC` (linkado pelo GCC) — **APROVADO**;
3. `DCC` chama objeto compilado por `Clang` (linkado pelo DCC) — **APROVADO**;
4. `Clang` chama objeto compilado por `DCC` (linkado pelo Clang) — **APROVADO**.

---

## 4. Limitações ABI Conhecidas

1. **Classificação de `eightbytes` SSE em structs**: structs de até 16 bytes contendo exclusivamente campos `float`/`double` (ex.: `struct Vec2 { double x, y; }`) ainda são classificadas como `INTEGER` (GP `rdi`/`rsi`/`rax`/`rdx`) em vez de `SSE` (`xmm0`/`xmm1`). Para interoperabilidade binária com GCC/Clang, structs puras de ponto flutuante ≤ 16B ainda não são compatíveis por valor (use ponteiro ou `> 16B`).
2. **`long double` x87 (80 bits)**: tratado como `double` (64 bits); não interoperável por valor com funções que esperam `long double` 80-bit em `st(0)`/pilha de 16 bytes.
3. **`_Complex`**: não implementado.
4. **Alocação de registradores**: todos os registradores virtuais SSA são atualmente alocados em slots de pilha (`rbp - offset`); não há `callee-saved` allocation (`rbx`, `r12`–`r15`), o que garante preservação trivial mas gera mais tráfego de memória.
