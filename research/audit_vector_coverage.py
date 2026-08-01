#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which conformance suites could not have seen the defect that shipped?

Pass 98 showed that gf16 ADD reported 512/512 bit-exact on silicon while the adder
it exercised was defective, and that gf16 SUB -- same cell, same board, same 512
pairs -- caught it. The whole difference was that SUB's vectors contained a NaN whose
payload is not the canonical quiet NaN and ADD's did not, because the defective path
returned the operand's raw payload and that is indistinguishable from correct when
the only NaN under test IS canonical.

That was one suite. This asks the same question of all of them: for each conformance
script, what does its vector set actually contain?

    non-canonical NaN   the property that decided pass 98's case
    NaN / Inf at all    a suite with none cannot test the special-value paths
    b-position          gf16 ADD pairs every a against cov[:8], and those eight
                        held no NaN -- so where the pairing is sliced, the slice is
                        what matters, not the full set
    zero, subnormal     the other structural edges

Two honesty constraints shape this, both learned the hard way earlier in the campaign:

  Literals are taken only from vector-defining assignments, never from the whole
  file. A frame byte or a baud constant is not a test vector, and counting one as a
  NaN would report coverage that does not exist.

  A script this cannot parse is reported as NOT ANALYSED, never as clean. "No
  finding" and "no look" are different results and are printed separately.

    python3 research/audit_vector_coverage.py [--verbose]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "conformance"))

from gf_ref import FORMATS                                # noqa: E402

CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "conformance")

# names whose right-hand side holds test vectors
VECNAME = re.compile(
    r"^\s*(?:(CORNERS|SPECIALS|VECTORS|corners|specials|sample|cov|vecs|pool)"
    r"\s*(?::[^=]+)?=|return\s+|\w*codes\.add\(|for\s+[ab]\s+in\s*(?=\[))(.*)$")

# Vectors that arrive from a published pack rather than being written in the
# script. Not unparseable -- differently sourced, and worth its own category so
# that "I could not read this" is not confused with "this reads its input".
PACK = re.compile(r"""(?:test_vectors|pack\s*\[|json\.load|\.get\(["']vectors)""")
HEX = re.compile(r"0[xX][0-9a-fA-F]+")
SLICE = re.compile(r"for\s+b\s+in\s+(\w+)\s*\[\s*:\s*(\d+)\s*\]")


EXPTEST = re.compile(r"\(\s*\w+\s*&\s*(0[xX][0-9a-fA-F]+)\s*\)\s*==\s*(0[xX][0-9a-fA-F]+)")
MANTTEST = re.compile(r"\(\s*\w+\s*&\s*(0[xX][0-9a-fA-F]+)\s*\)\s*!=\s*0")


def wrong_layout_masks(fmt, text: str):
    """Lines that DECIDE NaN/Inf using a mask that is not this format's.

    Narrow on purpose. A first, broader version flagged every appearance of a
    binary16 or binary32 constant and produced 19 hits, nearly all correct code:
    the decode suites emit IEEE binary32 by design, so 0x7F800000 belongs there,
    and gf10's 0x3FF is a legitimate ten-bit width mask. Only a mask used to
    classify the TARGET format's own codes can be wrong, so only those are read.
    """
    exp_mask = fmt.exp_max << fmt.mant_bits
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#") or not re.search(r"nan|inf", line, re.I):
            continue
        m = EXPTEST.search(line)
        if not m:
            continue
        got = int(m.group(1), 16)
        if got == int(m.group(2), 16) and got != exp_mask:
            mm = MANTTEST.search(line)
            out.append((ln, line.strip()[:88], got, exp_mask,
                        int(mm.group(1), 16) if mm else None, fmt.mant_max))
    return out


# Families whose format carries no NaN payload to omit, so pass 98's property is
# vacuous rather than missing. Each is evidenced by the corpus's own code, not by
# recollection: takum and posit decode a single NaR (takum16 returns "nar" for the
# lone code 1<<(N-1); posit maps NaR to one qNaN), and the integer, ternary and
# decimal-digit families have no NaN encoding at all.
NO_NAN_BY_DESIGN = {
    "takum": "single NaR code, no payload field",
    "posit": "single NaR code, no payload field",
    "int": "integer format, no NaN encoding",
    "uint": "integer format, no NaN encoding",
    "mxint": "integer format, no NaN encoding",
    "bcd": "decimal digits, no NaN encoding",
    "ternary": "trit format, no NaN encoding",
    "gfternary": "trit format, no NaN encoding",
    "trinet": "trit format, no NaN encoding",
    "vax": "legacy format, reserved operand rather than NaN payloads",
    "ms": "legacy MBF, no NaN encoding",
    "ibm": "legacy hexadecimal FP, no NaN encoding",
    "cray": "legacy format, no NaN payload field",
}


