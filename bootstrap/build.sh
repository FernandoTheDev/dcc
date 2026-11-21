#!/usr/bin/env bash
set -euo pipefail

RAIZ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CGD_CMD="${CGD:-cgd}"
OUT_DIR="${RAIZ_DIR}/build"
OUT_BIN="${OUT_DIR}/dcc"

echo "[bootstrap] Verificando compilador CGD..."
if ! command -v "${CGD_CMD}" >/dev/null 2>&1; then
    echo "erro: compilador 'cgd' nao encontrado no PATH (defina CGD=/caminho/para/cgd)." >&2
    exit 1
fi

CGD_VERSAO="$("${CGD_CMD}" --versao 2>&1 || "${CGD_CMD}" --version 2>&1 || true)"
echo "[bootstrap] CGD detectado: ${CGD_VERSAO}"

if ! command -v base64 >/dev/null 2>&1; then
    echo "erro: utilitario 'base64' (coreutils) nao encontrado." >&2
    exit 1
fi

mkdir -p "${OUT_DIR}"
echo "[bootstrap] Compilando DCC (src/main.delegua -> build/dcc)..."
"${CGD_CMD}" -o "${RAIZ_DIR}/src/main.delegua" -s "${OUT_BIN}"

chmod +x "${OUT_BIN}"
echo "[bootstrap] Binario gerado com sucesso: ${OUT_BIN}"
"${OUT_BIN}" --version
