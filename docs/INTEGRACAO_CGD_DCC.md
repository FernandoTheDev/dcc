# Relatório de Engenharia Cruzada — Integração CGD × DCC

**Data:** 21/11/2026  
**Projetos auditados em conjunto:**
- **CGD `0.9.0`** (`/home/fernandodev/cgd`, branch `dev` @ `9038032` + Ciclos I–III; runtime em `vendor/delegua-runtime` @ `fdd0463` + Ciclos I–III)
- **DCC `0.2.0`** (`/home/fernandodev/dcc`, branch `master` @ `686efc3` + Ciclo IV)

---

## 1. Por Que Engenharia Cruzada Foi Decisiva

Otimizar CGD e DCC isoladamente teria falhado em atingir os ganhos obtidos neste ciclo. A causa raiz dos dois maiores problemas só se tornou evidente ao observar os dois lados da fronteira simultaneamente:

1. **O problema de memória (6,40–7,10 GiB → 0,91 GiB)** era ~55% culpa da representação de objetos/coleções no runtime do CGD e ~45% culpa de estruturas de dados e ciclo de vida no DCC:
   - O CGD sozinho (slots inline + coleções vazias preguiçosas) derrubou o RSS de **6,40 GiB → 2,94 GiB**, mas parou ali porque o DCC continuava guardando 17,8 MB de código de máquina em `inteiro[]` (24 B/byte) e retendo AST+Tokens+IR no mesmo stack frame.
   - O DCC sozinho não podia migrar `EmissorX86_64.code` nem eliminar o subprocesso `base64 -d` porque `cgd:bytes.Bytes` era de tamanho fixo e sem I/O binário; tampouco podia liberar vetores sob Boehm GC sem `vetor.limpar()` e `Sistema.coletarGC()`.
   - A co-engenharia (`Bytes` crescível em `GC_MALLOC_ATOMIC` + `vetor.limpar()` + `Sistema.memoria()`/`coletarGC()` no CGD, consumidos imediatamente no DCC) derrubou o RSS de **2,94 GiB → 0,91 GiB**.
2. **O problema de tempo (29,94 s → 8,56 s)** expôs uma interação crítica na Etapa 3.4:
   - Quando o DCC trocou `inteiro[]` por `Bytes.obter()` no lexer e pré-processador, o tempo inicialmente **piorou** de `20,50 s → 28,12 s`.
   - O diagnóstico cruzado revelou a razão exata: cada chamada `Bytes.obter(pos)` atravessava `delegua_chamar_membro` + wrapper FFI (`foreign.d`) chamando `delegua_assegurar_descr(..., delegua_descr_nome(...))` dentro de um `libdelegua_rt.o` compilado em `-O0`!
   - A correção conjunta no CGD (`RT_OPT=-O2` + Inline Caching monomórfico `delegua_*_ic` + checagem FFI inline em `foreign.d`) transformou essa regressão em um ganho massivo: **`28,12 s → 8,93 s`**, chegando a **`8,56 s`** com o tracking de `RAX` no DCC.

---

## 2. Matriz de Responsabilidade e Interações CGD × DCC

| Gargalo Identificado | Camada Responsável | Correção no CGD | Correção no DCC | Efeito Combinado |
| --- | --- | --- | --- | --- |
| 13–33 allocs GC / instância (`TokenC99`, `NoAST`, `InstSSA`) | **CGD Runtime** | Slots fixos inline em `objeto` (`objetos.c`) | Extração de `CallInfoSSA` em `InstSSA` | `-3,3 GiB` RSS, `-8,8 s` |
| 222k folhas AST com `filhos: []` | **CGD Runtime** | `create_vetor()`/`create_map()` preguiçosos (`NULL`), `VETOR_INIT_CAP=4` | Uso direto sem wrappers extras | `-310 MiB` RSS |
| `EmissorX86_64.code` e `elf_obj` em `inteiro[]` + `base64 -d` | **CGD + DCC** | `Bytes` crescível em `GC_MALLOC_ATOMIC` + `gravarArquivo`/`lerArquivo` | Migração de `emissor.delegua`, `codegen.delegua`, `elf_obj.delegua`, `cli.delegua` | `-1,48 GiB` RSS, `elf_obj` `5,9×` mais rápido |
| Retenção conservadora no Boehm GC | **CGD + DCC** | `vetor.limpar()`, `map_limpar()` liberando `buckets`, `Sistema.memoria`/`coletarGC` | Subfunções de fase + `.limpar()` + coleta em TU >20k tokens | `-332 MiB` RSS (quebrou `< 1 GiB`) |
| Runtime lento em `-O0` + despacho dinâmico sem cache | **CGD Build + Codegen + Runtime** | `RT_OPT=-O2`, `delegua_prop_ic`/`def_ic`/`chamar_ic`, `foreign.d` inline | Benefício automático em todas as 8 fases | `20,63 s → 8,93 s` (`2,31×`) |
| `preproc.delegua` perdendo fast-path em escapes octais do CGD | **Interação CGD→DCC** | CGD emite literais com escapes octais (`\141`) em `build/dcc.c` | `preproc.delegua` trocou `contem("\\")` por `terminaCom("\\")` | `-1,4 GiB` churn GC, `preprocess` `2,2×` mais rápido |
| `ir_verify`/`ir_opt` usando `dicionario` por `texto(reg)` | **DCC** | `Bytes.criar(n)` em `GC_MALLOC_ATOMIC` | Bitsets densos em `ir_verify.delegua` e `ir_opt.delegua` | `OPT` alloc `330 → 2 MiB` |
| Loads redundantes `[rbp - off]` no código gerado pelo DCC | **DCC Backend** | — | Rastreamento intra-bloco de `RAX` em `codegen.delegua` | `-760 KB` `.text`, `dcc-self` mais rápido |

