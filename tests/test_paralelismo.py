#!/usr/bin/env python3
"""Suite de testes Ciclo V: paralelismo multi-TU, linker paralelo, determinismo bit a bit,
politica adaptativa de recursos (-j 1/2/4/8/auto, --parallel=off) e seguranca ELF concorrente.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DCC = str(ROOT / "build" / "dcc")
passed = 0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd, env=None, cwd=None, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd, timeout=timeout)


def ok(name: str, detail: str = ""):
    global passed
    passed += 1
    suf = f" ({detail})" if detail else ""
    print(f"[OK] {name}{suf}")


def test_cli_flags_invalidos():
    for bad in (["-j", "0"], ["-j", "-3"], ["-j", "xyz"], ["-j0"], ["-jabc"]):
        r = run_cmd([DCC, *bad, "inexistente.c"])
        assert r.returncode == 1, f"Esperado erro para {bad}, recebeu {r.returncode}"
        assert "invalido" in r.stderr.lower(), f"Stderr inesperado para {bad}: {r.stderr}"
    ok("cli_flags_j_invalidos")


def test_politica_recursos_taskset():
    with tempfile.TemporaryDirectory(prefix="dcc-par-cpu-") as tmp:
        cfile = Path(tmp) / "t.c"
        cfile.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        out = Path(tmp) / "t.o"
        r = run_cmd(["taskset", "-c", "0,1", DCC, "-j", "auto", "-v", "-c", str(cfile), "-o", str(out)])
        assert r.returncode == 0, r.stderr
        assert "cpusEff=2" in r.stderr, f"Afinidade nao detectada: {r.stderr}"
        assert "workers=1" in r.stderr, f"Politica conservadora para 2 CPUs violada: {r.stderr}"
    ok("politica_recursos_taskset_2cpus", "cpusEff=2 -> workers=1")


def test_multitu_determinismo_e_execucao():
    with tempfile.TemporaryDirectory(prefix="dcc-par-mtu-") as tmp:
        tdir = Path(tmp)
        srcs = []
        n_units = 16
        for i in range(n_units):
            p = tdir / f"mod_{i:02d}.c"
            p.write_text(
                f"static int segredo_{i} = {i + 7};\n"
                f"int fn_{i}(int x) {{\n"
                f"    int acc = segredo_{i};\n"
                f"    for (int k = 0; k < 12; k++) acc += (x + k) * {(i % 5) + 1};\n"
                f"    return acc;\n"
                f"}}\n",
                encoding="utf-8",
            )
            srcs.append(str(p))

        decls = "\n".join(f"int fn_{i}(int x);" for i in range(n_units))
        calls = " + ".join(f"fn_{i}({i + 1})" for i in range(n_units))
        main_c = tdir / "main.c"
        main_c.write_text(
            f"#include <stdio.h>\n{decls}\nint main(void) {{\n"
            f"    int s = {calls};\n"
            f"    printf(\"SUM=%d\\n\", s);\n"
            f"    return s & 127;\n"
            f"}}\n",
            encoding="utf-8",
        )
        srcs.append(str(main_c))

        hashes = {}
        outputs = {}
        modes = [
            ("j1", ["-j", "1"]),
            ("j2", ["-j", "2"]),
            ("j4", ["-j", "4"]),
            ("j8", ["-j", "8"]),
            ("auto", ["-j", "auto"]),
            ("off", ["--parallel=off"]),
            ("par_auto", ["--parallel=auto"]),
        ]
        for label, flags in modes:
            exe = tdir / f"app_{label}"
            r = run_cmd([DCC, *flags, "-O1", *srcs, "-o", str(exe)])
            assert r.returncode == 0, f"Falha em {label}: {r.stderr}"
            hashes[label] = sha256_file(exe)
            run_e = run_cmd([str(exe)])
            outputs[label] = (run_e.returncode, run_e.stdout.strip())

        # Tambem valida DCC_JOBS=4
        env = os.environ.copy()
        env["DCC_JOBS"] = "4"
        exe_env = tdir / "app_env"
        r_env = run_cmd([DCC, "-O1", *srcs, "-o", str(exe_env)], env=env)
        assert r_env.returncode == 0, r_env.stderr
        hashes["env4"] = sha256_file(exe_env)

        base_hash = hashes["j1"]
        for k, h in hashes.items():
            assert h == base_hash, f"Nao-determinismo em {k}: {h} != {base_hash}"
        assert len(set(outputs.values())) == 1, f"Saidas divergentes: {outputs}"
        ok("multitu_17_arquivos_determinismo", f"sha256={base_hash[:12]}.. out={outputs['j1'][1]}")


def test_multitu_erros_ordenados_e_limpeza_tmp():
    with tempfile.TemporaryDirectory(prefix="dcc-par-err-") as tmp:
        tdir = Path(tmp)
        f1 = tdir / "a_ok.c"
        f2 = tdir / "b_err1.c"
        f3 = tdir / "c_ok.c"
        f4 = tdir / "d_err2.c"
        f1.write_text("int f1(void) { return 1; }\n", encoding="utf-8")
        f2.write_text("int f2(void) { return variavel_inexistente_alpha; }\n", encoding="utf-8")
        f3.write_text("int f3(void) { return 3; }\n", encoding="utf-8")
        f4.write_text("int f4(void) { return variavel_inexistente_beta; }\n", encoding="utf-8")

        before_tmp = set(Path("/tmp").glob("dcc_tu_*.o"))
        r = run_cmd([DCC, "-j", "4", str(f1), str(f2), str(f3), str(f4), "-o", str(tdir / "out")])
        after_tmp = set(Path("/tmp").glob("dcc_tu_*.o"))
        assert r.returncode == 1, f"Esperado exit 1, recebeu {r.returncode}"
        pos_a = r.stderr.find("variavel_inexistente_alpha")
        pos_b = r.stderr.find("variavel_inexistente_beta")
        assert pos_a >= 0 and pos_b >= 0 and pos_a < pos_b, (
            f"Ordem deterministica de erros violada:\n{r.stderr}"
        )
        assert after_tmp <= before_tmp, f"Arquivos temporarios vazaram: {after_tmp - before_tmp}"
        ok("multitu_erros_ordenados_e_sem_vazamento_tmp")


def test_linker_paralelo_muitos_objetos_archive_e_relocs():
    """Testa linker paralelo com 40 objetos + .a encadeado + weak + >= 2500 relocacoes."""
    with tempfile.TemporaryDirectory(prefix="dcc-par-lnk-") as tmp:
        tdir = Path(tmp)
        objs = []
        # 20 objetos com 140 relocacoes cada (> 2800 relocs totais -> ativa prepararPatchesRelocWorker!)
        helper_c = tdir / "helper.c"
        helper_c.write_text(
            "int g_base = 3;\n"
            "int __attribute__((weak)) hook_fn(int v) { return v + 1; }\n"
            "int leaf_op(int v) { return v + g_base; }\n",
            encoding="utf-8",
        )
        helper_o = tdir / "helper.o"
        assert run_cmd([DCC, "-std=gnu99", "-c", str(helper_c), "-o", str(helper_o)]).returncode == 0
        objs.append(str(helper_o))

        # 20 objetos pesados em relocacoes
        for i in range(20):
            body = ["extern int leaf_op(int v);", f"int heavy_{i}(int x) {{ int s = x;"]
            for k in range(130):
                body.append(f"    s += leaf_op({(i + k) % 7});")
            body.append("    return s;\n}")
            c_p = tdir / f"heavy_{i:02d}.c"
            o_p = tdir / f"heavy_{i:02d}.o"
            c_p.write_text("\n".join(body) + "\n", encoding="utf-8")
            r = run_cmd([DCC, "-c", "-j1", str(c_p), "-o", str(o_p)])
            assert r.returncode == 0, r.stderr
            objs.append(str(o_p))

        # Biblioteca estatica .a com dependencia encadeada (ar_b chama ar_a) + override forte de hook_fn
        ar_a_c = tdir / "ar_a.c"
        ar_b_c = tdir / "ar_b.c"
        ar_unused_c = tdir / "ar_unused.c"
        ar_a_c.write_text("int ar_a_fn(int x) { return x * 2 + 5; }\n", encoding="utf-8")
        ar_b_c.write_text(
            "int ar_a_fn(int x);\n"
            "int hook_fn(int v) { return v + 10; }\n"
            "int ar_b_fn(int x) { return ar_a_fn(x) + 1; }\n",
            encoding="utf-8",
        )
        ar_unused_c.write_text("int nunca_usada(void) { return 999; }\n", encoding="utf-8")
        ar_objs = []
        for src in (ar_a_c, ar_b_c, ar_unused_c):
            op = src.with_suffix(".o")
            assert run_cmd([DCC, "-c", "-j1", str(src), "-o", str(op)]).returncode == 0
            ar_objs.append(str(op))
        lib_a = tdir / "libchain.a"
        assert run_cmd(["ar", "rcs", str(lib_a), *ar_objs]).returncode == 0

        decls = "\n".join(f"int heavy_{i}(int x);" for i in range(20))
        calls = " + ".join(f"heavy_{i}(1)" for i in range(20))
        main_c = tdir / "main.c"
        main_o = tdir / "main.o"
        main_c.write_text(
            f"#include <stdio.h>\n"
            f"int ar_b_fn(int x);\n"
            f"int hook_fn(int v);\n"
            f"{decls}\n"
            f"int main(void) {{\n"
            f"    int tot = ({calls}) + ar_b_fn(4) + hook_fn(2);\n"
            f"    printf(\"LNK=%d\\n\", tot);\n"
            f"    return 0;\n"
            f"}}\n",
            encoding="utf-8",
        )
        assert run_cmd([DCC, "-c", "-j1", str(main_c), "-o", str(main_o)]).returncode == 0

        # Linka com -j1, -j2, -j4, -j8 (exercitando workers paralelos via DCC_FORCE_PAR_LINKER=1)
        env_par = os.environ.copy()
        env_par["DCC_FORCE_PAR_LINKER"] = "1"
        hashes = {}
        outs = {}
        for j in (1, 2, 4, 8):
            exe = tdir / f"linked_j{j}"
            r = run_cmd([DCC, "-j", str(j), str(main_o), *objs, str(lib_a), "-o", str(exe)], env=env_par)
            assert r.returncode == 0, f"Linker falhou com -j{j}: {r.stderr}"
            hashes[j] = sha256_file(exe)
            re = run_cmd([str(exe)])
            assert re.returncode == 0, re.stderr
            outs[j] = re.stdout.strip()

        assert len(set(hashes.values())) == 1, f"Linker nao-deterministico: {hashes}"
        assert len(set(outs.values())) == 1, f"Saida divergente: {outs}"
        ok("linker_paralelo_2600plus_relocs_archive_weak", f"sha256={hashes[1][:12]}.. {outs[1]}")

        # Seguranca: ELF hostil misturado com 6 objetos validos em modo paralelo (-j4)
        bad_o = tdir / "corrompido.o"
        bad_o.write_bytes(b"\x7fELF\x02\x01\x01" + b"\x00" * 20)
        r_bad = run_cmd([DCC, "-j", "4", str(main_o), *objs[:6], str(bad_o), "-o", str(tdir / "bad_out")], env=env_par)
        assert r_bad.returncode == 1, f"ELF hostil nao rejeitado em -j4: rc={r_bad.returncode}"
        ok("linker_paralelo_rejeita_elf_hostil")


def main() -> int:
    test_cli_flags_invalidos()
    test_politica_recursos_taskset()
    test_multitu_determinismo_e_execucao()
    test_multitu_erros_ordenados_e_limpeza_tmp()
    test_linker_paralelo_muitos_objetos_archive_e_relocs()
    print(f"\nResumo Paralelismo/Determinismo DCC: {passed}/{passed} aprovados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