def format_for(filename: str):
    """The GF format a script targets, from its filename. None if not a GF cell."""
    stem = os.path.basename(filename).split("_")[0].lower()
    return FORMATS.get(stem)


SYMBOL = [
    (re.compile(r"\bNAN_MAX\b|(?:exp_max|EMAX)\s*<<[^)]*\)?\s*\|\s*"
                r"\w*(?:mant_max|M_MAX|MANT_MAX)\b"), "nan_other"),
    (re.compile(r"\bquiet_nan\b|(?:EMAX|exp_max)\s*<<\s*\w*(?:M_BITS|mant_bits)"
                r"\s*\)?\s*\|\s*1\b"), "nan_canonical"),
    (re.compile(r"\b(?:pos_inf|neg_inf)\b|(?:EMAX|exp_max)\s*<<\s*"
                r"\w*(?:M_BITS|mant_bits)\s*\)?\s*(?:$|[,)\]])"), "inf"),
    (re.compile(r"\bmant_max\b"), "subnormal"),
]


def vector_chunks(text: str) -> list[str]:
    """The right-hand side of every vector-defining assignment, brackets followed.

    Both the literal scan and the symbol scan read these same chunks. Reading them
    line by line instead was the first version's bug: the repaired gf16 SUB suite
    puts GFMT.pos_inf on a continuation line, so a per-line filter scored the fixed
    script as carrying no Inf.
    """
    out, lines = [], text.splitlines()
    i = 0
    while i < len(lines):
        m = VECNAME.match(lines[i])
        if not m:
            i += 1
            continue
        chunk = m.group(2)
        depth = (chunk.count("[") + chunk.count("(")
                 - chunk.count("]") - chunk.count(")"))
        j = i + 1
        while depth > 0 and j < len(lines) and j - i < 40:
            chunk += " " + lines[j]
            depth += (lines[j].count("[") + lines[j].count("(")
                      - lines[j].count("]") - lines[j].count(")"))
            j += 1
        out.append(chunk)
        i = max(j, i + 1)
    return out


def vector_symbols(text: str) -> set[str]:
    """Kinds contributed by format-derived names rather than hex literals.

    A suite that writes GFMT.pos_inf instead of 0x7E00 covers Inf just as well, and
    scoring only hex would mark the better-written script as the poorer one.
    """
    kinds = set()
    for chunk in vector_chunks(text):
        for rx, kind in SYMBOL:
            if rx.search(chunk):
                kinds.add(kind)
    return kinds


def vector_literals(text: str) -> list[int]:
    """Integers on the right-hand side of a vector-defining assignment.

    Everything else in the file is ignored, so a UART frame byte or a baud constant
    cannot be mistaken for a test vector.
    """
    out = []
    for chunk in vector_chunks(text):
        out += [int(h, 16) for h in HEX.findall(chunk)]
    return out


def b_slice(text: str, lits: list[int]):
    """(n, literals) when the pairing is `for b in NAME[:n]`, else (None, lits).

    Heuristic and stated as one: the first n literals of the vector definition stand
    in for the slice. It holds for the suites in this tree, where the definition is
    a literal corner list followed by generated randoms.
    """
    m = SLICE.search(text)
    if not m:
        return None, lits
    n = int(m.group(2))
    return n, lits[:n]


