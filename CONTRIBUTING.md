# Contribuindo para o DCC

Contribuições para melhorar a conformidade ISO C99, otimizações, ABI, diagnósticos e linker do DCC são bem-vindas.

## Diretrizes de Código

- Toda a implementação principal permanece em **Delégua** (`src/`), com tipos concretos em variáveis, parâmetros e retornos (`qualquer` apenas quando dinâmico).
- Não substitua etapas do compilador por chamadas a GCC, Clang, NASM ou `ld`.
- Não crie cabeçalhos falsos nem cadastros manuais de funções da libc: o compilador deve continuar consumindo os cabeçalhos reais do sistema.
- Toda extensão GNU deve ser classificada nas Categorias A, B ou C documentadas em `docs/GNU_COMPATIBILITY.md`.
- Formate todos os fontes Delégua com `make format` e valide com `make check-format`.

## Validação Obrigatória Antes de Abrir PR

```sh
./bootstrap/build.sh
make check-format
./bootstrap/verify.sh
```

Para cada defeito corrigido ou recurso C99 adicionado, inclua um caso de teste diferencial (comparando `stdout` e código de saída contra `gcc` e `clang`) ou de diagnóstico negativo em `tests/run_tests.py`.
