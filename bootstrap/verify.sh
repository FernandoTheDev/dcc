#!/usr/bin/env bash
set -euo pipefail

RAIZ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DCC_BIN="${RAIZ_DIR}/build/dcc"

if [ ! -x "${DCC_BIN}" ]; then
    echo "[verify] build/dcc ausente; executando bootstrap/build.sh..."
    "${RAIZ_DIR}/bootstrap/build.sh"
fi

echo "[verify] 1/3 Testando execucao independente fora da arvore do projeto (/tmp)..."
TMP_DIR="$(mktemp -d /tmp/dcc_verify_XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat <<'EOF' > "${TMP_DIR}/smoke.c"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    char *s = malloc(16);
    if (s == NULL) return 1;
    strcpy(s, "DCC-OK");
    printf("%s\n", s);
    free(s);
    return 0;
}
EOF

(cd /tmp && "${DCC_BIN}" "${TMP_DIR}/smoke.c" -o "${TMP_DIR}/smoke_bin")
SAIDA="$("${TMP_DIR}/smoke_bin")"
if [ "${SAIDA}" != "DCC-OK" ]; then
    echo "[verify] FALHA: saida inesperada '${SAIDA}'" >&2
    exit 1
fi
echo "[verify] Smoke fora da arvore OK: ${SAIDA}"

echo "[verify] 2/3 Verificando dependencias dinamicas do binario dcc..."
ldd "${DCC_BIN}"

echo "[verify] 3/3 Executando suite completa (tests/run_tests.py)..."
python3 "${RAIZ_DIR}/tests/run_tests.py"
echo "[verify] Todas as verificacoes do DCC passaram."
