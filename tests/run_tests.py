#!/usr/bin/env python3
"""Suite completa de conformidade, diferencial (GCC + Clang em -O0/-O1/-O2), ABI bidirecional,
headers reais do sistema (/usr/include), extensoes GNU (Cat A/B/C), linker ELF64 + arquivos .a
e diagnosticos profissionais (texto, cores ANSI, JSON, trilha de inclusao) do DCC.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ_DCC = Path(__file__).resolve().parents[1]
DCC_BIN = RAIZ_DCC / "build" / "dcc"


def rodar_bin(caminho: Path, args: list[str] | None = None) -> tuple[int, str]:
    cmd = [str(caminho), *(args or [])]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    return res.returncode, res.stdout


CASOS_DIFERENCIAIS: list[tuple[str, str, list[str], list[str]]] = [
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
        [],
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
    int s = somar_n(8, 1, 2, 3, 4, 5, 6, 7, 8);
    char out[64];
    int len = meu_fmt(out, 64, "dcc:%s:%d:%.2f", "va", s, 3.25);
    printf("%s (%d)\n", out, len);
    return s + len;
}
""",
        [],
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
#if defined(DEF_CLI) && !defined(REMOVIDA) && (VAL == 15) && (-1 < 0U) == 0
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
        [],
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
        [],
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
    int vl = testar_vla(6);
    printf("p=(%d,%d) c=%d,%d vla=%d fn=%s\n", p.x, p.y, c1, c2, vl, __func__);
    return p.x + p.y + c2 + vl;
}
""",
        [],
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
        [],
    ),
    # --- Novos casos diferenciais do Ciclo III (regressao dos bugs criticos corrigidos) ---
    (
        "c99_ieee754_nan_inf_float32_hexfloat_u64",
        r"""
#include <stdio.h>
#include <stdint.h>
#include <math.h>

float add_f32(float a, float b) {
    return a + b * 2.0f;
}

int main(void) {
    double zero = 0.0;
    double nan_v = zero / zero;
    double inf_v = 1.0 / zero;
    int nan_eq = (nan_v == nan_v);
    int nan_ne = (nan_v != nan_v);
    int nan_lt = (nan_v < 1.0);
    int nan_le = (nan_v <= 1.0);
    int nan_gt = (nan_v > 1.0);
    int nan_ge = (nan_v >= 1.0);
    int inf_ok = (inf_v > 1e100) && (-inf_v < -1e100);

    double hf = 0x1.fp+3;       // 1.9375 * 8 = 15.5
    float hff = 0x1.8p-1f;      // 1.5 * 0.5 = 0.75
    float sf = add_f32(1.25f, hff);
    float sqf = sqrtf(9.0f);

    uint64_t bigu = 10000000000000000000ULL;
    double bigd = (double)bigu;
    int u_ok = (bigd > 9e18);
    uint64_t back = (uint64_t)1.0e19;
    int back_ok = (back > 9000000000000000000ULL);

    printf("nan=%d,%d,%d,%d,%d,%d inf=%d hf=%.2f sf=%.2f sqf=%.1f u=%d,%d\n",
           nan_eq, nan_ne, nan_lt, nan_le, nan_gt, nan_ge,
           inf_ok, hf, (double)sf, (double)sqf, u_ok, back_ok);
    return nan_ne + inf_ok + u_ok + back_ok + (int)sqf;
}
""",
        ["-lm"],
        [],
    ),
    (
        "c99_int32_unsigned_wraparound_bitops_ret_trunc",
        r"""
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>

signed char ret_char(int x) { return x; }
bool ret_bool(int x) { return x; }

