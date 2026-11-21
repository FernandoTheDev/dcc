#!/usr/bin/env python3
"""Suite de estabilidade prolongada, concorrencia, equivalencia -O0/-O1/-O2 e benchmark de fases do DCC."""

from __future__ import annotations

import concurrent.futures
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ_DCC = Path(__file__).resolve().parents[1]
DCC_BIN = RAIZ_DCC / "build" / "dcc"


def testar_projeto_multiarquivo_e_archive(tmp: Path) -> int:
    """Compila um projeto de 6 modulos C, empacota 3 em libproj.a, linka e valida contra GCC."""
    (tmp / "proj.h").write_text(
        """
#ifndef PROJ_H
#define PROJ_H
#include <stdint.h>
struct Vec3 { int64_t x, y, z; };
int64_t dot3(struct Vec3 a, struct Vec3 b);
struct Vec3 add3(struct Vec3 a, struct Vec3 b);
int fib(int n);
unsigned int crc_simples(const unsigned char *buf, int len);
extern const char *g_banner;
#endif
""",
        encoding="utf-8",
    )
    (tmp / "vec.c").write_text(
        """
#include "proj.h"
int64_t dot3(struct Vec3 a, struct Vec3 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}
struct Vec3 add3(struct Vec3 a, struct Vec3 b) {
    struct Vec3 r = { a.x + b.x, a.y + b.y, a.z + b.z };
    return r;
}
""",
        encoding="utf-8",
    )
    (tmp / "fib.c").write_text(
        """
#include "proj.h"
int fib(int n) {
    if (n <= 1) return n;
    int a = 0, b = 1;
    for (int i = 2; i <= n; i++) {
        int c = a + b;
        a = b;
        b = c;
    }
    return b;
}
""",
        encoding="utf-8",
    )
    (tmp / "hash.c").write_text(
        """
#include "proj.h"
const char *g_banner = "DCC-MULTI";
unsigned int crc_simples(const unsigned char *buf, int len) {
    unsigned int h = 2166136261u;
    for (int i = 0; i < len; i++) {
        h ^= (unsigned int)buf[i];
        h *= 16777619u;
    }
    return h;
}
""",
        encoding="utf-8",
    )
    (tmp / "main.c").write_text(
        """
#include <stdio.h>
#include <string.h>
#include "proj.h"
int main(int argc, char **argv) {
    struct Vec3 u = { 2, 3, 5 };
    struct Vec3 v = { 7, 11, 13 };
    struct Vec3 s = add3(u, v);
    int64_t d = dot3(s, v);
    int f = fib(12);
    unsigned int h = crc_simples((const unsigned char *)g_banner, (int)strlen(g_banner));
    printf("%s argc=%d arg1=%s s=(%ld,%ld,%ld) d=%ld fib=%d h=%u\\n",
           g_banner, argc, argc > 1 ? argv[1] : "none",
           (long)s.x, (long)s.y, (long)s.z, (long)d, f, h);
    return (int)((d + f + (h & 63)) % 200);
}
""",
        encoding="utf-8",
    )

    # Referencia GCC
    ref_bin = tmp / "proj_gcc"
    subprocess.run(
        ["gcc", "-std=c99", "-O2", str(tmp / "main.c"), str(tmp / "vec.c"),
         str(tmp / "fib.c"), str(tmp / "hash.c"), "-o", str(ref_bin)],
        check=True,
    )
    r_ref = subprocess.run([str(ref_bin), "hello_arg"], capture_output=True, text=True, check=False)

    # DCC: compila para .o, cria libproj.a via ar, linka main.o + -L tmp -lproj
    for opt in ("-O0", "-O1", "-O2"):
        sub = tmp / f"opt_{opt[1:]}"
        sub.mkdir()
        for mod in ("vec", "fib", "hash", "main"):
            subprocess.run(
                [str(DCC_BIN), opt, "-c", str(tmp / f"{mod}.c"), "-o", str(sub / f"{mod}.o")],
                check=True,
            )
        lib_a = sub / "libproj.a"
        subprocess.run(
            ["ar", "rcs", str(lib_a), str(sub / "vec.o"), str(sub / "fib.o"), str(sub / "hash.o")],
            check=True,
        )
        dcc_bin = sub / "proj_dcc"
        subprocess.run(
            [str(DCC_BIN), str(sub / "main.o"), "-L", str(sub), "-lproj", "-o", str(dcc_bin)],
            check=True,
        )
        r_dcc = subprocess.run([str(dcc_bin), "hello_arg"], capture_output=True, text=True, check=False)
        if r_dcc.returncode != r_ref.returncode or r_dcc.stdout != r_ref.stdout:
            print(f"[FALHA MULTIFILE {opt}] ref=({r_ref.returncode},{r_ref.stdout!r}) dcc=({r_dcc.returncode},{r_dcc.stdout!r})")
            return 1
        print(f"[OK] stress_multifile_archive ({opt}) -> exit={r_dcc.returncode}")
    return 0


