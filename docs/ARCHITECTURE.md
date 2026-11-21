# Arquitetura Interna do DCC (v0.2.0)

## 1. Visão Geral do Pipeline

```text
  arquivos .c / .o / .a + flags (-I, -D, -U, -L, -l, -std=, -O0..3, -W*, -fdiagnostics-*, -ftime-report)
         │
         ▼
  src/driver/cli.delegua                  (Driver CLI, orquestração, Cronometro, resolução -L/-l, FFI chmod)
         │
         ├──► (.c) Pré-processador (3 módulos)
         │         ├── src/preprocessor/preproc.delegua    (Fases 1–3, #include/#include_next, MI-OPT/cache, anti-DoS)
         │         ├── src/preprocessor/pp_macros.delegua  (Tokenização PP, hide-set Prosser, #, ##, variádicas)
         │         └── src/preprocessor/pp_expr.delegua    (Avaliador #if 64-bit signed/unsigned, div0/INT64_MIN guards)
         │         │
         │         ▼
         │    Lexer e Literais (2 módulos)
         │         ├── src/lexer/literais.delegua          (ClassificadorChar, escapes C99, parseInteiroC99 u64, hex-float)
         │         └── src/lexer/lexer.delegua             (Tokenização C99/GNU99, bytesStr exatos, Fase 6)
         │         │
         │         ▼
         │    src/parser/parser.delegua                  (Precedence Climbing, guarda profundidade 96, pilhaTypedefs, Cat A/B/C)
         │         │
         │         ▼
         │    src/semantic/sema.delegua                  (Layout LP64, bit-fields, const/ponteiros, duplicatas, offsetof aninhado)
         │         │
         │         ▼
         │    IR SSA + Otimizador + Verificador (5 módulos)
         │         ├── src/ir/ir_tipos.delegua             (InstSSA, BlocoSSA, FuncaoSSA, GlobalSSA, ModuloSSA, RelocGlobal)
         │         ├── src/ir/ir_builder.delegua           (Lowering AST→SSA, structs <=8/9..16/>16B sret, .rela.data, float32)
         │         ├── src/ir/ir_opt.delegua               (Constant folding 32/64 seguro, DCE respeitando volatile e div/mod)
         │         ├── src/ir/ir_verify.delegua            (Verificador de invariantes SSA antes do backend)
         │         └── src/ir/ir_ssa.delegua               (Fachada de alto nível)
         │         │
         │         ├──► (-S) src/backend/x86_64/asm.delegua         ──► Assembly Intel x86-64 (.s)
         │         └──► Backend Objeto (2 módulos)
         │                   ├── src/backend/x86_64/emissor.delegua  (Codificação x86-64, NaN-safe SSE, 32/64-bit, rel32 bounds)
         │                   └── src/backend/x86_64/codegen.delegua  (Lowering SSA→CodigoObjeto PIC, sret, STB_WEAK, .rela.data)
         │                   │
         │                   ▼
         │              Emissão ELF64 (2 módulos)
         │                   ├── src/object/elf/elf_comum.delegua    (Constantes ELF64 e helpers little-endian compartilhados)
         │                   └── src/object/elf/elf_obj.delegua      (Objeto ELF64 ET_REL com 11 seções + .rela.data + STB_WEAK)
         │                   │
         ▼                   ▼
  Linker Nativo ELF64 (2 módulos)
         ├── src/linker/elf_leitor.delegua        (Leitura validada de .o ELF64 e archives GNU ar .a)
         └── src/linker/linker.delegua            (Ponto fixo .a, STB_WEAK, SHN_COMMON, _start argc/argv, PLT/GOT, bounds reloc)
         │
         ▼
  Executável ELF64 Dinâmico (ET_EXEC: PT_LOAD R E + PT_LOAD R W + PT_GNU_STACK + 13 Section Headers)
```

Módulos transversais:
- [`src/diagnostics/diag.delegua`](../src/diagnostics/diag.delegua): códigos `E1xxx`–`E9xxx`/`W1xxx`–`W2xxx`, `MapaFonte`, pilha de inclusão, cores ANSI (`isatty(2)` + `NO_COLOR`), JSON (`cgd:json`) e `-Wno-*`.
- [`src/types/tipos.delegua`](../src/types/tipos.delegua): enums de tokens/AST/IR, `TipoC` (com `ehConst`/`ehVolatile`/`ehRestrict` e `clonar()`), `TabelaTipos` LP64 e codificadores IEEE-754 puros (`double` 64-bit e `float` 32-bit).

---

## 2. Inventário de Módulos (`src/` — 23 arquivos, 12.838 LOC)

| Camada | Arquivos | Responsabilidade |
| :--- | :--- | :--- |
| Entrada & Driver | `main.delegua`, `driver/cli.delegua` | CLI, cronômetro por fase, I/O, resolução `-L`/`-l` |
| Diagnósticos | `diagnostics/diag.delegua` | Formatação texto/JSON, cores, include stack, ICE |
| Tipos | `types/tipos.delegua` | Tipos LP64, layout, qualificadores, IEEE-754 puro |
| Pré-processador | `preprocessor/preproc.delegua`, `pp_macros.delegua`, `pp_expr.delegua` | Fases 1–4, macros, `#if`, cache/MI-OPT, anti-DoS |
| Lexer | `lexer/lexer.delegua`, `lexer/literais.delegua` | Tokenização C99/GNU99, escapes exatos, literais u64/hex-float |
| Parser | `parser/parser.delegua` | AST C99/GNU99, Precedence Climbing, escopo de `typedef`, GNU Cat A/B/C |
| Semântica | `semantic/sema.delegua` | Tipagem, validações de erro/aviso, bit-fields, `const`, `offsetof` |
| IR SSA | `ir/ir_tipos.delegua`, `ir_builder.delegua`, `ir_opt.delegua`, `ir_verify.delegua`, `ir_ssa.delegua` | Construção SSA, otimização segura, verificação de invariantes |
| Backend x86-64 | `backend/x86_64/emissor.delegua`, `codegen.delegua`, `asm.delegua` | Emissão binária x86-64 PIC e Assembly `-S` |
| ELF64 & Linker | `object/elf/elf_comum.delegua`, `elf_obj.delegua`, `linker/elf_leitor.delegua`, `linker/linker.delegua` | Objetos `.o`, archives `.a` e executáveis dinâmicos `ET_EXEC` |

---

## 3. Regras de Acoplamento e Invariantes

1. **Dependência estritamente acíclica**: `types`/`diagnostics` → `lexer` → `preprocessor` → `parser` → `semantic` → `ir` → `backend` → `object/elf` → `linker` → `driver`.
2. **Sem duplicação entre camadas**: constantes ELF64 e helpers LE vivem apenas em `elf_comum.delegua`; classificação de caracteres, escapes C99 e parsing de literais inteiros/hex-float vivem apenas em `literais.delegua`.
3. **Barreira de invariantes antes do backend**: `ir_verify.delegua` valida blocos, terminadores, definições SSA únicas, registradores válidos e índices de strings/globais antes de `codegen.delegua` ou `asm.delegua`.
4. **Sem estados globais ocultos**: estado de compilação pertence às instâncias (`GerenciadorDiagnosticos`, `PreprocessadorDCC`, `LexerDCC`, `ParserDCC`, `AnalisadorSemantico`, `ConstrutorIR`).

Para detalhes aprofundados, veja [ABI.md](ABI.md), [LINKER.md](LINKER.md), [DIAGNOSTICS.md](DIAGNOSTICS.md) e [CGD_STDLIB.md](CGD_STDLIB.md).
