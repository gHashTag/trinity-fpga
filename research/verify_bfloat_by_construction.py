#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate bfloat24 and bfloat32 without a third-party implementation.

Pass 125 cross-validated five of the thirteen unpublished oracles and left eight
unvalidated for want of an independent implementation. Two of those eight do not need
one, because their layout makes them derivable from a format that is already validated.

Reading the oracles' own field values:

    bfloat16   1 + 8E + 7M    bias 127
    bfloat24   1 + 8E + 15M   bias 127
    bfloat32   1 + 8E + 23M   bias 127
    binary32   1 + 8E + 23M   bias 127

So bfloat32 and binary32 have identical fields, identical bias, and identical special
codes -- and binary32 is one of the 83 published, cross-validated packs. If the two
decode every code alike, bfloat32 inherits that validation entire.

bfloat24 is the same exponent field over a 15-bit mantissa, which is binary32 with the
low 8 mantissa bits removed. Every bfloat24 code should therefore decode to exactly
what binary32 decodes for that code shifted up by 8 -- checkable against numpy's
float32 with no oracle involved on the reference side.

Neither check needs a third party. Both are stronger than a sample, because the
relationship is exact rather than approximate.

    python3 research/verify_bfloat_by_construction.py [--sample N]
"""
from __future__ import annotations

import argparse
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))

from crossval_unpublished import load_oracles, decode        # noqa: E402


def structural_codes(width: int, exp_bits: int, mant_bits: int) -> list[int]:
    """Zero, both signs, every exponent boundary, both NaN payload ends."""
    emax = (1 << exp_bits) - 1
    mmax = (1 << mant_bits) - 1
    sign = 1 << (width - 1)
    out = {0, sign, 1, sign | 1, mmax, sign | mmax,
           1 << mant_bits, sign | (1 << mant_bits),
           emax << mant_bits, sign | (emax << mant_bits),
           (emax << mant_bits) | 1, (emax << mant_bits) | mmax,
           ((emax - 1) << mant_bits) | mmax,
           127 << mant_bits}
    return sorted(out)


def same_value(a, b) -> bool:
    """Compare an oracle result against another, tolerating the Special marker."""
    ka, kb = type(a).__name__, type(b).__name__
    sa, sb = repr(a).lower(), repr(b).lower()
    if ka == "Special" or kb == "Special":
        if ka != kb:
            return False
        return sa == sb
    try:
        return a == b
    except (TypeError, ValueError):
        return False


def check_bfloat32(oracles, sample: int) -> tuple[int, int, list[str]]:
    """bfloat32 and binary32 have identical fields; do they decode identically?"""
    m1, f1 = oracles["bfloat32"]
    m2, f2 = oracles["binary32"]
    rng = random.Random(20260802)
    codes = structural_codes(32, 8, 23) + [rng.randrange(1 << 32)
                                           for _ in range(sample)]
    bad, notes = 0, []
    for c in codes:
        x, y = decode(m1, f1, c), decode(m2, f2, c)
        if not same_value(x, y):
            bad += 1
            if len(notes) < 4:
                notes.append(f"0x{c:08X}: bfloat32 {x!r} vs binary32 {y!r}")
    return len(codes), bad, notes


def check_bfloat24(oracles, sample: int) -> tuple[int, int, list[str]]:
    """bfloat24 is binary32 with the low 8 mantissa bits removed.

    numpy is the reference here, not another oracle, so this is an independent check
    rather than a consistency one.
    """
    m, f = oracles["bfloat24"]
    rng = random.Random(20260802)
    codes = structural_codes(24, 8, 15) + [rng.randrange(1 << 24)
                                           for _ in range(sample)]
    bad, notes = 0, []
    for c in codes:
        word = c << 8                       # widen to a binary32 bit pattern
        ref = struct.unpack(">f", struct.pack(">I", word))[0]
        ours = decode(m, f, c)
        kind = type(ours).__name__
        if ref != ref:                                    # NaN
            ok = kind == "Special" and "nan" in repr(ours).lower()
        elif ref in (float("inf"), float("-inf")):
            ok = kind == "Special" and "inf" in repr(ours).lower()
        elif kind == "Special":
            ok = False
        else:
            try:
                ok = float(ours) == ref
            except (TypeError, ValueError, OverflowError):
                ok = False
        if not ok:
            bad += 1
            if len(notes) < 4:
                notes.append(f"0x{c:06X}: ours {ours!r} vs float32 {ref!r}")
    return len(codes), bad, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200_000)
    args = ap.parse_args()

    oracles = load_oracles()
    missing = [n for n in ("bfloat24", "bfloat32", "binary32")
               if n not in oracles]
    if missing:
        print(f"absent from the oracle set: {', '.join(missing)}")
        return 2

    n32, bad32, notes32 = check_bfloat32(oracles, args.sample)
    n24, bad24, notes24 = check_bfloat24(oracles, args.sample)

    print(f"{'check':<44} {'compared':>9} {'divergences':>12}")
    print(f"  bfloat32 == binary32 (identical fields){'':<6} {n32:>9} {bad32:>12}")
    print(f"  bfloat24 == binary32 truncated to 24 bits{'':<3} {n24:>9} {bad24:>12}")
    for s in notes32 + notes24:
        print(f"      {s}")

    if not (bad32 or bad24):
        print("""
Both hold. bfloat32 decodes every tested code exactly as binary32 does, and binary32 is
one of the 83 published packs with third-party cross-validation behind it -- so
bfloat32 inherits that. bfloat24 matches numpy's float32 on the widened word, which is
an independent reference rather than another oracle in this tree.

That takes the unvalidated set from eight to six: mxint8, pdp11_float, tekum8,
tekum16, tekum32, x87_48bit.

One question this raises rather than answers: if bfloat32 is bit-identical to binary32
in every field and every decoded value, publishing it as a separate format needs a
reason. It may have one -- a distinct provenance or intended use -- but the catalogue
should say what it is.""")
    return 1 if (bad32 or bad24) else 0


if __name__ == "__main__":
    raise SystemExit(main())