int main(void) {
    unsigned int umax = 0xFFFFFFFFu;
    int inv_zero = (~umax == 0u);
    unsigned int hi = 0x80000000u;
    int shl_zero = ((hi << 1) == 0u);
    unsigned int u0 = 0u;
    unsigned long sub_wrap = (unsigned long)(u0 - 1u);
    unsigned int shr_v = umax >> 1;
    int sdiv = (-7) / 2;
    unsigned int udiv = 0xFFFFFFFFu / 2u;

    int rc = (int)ret_char(300);  // 44
    int rb = (int)ret_bool(5);    // 1
    printf("inv=%d shl=%d wrap=%lu shr=%u sdiv=%d udiv=%u rc=%d rb=%d\n",
           inv_zero, shl_zero, sub_wrap, shr_v, sdiv, udiv, rc, rb);
    return inv_zero + shl_zero + rc + rb;
}
""",
        [],
        [],
    ),
    (
        "c99_strings_escapes_sizeof_ptr_arith",
        r"""
#include <stdio.h>
#include <stddef.h>

int main(void) {
    size_t sz1 = sizeof("hello");
    const char s_nul[] = "a\0b";
    size_t sz2 = sizeof(s_nul);
    const char *esc = "\x41\102"; // "AB"
    int arr[5] = { 10, 20, 30, 40, 50 };
    int v_comm = 2[arr];          // 30
    int *p = 1 + arr;             // &arr[1]
    p += 3;                       // &arr[4]
    p -= 1;                       // &arr[3]
    ptrdiff_t diff = p - arr;     // 3
    printf("sz=%lu,%lu nul=%d,%d,%d esc=%s v=%d p=%d diff=%ld\n",
           (unsigned long)sz1, (unsigned long)sz2,
           (int)s_nul[0], (int)s_nul[1], (int)s_nul[2],
           esc, v_comm, *p, (long)diff);
    return (int)sz1 + (int)sz2 + v_comm + *p + (int)diff;
}
""",
        [],
        [],
    ),
    (
        "c99_structs_9_16_e_sret_por_valor_e_offsetof_aninhado",
        r"""
#include <stdio.h>
#include <stddef.h>

struct S16 {
    long a;
    int b;
    int c;
};

struct S32 {
    long w;
    long x;
    long y;
    long z;
};

struct Inner { int u; int v; };
struct Outer { char tag; struct Inner in; };

struct S16 somar16(struct S16 p, struct S16 q) {
    struct S16 r = { p.a + q.a, p.b + q.b, p.c + q.c };
    return r;
}

struct S32 somar32(struct S32 p, struct S32 q, int extra) {
    struct S32 r = { p.w + q.w + extra, p.x + q.x, p.y + q.y, p.z + q.z };
    return r;
}

int main(void) {
    struct S16 a16 = { 100, 20, 3 };
    struct S16 b16 = { 5, 7, 9 };
    struct S16 c16 = somar16(a16, b16);

    struct S32 a32 = { 1, 2, 3, 4 };
    struct S32 b32 = { 10, 20, 30, 40 };
    struct S32 c32 = somar32(a32, b32, 5);
    struct S32 escolhido = (c16.b > 10) ? c32 : a32;

    size_t off_v = offsetof(struct Outer, in.v);
    printf("s16=(%ld,%d,%d) s32=(%ld,%ld,%ld,%ld) off=%lu\n",
           c16.a, c16.b, c16.c,
           escolhido.w, escolhido.x, escolhido.y, escolhido.z,
           (unsigned long)off_v);
    return (int)(c16.b + c16.c + escolhido.w + off_v);
}
""",
        [],
        [],
    ),
    (
        "c99_globais_ponteiros_rela_data_shadowing_bf_composto",
        r"""
#include <stdio.h>

enum Cor { VERMELHO = 100, VERDE = 200 };
typedef int meu_tipo_t;

int dobro(int x) { return x * 2; }

const char *g_msg = "rela-data-ok";
int g_nums[4] = { 11, 22, 33, 44 };
int *g_terceiro = &g_nums[2];
int (*g_fn)(int) = dobro;

struct BF {
    unsigned int a : 5;
    int s : 4;
};

int chamar_static_fp(int v) {
    static int (*fp)(int) = dobro;
    return fp(v);
}

