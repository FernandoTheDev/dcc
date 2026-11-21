# Estratégia de Testes, Segurança e Benchmarks — DCC

O DCC valida sua corretude, conformidade ABI, resistência a entradas hostis e desempenho por meio de **três suítes independentes e reproduzíveis**.

---

## 1. Suíte Principal: Diferencial, ABI Bidirecional, Linker e Diagnósticos (`tests/run_tests.py`)

Executada por `./bootstrap/verify.sh` ou `make test`. Total atual: **82 verificações automatizadas**.

1. **Testes diferenciais contra GCC e Clang (17 programas × 3 níveis `-O0`, `-O1`, `-O2` = 51 execuções)**:
   - Consome cabeçalhos reais de `/usr/include` (`stdio.h`, `stdlib.h`, `string.h`, `stdint.h`, `stdbool.h`, `limits.h`, `iso646.h`, `float.h`, `ctype.h`, `assert.h`, `errno.h`, `signal.h`, `math.h`, `time.h`, `stdarg.h`, `stddef.h`);
   - Valida IEEE-754 (`NaN`, `Inf`, `float` 32-bit, `sqrtf`, literais hex-float `0x1.fp+3`, `uint64_t <-> double`), aritmética 32-bit com wraparound `unsigned`, truncamento de retorno (`signed char`, `bool`), escapes C99 exatos (`\0`, octal, `\xNN`), `sizeof("str")`, aritmética comutativa (`2[arr]`, `1 + arr`, `p += n`), structs `9..16B` (`rax:rdx`) e `>16B` (`sret`), `offsetof` aninhado, `.rela.data` para ponteiros globais, shadowing de enumeradores e `typedef`, inicialização e atribuição composta de bit-fields, `argc`/`argv`, `switch`/`goto` e `sizeof((int)5)`.
   - Exige `stdout` e código de saída **exatamente idênticos** aos de `gcc` e `clang`.
2. **Interoperabilidade ABI Bidirecional (4 direções)**:
   - `DCC → GCC`, `GCC → DCC`, `DCC → Clang`, `Clang → DCC` cobrindo `float`, `double`, `struct S8`, `struct S16`, `struct S32` (`sret`), callbacks por ponteiro de função e `va_list` variádica.
3. **Linker Nativo, Archives `.a`, Símbolos Weak e Auditoria ELF64 (9 verificações)**:
   - Linkagem `DCC+DCC`, `GCC` sobre `DCC .o`, `DCC` com `GCC .o`, `DCC` com `Clang .o`;
   - Archives estáticos GNU `ar`: `libcalc.a` direto e via `-L <dir> -lcalc`;
   - Sobrescrita de símbolo `__attribute__((weak))` por definição forte;
   - Rejeição explícita de símbolo global duplicado (`E5010`);
   - Auditoria ELF64 via `readelf -h`, `readelf -W -l` (ausência de `RWE`), `readelf -W -S` (`.shstrtab`) e `ldd` (`libc.so.6`).
4. **Diagnósticos, Negativos, JSON, Cores e CLI (18 verificações)**:
   - Erros semânticos/sintáticos/GNU Cat C (`E2100`, `E2101`, `E2102`, `E3002`, `E3005`, `E3006`, `E3010`, `E1020`, `E9001`), `-Werror`, pilha de inclusão `In file included from ...`, saída `-fdiagnostics-format=json` validada por `json.loads`, cores ANSI (`\x1b[`), `-Wno-cpp` com `stdout` limpo, emissão `-S`, `-ftime-report` e execução independente de diretório atual (`cwd=/tmp`).

---

## 2. Suíte de Segurança e Fuzzing (`tests/test_security_fuzz.py`)

Executada por `make test-security`. Verifica que entradas hostis resultam em erro controlado (sem crash/segfault/SIGABRT e sem loop infinito dentro de timeouts curtos):

- **12 testes adversariais do pré-processador**: bomba exponencial de macros (`E1011`), recursão mútua com *hide-set*, `#include` cíclico (`E1002`), `#if` aninhado 300× (`E1003`), expressão `#if` profunda (`E1005`), divisão por zero (`E1006`), `INT64_MIN / -1`, `#if` vazio (`E1004`), tokens residuais em `#if` (`E1007`), `##` no início/fim (`E1014`), comentário `/*` não fechado (`E1001`).
- **50 testes de fuzzing determinístico e aleatório para lexer/parser**: parênteses/chaves profundamente aninhados (`E2010`), strings/chars não terminados, bytes arbitrários, declarações truncadas e gramática sintética malformada.
- **15 arquivos binários ELF64 e `.a` corrompidos/hostis**: arquivo vazio, truncado, magic inválido, 32-bit, big-endian, `ET_EXEC` passado como `.o`, `e_shoff`/`e_shstrndx`/`sh_offset` fora dos limites, `sh_addralign` bomba (`1<<40`), índice de símbolo de relocação fora da faixa e archives `ar` truncados/corrompidos.

---

## 3. Suíte de Estresse, Concorrência e Benchmarks (`tests/test_stress.py`)

Executada por `make test-stress`:

- **Projeto multi-arquivo + archive `.a`** (5 arquivos: `math_ops.c`, `vec_ops.c`, `str_ops.c` em `libutil.a` + `main.c`) compilado e linkado nos 3 níveis `-O0`, `-O1`, `-O2` com resultado validado;
- **Estresse de concorrência**: 24 compilações paralelas em 4 workers simultâneos (verificando ausência de arquivos temporários compartilhados ou *race conditions*);
- **Benchmark instrumentado (`-ftime-report`)**: compila programa real com `<stdio.h>`, `<stdlib.h>`, `<string.h>` e `<math.h>` em `-O2`.

### Medições Reais (Linux x86-64, CGD v0.9.0, DCC v0.2.0)

| Métrica | Antes das Otimizações (Ciclo III inicial) | Depois (`ClassificadorChar` + `fatiar` + cache/MI-OPT) | Ganho |
| :--- | :---: | :---: | :---: |
| 24 compilações paralelas (4 workers) | `8.76 s` | `6.62–6.76 s` | **~23% mais rápido** |
| Benchmark total (`stdio+stdlib+string+math`, `-O2`) | `3005 ms` | `2552–2897 ms` | **~15% mais rápido** |
| Decomposição de fases (última medição) | `pp=2430ms lex=215ms parse=270ms sema=20ms ir=3ms opt+verify=2ms codegen=1ms elf=10ms link=51ms` | `pp=1955–2256ms lex=203–237ms parse=287–309ms sema=20–21ms ir=2–3ms opt+verify=2ms codegen=1ms elf=10–12ms link=54–66ms` | Gargalo claramente concentrado no pré-processamento dos headers reais da `glibc` |

---

## 4. Comandos Rápidos

```sh
make check-format    # Valida formatação Delégua em src/
make test            # 82 verificações (diferencial + ABI + linker + diagnósticos)
make test-security   # Pré-processador adversarial + 50 fuzz + 15 ELF/.a hostis
make test-stress     # Multi-arquivo + 24 paralelas + benchmark -ftime-report
make test-all        # Executa todas as 3 suítes
```
