# Contribuindo para o DCC

Contribuições para melhorar a conformidade ISO C99, segurança, otimizações, ABI, diagnósticos e linker do DCC são bem-vindas.

## Diretrizes Técnicas Obrigatórias

- Toda a implementação principal permanece em **Delégua** (`src/`), com tipagem explícita (`qualquer` apenas onde o modelo dinâmico da linguagem exigir).
- Não delegue pré-processamento, compilação, montagem ou linkagem a GCC, Clang, NASM ou `ld`.
- Não crie cabeçalhos falsos nem cadastros manuais de funções da libc: o compilador deve continuar consumindo os cabeçalhos reais do sistema.
- Utilize a biblioteca padrão real do CGD (`~/.delegua/cgd`) quando adequada (consulte [docs/CGD_STDLIB.md](docs/CGD_STDLIB.md)), sem duplicar utilitários desnecessariamente.
- Toda extensão GNU deve ser classificada nas Categorias A, B ou C documentadas em [docs/GNU_COMPATIBILITY.md](docs/GNU_COMPATIBILITY.md).
- Mantenha `docs/C99_CONFORMANCE.md` e `docs/CONTINUITY.md` honestos e sincronizados com testes realmente executados.
- Formate todos os fontes Delégua com `make format` e valide com `make check-format`.

## Validação Obrigatória Antes de Abrir PR

```sh
./bootstrap/build.sh
make check-format
./bootstrap/verify.sh
make test-security
make test-stress
```

Para cada defeito corrigido ou recurso C99 adicionado:
- Inclua um caso diferencial (comparando `stdout` e código de saída contra `gcc` e `clang` em `-O0/-O1/-O2`) ou de diagnóstico negativo em `tests/run_tests.py`;
- Para correções de segurança ou robustez contra entradas malformadas, inclua um caso reproduzível em `tests/test_security_fuzz.py`.