int main(void) {
    int VERMELHO = 7; // sombreia enumerador!
    int meu_tipo_t = 9; // sombreia typedef!
    struct BF bf = { 4, -2 };
    bf.a += 6;
    int ret_bf = (bf.s = -3);
    int r1 = g_fn(5);
    int r2 = chamar_static_fp(6);
    printf("msg=%s g3=%d fn=%d,%d sh=%d,%d bf=%u,%d,%d\n",
           g_msg, *g_terceiro, r1, r2, VERMELHO, meu_tipo_t,
           bf.a, bf.s, ret_bf);
    return *g_terceiro + r1 + r2 + VERMELHO + meu_tipo_t + (int)bf.a;
}
""",
        [],
        [],
    ),
    (
        "c99_argc_argv_switch_goto_sizeof_cast",
        r"""
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    int acc = 0;
    for (int i = 1; i < argc; i++) {
        switch (argv[i][0]) {
            case 'a': acc += 10; break;
            case 'b': acc += 20; /* fallthrough */
            case 'c': acc += 5; break;
            default: acc += 1; break;
        }
    }
    int n = 0;
loop_lbl:
    n++;
    if (n < 4) goto loop_lbl;
    int szc = (int)sizeof((int)5);
    printf("argc=%d a1=%s a2=%s acc=%d n=%d szc=%d\n",
           argc, argc > 1 ? argv[1] : "", argc > 2 ? argv[2] : "",
           acc, n, szc);
    return argc + acc + n + szc;
}
""",
        [],
        ["alpha", "beta", "zzz"],
    ),
    (
        "c99_desig_aninhado_comma_agg_str_ops_builtin_expect",
        r"""
#include <stdio.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    int type;
    union {
        long num;
        struct { const char *ptr; int len; } text;
    } value;
} Val;

static Val make_num(long n) {
    return (Val){ .type = 1, .value.num = n };
}

static Val make_txt(const char *s, int len) {
    return (Val){ .type = 2, .value.text.ptr = s, .value.text.len = len };
}

static bool is_neg_str(const char *s) {
    return strcmp(s, "\055") == 0; // "-" via escape octal (nao deve colidir com operador unario '-')
}

int main(void) {
    int side = 0;
    Val v1 = make_num(42);
    Val v2 = make_txt("\053", 1); // "+"
    long n = (side++, make_num(10)).value.num;
    int exp_ok = __builtin_expect(v1.value.num == 42, 1) ? 1 : 0;
    bool b_neg = is_neg_str("-");
    bool b_pos = is_neg_str("+");
    printf("v1=%ld v2=%s,%d n=%ld side=%d exp=%d b=%d,%d\n",
           v1.value.num, v2.value.text.ptr, v2.value.text.len,
           n, side, exp_ok, (int)b_neg, (int)b_pos);
    return (int)(v1.value.num + n + side + exp_ok + (int)b_neg);
}
""",
        ["-std=gnu99"],
        [],
    ),
]


def rodar_diferenciais(tmp: Path) -> int:
    falhas = 0
    for nome, codigo, flags, run_args in CASOS_DIFERENCIAIS:
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
            refs[comp] = rodar_bin(bin_ref, run_args)

        if len(refs) < 2:
            continue
        if refs["gcc"] != refs["clang"]:
            print(f"[AVISO REF] GCC vs Clang divergem em {nome}: {refs}")

        ec_ref, out_ref = refs["gcc"]
        for opt in ("-O0", "-O1", "-O2"):
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
            ec_dcc, out_dcc = rodar_bin(bin_dcc, run_args)
            if ec_dcc != ec_ref or out_dcc != out_ref:
                print(f"[DIVERGENCIA] {nome} ({opt}):")
                print(f"  REF: exit={ec_ref} stdout={out_ref!r}")
                print(f"  DCC: exit={ec_dcc} stdout={out_dcc!r}")
                falhas += 1
            else:
                print(f"[OK] {nome} ({opt}) vs GCC+Clang -> exit={ec_dcc}")
    return falhas


def rodar_testes_abi_bidirecional(tmp: Path) -> int:
    """Valida interoperabilidade ABI System V AMD64 nas 4 direcoes:
    DCC -> GCC, GCC -> DCC, DCC -> Clang, Clang -> DCC
    cobrindo int/long, float 32-bit, double, struct<=8B, struct 9..16B, struct>16B (sret),
    variadicos e callbacks.
    """
    falhas = 0
    abi_hdr = tmp / "abi_shared.h"
    abi_hdr.write_text(
        r"""
