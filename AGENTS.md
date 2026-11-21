# Contexto do Repositório DCC (Delégua C Compiler)

O DCC é um compilador C nativo independente para Linux x86-64 (System V AMD64 ABI),
escrito em Delégua e compilado via CGD.

## Regras Inegociáveis

1. Não delegar pré-processamento, compilação, montagem ou linkagem a GCC, Clang, NASM ou `ld`.
2. Processar os cabeçalhos originais do sistema (`/usr/include` + diretório freestanding); nunca simular headers nem cadastrar funções da libc manualmente.
3. Classificar extensões GNU explicitamente em Categorias A (metadado ignorável), B (relevante para semântica/layout/ABI) ou C (erro explícito). Nunca ignorar silenciosamente extensões que alterem semântica ou ABI.
4. Manter `docs/C99_CONFORMANCE.md` e `docs/CONTINUITY.md` honestos e atualizados com os testes realmente executados.
5. Em código Delégua, manter tipagem explícita e formatação validada por `make check-format`.

## Comandos Principais

```sh
./bootstrap/build.sh
./bootstrap/verify.sh
make check-format
```
