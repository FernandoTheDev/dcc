# Desenvolvimento Assistido e Gerado por IA — DCC

Este documento registra, de forma explícita e sem omissões, como o **DCC (Delégua C Compiler)** foi projetado, implementado, auditado e validado com o auxílio de sistemas de inteligência artificial.

---

## 1. Natureza do Desenvolvimento

O DCC é um projeto **amplamente gerado e iterativamente refinado por agentes de IA** atuando sob especificação, direção arquitetural, restrições rígidas e revisão de resultados por mantenedores humanos.

Especificamente, agentes de IA foram utilizados para:

- Extração e reestruturação do compilador C experimental originado no CGD em projeto autônomo;
- Escrita e refatoração dos módulos em Delégua (`src/`);
- Condução da auditoria técnica estrutural e de segurança registrada em [AUDIT_REPORT.md](AUDIT_REPORT.md);
- Implementação das correções de C99, ABI System V AMD64, IR SSA, backend x86-64, emissão ELF64, leitura de archives `.a` e diagnósticos;
- Criação das suítes de testes diferenciais (`tests/run_tests.py`), adversariais/fuzzing (`tests/test_security_fuzz.py`) e estresse/benchmarks (`tests/test_stress.py`);
- Redação e atualização da documentação técnica.

---

## 2. Histórico de Ciclos

| Ciclo | Foco Principal | Resultado Verificável |
| :--- | :--- | :--- |
| **Ciclo I** | Compilador C experimental dentro do ecossistema CGD | Pipeline inicial C99 com pré-processador, SSA, backend x86-64 e linking |
| **Ciclo II** | Independência como projeto `dcc` (v0.1.0) | Consumo real de `/usr/include`, camada GNU Cat A/B/C, objetos ELF64 `.o`, linker nativo e 35 testes iniciais |
| **Ciclo III** | Auditoria, refatoração, segurança e estabilização (v0.2.0) | Divisão modular de 13→23 módulos, adoção da stdlib `cgd:*`, endurecimento de segurança em PP/lexer/parser/IR/ELF/linker, suporte a `float` 32-bit, `NaN`, structs 9–16B e `>16B` (`sret`), `.rela.data`, archives `.a`, diagnósticos JSON/ANSI/códigos e expansão para 82 verificações + suíte adversarial + estresse |

---

## 3. O que É e o que NÃO É Garantido

### O que possui evidência objetiva e reproduzível

- **Testes diferenciais automatizados**: todo caso positivo em `tests/run_tests.py` compila o mesmo código C com `dcc` (`-O0`, `-O1`, `-O2`), `gcc` e `clang`, exigindo saída (`stdout`) e código de retorno idênticos.
- **Interoperabilidade binária real**: objetos `.o` compilados pelo DCC são linkados com objetos `.o` do GCC e do Clang nas 4 direções (`DCC -> GCC`, `GCC -> DCC`, `DCC -> Clang`, `Clang -> DCC`), validando a ABI System V AMD64 na prática.
- **Inspeção binária externa**: `readelf` e `ldd` auditam cabeçalhos ELF64, permissões de segmento (ausência de `RWE`), tabelas de seções e dependências dinâmicas.
- **Testes adversariais e de estresse**: entradas hostis em pré-processador, lexer, parser e leitor ELF/`.a` são testadas em `tests/test_security_fuzz.py`, e concorrência/multi-arquivo em `tests/test_stress.py`.
- **Formatação estática**: `make check-format` verifica 100% dos arquivos em `src/` via `cgd --verificar-formatacao`.

### O que NÃO foi feito (limitações honestas)

- **Não houve auditoria formal humana independente** linha por linha de toda a base de código.
- **Não há prova formal de correção** da tradução C99 → SSA → x86-64.
- **Não há conformidade completa de 100% com ISO C99** nem com todas as extensões GNU (ver [C99_CONFORMANCE.md](C99_CONFORMANCE.md)).
- **Não há garantia absoluta de segurança** contra entradas maliciosas desconhecidas (ver [../SECURITY.md](../SECURITY.md)).

---

## 4. Princípios de Qualidade Adotados no Uso de IA

Para mitigar riscos típicos de código gerado por IA (alucinações de API, atalhos silenciosos, testes viciados ou afirmações exageradas), o repositório impõe regras estritas (documentadas em [../AGENTS.md](../AGENTS.md)):

1. Nunca delegar fases do compilador a GCC, Clang, NASM ou `ld`;
2. Nunca simular headers da libc nem cadastrar funções da biblioteca padrão manualmente;
3. Nunca silenciar extensões GNU que alterem layout/semântica/ABI (classificação explícita Cat A/B/C);
4. Confirmar assinaturas reais da biblioteca padrão `~/.delegua/cgd` antes de usá-las;
5. Nunca alterar testes para mascarar falhas reais do compilador;
6. Documentar apenas resultados de testes e medições efetivamente executados.

---

## 5. Orientações para Contribuidores e Revisores Humanos

Revisões humanas são especialmente valiosas em:

- Casos de borda do padrão ISO C99 (conversões usuais, inicializadores complexos, regras de linkage e escopo);
- Classificação System V AMD64 ABI para structs mistas (campos `float`/`double` combinados com inteiros em `eightbytes` SSE);
- Revisão de segurança do leitor ELF/`.a` e do pré-processador;
- Otimização de desempenho do pré-processador em grandes árvores de cabeçalhos `glibc`.