def classify(fmt, code: int) -> str:
    code &= (1 << (fmt.exp_bits + fmt.mant_bits + 1)) - 1
    e = (code >> fmt.mant_bits) & fmt.exp_max
    m = code & fmt.mant_max
    if fmt.has_inf and e == fmt.exp_max:
        if m == 0:
            return "inf"
        return "nan_canonical" if code == fmt.quiet_nan else "nan_other"
    if e == 0:
        return "zero" if m == 0 else "subnormal"
    return "normal"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(CONF)
                   if f.endswith(".py") and "conformance" in f)
    analysed, skipped_fmt, skipped_novec = [], [], []

    for f in files:
        fmt = format_for(f)
        if fmt is None:
            skipped_fmt.append(f)
            continue
        text = open(os.path.join(CONF, f), encoding="utf-8", errors="replace").read()
        lits = vector_literals(text)
        if not lits and not vector_symbols(text):
            skipped_novec.append((f, "vectors come from a published pack"
                                  if PACK.search(text) else
                                  "no vector-defining form this can read"))
            continue
        n, bl = b_slice(text, lits)
        syms = vector_symbols(text)
        kinds = {classify(fmt, c) for c in lits} | syms
        bkinds = {classify(fmt, c) for c in bl} | syms
        analysed.append((f, fmt, lits, kinds, n, bl, bkinds))

    vacuous, unknown = [], []
    for f in skipped_fmt:
        fam = re.sub(r"\d+$", "", os.path.basename(f).split("_")[0].lower())
        (vacuous if fam in NO_NAN_BY_DESIGN else unknown).append((f, fam))

    print(f"conformance scripts               : {len(files)}")
    print(f"  analysed (GF format + vectors)  : {len(analysed)}")
    print(f"  not a GF format                 : {len(skipped_fmt)}")
    print(f"      of those, no NaN payload    : {len(vacuous)}  "
          f"(property vacuous, not missing)")
    print(f"      of those, layout unknown    : {len(unknown)}  "
          f"(NOT analysed -- unknown, not clean)")
    print(f"  vectors not read from the script: {len(skipped_novec)}\n")

    fams = sorted({fam for _, fam in vacuous})
    print("No NaN payload to omit, so pass 98's property cannot apply:")
    for fam in fams:
        n = sum(1 for _, x in vacuous if x == fam)
        print(f"  {fam:<12} {n:>2}   {NO_NAN_BY_DESIGN[fam]}")
    print()

    inf_cells = [r for r in analysed if r[1].has_inf]
    print(f"Of the analysed, {len(inf_cells)} target a format with Inf/NaN "
          f"(HAS_INF=1); the rest have no NaN to carry.\n")

    weak, ok = [], []
    for f, fmt, lits, kinds, n, bl, bkinds in inf_cells:
        why = []
        if "nan_other" not in kinds:
            why.append("no non-canonical NaN")
        if "nan_canonical" not in kinds and "nan_other" not in kinds:
            why.append("no NaN at all")
        if "inf" not in kinds:
            why.append("no Inf")
        if n is not None and not ({"nan_other", "nan_canonical", "inf"} & bkinds):
            why.append(f"no special in b-position (cov[:{n}])")
        (weak if why else ok).append((f, why, len(lits)))

    mask_hits = []
    for f, fmt, *_ in analysed:
        text = open(os.path.join(CONF, f), encoding="utf-8",
                    errors="replace").read()
        for hit in wrong_layout_masks(fmt, text):
            mask_hits.append((f, fmt, hit))
    print(f"NaN/Inf decisions using another format's mask : {len(mask_hits)}")
    for f, fmt, (ln, src, got, want, gm, wm) in mask_hits:
        print(f"  {f}  L{ln}   ({fmt.name} = 1+{fmt.exp_bits}E+{fmt.mant_bits}M)")
        print(f"      {src}")
        print(f"      exp-mask 0x{got:04X}, correct 0x{want:04X}"
              + (f";  mant-mask 0x{gm:04X}, correct 0x{wm:04X}"
                 if gm is not None else ""))
    print()

    print(f"HAS_INF suites carrying every special-value property : {len(ok)}")
    print(f"HAS_INF suites missing at least one                  : {len(weak)}\n")
    for f, why, nl in sorted(weak):
        print(f"  {f}")
        print(f"      {nl} vector literals -- {'; '.join(why)}")
    if ok and args.verbose:
        print("\ncomplete:")
        for f, _, nl in sorted(ok):
            print(f"  {f}  ({nl} literals)")

    if skipped_novec:
        print(f"\nVectors not read from the script text ({len(skipped_novec)}) -- "
              f"unknown, not clean:")
        for f, why in sorted(skipped_novec)[:12]:
            print(f"  {f}\n      {why}")
        if len(skipped_novec) > 12:
            print(f"  ... and {len(skipped_novec) - 12} more")

    print("""
What this does and does not say. A suite listed above is not wrong and its cell is
not defective -- gf16 ADD's 512/512 was a true report of what its vectors covered.
The claim is narrower and it is about the vectors: where a special-value property is
absent, a bit-exact result cannot bound the cell's behaviour on that property, and
pass 98 is the case where exactly that gap hid a real defect.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