---

## 3. Verificação da Cadeia Completa de Bootstrap Indireto

Fluxo validado de ponta a ponta em 21/11/2026:

```text
DCC 0.2.0 (23 módulos .delegua)
   │  cgd -o --emitir-c src/main.delegua -s build/dcc        (1,00 s | 199 MB RSS)
   ▼
build/dcc.c (42.915 linhas, 5.255.487 B, sha256: a1401f96...)
   │  ./bootstrap/build.sh (cgd -o --cc=clang)               (16,99 s | 264 MB RSS)
   ▼
build/dcc (4.658.888 B)
   │  ./build/dcc -std=gnu99 -O0 ... -c build/dcc.c -o build/dcc-self.o
   │  (9,55 s | 1.058.936 KB RSS = 1,01 GiB)
   ▼
build/dcc-self.o (22.130.832 B, sha256: db91f61b..., ELF64 válido)
   │  gcc -no-pie build/dcc-self.o ~/.local/share/cgd/lib/libdelegua_rt.o -lgc -lm -lpthread -ldl -lcurl -lffi
   ▼
build/dcc-self (20.097.112 B)
   │  ./build/dcc-self examples/hello_libc.c -o /tmp/hello_bootstrap_final
   │  (0,29 s | 136 MB RSS)
   ▼
/tmp/hello_bootstrap_final → imprime "DCC" (exit 0)
```

---

## 4. Compatibilidade Cruzada entre Compiladores C (GCC × Clang × TinyCC)

Todas as mudanças do CGD Ciclo III (incluindo slots inline com FAM, macros atômicas `DELEGUA_ATOMIC_LOAD_PTR`/`STORE_PTR`, `cgd_ic[]` e `bytes_rt.c`) foram validadas com **GCC 16.2.1**, **Clang 22.1.8** e **TinyCC 0.9.28rc**:
- Os binários do DCC compilados por GCC, Clang e TinyCC produzem objetos `dcc-self.o` **100% idênticos bit-a-bit** sobre `frozen_dcc.c` (`sha256: 6144e0665d578e7da0d78b6db63f236150f777d1941ab5548f5d0a6647e5f9ba`).
- `delegua_rt.h` também continua sendo pré-processado e compilado diretamente pelo próprio **DCC 0.2.0** (sem modificações ou gambiarras), validando a compatibilidade C99/GNU99 das novas estruturas do runtime CGD.

---

## 5. Próximo Horizonte Conjunto (CGD Ciclo IV × DCC Ciclo V)

1. **Compilação *streaming* por função no DCC**: emitir `AST → IR → x86-64` por função de nível superior para derrubar o RSS do bootstrap de **~0,91 GiB para < 300 MiB**.
2. **Vetores primitivos *unboxed* (`inteiro[]`/`real[]`) e PIC/despacho estático em classes fechadas no CGD**: reduzir em 3× o custo de arrays numéricos e acelerar locais polimórficos da AST/IR.
3. **Alocação *linear scan* de registradores no DCC**: aproximar o tamanho e a velocidade de `build/dcc-self` do código produzido por compiladores nativos estabelecidos.
4. **Redução do volume C gerado pelo CGD**: compactar chamadas IC / macros em `delegua_rt.h` para acelerar tanto o build com GCC/Clang quanto a auto-compilação pelo próprio DCC.