#ifndef ABI_SHARED_H
#define ABI_SHARED_H
struct S8  { int a; int b; };
struct S16 { long a; int b; int c; };
struct S32 { long a; long b; long c; long d; };

float abi_f32(float x, float y);
double abi_f64(double x, double y);
struct S8 abi_s8(struct S8 p, int k);
struct S16 abi_s16(struct S16 p, long k);
struct S32 abi_s32(struct S32 p, long k);
int abi_cb(int (*fn)(int, int), int x, int y);
int abi_var(int n, ...);
#endif
""",
        encoding="utf-8",
    )

    callee_src = tmp / "abi_callee.c"
    callee_src.write_text(
        r"""
#include <stdarg.h>
#include "abi_shared.h"

float abi_f32(float x, float y) { return x * 2.0f + y; }
double abi_f64(double x, double y) { return x + y * 3.0; }
struct S8 abi_s8(struct S8 p, int k) {
    struct S8 r = { p.a + k, p.b * k };
    return r;
}
struct S16 abi_s16(struct S16 p, long k) {
    struct S16 r = { p.a + k, p.b + 1, p.c + 2 };
    return r;
}
struct S32 abi_s32(struct S32 p, long k) {
    struct S32 r = { p.a + k, p.b + k, p.c + k, p.d + k };
    return r;
}
int abi_cb(int (*fn)(int, int), int x, int y) { return fn(x, y) + 1; }
int abi_var(int n, ...) {
    va_list ap;
    va_start(ap, n);
    int s = 0;
    for (int i = 0; i < n; i++) s += va_arg(ap, int);
    va_end(ap);
    return s;
}
""",
        encoding="utf-8",
    )

    caller_src = tmp / "abi_caller.c"
    caller_src.write_text(
        r"""
#include <stdio.h>
#include "abi_shared.h"

static int mul_cb(int a, int b) { return a * b; }

