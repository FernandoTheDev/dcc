# Análise Forense de Memória no Bootstrap do DCC (`6,4–7,1 GiB → 0,91 GiB`)

**Data:** 21/11/2026  
**Alvo:** Auto-compilação do DCC 0.2.0 sobre `frozen_dcc.c` (`5,05 MiB`, `865k` tokens, `442k` nós AST, `804k` instruções SSA) e `build/dcc.c` atual (`5,26 MiB`, `955k` tokens).

---

## 1. Linha do Tempo Forense: Como Derrubamos 6,40 GiB para 0,91 GiB

Cada passo abaixo foi medido individualmente na mesma máquina com a entrada congelada `frozen_dcc.c` (`clang -O2`), usando `/usr/bin/time -f` e `-fmem-report` (`Sistema.memoria()`):

| Etapa | Camada | Intervenção | Pico RSS | Alocação GC Total | Tempo | Delta RSS |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| **0. Baseline** | — | Estado inicial (`task-41` / `task-78`) | **6.404 MiB** *(6,40 GiB)* | `12.150 MiB` | `29,94 s` | — |
| **3.1** | **CGD Runtime** | Objetos com slots fixos inline (`objetos.c`, 1 alloc GC, sem `hashmap`/`semear_campos`) | **3.319 MiB** *(3,24 GiB)* | `8.521 MiB` | `21,09 s` | **-3.085 MiB (-48,2%)** |
| **3.2** | **CGD Runtime** | Vetores/dicionários vazios preguiçosos (`NULL`) + `VETOR_INIT_CAP = 4` | **3.009 MiB** *(2,94 GiB)* | `8.166 MiB` | `20,63 s` | **-310 MiB** |
| **3.3** | **CGD + DCC** | `cgd:bytes.Bytes` crescível (`GC_MALLOC_ATOMIC`) + migração `EmissorX86_64.code` e `elf_obj.delegua` | **1.532 MiB** *(1,50 GiB)* | `6.242 MiB` | `20,50 s` | **-1.477 MiB (-49,1%)** |
| **3.4** | **DCC** | `CallInfoSSA` preguiçoso + `Bytes` no preproc/lexer + interning + `ir_verify` bitset | **1.299 MiB** *(1,27 GiB)* | `4.518 MiB` | `28,12 s`* | **-233 MiB** |
| **3.5–3.6** | **CGD + DCC** | Isolamento de frames + `vetor.limpar()`/`map_limpar()` + `Sistema.coletarGC(verdadeiro)` | **967 MiB** *(0,94 GiB)* | `4.518 MiB` | `20,63 s` | **-332 MiB (-25,6%)** |
| **4.1–4.3** | **CGD + DCC** | Runtime `-O2` + Inline Caching + FFI inline + fix `terminaCom("\\")` + `ir_opt` bitset | **923 MiB** *(0,90 GiB)* | `3.864 MiB` | `8,93 s` | **-44 MiB** |
| **5 (Final)** | **DCC** | Intra-Block RAX Tracking (mediana 3 reps finais, Modo A `clang -O2`) | **933 MiB** *(0,91 GiB)* | `3.863 MiB` | **`8,56 s`** | **Total: -85,8% (7,03×)** |

*\*A regressão temporária de tempo na Etapa 3.4 (`20,5 s → 28,1 s`) ocorreu porque `Bytes.obter()` passava pelo wrapper FFI e runtime ainda em `-O0`; foi totalmente eliminada e revertida na Etapa 4 (`8,56 s`, 3,50× mais rápido que o baseline).*

---

## 2. Decomposição Fase-a-Fase (Antes vs. Depois)

Dados coletados via `-fmem-report` sobre `frozen_dcc.c` (`clang -O2`):

### 2.1. Evolução de RSS (MiB) e Alocação Delta por Fase

