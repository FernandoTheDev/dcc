# Relatório de Performance do DCC — Ciclo IV

**Data:** 21/11/2026  
**Versão:** DCC `0.2.0` + CGD `0.9.0` (Ciclo III)  
**Hardware:** Intel Core i5-11300H (8 threads), 15 GiB RAM, Linux `7.2.5-200.fc44.x86_64`  
**Toolchains C:** GCC `16.2.1`, Clang `22.1.8`, TinyCC `0.9.28rc`  
**Script reproduzível:** [`scripts/bench_ciclo4.py`](file:///home/fernandodev/dcc/scripts/bench_ciclo4.py)  
**Dados brutos:** [`build/audit_ciclo4/bench_results.json`](file:///home/fernandodev/dcc/build/audit_ciclo4/bench_results.json) e [`build/audit_ciclo4/bench_summary.csv`](file:///home/fernandodev/dcc/build/audit_ciclo4/bench_summary.csv)

---

## 1. Metodologia (Separação Estrita Modo A vs. Modo B)

Para evitar comparações inválidas entre mudanças no compilador e variações no próprio arquivo de entrada:
- **Modo A (Entrada Congelada)**: compila o snapshot imutável [`build/audit_ciclo4/frozen_dcc.c`](file:///home/fernandodev/dcc/build/audit_ciclo4/frozen_dcc.c) (`5.051.288 B`, `42.137` linhas, `sha256: 5044bfd642e9fdb2e2c7fa0dd11a93ae2c8bec4d4967659d0383c4e15eaa726a`), idêntico ao usado no histórico [`build/bench-backends-20261121-154854/dcc-input.c`](file:///home/fernandodev/dcc/build/bench-backends-20261121-154854/dcc-input.c).
  - Nota transparente: `frozen_dcc.c` inclui `~/.local/share/cgd/vendor/delegua-runtime/src/delegua_rt.h`; as adições de protótipos IC/`Bytes` no Ciclo III elevaram os tokens pré-processados de `865.315` para `865.329` (+0,0016%).
- **Modo B (Pipeline Completo Atual)**: compila o `dcc.c` gerado atualmente pelo CGD Ciclo III (`5.255.575 B`, `42.915` linhas, `955.348` tokens, `894` funções).
- **Regra de execução**: todas as compilações pesadas foram executadas **sequencialmente** (nunca em paralelo), 3 repetições por configuração, registrando `min / mediana / max`, pico RSS (`/usr/bin/time -f`), tempos internos `-ftime-report` e `sha256` do `.o` emitido.
- **Diferença `-O0` vs `-O2`**: o script histórico `bench.sh` construía o DCC com `cgd` sem `-o` (`-O0` no compilador C), enquanto `bootstrap/build.sh` usa `cgd -o` (`-O2` no Clang). Ambos os modos são reportados separadamente abaixo.

---

## 2. Modo A (Entrada Congelada `frozen_dcc.c`) — Antes vs. Depois

### 2.1. Perfil de Produção (`cgd -o` — Clang `-O2`, padrão do `bootstrap/build.sh`)

| Métrica | Baseline Ciclo III (`task-41`) | Ciclo IV Mediana (min / max) | Melhoria |
| --- | ---: | ---: | ---: |
| **Tempo total (wall)** | `29,94 s` | **`8,56 s`** (`8,54 s / 9,05 s`) | **3,50× mais rápido** |
| **Pico RSS** | `6.715.172 KB` (6,40 GiB) | **`955.216 KB` (0,91 GiB)** (`954.720 / 972.968 KB`) | **7,03× menor (-85,8%)** |
| **Preprocess** | `2.215 ms` | **`1.019 ms`** (`1.000 / 1.029 ms`) | **2,17×** |
| **Lex** | `3.745 ms` | **`1.344 ms`** (`1.335 / 1.346 ms`) | **2,79×** |
| **Parse** | `7.911 ms` | **`1.678 ms`** (`1.661 / 1.701 ms`) | **4,71×** |
| **Sema** | `1.997 ms` | **`557 ms`** (`551 / 557 ms`) | **3,59×** |
| **IR** | `6.670 ms` | **`1.326 ms`** (`1.306 / 1.330 ms`) | **5,03×** |
| **Opt + Verify** | `2.430 ms` | **`941 ms`** (`939 / 985 ms`) | **2,58×** |
| **Codegen x86-64** | `4.170 ms` | **`1.504 ms`** (`1.489 / 1.525 ms`) | **2,77×** |
| **ELF64 Obj** | `311 ms` | **`53 ms`** (`52 / 79 ms`) | **5,87×** |
| **Tamanho `.o`** | `20.950.672 B` | **`20.190.680 B`** | **-760 KB (-3,6%)** |

### 2.2. Matriz de Backends C (`-O0`, equivalente ao `bench.sh` histórico `20261121-154854`)

| Backend C (Build DCC) | Build Antes → Depois | Auto-compilação Antes | Auto-compilação Depois (min / med / max) | Speedup | Pico RSS Antes → Depois (mediana) | Redução RSS |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| **GCC 16 (`-O0`)** | `6,38 s → 6,82 s` | `36,33 s` | **`12,86 s`** (`12,68 / 12,86 / 13,29`) | **2,83×** | `7.118.316 KB` (6,79 GiB) → **`1.176.720 KB` (1,12 GiB)** | **6,05× (-83,5%)** |
| **Clang 22 (`-O0`)** | `2,28 s → 2,32 s` | `34,81 s` | **`13,15 s`** (`13,06 / 13,15 / 13,72`) | **2,65×** | `6.569.316 KB` (6,26 GiB) → **`931.564 KB` (0,89 GiB)** | **7,05× (-85,8%)** |
| **TinyCC (`-O0`)** | `1,03 s → 1,03 s` | `43,76 s` | **`23,26 s`** (`22,95 / 23,26 / 23,93`) | **1,88×** | `6.376.212 KB` (6,08 GiB) → **`955.824 KB` (0,91 GiB)** | **6,67× (-85,0%)** |
| **Clang 22 (`-O2`)** | `15,61 s → 16,99 s` | `29,94 s` | **`8,56 s`** (`8,54 / 8,56 / 9,05`) | **3,50×** | `6.715.172 KB` (6,40 GiB) → **`955.216 KB` (0,91 GiB)** | **7,03× (-85,8%)** |
| *Referência `tcc -c`* | *—* | *`0,07 s`* | *`0,07 s` (`0,07 / 0,07 / 0,07`)* | *Ref.* | *`21.048 KB` → `21.488 KB` (`.o`: `8,75 MB`)* | *Ref. C puro* |

**Determinismo Bit-a-Bit**: todas as 12 execuções acima (GCC `-O0`, Clang `-O0`, TinyCC `-O0`, Clang `-O2`) produziram o **exato mesmo arquivo objeto ELF64** (`20.190.680 B`, `sha256: 6144e0665d578e7da0d78b6db63f236150f777d1941ab5548f5d0a6647e5f9ba`).

---

## 3. Modo B (Pipeline Completo Atual — `build/dcc.c` Ciclo IV)

No Modo B, o CGD 0.9.0 (Ciclo III) gera `current_dcc.c` (`42.915` linhas, `5.255.575 B`, `955.348` tokens, `499.959` nós AST, `880.583` instruções SSA, `894` funções) em **`1,00 s`** (RSS `198.820 KB`), e `dcc` (`clang -O2`) auto-compila esse arquivo:

| Métrica (Modo B, 3 reps) | Mínimo | Mediana | Máximo |
| --- | ---: | ---: | ---: |
| **Tempo total (wall)** | `9,48 s` | **`9,53 s`** | `10,61 s` |
| **Pico RSS** | `1.036.824 KB` (0,99 GiB) | **`1.038.188 KB` (0,99 GiB)** | `1.071.984 KB` (1,02 GiB) |
| **Objeto ELF64 emitido** | `22.130.856 B` | `22.130.856 B` | `22.130.856 B` |
| **SHA-256 consistente** | `sim` (`17952d8f62234cac...`) | `sim` | `sim` |

Breakdown das fases na mediana do Modo B (`total=9.341 ms`): `preprocess=1.086 ms`, `lex=1.503 ms`, `parse=1.856 ms`, `sema=618 ms`, `ir=1.492 ms`, `opt+verify=1.081 ms`, `codegen=1.643 ms`, `elf_obj=58 ms`.

---

## 4. Benchmarks de Carga Cotidiana e Stress

| Carga | Antes (v0.1.0 / v0.2.0 Ciclo III) | Depois (Ciclo IV) | Ganho |
| --- | ---: | ---: | ---: |
| `examples/hello_libc.c` via `build/dcc` (`clang -O2`, 5 reps) | `266,7 ms` (era `682 ms` v0.1) | **`168,5 ms`** | **1,58×** (4,05× vs v0.1) |
| `examples/hello_libc.c` via `build/dcc` (`gcc -O2`, 5 reps) | `290,7 ms` | **`168,1 ms`** | **1,73×** |
| `examples/hello_libc.c` via `build/dcc-self` (auto-compilado!) | `322 ms` | **`237–290 ms`** | **1,11–1,36×** |
| `tests/test_stress.py`: 24 compilações paralelas (4×) | `2,61 s` (era `8,76 s`) | **`1,35 s`** | **1,93×** (6,49× vs v0.1) |
| `tests/test_stress.py`: benchmark `-O2` (`-ftime-report`) | `872 ms` (era `3.005 ms`) | **`250 ms`** | **3,49×** (12,0× vs v0.1) |

---

## 5. Comparação Honesta com `tcc` (Gap Remanescente)

Mesmo após **3,50×** de speedup e **7,03×** de redução de RSS, o DCC (`8,56 s`, `933 MiB`) ainda está a ~120× de tempo e ~43× de RSS em relação ao TinyCC (`0,07 s`, `21 MiB`). Isso decorre de fatores estruturais bem entendidos:
1. O DCC é um compilador multi-passo completo (Pré-processador → Lexer → AST → Sema → IR SSA → Otimizador/Verificador → Codegen → ELF64) mantendo todas as representações intermediárias em memória, enquanto o TCC faz compilação *single-pass* direta de tokens para código de máquina.
2. O DCC roda sobre valores dinâmicos boxed (`delegua_value` de 24 B) + Boehm GC, onde cada nó de AST/IR ocupa ~224–464 B contra ~32–64 B em C puro com arenas.
3. Os ganhos mais promissores para o próximo salto são: compilação *streaming* função-a-função (baixando AST → IR → x86-64 por função, descartando AST/IR imediatamente) e vetores primitivos *unboxed* no CGD.
