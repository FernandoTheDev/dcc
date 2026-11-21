#!/usr/bin/env python3
"""Suite independente de conformidade, diferencial (GCC + Clang), ABI, headers reais
do sistema (/usr/include), extensoes GNU (Cat A/B/C), linker ELF64 e diagnosticos do DCC.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ_DCC = Path(__file__).resolve().parents[1]
DCC_BIN = RAIZ_DCC / "build" / "dcc"


def rodar_bin(caminho: Path) -> tuple[int, str]:
    res = subprocess.run([str(caminho)], capture_output=True, text=True, timeout=10, check=False)
    return res.returncode, res.stdout


CASOS_DIFERENCIAIS: list[tuple[str, str, list[str]]] = [
    (
        "sys_headers_hello_libc",
        r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    char *mem = malloc(32);
    if (mem == NULL)
        return 1;
    strcpy(mem, "DCC");
    printf("%s\n", mem);
    free(mem);
    return 0;
}
""",
        [],
    ),
    (
        "sys_headers_stdout_fprintf_fflush",
        r"""
#include <stdio.h>
int main(void) {
    fprintf(stdout, "via-stdout:%d\n", 2026);
    fflush(stdout);
    return 17;
}
""",
        [],
    ),
    (
        "sys_headers_stdint_stdbool_limits_iso646_float",
        r"""
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <limits.h>
#include <iso646.h>
#include <float.h>
#include <inttypes.h>
int main(void) {
    int8_t a = -5;
    uint8_t b = 250;
    int16_t c = -300;
    uint16_t d = 60000;
    int32_t e = -100000;
    uint32_t f = 3000000000U;
    int64_t g = -5000000000LL;
    uint64_t h = 5000000000ULL;
    bool ok = (a < 0) and (b == 250) and (not false);
    printf("%d %u %d %u %" PRId32 " %" PRIu32 " %" PRId64 " %" PRIu64 " %d %d %d\n",
           (int)a, (unsigned)b, (int)c, (unsigned)d, e, f, g, h,
           (int)ok, CHAR_BIT, DBL_DIG);
    return (int)ok + CHAR_BIT + DBL_DIG;
}
""",
        [],
    ),
    (
        "sys_headers_ctype_assert_errno_signal",
        r"""
#include <stdio.h>
#include <ctype.h>
#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <string.h>
int main(void) {
    assert(isdigit('9') != 0);
    assert(isalpha('A') != 0);
    assert(isspace(' ') != 0);
    char s[] = "dcc";
    s[0] = (char)toupper(s[0]);
    printf("%s sig=%d err=%d\n", s, SIGINT, ENOENT);
    return SIGINT + ENOENT;
}
""",
        [],
    ),
    (
        "sys_headers_math_time_libm",
        r"""
#include <stdio.h>
#include <math.h>
#include <time.h>
int main(void) {
    double s = sqrt(144.0);
    double p = pow(2.0, 6.0);
    double fl = floor(4.9);
    double cl = ceil(4.1);
    double fa = fabs(-7.5);
    double dt = difftime(300, 220);
    time_t now = time(NULL);
    int tok = (now > 1000000000L) ? 1 : 0;
    printf("%.1f %.1f %.1f %.1f %.1f %.1f %d\n", s, p, fl, cl, fa, dt, tok);
    return (int)(s + p + fl + cl + fa + dt) + tok;
}
""",
        ["-lm"],
    ),
    (
        "sys_headers_stdarg_vsnprintf_glibc",
        r"""
#include <stdio.h>
#include <stdarg.h>

int somar_n(int n, ...) {
    va_list ap, cp;
    va_start(ap, n);
    va_copy(cp, ap);
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += va_arg(ap, int);
    }
    int primeiro = va_arg(cp, int);
    va_end(cp);
    va_end(ap);
    return total + primeiro;
}

int meu_fmt(char *buf, size_t sz, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int r = vsnprintf(buf, sz, fmt, ap);
    va_end(ap);
    return r;
}

int main(void) {
    int s = somar_n(8, 1, 2, 3, 4, 5, 6, 7, 8); // 36 + 1 = 37
    char out[64];
    int len = meu_fmt(out, 64, "dcc:%s:%d:%.2f", "va", s, 3.25);
    printf("%s (%d)\n", out, len);
    return s + len;
}
""",
        [],
    ),
    (
        "pp_c99_trigraphs_macros_variadicas_defined_undef",
        r"""
??=include <stdio.h>
??=define VAL \
    (10 + 5)
#define STR(x) #x
#define COLAR(a, b) a##b
#define LOG(f, ...) printf(f, __VA_ARGS__)
#if defined(DEF_CLI) && !defined(REMOVIDA) && (VAL == 15)
int escolhido(void) { return DEF_CLI + VAL; }
#else
int escolhido(void) { return 0; }
#endif
int main(void) ??<
    int COLAR(v_, 1) = escolhido();
    LOG("%s=%d stdc=%ld\n", STR(ok), v_1, (long)__STDC_VERSION__);
    return v_1;
??>
""",
        ["-DDEF_CLI=25", "-DREMOVIDA=1", "-UREMOVIDA"],
    ),
    (
        "tipos_lp64_padding_offsetof_bitfields",
        r"""
#include <stdio.h>
#include <stddef.h>

struct Mix {
    char a;
    int b;
    char c;
    double d;
    short e;
};

struct Bits {
    unsigned int baixo : 3;
    unsigned int meio  : 5;
    int sinal          : 4;
};

int main(void) {
    struct Mix m = { .a = 'A', .b = 42, .c = 'Z', .d = 2.5, .e = -9 };
    struct Bits bf;
    bf.baixo = 5;
    bf.meio = 21;
    bf.sinal = -3;
    printf("sz=%lu off=%lu,%lu,%lu,%lu,%lu bf=%u,%u,%d szbf=%lu\n",
           (unsigned long)sizeof(struct Mix),
           (unsigned long)offsetof(struct Mix, a),
           (unsigned long)offsetof(struct Mix, b),
           (unsigned long)offsetof(struct Mix, c),
           (unsigned long)offsetof(struct Mix, d),
           (unsigned long)offsetof(struct Mix, e),
           bf.baixo, bf.meio, bf.sinal,
           (unsigned long)sizeof(struct Bits));
    return (int)sizeof(struct Mix) + (int)bf.baixo + (int)bf.meio + bf.sinal;
}
""",
        [],
    ),
    (
        "gnu_cat_a_e_cat_b_packed_aligned",
        r"""
#include <stdio.h>
#include <stddef.h>

struct __attribute__((packed)) Empacotada {
    char a;
    int b;
    short c;
};

struct __attribute__((aligned(16))) Alinhada {
    int x;
};

__attribute__((unused)) static int auxiliar(int v) {
    return v + 1;
}

int main(void) {
    struct Empacotada e;
    e.a = 1;
    e.b = 1000;
    e.c = 7;
    printf("pack_sz=%lu pack_off=%lu,%lu,%lu al_sz=%lu vals=%d,%d,%d\n",
           (unsigned long)sizeof(struct Empacotada),
           (unsigned long)offsetof(struct Empacotada, a),
           (unsigned long)offsetof(struct Empacotada, b),
           (unsigned long)offsetof(struct Empacotada, c),
           (unsigned long)sizeof(struct Alinhada),
           (int)e.a, e.b, (int)e.c);
    return (int)sizeof(struct Empacotada) + (int)sizeof(struct Alinhada);
}
""",
        ["-std=gnu99"],
    ),
    (
        "c99_vla_literais_compostos_static_func_struct_valor",
        r"""
#include <stdio.h>

struct Par {
    int x;
    int y;
};

struct Par somar_par(struct Par a, struct Par b) {
    struct Par r = { .x = a.x + b.x, .y = a.y + b.y };
    return r;
}

int contar(void) {
    static int c = 10;
    c += 3;
    return c;
}

int testar_vla(int n) {
    int v[n];
    int s = 0;
    for (int i = 0; i < n; i++) {
        v[i] = i + 1;
        s += v[i];
    }
    return s + (int)sizeof(v);
}

int main(void) {
    struct Par p = somar_par((struct Par){ 4, 6 }, (struct Par){ 10, 20 });
    int c1 = contar();
    int c2 = contar();
    int vl = testar_vla(6); // 21 + 24 = 45
    printf("p=(%d,%d) c=%d,%d vla=%d fn=%s\n", p.x, p.y, c1, c2, vl, __func__);
    return p.x + p.y + c2 + vl;
}
""",
        [],
    ),
    (
        "abi_qsort_callback_e_10_args_pilha",
        r"""
#include <stdio.h>
#include <stdlib.h>

int cmp_asc(const void *pa, const void *pb) {
    int a = *(const int *)pa;
    int b = *(const int *)pb;
    return (a > b) - (a < b);
}

int soma10(int a1, int a2, int a3, int a4, int a5, int a6, int a7, int a8, int a9, int a10) {
    return a1 + a2 * 2 + a3 * 3 + a4 * 4 + a5 * 5 + a6 * 6 + a7 * 7 + a8 * 8 + a9 * 9 + a10 * 10;
}

int main(void) {
    int xs[5] = { 30, -4, 12, 0, 7 };
    qsort(xs, 5, sizeof(int), cmp_asc);
    int s = soma10(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
    printf("%d %d %d %d %d | %d\n", xs[0], xs[1], xs[2], xs[3], xs[4], s);
    return (s % 200) + xs[4];
}
""",
        [],
    ),
]