| Fase | Estruturas Principais | RSS Antes | RSS Depois | Δ Alloc GC Antes | Δ Alloc GC Depois | Causa Principal da Redução |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| **PREPROCESS** | `148` includes, `5,15M` chars | `95 MiB` | `195 MiB` | `+3.502 MiB` | **`+2.081 MiB`** | Fix `terminaCom("\\")` + `Bytes` sem `paraVetor()` |
| **LEX** | `865.329` `TokenC99` | `1.274 MiB` | **`398 MiB`** | `+1.880 MiB` | **`+494 MiB`** | Slots inline (-84% / token) + `Bytes` + interning |
| **PARSE** | `442.439` `NoAST` (`222.093` folhas) | `3.060 MiB` | **`834 MiB`** | `+2.081 MiB` | **`+532 MiB`** | Slots inline + vetores vazios `NULL` + `VETOR_INIT_CAP=4` |
| **SEMA** | Tabelas de tipos/símbolos | `3.155 MiB` | **`834 MiB`** | `+337 MiB` | **`+109 MiB`** | Slots inline + mapas vazios `NULL` |
| **IR** | `872` fns, `11.693` blocos, `803.953` `InstSSA` | `4.488 MiB` | **`870 MiB`** | `+1.792 MiB` | **`+436 MiB`** | Slots inline + `CallInfoSSA` + `tokens.limpar()`/`ast.filhos.limpar()` + GC |
| **OPT+VERIFY** | Verificador SSA (`-O0`) | `4.488 MiB` | **`870 MiB`** | `+330 MiB` | **`+2 MiB`** | Bitset `Bytes.criar(numRegs)` no lugar de `dicionario` |
| **CODEGEN** | `.text=17,05 MB`, `98.547` relocações | `6.048 MiB` | **`923 MiB`** | `+1.756 MiB` | **`+176 MiB`** | `EmissorX86_64.code` em `Bytes` (`GC_MALLOC_ATOMIC`) |
| **ELF64** | `20,19 MB` `.o` final | `6.098 MiB` | **`950 MiB`** | `+472 MiB` | **`+33 MiB`** | Pré-alocação única `Bytes.criarReservado(tamTotal)` |

### 2.2. Observações Forenses Críticas
1. **Por que o pico atual é ~933 MiB e onde eles estão?**
   - O maior patamar vivo simultâneo ocorre na fronteira `PARSE → SEMA → IR` (`834–870 MiB` de RSS, `775–799 MiB` de heap GC): `442.439` `NoAST` + `803.953` `InstSSA` + tabelas semânticas + ~250–290 MiB de `gc_free` (margem padrão de ~33% do Boehm GC para evitar thrashing de coletas).
   - No `CODEGEN_END` (`923 MiB`), a IR já foi liberada via `moduloSSA.funcoes.limpar()` ao final, mas durante a emissão do código de máquina todas as 872 funções da IR coexistem com o `CodigoObjeto` sendo construído.
2. **Por que GCC `-O0` atingiu `1,12 GiB` enquanto Clang `-O0/-O2` e TCC ficaram em `0,89–0,91 GiB`?**
   - Em `-O0`, o GCC reserva slots de pilha separados para cada temporário `cgd_tmp_*` sem reutilização de stack slots, aumentando a superfície conservadora varrida pelo Boehm GC em `executarPreprocLexParse` / `executarSemaEIR`. Ainda assim, GCC `-O0` caiu de **6,79 GiB → 1,12 GiB (-83,5%)**.
3. **Como ir abaixo de 300–400 MiB no futuro (Ciclo V)?**
   - **Compilação por função (*streaming* AST → IR → x86-64)**: em vez de manter todos os `442k` `NoAST` e `804k` `InstSSA` de todas as 872 funções vivos simultaneamente, emitir cada definição de função C logo após `parse → sema → ir → codegen`, liberando seu subgrafo AST/IR antes da função seguinte. Isso derrubaria o pico vivo de ~870 MiB para ~150–250 MiB.
   - **Compressão estrutural de `NoAST` e `InstSSA`**: união de campos mutuamente exclusivos ou vetores paralelos *Structure-of-Arrays* (SoA) em `Bytes`/inteiros para instruções SSA.

---

## 3. Perfil de Memória no Modo B (`build/dcc.c` Atual — 955k Tokens)

Com o código-fonte expandido do DCC 0.2.0 Ciclo IV (`955.348` tokens, `499.959` nós AST, `880.583` instruções SSA, `+10,4%` tokens em relação a `frozen_dcc.c`):
- `PREPROCESS_END`: `194 MiB` (desce para **`66 MiB`** em `LEX_START` após liberação e coleta GC!)
- `LEX_END`: `405 MiB`
- `PARSE_END`: `877 MiB`
- `SEMA_END`: `877 MiB`
- `IR_END`: `937 MiB`
- `CODEGEN_END`: `987 MiB`
- `ELF_END`: **`1.012 MiB` (0,99 GiB)** — mediana de pico RSS em 3 reps: **`1.038.188 KB` (0,99 GiB)**, cumprindo a meta exploratória de **~1 GiB** mesmo com uma entrada 10% maior!