int main(void) {
    float f = abi_f32(1.5f, 2.25f);          // 5.25
    double d = abi_f64(1.0, 2.5);            // 8.5
    struct S8 r8 = abi_s8((struct S8){ 3, 4 }, 5);                 // (8, 20)
    struct S16 r16 = abi_s16((struct S16){ 100, 10, 20 }, 7);      // (107, 11, 22)
    struct S32 r32 = abi_s32((struct S32){ 1, 2, 3, 4 }, 10);      // (11, 12, 13, 14)
    int cb = abi_cb(mul_cb, 6, 7);                                 // 43
    int vr = abi_var(5, 1, 2, 3, 4, 5);                            // 15
    printf("f=%.2f d=%.1f s8=(%d,%d) s16=(%ld,%d,%d) s32=(%ld,%ld,%ld,%ld) cb=%d vr=%d\n",
           (double)f, d, r8.a, r8.b, r16.a, r16.b, r16.c,
           r32.a, r32.b, r32.c, r32.d, cb, vr);
    return r8.a + r8.b + cb + vr; // 8 + 20 + 43 + 15 = 86
}
""",
        encoding="utf-8",
    )

    esperado = "f=5.25 d=8.5 s8=(8,20) s16=(107,11,22) s32=(11,12,13,14) cb=43 vr=15\n"

    o_caller_dcc = tmp / "abi_caller_dcc.o"
    o_callee_dcc = tmp / "abi_callee_dcc.o"
    o_caller_gcc = tmp / "abi_caller_gcc.o"
    o_callee_gcc = tmp / "abi_callee_gcc.o"
    o_caller_clang = tmp / "abi_caller_clang.o"
    o_callee_clang = tmp / "abi_callee_clang.o"

    subprocess.run([str(DCC_BIN), "-c", "-I", str(tmp), str(caller_src), "-o", str(o_caller_dcc)], check=True)
    subprocess.run([str(DCC_BIN), "-c", "-I", str(tmp), str(callee_src), "-o", str(o_callee_dcc)], check=True)
    subprocess.run(["gcc", "-std=c99", "-c", "-I", str(tmp), str(caller_src), "-o", str(o_caller_gcc)], check=True)
    subprocess.run(["gcc", "-std=c99", "-c", "-I", str(tmp), str(callee_src), "-o", str(o_callee_gcc)], check=True)
    subprocess.run(["clang", "-std=c99", "-c", "-I", str(tmp), str(caller_src), "-o", str(o_caller_clang)], check=True)
    subprocess.run(["clang", "-std=c99", "-c", "-I", str(tmp), str(callee_src), "-o", str(o_callee_clang)], check=True)

    pares = [
        ("abi_dcc_chama_gcc", [str(DCC_BIN), str(o_caller_dcc), str(o_callee_gcc), "-o", str(tmp / "abi_dg")], tmp / "abi_dg"),
        ("abi_gcc_chama_dcc", ["gcc", str(o_caller_gcc), str(o_callee_dcc), "-o", str(tmp / "abi_gd")], tmp / "abi_gd"),
        ("abi_dcc_chama_clang", [str(DCC_BIN), str(o_caller_dcc), str(o_callee_clang), "-o", str(tmp / "abi_dc")], tmp / "abi_dc"),
        ("abi_clang_chama_dcc", ["clang", str(o_caller_clang), str(o_callee_dcc), "-o", str(tmp / "abi_cd")], tmp / "abi_cd"),
    ]
    for nome, cmd, out_bin in pares:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            print(f"[FALHA LINK {nome}] {r.stderr}")
            falhas += 1
            continue
        ec, out = rodar_bin(out_bin)
        if ec != 86 or out != esperado:
            print(f"[FALHA ABI {nome}] ec={ec} out={out!r} esperado={esperado!r}")
            falhas += 1
        else:
            print(f"[OK] {nome} -> exit={ec}")

    # Teste ABI TLS (__thread / R_X86_64_GOTTPOFF + STT_TLS) e retorno bool estreito (bits superiores RAX)
    (tmp / "abi_tls_def.c").write_text(
        "#include <stdbool.h>\n"
        "__thread int g_abi_tls = 40;\n"
        "int abi_tls_get(void) { return g_abi_tls; }\n"
        "bool abi_ret_false_dirty(unsigned long x) { return (x & 1UL) != 0UL; }\n",
        encoding="utf-8",
    )
    (tmp / "abi_tls_use.c").write_text(
        "#include <stdbool.h>\n"
        "extern __thread int g_abi_tls;\n"
        "int abi_tls_get(void);\n"
        "bool abi_ret_false_dirty(unsigned long x);\n"
        "int main(void) {\n"
        "    g_abi_tls += 2;\n"
        "    int r = abi_tls_get();\n"
        "    if (abi_ret_false_dirty(0x1234567800UL)) return 99;\n"
        "    if (!abi_ret_false_dirty(0x1234567801UL)) return 98;\n"
        "    return r;\n"
        "}\n",
        encoding="utf-8",
    )
    subprocess.run(["gcc", "-std=gnu99", "-O2", "-c", str(tmp / "abi_tls_def.c"), "-o", str(tmp / "abi_tls_def.o")], check=True)
    r_tu = subprocess.run([str(DCC_BIN), "-std=gnu99", "-c", str(tmp / "abi_tls_use.c"), "-o", str(tmp / "abi_tls_use.o")], capture_output=True, text=True, check=False)
    r_tl = subprocess.run(["gcc", str(tmp / "abi_tls_use.o"), str(tmp / "abi_tls_def.o"), "-o", str(tmp / "abi_tls_bin")], capture_output=True, text=True, check=False) if r_tu.returncode == 0 else r_tu
    ec_t, _ = rodar_bin(tmp / "abi_tls_bin") if r_tl.returncode == 0 else (-1, "")
    if ec_t != 42:
        print(f"[FALHA abi_tls_e_bool_estreito] ec={ec_t} err={r_tu.stderr}\n{r_tl.stderr}")
        falhas += 1
    else:
        print("[OK] abi_tls_e_bool_estreito -> exit=42")
    return falhas


def rodar_testes_linker_cruzado(tmp: Path) -> int:
    falhas = 0
    (tmp / "mod_calc.c").write_text(
        'int g_mult = 5;\nconst char *g_tag = "OK";\nint calc(int x, int y) { return (x + y) * g_mult; }\n',
        encoding="utf-8",
    )
    (tmp / "mod_main.c").write_text(
        '#include <stdio.h>\nextern int g_mult;\nextern const char *g_tag;\nextern int calc(int x, int y);\n'
        'int main(void) { int r = calc(4, 6); printf("r=%d m=%d t=%s\\n", r, g_mult, g_tag); return r; }\n',
        encoding="utf-8",
    )

    obj_calc_dcc = tmp / "calc_dcc.o"
    obj_main_dcc = tmp / "main_dcc.o"
    obj_calc_gcc = tmp / "calc_gcc.o"
    obj_calc_clang = tmp / "calc_clang.o"
    lib_calc_a = tmp / "libcalc.a"

    subprocess.run([str(DCC_BIN), "-c", str(tmp / "mod_calc.c"), "-o", str(obj_calc_dcc)], check=True)
    subprocess.run([str(DCC_BIN), "-c", str(tmp / "mod_main.c"), "-o", str(obj_main_dcc)], check=True)
    subprocess.run(["gcc", "-std=c99", "-c", str(tmp / "mod_calc.c"), "-o", str(obj_calc_gcc)], check=True)
    subprocess.run(["clang", "-std=c99", "-c", str(tmp / "mod_calc.c"), "-o", str(obj_calc_clang)], check=True)
    subprocess.run(["ar", "rcs", str(lib_calc_a), str(obj_calc_dcc)], check=True)

    combos = [
        ("linker_dcc_dcc", [str(DCC_BIN), str(obj_main_dcc), str(obj_calc_dcc), "-o", str(tmp / "l1")], tmp / "l1"),
        ("linker_gcc_sobre_dcc_o", ["gcc", str(obj_main_dcc), str(obj_calc_dcc), "-o", str(tmp / "l2")], tmp / "l2"),
        ("linker_dcc_com_gcc_o", [str(DCC_BIN), str(obj_main_dcc), str(obj_calc_gcc), "-o", str(tmp / "l3")], tmp / "l3"),
        ("linker_dcc_com_clang_o", [str(DCC_BIN), str(obj_main_dcc), str(obj_calc_clang), "-o", str(tmp / "l4")], tmp / "l4"),
        ("linker_archive_direto_a", [str(DCC_BIN), str(obj_main_dcc), str(lib_calc_a), "-o", str(tmp / "l5")], tmp / "l5"),
        ("linker_archive_L_l", [str(DCC_BIN), str(obj_main_dcc), "-L", str(tmp), "-lcalc", "-o", str(tmp / "l6")], tmp / "l6"),
    ]
    for nome, cmd, out_bin in combos:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            print(f"[FALHA {nome}] {r.stdout}\n{r.stderr}")
            falhas += 1
            continue
        ec, out = rodar_bin(out_bin)
        if ec != 50 or out != "r=50 m=5 t=OK\n":
            print(f"[FALHA EXEC {nome}] ec={ec} out={out!r}")
            falhas += 1
        else:
            print(f"[OK] {nome} -> exit={ec}")

    # Teste de simbolos weak vs strong
    (tmp / "w_weak.c").write_text(
        'int __attribute__((weak)) valor_cfg(void) { return 10; }\n'
        'int main(void) { return valor_cfg(); }\n',
        encoding="utf-8",
    )
    (tmp / "w_strong.c").write_text("int valor_cfg(void) { return 42; }\n", encoding="utf-8")
    subprocess.run([str(DCC_BIN), "-std=gnu99", "-c", str(tmp / "w_weak.c"), "-o", str(tmp / "w_weak.o")], check=True)
    subprocess.run([str(DCC_BIN), "-std=gnu99", "-c", str(tmp / "w_strong.c"), "-o", str(tmp / "w_strong.o")], check=True)
    r_ws = subprocess.run([str(DCC_BIN), str(tmp / "w_weak.o"), str(tmp / "w_strong.o"), "-o", str(tmp / "w_bin")], capture_output=True, text=True, check=False)
    ec_ws, _ = rodar_bin(tmp / "w_bin") if r_ws.returncode == 0 else (-1, "")
    if ec_ws != 42:
        print(f"[FALHA linker_weak_strong] rc={r_ws.returncode} ec={ec_ws} err={r_ws.stderr}")
        falhas += 1
    else:
        print("[OK] linker_weak_override_strong -> exit=42")

    # Teste de simbolo global duplicado (deve falhar com E5010)
    r_dup = subprocess.run([str(DCC_BIN), str(obj_main_dcc), str(obj_calc_dcc), str(obj_calc_gcc), "-o", str(tmp / "dup_bin")], capture_output=True, text=True, check=False)
    if r_dup.returncode == 0 or "duplicada" not in r_dup.stderr:
        print(f"[FALHA linker_simbolo_duplicado] rc={r_dup.returncode} err={r_dup.stderr!r}")
        falhas += 1
    else:
        print("[OK] linker_rejeita_simbolo_duplicado")

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
    (tmp / "inc_erro.h").write_text("int f_inc(void) { return nao_existe_no_header; }\n", encoding="utf-8")

    casos_neg = [
        ("diag_var_indefinida", "int main(void) {\n    return nao_existe;\n}\n", ["error:", "nao_existe", "^", "E3000"], []),
        ("diag_gnu_cat_c", "int __attribute__((vector_size(16))) x;\nint main(void) { return 0; }\n", ["Categoria C", "vector_size"], ["-std=gnu99"]),
        ("diag_inline_asm_cat_c", 'int main(void) { __asm__("nop"); return 0; }\n', ["Categoria C", "inline assembly"], ["-std=gnu99"]),
        ("diag_gnu_stmt_expr_cat_c", "int main(void) { int x = ({ 1 + 2; }); return x; }\n", ["Categoria C", "statement expression"], ["-std=gnu99"]),
        ("diag_gnu_computed_goto_cat_c", "int main(void) { lbl: void *p = &&lbl; return p != 0; }\n", ["Categoria C", "label computado"], ["-std=gnu99"]),
        ("diag_pp_error", '#error "falha intencional"\nint main(void) { return 0; }\n', ["#error", "falha intencional"], []),
        ("diag_werror_warning", '#warning "aviso"\nint main(void) { return 0; }\n', ["-Werror", "diag_werror_warning.c:1:"], ["-Werror"]),
        ("diag_const_write", "int main(void) { const int c = 5; c = 6; return c; }\n", ["const", "E3010"], []),
        ("diag_struct_recursivo", "struct Rec { struct Rec x; }; int main(void){ return 0; }\n", ["incompleto ou recursivo", "E3005"], []),
        ("diag_campo_duplicado", "struct D { int x; int x; }; int main(void){ return 0; }\n", ["campo duplicado", "E3002"], []),
        ("diag_case_duplicado", "int main(void){ switch(1){ case 1: break; case 1: break; } return 0; }\n", ["duplicado", "E3008"], []),
        ("diag_include_stack", '#include "inc_erro.h"\nint main(void) { return 0; }\n', ["In file included from", "inc_erro.h:1:", "nao_existe_no_header"], ["-I", str(tmp)]),
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
        ok = r.returncode != 0 and r.stdout == "" and all(t in r.stderr for t in trechos)
        if not ok:
            print(f"[FALHA NEG {nome}] rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr!r}")
            falhas += 1
        else:
            print(f"[OK] negativo:{nome}")

    # Testa formato JSON de diagnosticos (-fdiagnostics-format=json)
    arq_js = tmp / "diag_var_indefinida.c"
    r_js = subprocess.run(
        [str(DCC_BIN), "-fdiagnostics-format=json", str(arq_js), "-o", str(tmp / "js.out")],
        capture_output=True, text=True, check=False,
    )
    try:
        parsed_js = json.loads(r_js.stderr)
        ok_js = r_js.returncode != 0 and isinstance(parsed_js, list) and parsed_js[0]["code"] == "E3000" and parsed_js[0]["severity"] == "error"
    except Exception:
        ok_js = False
    if not ok_js:
        print(f"[FALHA diag_json] stderr={r_js.stderr!r}")
        falhas += 1
    else:
        print("[OK] diagnostico_formato_json")

    # Testa cores ANSI (-fdiagnostics-color=always vs never)
    r_col_on = subprocess.run([str(DCC_BIN), "-fdiagnostics-color=always", str(arq_js)], capture_output=True, text=True, check=False)
    r_col_off = subprocess.run([str(DCC_BIN), "-fdiagnostics-color=never", str(arq_js)], capture_output=True, text=True, check=False)
    if "\x1b[" not in r_col_on.stderr or "\x1b[" in r_col_off.stderr:
        print("[FALHA diag_color]")
        falhas += 1
    else:
        print("[OK] diagnostico_cores_ansi")

    # Testa -Wno-cpp suprimindo #warning mesmo com -Werror e -E sem vazar aviso para stdout
    arq_warn = tmp / "warn_sup.c"
    arq_warn.write_text('#warning "ignorar"\nint main(void) { return 0; }\n', encoding="utf-8")
    r_wno = subprocess.run([str(DCC_BIN), "-Werror", "-Wno-cpp", str(arq_warn), "-o", str(tmp / "wno.out")], capture_output=True, text=True, check=False)
    r_pp = subprocess.run([str(DCC_BIN), "-E", str(arq_warn)], capture_output=True, text=True, check=False)
    if r_wno.returncode != 0 or r_pp.returncode != 0 or "warning:" in r_pp.stdout or "warning:" not in r_pp.stderr:
        print(f"[FALHA diag_wno_e_pp_stderr] wno={r_wno.returncode} pp_out={r_pp.stdout!r} pp_err={r_pp.stderr!r}")
        falhas += 1
    else:
        print("[OK] diagnostico_wno_cpp_e_stderr_limpo")

    # Testa -S (assembly) e independencia de diretorio de trabalho (executa de /tmp!)
    asm_file = tmp / "teste.s"
    arq_ok = tmp / "ok_cwd.c"
    arq_ok.write_text('#include <stdio.h>\nint main(void) { puts("cwd-ok"); return 0; }\n', encoding="utf-8")
    r_s = subprocess.run([str(DCC_BIN), "-S", "-ftime-report", str(arq_ok), "-o", str(asm_file)], cwd="/tmp", capture_output=True, text=True, check=False)
    if r_s.returncode != 0 or "section .text" not in asm_file.read_text(encoding="utf-8") or "[dcc-time]" not in r_s.stderr:
        print(f"[FALHA -S cwd=/tmp] {r_s.stderr}")
        falhas += 1
    else:
        print("[OK] backend_asm_ftime_e_independencia_cwd")
    return falhas


def main() -> int:
    if not DCC_BIN.exists():
        print(f"Binario nao encontrado: {DCC_BIN}. Execute ./bootstrap/build.sh primeiro.")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="dcc_tests_"))
    try:
        falhas = 0
        falhas += rodar_diferenciais(tmp)
        falhas += rodar_testes_abi_bidirecional(tmp)
        falhas += rodar_testes_linker_cruzado(tmp)
        falhas += rodar_testes_diagnosticos_e_cli(tmp)
        total = len(CASOS_DIFERENCIAIS) * 3 + 5 + 9 + 18
        print(f"\nResumo DCC: {total - falhas}/{total} verificacoes aprovadas, {falhas} falhas.")
        return 1 if falhas > 0 else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
