#!/usr/bin/env python3
"""Benchmark unificado CGD x DCC — Modo A (entrada C congelada) e Modo B (pipeline completo).

Executa sequencialmente (nunca em paralelo) GCC, Clang e TCC com 3 repeticoes por cenario,
registrando min/mediana/max, pico RSS, metricas de GC, volume de C, tamanho de binario e .o.
"""

import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

DCC_ROOT = Path("/home/fernandodev/dcc")
CGD_ROOT = Path("/home/fernandodev/cgd")
OUT_DIR = DCC_ROOT / "build" / "audit_ciclo4"
FROZEN_C = OUT_DIR / "frozen_dcc.c"
HOME = Path.home()
CGD_INC = HOME / ".local" / "share" / "cgd"

TIME_FMT = "elapsed_s=%e\npeak_rss_kb=%M\nuser_s=%U\nsystem_s=%S\nexit=%x"
RE_TIME_REPORT = re.compile(
    r"\[dcc-time\] preprocess=(\d+)ms lex=(\d+)ms parse=(\d+)ms sema=(\d+)ms "
    r"ir=(\d+)ms opt\+verify=(\d+)ms codegen=(\d+)ms elf_obj=(\d+)ms link=(\d+)ms total=(\d+)ms"
)
RE_MEM_LINE = re.compile(
    r"\[dcc-mem\] (\S+) rss=(\d+)MiB hwm=(\d+)MiB pss=(\d+)MiB gc_heap=(\d+)MiB "
    r"gc_free=(\d+)MiB gc_unmap=(\d+)MiB gc_use=(\d+)MiB gc_total=(\d+)MiB gc_cyc=(\d+)(.*)"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_timed(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> dict:
    metrics_file = OUT_DIR / f".metrics_{os.getpid()}.txt"
    full_cmd = ["/usr/bin/time", "-f", TIME_FMT, "-o", str(metrics_file), *cmd]
    proc = subprocess.run(
        full_cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    metrics = {}
    if metrics_file.exists():
        for line in metrics_file.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                metrics[k] = float(v) if k.endswith("_s") else int(v)
        metrics_file.unlink(missing_ok=True)
    return {
        "returncode": proc.returncode,
        "output": proc.stdout,
        **metrics,
    }


def parse_dcc_telemetry(output: str) -> tuple[dict, list[dict]]:
    phases = {}
    m = RE_TIME_REPORT.search(output)
    if m:
        keys = [
            "preprocess_ms",
            "lex_ms",
            "parse_ms",
            "sema_ms",
            "ir_ms",
            "opt_verify_ms",
            "codegen_ms",
            "elf_obj_ms",
            "link_ms",
            "total_ms",
        ]
        phases = {k: int(v) for k, v in zip(keys, m.groups())}
    mem_events = []
    for line in output.splitlines():
        mm = RE_MEM_LINE.search(line)
        if mm:
            mem_events.append(
                {
                    "marker": mm.group(1),
                    "rss_mib": int(mm.group(2)),
                    "hwm_mib": int(mm.group(3)),
                    "pss_mib": int(mm.group(4)),
                    "gc_heap_mib": int(mm.group(5)),
                    "gc_free_mib": int(mm.group(6)),
                    "gc_unmap_mib": int(mm.group(7)),
                    "gc_use_mib": int(mm.group(8)),
                    "gc_total_mib": int(mm.group(9)),
                    "gc_cycles": int(mm.group(10)),
                    "extra": mm.group(11).strip(),
                }
            )
    return phases, mem_events


def summarize(values: list[float | int]) -> dict:
    s = sorted(values)
    return {
        "min": s[0],
        "median": statistics.median(s),
        "max": s[-1],
        "spread": round(s[-1] - s[0], 4),
    }


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assert FROZEN_C.exists(), f"Frozen input missing: {FROZEN_C}"

    compilers = {
        "gcc": "/usr/bin/gcc",
        "clang": "/usr/bin/clang",
        "tcc": "/usr/local/sbin/tcc",
    }
    versions = {}
    for name, path in compilers.items():
        r = subprocess.run([path, "-v" if name == "tcc" else "--version"], capture_output=True, text=True)
        versions[name] = (r.stdout + r.stderr).splitlines()[0].strip()

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reps": reps,
        "compilers": compilers,
        "compiler_versions": versions,
        "frozen_input": {
            "path": str(FROZEN_C),
            "bytes": FROZEN_C.stat().st_size,
            "lines": sum(1 for _ in FROZEN_C.open("rb")),
            "sha256": sha256_file(FROZEN_C),
        },
        "cgd_emit_c": {},
        "builds_O0": {},
        "builds_O2": {},
        "mode_a_O0": {},
        "mode_a_O2": {},
        "mode_b_clang_O2": {},
        "tcc_direct": {},
    }

    # 1. Measure CGD C emission alone (--emitir-c)
    emit_c_out = OUT_DIR / "current_dcc"
    r_emit = run_timed(["cgd", "-o", "--emitir-c", str(DCC_ROOT / "src/main.delegua"), "-s", str(emit_c_out)])
    assert r_emit["returncode"] == 0, r_emit["output"]
    current_c = Path(str(emit_c_out) + ".c")
    report["cgd_emit_c"] = {
        "elapsed_s": r_emit["elapsed_s"],
        "peak_rss_kb": r_emit["peak_rss_kb"],
        "c_bytes": current_c.stat().st_size,
        "c_lines": sum(1 for _ in current_c.open("rb")),
        "sha256": sha256_file(current_c),
    }
    print(f"[cgd --emitir-c] {r_emit['elapsed_s']}s, {current_c.stat().st_size} B, {report['cgd_emit_c']['c_lines']} lines", flush=True)

    # 2. Build DCC with GCC, Clang, TCC at -O0 (matching bench.sh) and Clang at -O2 (matching bootstrap/build.sh)
    for backend, cc_path in compilers.items():
        bin_path = OUT_DIR / f"dcc-{backend}-O0"
        rb = run_timed(["cgd", str(DCC_ROOT / "src/main.delegua"), f"--cc={cc_path}", "-s", str(bin_path)])
        assert rb["returncode"] == 0, f"Build {backend} -O0 failed:\n{rb['output']}"
        report["builds_O0"][backend] = {
            "elapsed_s": rb["elapsed_s"],
            "peak_rss_kb": rb["peak_rss_kb"],
            "binary_bytes": bin_path.stat().st_size,
        }
        print(f"[build -O0 {backend}] {rb['elapsed_s']}s, rss={rb['peak_rss_kb']}KB, bin={bin_path.stat().st_size}B", flush=True)

    # Clang -O2 (bootstrap/build.sh default)
    bin_clang_o2 = OUT_DIR / "dcc-clang-O2"
    rb2 = run_timed(["cgd", "-o", str(DCC_ROOT / "src/main.delegua"), "--cc=/usr/bin/clang", "-s", str(bin_clang_o2)])
    assert rb2["returncode"] == 0, f"Build clang -O2 failed:\n{rb2['output']}"
    report["builds_O2"]["clang"] = {
        "elapsed_s": rb2["elapsed_s"],
        "peak_rss_kb": rb2["peak_rss_kb"],
        "binary_bytes": bin_clang_o2.stat().st_size,
    }
    print(f"[build -O2 clang] {rb2['elapsed_s']}s, rss={rb2['peak_rss_kb']}KB, bin={bin_clang_o2.stat().st_size}B", flush=True)

    # 3. TCC compiling frozen_dcc.c directly (reference)
    tcc_runs = []
    for _ in range(reps):
        obj_tcc = OUT_DIR / "tcc_direct.o"
        rt = run_timed([compilers["tcc"], "-I", str(CGD_INC), "-c", str(FROZEN_C), "-o", str(obj_tcc)])
        assert rt["returncode"] == 0, rt["output"]
        tcc_runs.append({"elapsed_s": rt["elapsed_s"], "peak_rss_kb": rt["peak_rss_kb"], "obj_bytes": obj_tcc.stat().st_size})
        obj_tcc.unlink(missing_ok=True)
    report["tcc_direct"] = {
        "runs": tcc_runs,
        "elapsed_s": summarize([r["elapsed_s"] for r in tcc_runs]),
        "peak_rss_kb": summarize([r["peak_rss_kb"] for r in tcc_runs]),
    }

    # 4. Mode A: Frozen C input across GCC (-O0), Clang (-O0), TCC (-O0) AND Clang (-O2)
    def run_self_bench(label: str, bin_path: Path, input_c: Path) -> dict:
        runs = []
        last_mem = []
        obj_path = OUT_DIR / f"self_{label}.o"
        for i in range(reps):
            args = [
                str(bin_path),
                "-v",
                "-std=gnu99",
                "-O0",
                "-D__GNUC__=4",
                "-DDELEGUA_OPERADORES_C",
                "-I",
                str(CGD_INC),
                "-c",
                str(input_c),
                "-o",
                str(obj_path),
                "-ftime-report",
            ]
            if i == reps - 1:
                args.append("-fmem-report")
            r = run_timed(args)
            assert r["returncode"] == 0, f"Run {label} #{i+1} failed:\n{r['output']}"
            phases, mem_events = parse_dcc_telemetry(r["output"])
            if mem_events:
                last_mem = mem_events
            runs.append(
                {
                    "elapsed_s": r["elapsed_s"],
                    "peak_rss_kb": r["peak_rss_kb"],
                    "user_s": r["user_s"],
                    "system_s": r["system_s"],
                    "obj_bytes": obj_path.stat().st_size,
                    "obj_sha256": sha256_file(obj_path),
                    "phases": phases,
                }
            )
            print(
                f"  [{label} run {i+1}/{reps}] {r['elapsed_s']}s, rss={r['peak_rss_kb']}KB, obj={obj_path.stat().st_size}B",
                flush=True,
            )
        obj_path.unlink(missing_ok=True)
        return {
            "runs": runs,
            "elapsed_s": summarize([x["elapsed_s"] for x in runs]),
            "peak_rss_kb": summarize([x["peak_rss_kb"] for x in runs]),
            "obj_bytes": runs[0]["obj_bytes"],
            "obj_sha256_consistent": len({x["obj_sha256"] for x in runs}) == 1,
            "obj_sha256": runs[0]["obj_sha256"],
            "mem_profile": last_mem,
        }

    for backend in ("gcc", "clang", "tcc"):
        report["mode_a_O0"][backend] = run_self_bench(f"modeA_O0_{backend}", OUT_DIR / f"dcc-{backend}-O0", FROZEN_C)

    report["mode_a_O2"]["clang"] = run_self_bench("modeA_O2_clang", bin_clang_o2, FROZEN_C)

    # 5. Mode B: Full Pipeline (current CGD-emitted current_dcc.c compiled by current dcc-clang-O2)
    report["mode_b_clang_O2"] = run_self_bench("modeB_O2_clang", bin_clang_o2, current_c)

    # Save JSON + CSV
    json_path = OUT_DIR / "bench_results.json"
    json_path.write_text(json.dumps(report, indent=2))

    csv_path = OUT_DIR / "bench_summary.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "backend", "opt", "min_s", "median_s", "max_s", "median_rss_kb", "obj_bytes"])
        for backend, data in report["mode_a_O0"].items():
            w.writerow(["ModeA_Frozen", backend, "-O0", data["elapsed_s"]["min"], data["elapsed_s"]["median"], data["elapsed_s"]["max"], data["peak_rss_kb"]["median"], data["obj_bytes"]])
        d2 = report["mode_a_O2"]["clang"]
        w.writerow(["ModeA_Frozen", "clang", "-O2", d2["elapsed_s"]["min"], d2["elapsed_s"]["median"], d2["elapsed_s"]["max"], d2["peak_rss_kb"]["median"], d2["obj_bytes"]])
        db = report["mode_b_clang_O2"]
        w.writerow(["ModeB_FullPipeline", "clang", "-O2", db["elapsed_s"]["min"], db["elapsed_s"]["median"], db["elapsed_s"]["max"], db["peak_rss_kb"]["median"], db["obj_bytes"]])
    print(f"Saved {json_path} and {csv_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