def rodar_diferenciais(tmp: Path) -> int:
    falhas = 0
    for nome, codigo, flags in CASOS_DIFERENCIAIS:
        arq_c = tmp / f"{nome}.c"
        arq_c.write_text(codigo, encoding="utf-8")

        refs: dict[str, tuple[int, str]] = {}
        for comp in ("gcc", "clang"):
            std_flag = "-std=gnu99" if "-std=gnu99" in flags else "-std=c99"
            flags_ref = [f for f in flags if not f.startswith("-std=")]
            bin_ref = tmp / f"{nome}_{comp}"
            r = subprocess.run(
                [comp, std_flag, "-O0", str(arq_c), *flags_ref, "-o", str(bin_ref)],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode != 0:
                print(f"[FALHA REF {comp}] {nome}:\n{r.stderr}")
                falhas += 1
                break
            refs[comp] = rodar_bin(bin_ref)

        if len(refs) < 2:
            continue
        if refs["gcc"] != refs["clang"]:
            print(f"[AVISO REF] GCC vs Clang divergem em {nome}: {refs}")

        ec_ref, out_ref = refs["gcc"]
        for opt in ("-O0", "-O2"):
            bin_dcc = tmp / f"{nome}_dcc_{opt[1:]}"
            r = subprocess.run(
                [str(DCC_BIN), opt, *flags, str(arq_c), "-o", str(bin_dcc)],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode != 0:
                print(f"[FALHA DCC] {nome} ({opt}):\n{r.stdout}\n{r.stderr}")
                falhas += 1
                continue
            ec_dcc, out_dcc = rodar_bin(bin_dcc)
            if ec_dcc != ec_ref or out_dcc != out_ref:
                print(f"[DIVERGENCIA] {nome} ({opt}):")
                print(f"  REF: exit={ec_ref} stdout={out_ref!r}")
                print(f"  DCC: exit={ec_dcc} stdout={out_dcc!r}")
                falhas += 1
            else:
                print(f"[OK] {nome} ({opt}) vs GCC+Clang -> exit={ec_dcc}")
    return falhas


def rodar_testes_linker_cruzado(tmp: Path) -> int:
    falhas = 0
    (tmp / "mod_calc.c").write_text(
        "int g_mult = 5;\nint calc(int x, int y) { return (x + y) * g_mult; }\n",
        encoding="utf-8",
    )
    (tmp / "mod_main.c").write_text(
        '#include <stdio.h>\nextern int g_mult;\nextern int calc(int x, int y);\n'
        'int main(void) { int r = calc(4, 6); printf("r=%d m=%d\\n", r, g_mult); return r; }\n',
        encoding="utf-8",
    )

    obj_calc_dcc = tmp / "calc_dcc.o"
    obj_main_dcc = tmp / "main_dcc.o"
    obj_calc_gcc = tmp / "calc_gcc.o"
    obj_calc_clang = tmp / "calc_clang.o"

    subprocess.run([str(DCC_BIN), "-c", str(tmp / "mod_calc.c"), "-o", str(obj_calc_dcc)], check=True)
    subprocess.run([str(DCC_BIN), "-c", str(tmp / "mod_main.c"), "-o", str(obj_main_dcc)], check=True)
    subprocess.run(["gcc", "-std=c99", "-c", str(tmp / "mod_calc.c"), "-o", str(obj_calc_gcc)], check=True)
    subprocess.run(["clang", "-std=c99", "-c", str(tmp / "mod_calc.c"), "-o", str(obj_calc_clang)], check=True)

    combos = [
        ("linker_dcc_dcc", [str(DCC_BIN), str(obj_main_dcc), str(obj_calc_dcc), "-o", str(tmp / "l1")], tmp / "l1"),
        ("linker_gcc_sobre_dcc_o", ["gcc", str(obj_main_dcc), str(obj_calc_dcc), "-o", str(tmp / "l2")], tmp / "l2"),
        ("linker_dcc_com_gcc_o", [str(DCC_BIN), str(obj_main_dcc), str(obj_calc_gcc), "-o", str(tmp / "l3")], tmp / "l3"),
        ("linker_dcc_com_clang_o", [str(DCC_BIN), str(obj_main_dcc), str(obj_calc_clang), "-o", str(tmp / "l4")], tmp / "l4"),
    ]
    for nome, cmd, out_bin in combos:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            print(f"[FALHA {nome}] {r.stdout}\n{r.stderr}")
            falhas += 1
            continue
        ec, out = rodar_bin(out_bin)
        if ec != 50 or out != "r=50 m=5\n":
            print(f"[FALHA EXEC {nome}] ec={ec} out={out!r}")
            falhas += 1
        else:
            print(f"[OK] {nome} -> exit={ec}")

    # Auditoria ELF64 no .o e no executavel linkado pelo DCC
    env_c = dict(os.environ)
    env_c["LC_ALL"] = "C"
    rh_obj = subprocess.run(["readelf", "-h", str(obj_main_dcc)], capture_output=True, text=True, env=env_c, check=True).stdout
    rph = subprocess.run(["readelf", "-W", "-l", str(tmp / "l1")], capture_output=True, text=True, env=env_c, check=True).stdout
    rsh = subprocess.run(["readelf", "-W", "-S", str(tmp / "l1")], capture_output=True, text=True, env=env_c, check=True).stdout
    rldd = subprocess.run(["ldd", str(tmp / "l1")], capture_output=True, text=True, env=env_c, check=True).stdout
    if "REL (Relocatable file)" not in rh_obj or "RWE" in rph or ".shstrtab" not in rsh or "libc.so.6" not in rldd:
        print("[FALHA AUDITORIA ELF64]")
        falhas += 1
    else:
        print("[OK] auditoria_elf64_et_rel_e_et_exec")
    return falhas


def rodar_testes_diagnosticos_e_cli(tmp: Path) -> int:
    falhas = 0
    casos_neg = [
        ("diag_var_indefinida", "int main(void) {\n    return nao_existe;\n}\n", ["error:", "nao_existe", "^"], []),
        ("diag_gnu_cat_c", "int __attribute__((vector_size(16))) x;\nint main(void) { return 0; }\n", ["Categoria C", "vector_size"], ["-std=gnu99"]),
        ("diag_inline_asm_cat_c", 'int main(void) { __asm__("nop"); return 0; }\n', ["Categoria C", "inline assembly"], ["-std=gnu99"]),
        ("diag_pp_error", '#error "falha intencional"\nint main(void) { return 0; }\n', ["#error", "falha intencional"], []),
        ("diag_werror_warning", '#warning "aviso"\nint main(void) { return 0; }\n', ["-Werror"], ["-Werror"]),
        ("cli_flag_g_nao_suportada", "int main(void) { return 0; }\n", ["DWARF", "-g"], ["-g"]),
        ("cli_flag_desconhecida", "int main(void) { return 0; }\n", ["opcao desconhecida"], ["--flag-invalida"]),
    ]
    for nome, codigo, trechos, flags in casos_neg:
        arq = tmp / f"{nome}.c"
        arq.write_text(codigo, encoding="utf-8")
        r = subprocess.run(
            [str(DCC_BIN), *flags, str(arq), "-o", str(tmp / f"{nome}.out")],
            capture_output=True,
            text=True,
            check=False,
        )
        comb = r.stdout + "\n" + r.stderr
        ok = r.returncode != 0 and all(t in comb for t in trechos)
        if not ok:
            print(f"[FALHA NEG {nome}] rc={r.returncode} saida={comb!r}")
            falhas += 1
        else:
            print(f"[OK] negativo:{nome}")

    # Testa -S (assembly) e independencia de diretorio de trabalho (executa de /tmp!)
    asm_file = tmp / "teste.s"
    arq_ok = tmp / "ok_cwd.c"
    arq_ok.write_text('#include <stdio.h>\nint main(void) { puts("cwd-ok"); return 0; }\n', encoding="utf-8")
    r_s = subprocess.run([str(DCC_BIN), "-S", str(arq_ok), "-o", str(asm_file)], cwd="/tmp", capture_output=True, text=True, check=False)
    if r_s.returncode != 0 or "section .text" not in asm_file.read_text(encoding="utf-8"):
        print(f"[FALHA -S cwd=/tmp] {r_s.stderr}")
        falhas += 1
    else:
        print("[OK] backend_asm_e_independencia_cwd")
    return falhas


def main() -> int:
    if not DCC_BIN.exists():
        print(f"Binario nao encontrado: {DCC_BIN}. Execute ./bootstrap/build.sh primeiro.")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="dcc_tests_"))
    try:
        falhas = 0
        falhas += rodar_diferenciais(tmp)
        falhas += rodar_testes_linker_cruzado(tmp)
        falhas += rodar_testes_diagnosticos_e_cli(tmp)
        total = len(CASOS_DIFERENCIAIS) * 2 + 5 + 8
        print(f"\nResumo DCC: {total - falhas}/{total} verificacoes aprovadas, {falhas} falhas.")
        return 1 if falhas > 0 else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
