# Relatório de Performance e Memória — DCC 0.2.0 (Ciclo V)

Data: 21/11/2026  
Script reproduzível: `scripts/bench_paralelismo.py 3` (execução estritamente sequencial, 3 repetições nos cenários principais, dados brutos em `build/audit_ciclo5/bench_paralelismo.json`).

> **Transparência metodológica**: este relatório separa estritamente os ganhos **sequenciais (`-j1`)** (streaming por função, `cgd:memoria.Arena`, despacho $O(1)$ em `ir_opt`/`ir_verify`, liberação progressiva de tokens, linker em `Bytes` e IC de classes fechadas no CGD) dos ganhos de **paralelismo real (`-j2/-j4/-j8/-j auto`)** em Multi-TU e Linker.

---

## 1. Modo A — Entrada Congelada `frozen_dcc.c` (5,05 MiB, mesmos headers `~/.local/share/cgd`)

Saída validada em todos os compiladores e modos `-j`: **`18.951.128 bytes`**, `sha256 = 9b3c0d377d05a831e309977ef4287f595bad4ee07bf238dc4f345da8d44a1d39` (100% bit a bit idêntica entre Ciclo IV e Ciclo V).

*(Nota: o SHA-256 e tamanho diferem da referência histórica do Ciclo IV `20.190.680 B` porque `frozen_dcc.c` faz `#include "vendor/delegua-runtime/src/delegua_rt.h"` do runtime CGD Ciclo IV atualizado; ambos os binários Ciclo IV e Ciclo V foram medidos sob os **exatos mesmos headers** para comparação justa.)*

### 1.1. Comparação Direta Ciclo IV vs Ciclo V (`clang -O2`, `-j1`, mediana de 3 execuções)

| Métrica / Fase | Ciclo IV (`dcc-clang-O2`) | Ciclo V (`dcc-c5-clang_O2 -j1`) | Variação |
|---|---:|---:|---:|
| **Tempo parede (mediana)** | `12,11 s` (`12,06–12,30 s`) | **`8,66 s`** (`8,64–8,66 s`) | **`-28,5%` (`1,40×` mais rápido)** |
| **Pico RSS (mediana)** | `995.100 KB` (`971,8 MiB`) | **`572.960 KB`** (**`559,5 MiB`**) | **`-42,4%` (`-422 MB` / `-412 MiB`!)** |
| `preprocess` | `1.714 ms` | `1.555 ms` | `-9,3%` |
| `lex` | `1.456 ms` | **`1.132 ms`** | `-22,3%` |
| `parse` | `1.807 ms` | `1.882 ms` | `+4,2%` *(inclui 4 coletas mid-parse)* |
| `sema` | `572 ms` | `616 ms` | `+7,7%` *(streaming)* |
| `ir` | `1.316 ms` | `1.278 ms` | `-2,9%` |
| **`opt+verify`** | `3.611 ms` | **`838 ms`** | **`-76,8%` (`4,31×` mais rápido!)** |
| **`codegen`** | `1.420 ms` | **`928 ms`** | **`-34,6%` (`1,53×` mais rápido!)** |
| `elf_obj` | `52 ms` | `56 ms` | estável |

### 1.2. Portabilidade de Compiladores C (Modo A, `-j1`)

| Compilador Gerador | Build do DCC | Tempo Modo A | Pico RSS | SHA-256 `.o` |
|---|---:|---:|---:|---|
| `clang -O2` | `24,56 s` | **`8,66 s`** | **`572.960 KB`** | `9b3c0d377d05...` (MATCH) |
| `gcc -O0` | `8,29 s` | `13,33 s` | `843.348 KB` | `9b3c0d377d05...` (MATCH) |
| `clang -O0` | `3,11 s` | `13,87 s` | `575.564 KB` | `9b3c0d377d05...` (MATCH) |
| `tcc -O0` (TinyCC 0.9.28rc) | **`1,36 s`** | `24,45 s` | **`572.424 KB`** | `9b3c0d377d05...` (MATCH) |

### 1.3. Perfil de Memória Fase a Fase (`-fmem-report` em `frozen_dcc.c`)

| Marco | RSS | HWM (Pico) | Heap GC | Livre GC | Desmapeado |
|---|---:|---:|---:|---:|---:|
| `PREPROCESS_END` | `58 MiB` | `341 MiB` | `72 MiB` | `35 MiB` | `256 MiB` |
| `LEX_END` (`961.753` tokens) | `415 MiB` | `415 MiB` | `376 MiB` | `0 MiB` | `0 MiB` |
| `PARSE_END` (`461.703` nós AST) | `556 MiB` | `556 MiB` | `505 MiB` | `62 MiB` | `5 MiB` |
| `SEMA/IR/OPT/CODEGEN_END` | **`474 MiB`** | **`559 MiB`** | `424 MiB` | `188 MiB` | `118 MiB` |
| `ELF_END` (`18,95 MiB` `.o`) | **`477 MiB`** | **`559 MiB`** | `435 MiB` | `347 MiB` | `108 MiB` |

