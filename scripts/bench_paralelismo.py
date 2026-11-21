#!/usr/bin/env python3
"""Suite completa de benchmarks Ciclo V (CGD x DCC):
- Modo A (frozen_dcc.c): Cycle IV vs Cycle V (Clang -O2, GCC -O0, Clang -O0, TCC -O0) + -j1/-j2/-j4/-j8/-j auto
- Modo B (pipeline atual dcc_c5_current.c + bootstrap indireto)
- Multi-TU (16+1 TUs): -j1 vs -j2 vs -j4 vs -j8 vs -j auto vs taskset -c 0,1
- Granularidade single-TU (pequena, 500 funcoes pequenas, 4 funcoes grandes)
- Linker paralelo: 1, 10, 100 e 300 .o + .a encadeado + >3000 relocs (Cycle IV vs Cycle V -j1/-j2/-j4/-j8)

Executa TODOS os cenarios estritamente em sequencia (nunca em paralelo), salvando JSON em
build/audit_ciclo5/bench_paralelismo.json.
"""

import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DCC_ROOT = Path("/home/fernandodev/dcc")
OUT_DIR = DCC_ROOT / "build" / "audit_ciclo5"
FROZEN_C = DCC_ROOT / "build" / "audit_ciclo4" / "frozen_dcc.c"
C4_BIN = DCC_ROOT / "build" / "audit_ciclo4" / "dcc-clang-O2"
CGD_INC = Path.home() / ".local" / "share" / "cgd"

