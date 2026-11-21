#!/usr/bin/env bash
# Benchmark sequencial: CGD (GCC/Clang/TCC) e DCC self-compile.
set -uo pipefail

cd "${DCC_DIR:-$HOME/dcc}" || exit 1
command -v cgd >/dev/null || { echo 'ERRO: cgd não está no PATH'; exit 1; }
command -v /usr/bin/time >/dev/null || { echo 'ERRO: GNU time ausente'; exit 1; }

stamp=$(date +%Y%m%d-%H%M%S)
report_dir="$PWD/build/bench-backends-$stamp"
mkdir -p "$report_dir"

if [[ ! -f build/dcc.c ]]; then
  echo 'ERRO: build/dcc.c não existe. Execute make build primeiro.' >&2
  exit 1
fi
cp build/dcc.c "$report_dir/dcc-input.c"
sha256sum "$report_dir/dcc-input.c" > "$report_dir/input.sha256"
printf 'Resultados em: %s\n' "$report_dir"
printf 'Compilação CGD → executável usando 3 backends, sequencialmente.\n'

# Primeiro GCC, depois Clang, depois TCC.
backends=(gcc clang tcc)
for backend in "${backends[@]}"; do
  compiler=$(command -v "$backend" || true)
  if [[ -z "$compiler" ]]; then
    echo "[PULADO] $backend não encontrado" | tee "$report_dir/$backend.status"
    continue
  fi
  out="$report_dir/dcc-$backend"
  echo "===== CGD + $backend ($compiler) ====="
  /usr/bin/time -f $'elapsed_s=%e\npeak_rss_kb=%M\nuser_s=%U\nsystem_s=%S\ncpu=%P\nexit=%x' \
    -o "$report_dir/$backend.build.metrics" \
    cgd src/main.delegua --cc="$compiler" -s "$out" \
    > "$report_dir/$backend.build.log" 2>&1
  status=$?
  printf '%s\n' "$status" > "$report_dir/$backend.build.exit"
  cat "$report_dir/$backend.build.metrics"
  if ((status != 0)); then
    echo "[ERRO] CGD + $backend: veja $report_dir/$backend.build.log"
    tail -n 12 "$report_dir/$backend.build.log"
    continue
  fi
  if [[ ! -x "$out" ]]; then
    echo "[ERRO] CGD não produziu executável em $out"
    continue
  fi
  stat -c 'binary_bytes=%s' "$out"
  "$out" --version > "$report_dir/$backend.version.log" 2>&1 || true
  echo "[OK] $backend"
done

if [[ "${RUN_SELF:-1}" == 1 ]]; then
  echo '===== DCC self-compile usando a mesma entrada C congelada ====='
  echo 'AVISO: cada execução pode consumir mais de 5 GiB de RAM.'
  for backend in "${backends[@]}"; do
    bin="$report_dir/dcc-$backend"
    [[ -x "$bin" ]] || continue
    echo "===== DCC gerado pelo $backend ====="
    /usr/bin/time -f $'elapsed_s=%e\npeak_rss_kb=%M\nuser_s=%U\nsystem_s=%S\ncpu=%P\nexit=%x' \
      -o "$report_dir/$backend.self.metrics" \
      timeout "${SELF_TIMEOUT:-600}" \
      "$bin" -v -std=gnu99 -O0 \
      -D__GNUC__=4 -DDELEGUA_OPERADORES_C \
      -I "$HOME/.local/share/cgd" \
      -c "$report_dir/dcc-input.c" \
      -o "$report_dir/dcc-self-$backend.o" -ftime-report \
      > "$report_dir/$backend.self.log" 2>&1
    status=$?
    printf '%s\n' "$status" > "$report_dir/$backend.self.exit"
    cat "$report_dir/$backend.self.metrics"
    if ((status != 0)); then
      echo "[ERRO] Self-compile via $backend: veja $report_dir/$backend.self.log"
      tail -n 12 "$report_dir/$backend.self.log"
    else
      stat -c 'object_bytes=%s' "$report_dir/dcc-self-$backend.o"
      grep '\[dcc-time\]' "$report_dir/$backend.self.log" | tail -n 1 || true
    fi
  done
fi

echo
echo '===== RESUMO ====='
printf '%-8s %-8s %-14s %-16s %-8s\n' 'backend' 'etapa' 'tempo(s)' 'pico(GiB)' 'exit'
for backend in "${backends[@]}"; do
  for stage in build self; do
    file="$report_dir/$backend.$stage.metrics"
    [[ -f "$file" ]] || continue
    sec=$(sed -n 's/^elapsed_s=//p' "$file")
    kb=$(sed -n 's/^peak_rss_kb=//p' "$file")
    code=$(cat "$report_dir/$backend.$stage.exit" 2>/dev/null || echo '?')
    gib=$(awk -v x="$kb" 'BEGIN {printf "%.2f", x/1048576}')
    printf '%-8s %-8s %-14s %-16s %-8s\n' "$backend" "$stage" "$sec" "$gib" "$code"
  done
done
printf '\nLogs completos: %s\n' "$report_dir"