O pipeline streaming manteve o incremento de pico RSS entre `PARSE_END` e `ELF_END` em apenas **`+3 MiB`** (`556 → 559 MiB`), eliminando totalmente o pico secundário de IR+Codegen (`+100 MiB` no Ciclo IV).

### 1.4. Varredura `-j` em Single-TU (`frozen_dcc.c`, `clang -O2`)

| Modo | Tempo | Pico RSS | SHA-256 |
|---|---:|---:|---|
| `-j 1` | `8,76 s` | `570.248 KB` | `9b3c0d377d05...` (MATCH) |
| `-j 2` | `8,78 s` | `574.620 KB` | `9b3c0d377d05...` (MATCH) |
| `-j 4` | `8,78 s` | `572.700 KB` | `9b3c0d377d05...` (MATCH) |
| `-j 8` | `9,72 s` | `569.932 KB` | `9b3c0d377d05...` (MATCH) |
| `-j auto` | `8,96 s` | `572.860 KB` | `9b3c0d377d05...` (MATCH) |

---

## 2. Modo B — Pipeline Atual (Auto-Compilação Completa do DCC Ciclo V)

- Entrada gerada por `cgd -o --emitir-c src/main.delegua` (`1,31 s`): **`70.988 linhas`**, `6.895.147 bytes`, `1.320.946 tokens`, `676.577 nós AST`, `1.048 funções`.
- Auto-compilação com `dcc-c5-clang_O2 -j auto` (3 repetições):
  - Tempo mediano: **`12,83 s`** (`12,66–13,37 s`; `opt+verify=1.311 ms`, `codegen=1.365 ms`, `elf_obj=81 ms`).
  - Pico RSS mediano: **`849.800 KB` (`829,9 MiB`)** — **18,1% menor** que o Modo B do Ciclo IV (`1.038.188 KB`) apesar de a entrada C ser **+65,4% maior em linhas** (`42.915 → 70.988`) e **+38,3% maior em tokens** (`955k → 1.321k`)!
  - Bootstrap indireto completo verificado: `build/dcc-self.o` (`25.292.392 B`) → `build/dcc-self` (`22.970.480 B`) → compilou e executou `examples/hello_libc.c` imprimindo **`DCC`**.

---

## 3. Paralelismo Multi-TU Real (17 Arquivos `.c` → Executável ELF64, 3 repetições)

Cada um dos 16 módulos inclui `<stdio.h>` e `<stdint.h>` reais da glibc + 26 funções C99 (~420 funções + `main.c`), compilados e linkados pelo DCC em um único comando:

| Modo | Tempo Mediano | Min / Max | Speedup vs `-j1` | Pico RSS (driver) | SHA-256 Executável |
|---|---:|---:|---:|---:|---|
| `-j 1` (sequencial) | `1,96 s` | `1,93 / 2,38 s` | `1,00×` | `172.616 KB` | `b3cbb0ec9156...` |
| `-j 2` | `1,64 s` | `1,63 / 1,67 s` | `1,20×` | `171.088 KB` | `b3cbb0ec9156...` (MATCH) |
| **`-j 4`** | **`1,06 s`** | `1,01 / 1,12 s` | **`1,85×`** | `171.424 KB` | `b3cbb0ec9156...` (MATCH) |
| **`-j 8`** | **`0,83 s`** | `0,81 / 0,83 s` | **`2,36×`** | `171.500 KB` | `b3cbb0ec9156...` (MATCH) |
| **`-j auto` (4 workers)** | **`1,09 s`** | `1,01 / 1,12 s` | **`1,80×`** | `171.664 KB` | `b3cbb0ec9156...` (MATCH) |
| `taskset -c 0,1 -j auto` | `2,32 s` | `2,19 / 2,69 s` | `1 worker` (política) | `171.900 KB` | `b3cbb0ec9156...` (MATCH) |

*(Nota: em `Multi-TU`, o `maxrss` reportado pelo `/usr/bin/time` reflete o maior processo individual da árvore; o ganho de parede de `1,96 s → 0,83 s` comprova paralelismo real sem contenção do Boehm GC entre TUs.)*

---

## 4. Granularidade Single-TU (Sem Regressão em Arquivos Pequenos)

| Cenário | `-j 1` | `-j auto` | Pico RSS | SHA-256 |
|---|---:|---:|---:|---|
| Arquivo pequeno (2 funções) | `0,05 s` | `0,05 s` | `31.480 KB` | MATCH |
| 400 funções pequenas | `0,17 s` | `0,18 s` | `46.020 KB` | MATCH |
| 4 funções grandes (~350 stmts cada) | `0,36 s` | `0,37 s` | `60.576 KB` | MATCH |
