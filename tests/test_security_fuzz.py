#!/usr/bin/env python3
"""Suite de auditoria de seguranca e fuzzing do DCC:
- Bombas e casos adversariais no pre-processador (expansao exponencial, recursao, #include ciclico, #if extremo)
- Fuzzing do lexer e parser (aninhamento profundo, truncamento, bytes invalidos, entradas malformadas)
- Entradas ELF64 (.o) e ar (.a) malformadas/hostis entregues diretamente ao linker nativo do DCC.
Garante termino controlado (sem crash por sinal, sem OOM, sem loop infinito).
"""

from __future__ import annotations

import random
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ_DCC = Path(__file__).resolve().parents[1]
DCC_BIN = RAIZ_DCC / "build" / "dcc"


def rodar_dcc_seguro(args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(DCC_BIN), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def testar_preproc_adversarial(tmp: Path) -> int:
    falhas = 0
    casos: list[tuple[str, str, bool, list[str]]] = []

    # 1. Bomba de expansao exponencial (2^24 tokens se nao houver limite)
    linhas_bomba = ["#define M0 x"]
    for i in range(1, 25):
        linhas_bomba.append(f"#define M{i} M{i-1} M{i-1}")
    linhas_bomba.append("int main(void) { M24; return 0; }\n")
    casos.append(("pp_bomba_exponencial", "\n".join(linhas_bomba), False, ["E1011"]))

    # 2. Recursao direta e mutua (hide-set deve encerrar rapidamente sem erro de loop)
    casos.append((
        "pp_recursao_mutua_hideset",
        "#define A B\n#define B A\nint main(void) { int A = 7; return A; }\n",
        True,
        [],
    ))

    # 3. #include ciclico
    (tmp / "ciclo_a.h").write_text('#include "ciclo_b.h"\n', encoding="utf-8")
    (tmp / "ciclo_b.h").write_text('#include "ciclo_a.h"\n', encoding="utf-8")
    casos.append(("pp_include_ciclico", '#include "ciclo_a.h"\nint main(void){return 0;}\n', False, ["E1002"]))

    # 4. #if profundamente aninhado (300 niveis > limite 256)
    deep_if = "#if 1\n" * 300 + "int main(void){return 0;}\n" + "#endif\n" * 300
    casos.append(("pp_if_profundo", deep_if, False, ["E1003"]))

    # 5. Expressao #if profundamente aninhada
    deep_expr = "#if " + "(" * 160 + "1" + ")" * 160 + "\nint main(void){return 0;}\n#endif\n"
    casos.append(("pp_if_expr_profunda", deep_expr, False, ["E1005"]))

    # 6. Divisao por zero em #if ativo
    casos.append(("pp_if_div_zero", "#if 10 / 0\n#endif\nint main(void){return 0;}\n", False, ["E1006"]))

    # 7. INT64_MIN / -1 em #if (nao deve causar SIGFPE!)
    casos.append((
        "pp_if_int64min_div_neg1",
        "#if (-9223372036854775807LL - 1) / -1\nint main(void){return 0;}\n#else\nint main(void){return 1;}\n#endif\n",
        True,
        [],
    ))

    # 8. #if vazio e tokens residuais em #if
    casos.append(("pp_if_vazio", "#if\n#endif\nint main(void){return 0;}\n", False, ["E1004"]))
    casos.append(("pp_if_tokens_residuais", "#if 1 2\n#endif\nint main(void){return 0;}\n", False, ["E1007"]))

    # 9. Token pasting malformado no inicio/fim de macro
    casos.append(("pp_paste_inicio", "#define BAD ##x\nint main(void){return 0;}\n", False, ["E1014"]))
    casos.append(("pp_paste_fim", "#define BAD x##\nint main(void){return 0;}\n", False, ["E1014"]))

    # 10. Comentario /* nao fechado
    casos.append(("pp_comentario_aberto", "int main(void) { return 0; } /* nunca fecha", False, ["E1001"]))

    for nome, codigo, deve_passar, trechos in casos:
        arq = tmp / f"{nome}.c"
        out = tmp / f"{nome}.out"
        arq.write_text(codigo, encoding="utf-8")
        try:
            r = rodar_dcc_seguro(["-I", str(tmp), str(arq), "-o", str(out)])
        except subprocess.TimeoutExpired:
            print(f"[FALHA SEC-PP TIMEOUT] {nome}")
            falhas += 1
            continue

        if r.returncode < 0:
            print(f"[FALHA SEC-PP CRASH sinal={-r.returncode}] {nome}")
            falhas += 1
            continue
        if deve_passar:
            if r.returncode != 0:
                print(f"[FALHA SEC-PP ESPERAVA OK] {nome}: {r.stderr}")
                falhas += 1
            else:
                print(f"[OK] sec_pp:{nome}")
        else:
            ok = r.returncode != 0 and all(t in r.stderr for t in trechos) and r.stdout == ""
            if not ok:
                print(f"[FALHA SEC-PP] {nome}: rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr!r}")
                falhas += 1
            else:
                print(f"[OK] sec_pp:{nome}")
    return falhas


def testar_lexer_parser_fuzz(tmp: Path) -> int:
    falhas = 0
    casos_malformados: list[tuple[str, str]] = [
        ("vazio", ""),
        ("apenas_diretivas", "#define X 1\n#ifdef X\n#endif\n"),
        ("string_nao_terminada", 'int main(void) { const char *s = "aberto;\n return 0; }\n'),
        ("char_vazio", "int main(void) { return ''; }\n"),
        ("char_nao_terminado", "int main(void) { return 'a;\n }\n"),
        ("float_expoente_vazio", "int main(void) { double d = 1.5e+; return (int)d; }\n"),
        ("hex_float_invalido", "int main(void) { double d = 0x1.p; return (int)d; }\n"),
        ("parens_profundos", "int main(void) { return " + "(" * 350 + "1" + ")" * 350 + "; }\n"),
        ("blocos_profundos", "int main(void) " + "{" * 350 + "return 0;" + "}" * 350 + "\n"),
        ("structs_profundos", "struct S0 { " * 270 + "int x;" + " };" * 270 + "\nint main(void){return 0;}\n"),
        ("chaves_desbalanceadas", "int main(void) { if (1) { return 0; \n"),
        ("declarador_truncado", "int (*fp)(int, "),
        ("caractere_invalido", "int main(void) { return @; }\n"),
        ("switch_quebrado", "int main(void) { switch (1) { case : break; } }\n"),
        ("array_negativo", "int main(void) { int a[-5]; return 0; }\n"),
        ("array_overflow", "int main(void) { static long a[500000000]; return 0; }\n"),
        ("struct_recursivo", "struct Rec { struct Rec self; }; int main(void){return 0;}\n"),
        ("campo_incompleto", "struct Bad { struct Undef u; }; int main(void){return 0;}\n"),
        ("bitfield_invalido", "struct B { double x : 3; }; int main(void){return 0;}\n"),
        ("bitfield_grande", "struct B { int x : 64; }; int main(void){return 0;}\n"),
    ]

    # Gera 30 entradas pseudo-aleatorias determinísticas (token soups & truncamentos)
    rng = random.Random(20261121)
    voc = [
        "int", "char", "struct", "union", "enum", "typedef", "const", "volatile", "static",
        "return", "if", "else", "while", "for", "switch", "case", "default", "goto", "sizeof",
        "(", ")", "{", "}", "[", "]", ";", ",", ".", "->", "*", "&", "+", "-", "/", "%",
        "=", "==", "&&", "||", "?", ":", "0", "42", "3.14", "\"abc\"", "'x'", "foo", "bar",
    ]
    for i in range(30):
        n_toks = rng.randint(5, 80)
        soup = " ".join(rng.choice(voc) for _ in range(n_toks)) + "\n"
        casos_malformados.append((f"fuzz_soup_{i:02d}", soup))

    # Entrada com bytes UTF-8 / controle inesperados
    for nome, codigo in casos_malformados:
        arq = tmp / f"fuzz_{nome}.c"
        out = tmp / f"fuzz_{nome}.out"
        arq.write_text(codigo, encoding="utf-8")
        try:
            r = rodar_dcc_seguro([str(arq), "-o", str(out)], timeout=6.0)
        except subprocess.TimeoutExpired:
            print(f"[FALHA FUZZ-PARSE TIMEOUT] {nome}")
            falhas += 1
            continue
        if r.returncode < 0:
            print(f"[FALHA FUZZ-PARSE CRASH sinal={-r.returncode}] {nome}")
            falhas += 1
            continue
        # Entradas validas por acaso (ex: vazio sem main) ou invalidas devem encerrar de forma limpa
        if nome in ("parens_profundos", "blocos_profundos", "structs_profundos") and "E2010" not in r.stderr:
            print(f"[FALHA FUZZ-DEPTH] {nome}: esperado E2010, obtido: {r.stderr!r}")
            falhas += 1
            continue
    if falhas == 0:
        print(f"[OK] fuzz_lexer_parser ({len(casos_malformados)} entradas adversariais/aleatorias sem crash)")
    return falhas


def montar_elf_hdr(
    ei_class: int = 2,
    ei_data: int = 1,
    e_type: int = 1,
    e_machine: int = 62,
    e_shoff: int = 64,
    e_shentsize: int = 64,
    e_shnum: int = 2,
    e_shstrndx: int = 1,
) -> bytearray:
    hdr = bytearray(64)
    hdr[0:4] = b"\x7fELF"
    hdr[4] = ei_class
    hdr[5] = ei_data
    hdr[6] = 1  # EV_CURRENT
    struct.pack_into("<HHIQQQIHHHHHH", hdr, 16,
                     e_type, e_machine, 1, 0, 0, e_shoff, 0, 64, 0, 0, e_shentsize, e_shnum, e_shstrndx)
    return hdr


def montar_shdr(
    sh_name: int, sh_type: int, sh_flags: int, sh_offset: int, sh_size: int,
    sh_link: int = 0, sh_info: int = 0, sh_align: int = 1, sh_entsize: int = 0
) -> bytes:
    return struct.pack("<IIQQQQIIQQ", sh_name, sh_type, sh_flags, 0, sh_offset, sh_size,
                       sh_link, sh_info, sh_align, sh_entsize)


def testar_elf_e_ar_malformados(tmp: Path) -> int:
    falhas = 0
    casos_bin: list[tuple[str, str, bytes]] = []

    casos_bin.append(("elf_vazio", ".o", b""))
    casos_bin.append(("elf_truncado_10b", ".o", b"\x7fELF\x02\x01\x01\x00\x00\x00"))
    casos_bin.append(("elf_magic_ruim", ".o", b"NOT_AN_ELF_FILE" + b"\x00" * 64))
    casos_bin.append(("elf_32bit_class", ".o", bytes(montar_elf_hdr(ei_class=1))))
    casos_bin.append(("elf_big_endian", ".o", bytes(montar_elf_hdr(ei_data=2))))
    casos_bin.append(("elf_et_exec_como_o", ".o", bytes(montar_elf_hdr(e_type=2))))
    casos_bin.append(("elf_shoff_oob", ".o", bytes(montar_elf_hdr(e_shoff=999999))))
    casos_bin.append(("elf_shentsize_pequeno", ".o", bytes(montar_elf_hdr(e_shentsize=16)) + b"\x00" * 128))
    casos_bin.append(("elf_shstrndx_oob", ".o", bytes(montar_elf_hdr(e_shnum=2, e_shstrndx=9)) + b"\x00" * 128))

    # ELF com sh_align = 1 << 28 (bomba de OOM se nao validado!)
    shstr = b"\x00.text\x00.shstrtab\x00"
    off_shstr = 64
    off_shdrs = 64 + len(shstr)
    elf_align_bomb = bytearray(montar_elf_hdr(e_shoff=off_shdrs, e_shnum=3, e_shstrndx=2))
    elf_align_bomb += shstr
    elf_align_bomb += montar_shdr(0, 0, 0, 0, 0)
    elf_align_bomb += montar_shdr(1, 1, 6, 64, 4, sh_align=(1 << 28))
    elf_align_bomb += montar_shdr(7, 3, 0, off_shstr, len(shstr), sh_align=1)
    casos_bin.append(("elf_bomba_sh_align", ".o", bytes(elf_align_bomb)))

    # ELF com sh_offset + sh_size fora do arquivo
    elf_sec_oob = bytearray(montar_elf_hdr(e_shoff=off_shdrs, e_shnum=3, e_shstrndx=2))
    elf_sec_oob += shstr
    elf_sec_oob += montar_shdr(0, 0, 0, 0, 0)
    elf_sec_oob += montar_shdr(1, 1, 6, 64, 500000, sh_align=16)
    elf_sec_oob += montar_shdr(7, 3, 0, off_shstr, len(shstr), sh_align=1)
    casos_bin.append(("elf_secao_oob", ".o", bytes(elf_sec_oob)))

    # ELF com relocacao apontando symIdx fora dos limites
    shstr2 = b"\x00.text\x00.rela.text\x00.shstrtab\x00"
    rela_bad = struct.pack("<QQq", 0, (999 << 32) | 2, 0)
    off_rela2 = 64 + len(shstr2)
    off_shdrs2 = off_rela2 + len(rela_bad)
    elf_rel_oob = bytearray(montar_elf_hdr(e_shoff=off_shdrs2, e_shnum=4, e_shstrndx=3))
    elf_rel_oob += shstr2 + rela_bad
    elf_rel_oob += montar_shdr(0, 0, 0, 0, 0)
    elf_rel_oob += montar_shdr(1, 1, 6, 64, 4, sh_align=16)
    elf_rel_oob += montar_shdr(7, 4, 64, off_rela2, len(rela_bad), sh_link=0, sh_info=1, sh_align=8, sh_entsize=24)
    elf_rel_oob += montar_shdr(18, 3, 0, 64, len(shstr2), sh_align=1)
    casos_bin.append(("elf_reloc_symidx_oob", ".o", bytes(elf_rel_oob)))

    # Arquivo .a truncado e .a com tamanho de membro gigante
    casos_bin.append(("ar_truncado", ".a", b"!<arch>\nshort_hdr"))
    ar_hdr_bad = b"bad.o/          0           0     0     100644  9999999   `\n"
    casos_bin.append(("ar_membro_oob", ".a", b"!<arch>\n" + ar_hdr_bad + b"\x00" * 16))
    ar_hdr_sig = b"bad.o/          0           0     0     100644  16        XX"
    casos_bin.append(("ar_assinatura_ruim", ".a", b"!<arch>\n" + ar_hdr_sig + b"\x00" * 16))

    for nome, ext, dados in casos_bin:
        arq = tmp / f"hostil_{nome}{ext}"
        out = tmp / f"hostil_{nome}.out"
        arq.write_bytes(dados)
        try:
            r = rodar_dcc_seguro([str(arq), "-o", str(out)], timeout=6.0)
        except subprocess.TimeoutExpired:
            print(f"[FALHA SEC-ELF TIMEOUT] {nome}")
            falhas += 1
            continue
        if r.returncode <= 0 or "error:" not in r.stderr:
            print(f"[FALHA SEC-ELF] {nome}: rc={r.returncode} stderr={r.stderr!r}")
            falhas += 1
        else:
            print(f"[OK] sec_elf:{nome} -> rejeitado controladamente")
    return falhas


def main() -> int:
    if not DCC_BIN.exists():
        print(f"Binario nao encontrado: {DCC_BIN}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="dcc_sec_fuzz_"))
    try:
        falhas = 0
        falhas += testar_preproc_adversarial(tmp)
        falhas += testar_lexer_parser_fuzz(tmp)
        falhas += testar_elf_e_ar_malformados(tmp)
        print(f"\nResumo Seguranca/Fuzzing DCC: {'APROVADO' if falhas == 0 else f'{falhas} FALHA(S)'}")
        return 1 if falhas > 0 else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