TIME_FMT = "elapsed_s=%e\npeak_rss_kb=%M\nuser_s=%U\nsystem_s=%S\nexit=%x"
RE_TIME = re.compile(
    r"\[dcc-time\] preprocess=(\d+)ms lex=(\d+)ms parse=(\d+)ms sema=(\d+)ms "
    r"ir=(\d+)ms opt\+verify=(\d+)ms codegen=(\d+)ms elf_obj=(\d+)ms link=(\d+)ms total=(\d+)ms"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_timed(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> dict:
    mf = OUT_DIR / f".metrics_{os.getpid()}.txt"
    proc = subprocess.run(
        ["/usr/bin/time", "-f", TIME_FMT, "-o", str(mf), *cmd],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    metrics = {}
    if mf.exists():
        for line in mf.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                metrics[k] = float(v) if k.endswith("_s") else int(v)
        mf.unlink(missing_ok=True)
    phases = {}
    m = RE_TIME.search(proc.stdout)
    if m:
        keys = [
            "preprocess_ms", "lex_ms", "parse_ms", "sema_ms", "ir_ms",
            "opt_verify_ms", "codegen_ms", "elf_obj_ms", "link_ms", "total_ms",
        ]
        phases = {k: int(v) for k, v in zip(keys, m.groups())}
    return {
        "returncode": proc.returncode,
        "output": proc.stdout,
        "phases": phases,
        **metrics,
    }


def summarize(runs: list[dict]) -> dict:
    el = sorted(r["elapsed_s"] for r in runs)
    rss = sorted(r["peak_rss_kb"] for r in runs)
    res = {
        "elapsed_s": {
            "min": el[0],
            "median": round(statistics.median(el), 4),
            "max": el[-1],
        },
        "peak_rss_kb": {
            "min": rss[0],
            "median": int(statistics.median(rss)),
            "max": rss[-1],
        },
    }
    if runs and runs[0].get("phases"):
        ph = {}
        for k in runs[0]["phases"].keys():
            vals = sorted(r["phases"][k] for r in runs if k in r.get("phases", {}))
            if vals:
                ph[k] = int(statistics.median(vals))
        res["phases_median_ms"] = ph
    return res


def build_c5_binaries() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bins = {}
    specs = [
        ("clang_O2", ["-o", "--cc=/usr/bin/clang"]),
        ("gcc_O0", ["--cc=/usr/bin/gcc"]),
        ("clang_O0", ["--cc=/usr/bin/clang"]),
        ("tcc_O0", ["--cc=/usr/local/sbin/tcc"]),
    ]
    for name, flags in specs:
        out_bin = OUT_DIR / f"dcc-c5-{name}"
        r = run_timed(["cgd", *flags, str(DCC_ROOT / "src/main.delegua"), "-s", str(out_bin)])
        assert r["returncode"] == 0, f"Build {name} falhou:\n{r['output']}"
        bins[name] = {
            "path": str(out_bin),
            "build_s": r["elapsed_s"],
            "size_bytes": out_bin.stat().st_size,
        }
        print(f"[build] {name}: {r['elapsed_s']}s, {out_bin.stat().st_size} B", flush=True)
    return bins


def bench_mode_a(bins: dict, reps: int) -> dict:
    res = {}
    # 1. Cycle IV Clang -O2 baseline (mesmos headers)
    c4_runs = []
    out_c4 = OUT_DIR / "mode_a_c4.o"
    for _ in range(reps):
        r = run_timed([str(C4_BIN), "-std=gnu99", "-O1", "-c", "-I", str(CGD_INC),
                       "-ftime-report", str(FROZEN_C), "-o", str(out_c4)])
        assert r["returncode"] == 0, r["output"]
        c4_runs.append(r)
    c4_sha = sha256_file(out_c4)
    res["cycle4_clang_O2"] = {**summarize(c4_runs), "sha256": c4_sha, "obj_bytes": out_c4.stat().st_size}
    print(f"[Mode A] Cycle IV clang-O2: {res['cycle4_clang_O2']['elapsed_s']['median']}s, "
          f"RSS={res['cycle4_clang_O2']['peak_rss_kb']['median']}KB, sha={c4_sha[:12]}", flush=True)

    # 2. Cycle V compilers (Clang -O2, GCC -O0, Clang -O0, TCC -O0)
    for cname in ("clang_O2", "gcc_O0", "clang_O0", "tcc_O0"):
        bpath = bins[cname]["path"]
        n_rep = reps if cname == "clang_O2" else 1
        runs = []
        out_o = OUT_DIR / f"mode_a_c5_{cname}.o"
        for _ in range(n_rep):
            r = run_timed([bpath, "-std=gnu99", "-O1", "-c", "-j", "1", "-I", str(CGD_INC),
                           "-ftime-report", str(FROZEN_C), "-o", str(out_o)])
            assert r["returncode"] == 0, r["output"]
            runs.append(r)
        sha = sha256_file(out_o)
        assert sha == c4_sha, f"SHA diverge em {cname}: {sha} != {c4_sha}"
        res[f"cycle5_{cname}_j1"] = {**summarize(runs), "sha256": sha, "obj_bytes": out_o.stat().st_size}
        print(f"[Mode A] Cycle V {cname} -j1: {res[f'cycle5_{cname}_j1']['elapsed_s']['median']}s, "
              f"RSS={res[f'cycle5_{cname}_j1']['peak_rss_kb']['median']}KB, sha={sha[:12]} (MATCH)", flush=True)

    # 3. Cycle V Clang -O2 across -j1, -j2, -j4, -j8, -j auto
    b_opt = bins["clang_O2"]["path"]
    j_res = {}
    for j in ("1", "2", "4", "8", "auto"):
        out_j = OUT_DIR / f"mode_a_c5_j{j}.o"
        r = run_timed([b_opt, "-std=gnu99", "-O1", "-c", "-j", j, "-I", str(CGD_INC),
                       "-ftime-report", str(FROZEN_C), "-o", str(out_j)])
        assert r["returncode"] == 0, r["output"]
        sha = sha256_file(out_j)
        assert sha == c4_sha, f"SHA diverge em -j{j}: {sha} != {c4_sha}"
        j_res[f"j_{j}"] = {**summarize([r]), "sha256": sha}
        print(f"[Mode A] Cycle V clang-O2 -j {j}: {r['elapsed_s']}s, RSS={r['peak_rss_kb']}KB (SHA MATCH)", flush=True)
    res["j_sweep"] = j_res
    return res


def bench_mode_b(b_opt: str, reps: int) -> dict:
    cur_c_base = OUT_DIR / "dcc_c5_current"
    r_emit = run_timed(["cgd", "-o", "--emitir-c", str(DCC_ROOT / "src/main.delegua"), "-s", str(cur_c_base)])
    assert r_emit["returncode"] == 0, r_emit["output"]
    cur_c = Path(str(cur_c_base) + ".c")
    c_lines = sum(1 for _ in cur_c.open("r", encoding="utf-8", errors="ignore"))

    runs = []
    out_o = OUT_DIR / "mode_b_c5.o"
    for _ in range(reps):
        r = run_timed([b_opt, "-std=gnu99", "-O1", "-c", "-j", "auto", "-I", str(CGD_INC),
                       "-ftime-report", str(cur_c), "-o", str(out_o)])
        assert r["returncode"] == 0, r["output"]
        runs.append(r)
    summary = summarize(runs)
    summary["c_lines"] = c_lines
    summary["c_bytes"] = cur_c.stat().st_size
    summary["obj_bytes"] = out_o.stat().st_size
    summary["sha256"] = sha256_file(out_o)
    summary["cgd_emit_s"] = r_emit["elapsed_s"]
    print(f"[Mode B] Cycle V clang-O2 ({c_lines} lines): {summary['elapsed_s']['median']}s, "
          f"RSS={summary['peak_rss_kb']['median']}KB", flush=True)
    return summary


def bench_multi_tu(b_opt: str, reps: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="dcc-bench-mtu-") as tmp:
        tdir = Path(tmp)
        n_units = 16
        srcs = []
        for u in range(n_units):
            lines = ["#include <stdio.h>", "#include <stdint.h>"]
            for fn_i in range(25):
                lines.append(
                    f"int mod{u}_fn{fn_i}(int x) {{\n"
                    f"    int acc = {u + fn_i + 1};\n"
                    f"    for (int i = 0; i < 16; i++) {{\n"
                    f"        acc = (acc * 31 + x + i) ^ (acc >> 3);\n"
                    f"    }}\n"
                    f"    return acc & 0xFFFF;\n"
                    f"}}"
                )
            lines.append(
                f"int mod{u}_total(int seed) {{\n"
                f"    int s = 0;\n"
                + "\n".join(f"    s += mod{u}_fn{fn_i}(seed + {fn_i});" for fn_i in range(25))
                + "\n    return s;\n}"
            )
            p = tdir / f"tu_{u:02d}.c"
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            srcs.append(str(p))

        decls = "\n".join(f"int mod{u}_total(int seed);" for u in range(n_units))
        calls = " + ".join(f"mod{u}_total({u + 1})" for u in range(n_units))
        main_c = tdir / "main.c"
        main_c.write_text(
            f"#include <stdio.h>\n{decls}\nint main(void) {{ printf(\"%d\\n\", {calls}); return 0; }}\n",
            encoding="utf-8",
        )
        srcs.append(str(main_c))

        res = {}
        ref_sha = None
        for label, extra in [
            ("j1", ["-j", "1"]),
            ("j2", ["-j", "2"]),
            ("j4", ["-j", "4"]),
            ("j8", ["-j", "8"]),
            ("auto", ["-j", "auto"]),
            ("taskset_2cpu_auto", ["-j", "auto"]),
        ]:
            runs = []
            exe = tdir / f"app_{label}"
            for _ in range(reps):
                cmd = ([b_opt, *extra, "-O1", *srcs, "-o", str(exe)]
                       if label != "taskset_2cpu_auto"
                       else ["taskset", "-c", "0,1", b_opt, *extra, "-O1", *srcs, "-o", str(exe)])
                r = run_timed(cmd)
                assert r["returncode"] == 0, f"Multi-TU {label} falhou:\n{r['output']}"
                runs.append(r)
            sha = sha256_file(exe)
            if ref_sha is None:
                ref_sha = sha
            assert sha == ref_sha, f"Multi-TU SHA diverge em {label}: {sha} != {ref_sha}"
            s = summarize(runs)
            s["sha256"] = sha
            res[label] = s
            print(f"[Multi-TU 17 files] {label}: {s['elapsed_s']['median']}s, "
                  f"RSS={s['peak_rss_kb']['median']}KB (SHA MATCH)", flush=True)
        return res


def bench_granularity(b_opt: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="dcc-bench-gran-") as tmp:
        tdir = Path(tmp)
        res = {}

        # 1. Small TU
        small_c = tdir / "small.c"
        small_c.write_text("int add(int a, int b) { return a + b; }\nint main(void) { return add(2, 3); }\n")
        # 2. Many small functions (400 fns)
        many_c = tdir / "many_small.c"
        mlines = []
        for i in range(400):
            mlines.append(f"int f_{i}(int x) {{ int s = x + {i}; for (int k = 0; k < 5; k++) s += k * 3; return s; }}")
        mlines.append("int main(void) { return f_0(1) + f_399(2); }")
        many_c.write_text("\n".join(mlines) + "\n")
        # 3. Few huge functions (4 fns x 400 stmts)
        huge_c = tdir / "few_huge.c"
        hlines = []
        for i in range(4):
            hlines.append(f"int big_{i}(int x) {{ int a = x + {i}; int b = 1;")
            for k in range(350):
                hlines.append(f"    a = (a + b + {k}) ^ (a >> 1); b = b + (a & 7) + 1;")
            hlines.append("    return a + b;\n}")
        hlines.append("int main(void) { return (big_0(1) + big_1(2) + big_2(3) + big_3(4)) & 127; }")
        huge_c.write_text("\n".join(hlines) + "\n")

        for name, cpath in [("small", small_c), ("many_small_400fns", many_c), ("few_huge_4fns", huge_c)]:
            out1 = tdir / f"{name}_j1.o"
            outa = tdir / f"{name}_auto.o"
            r1 = run_timed([b_opt, "-O1", "-c", "-j", "1", str(cpath), "-o", str(out1)])
            ra = run_timed([b_opt, "-O1", "-c", "-j", "auto", str(cpath), "-o", str(outa)])
            assert r1["returncode"] == 0 and ra["returncode"] == 0
            assert sha256_file(out1) == sha256_file(outa)
            res[name] = {
                "j1_s": r1["elapsed_s"], "j1_rss_kb": r1["peak_rss_kb"],
                "auto_s": ra["elapsed_s"], "auto_rss_kb": ra["peak_rss_kb"],
                "sha_match": True,
            }
            print(f"[Granularity] {name}: j1={r1['elapsed_s']}s auto={ra['elapsed_s']}s "
                  f"RSS={r1['peak_rss_kb']}KB", flush=True)
        return res


def bench_linker(b_opt: str, reps: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="dcc-bench-lnk-") as tmp:
        tdir = Path(tmp)
        helper_c = tdir / "helper.c"
        helper_c.write_text("int g_val = 7;\nint leaf(int x) { return x + g_val; }\n")
        helper_o = tdir / "helper.o"
        assert run_timed([b_opt, "-c", "-j1", str(helper_c), "-o", str(helper_o)])["returncode"] == 0

        # Pre-generate 300 .o files (~20 relocs each = ~6000 relocs total!)
        all_objs = []
        for i in range(300):
            lines = ["extern int leaf(int x);", f"int obj_{i}(int x) {{ int s = x;"]
            for k in range(18):
                lines.append(f"    s += leaf({(i + k) % 11});")
            lines.append("    return s;\n}")
            cp = tdir / f"o_{i:03d}.c"
            op = tdir / f"o_{i:03d}.o"
            cp.write_text("\n".join(lines) + "\n")
            all_objs.append((cp, op))

        # Compile the 300 .o files in parallel using DCC itself (-c -j 4)!
        rc = run_timed([b_opt, "-c", "-j", "4", *[str(p[0]) for p in all_objs]], cwd=tdir)
        assert rc["returncode"] == 0, rc["output"]
        obj_paths = [str(tdir / f"o_{i:03d}.o") for i in range(300)]

        res = {}
        for count in (1, 10, 100, 300):
            sub_objs = obj_paths[:count]
            decls = "\n".join(f"int obj_{i}(int x);" for i in range(count))
            calls = " + ".join(f"obj_{i}(1)" for i in range(count))
            mc = tdir / f"main_{count}.c"
            mo = tdir / f"main_{count}.o"
            mc.write_text(f"#include <stdio.h>\n{decls}\nint main(void) {{ printf(\"%d\\n\", {calls}); return 0; }}\n")
            assert run_timed([b_opt, "-c", "-j1", str(mc), "-o", str(mo)])["returncode"] == 0

            entry = {}
            # Cycle IV sequential linker
            exe_c4 = tdir / f"exec_{count}_c4"
            c4_runs = [run_timed([str(C4_BIN), str(mo), str(helper_o), *sub_objs, "-o", str(exe_c4)])
                       for _ in range(reps if count >= 100 else 1)]
            assert all(r["returncode"] == 0 for r in c4_runs)
            entry["cycle4_seq"] = summarize(c4_runs)

            # Cycle V linker (-j1, -j2, -j4, -j8, -j auto)
            ref_sha = None
            for j in ("1", "2", "4", "8", "auto"):
                exe_j = tdir / f"exec_{count}_j{j}"
                n_r = reps if (count >= 100 and j in ("1", "4", "auto")) else 1
                runs = [run_timed([b_opt, "-j", j, str(mo), str(helper_o), *sub_objs, "-o", str(exe_j)])
                        for _ in range(n_r)]
                assert all(r["returncode"] == 0 for r in runs), runs[0]["output"]
                sha = sha256_file(exe_j)
                if ref_sha is None:
                    ref_sha = sha
                assert sha == ref_sha, f"Linker SHA diverge count={count} -j{j}"
                entry[f"cycle5_j{j}"] = {**summarize(runs), "sha256": sha}

            res[f"objs_{count}"] = entry
            print(
                f"[Linker {count:3d} .o] C4={entry['cycle4_seq']['elapsed_s']['median']}s "
                f"(RSS={entry['cycle4_seq']['peak_rss_kb']['median']}KB) | "
                f"C5 j1={entry['cycle5_j1']['elapsed_s']['median']}s "
                f"j2={entry['cycle5_j2']['elapsed_s']['median']}s "
                f"j4={entry['cycle5_j4']['elapsed_s']['median']}s "
                f"j8={entry['cycle5_j8']['elapsed_s']['median']}s "
                f"(RSS j1={entry['cycle5_j1']['peak_rss_kb']['median']}KB)",
                flush=True,
            )
        return res


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    bins = build_c5_binaries()
    b_opt = bins["clang_O2"]["path"]

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reps": reps,
        "binaries": bins,
        "mode_a": bench_mode_a(bins, reps),
        "mode_b": bench_mode_b(b_opt, reps),
        "multi_tu": bench_multi_tu(b_opt, reps),
        "granularity": bench_granularity(b_opt),
        "linker": bench_linker(b_opt, reps),
    }

    out_json = OUT_DIR / "bench_paralelismo.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nRelatorio salvo em: {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