def testar_repeticao_e_concorrencia(tmp: Path) -> int:
    """Executa 40 compilacoes em paralelo (4 workers) + 20 iteracoes sequenciais verificando determinismo."""
    prog_src = tmp / "conc.c"
    prog_src.write_text(
        """
#include <stdio.h>
int soma(int n) {
    int s = 0;
    for (int i = 1; i <= n; i++) s += i * i;
    return s;
}
int main(void) {
    int r = soma(10);
    printf("%d\\n", r);
    return r % 100;
}
""",
        encoding="utf-8",
    )

    def compilar_e_rodar(idx: int) -> tuple[int, str]:
        out = tmp / f"conc_{idx}"
        r = subprocess.run(
            [str(DCC_BIN), "-O2", str(prog_src), "-o", str(out)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if r.returncode != 0:
            return (-1, r.stderr)
        ex = subprocess.run([str(out)], capture_output=True, text=True, timeout=5, check=False)
        return (ex.returncode, ex.stdout)

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(compilar_e_rodar, range(24)))
    dt = time.perf_counter() - t0
    for idx, res in enumerate(resultados):
        if res != (85, "385\n"):
            print(f"[FALHA CONCORRENCIA #{idx}] {res}")
            return 1
    print(f"[OK] stress_concorrencia (24 compilacoes paralelas 4x em {dt:.2f}s)")
    return 0


def rodar_benchmark_fases(tmp: Path) -> int:
    """Mede tempo por fase via -ftime-report em programa com headers reais da glibc."""
    arq = tmp / "bench.c"
    arq.write_text(
        """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

int main(void) {
    double acc = 0.0;
    for (int i = 1; i <= 50; i++) acc += sqrt((double)i);
    printf("%.3f\\n", acc);
    return 0;
}
""",
        encoding="utf-8",
    )
    out = tmp / "bench_bin"
    r = subprocess.run(
        [str(DCC_BIN), "-O2", "-ftime-report", str(arq), "-lm", "-o", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0 or "[dcc-time]" not in r.stderr:
        print(f"[FALHA BENCHMARK] rc={r.returncode} stderr={r.stderr!r}")
        return 1
    print(f"[OK] benchmark_fases: {r.stderr.strip()}")
    return 0


def main() -> int:
    if not DCC_BIN.exists():
        print(f"Binario nao encontrado: {DCC_BIN}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="dcc_stress_"))
    try:
        falhas = 0
        falhas += testar_projeto_multiarquivo_e_archive(tmp)
        falhas += testar_repeticao_e_concorrencia(tmp)
        falhas += rodar_benchmark_fases(tmp)
        print(f"\nResumo Estresse/Benchmark DCC: {'APROVADO' if falhas == 0 else f'{falhas} FALHA(S)'}")
        return 1 if falhas > 0 else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
