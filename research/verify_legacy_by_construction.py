#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate pdp11_float and x87_48bit against published formats they derive from.

Pass 126 showed that an oracle whose layout is exactly derivable from an
already-validated one needs no third-party implementation. Two of the six remaining
unvalidated oracles are in that position, and their own field values say so:

    pdp11_float   1 + 8E + 23M    bias 128     — and vax_f is 1 + 8E + 23M, bias 128
    x87_48bit     1 + 15E + 32M   bias 16383   — and x87_fp80 is 1 + 15E + 64M, bias 16383

`vax_f` and `x87_fp80` are both among the 83 published packs. So if the relationships
hold, these two inherit that standing.

The pdp11 case is historically expected: DEC's VAX F-format was carried over from the
PDP-11, and if the oracles agree that is a confirmation rather than a coincidence — and
if they do not, the disagreement is the finding.

The x87 case is not assumed. A 32-bit mantissa against a 64-bit one could be a
truncation, a rounding, or an unrelated encoding, so this tries the truncation
hypothesis and reports what happens instead of asserting it.

    python3 research/verify_legacy_by_construction.py [--sample N]
"""
from __future__ import annotations

import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))

from crossval_unpublished import load_oracles, decode        # noqa: E402


def structural(width: int, exp_bits: int, mant_bits: int) -> list[int]:
    emax = (1 << exp_bits) - 1
    mmax = (1 << mant_bits) - 1
    sign = 1 << (width - 1)
    out = {0, sign, 1, sign | 1, mmax, sign | mmax,
           1 << mant_bits, sign | (1 << mant_bits),
           emax << mant_bits, sign | (emax << mant_bits),
           (emax << mant_bits) | 1, (emax << mant_bits) | mmax,
           ((emax - 1) << mant_bits) | mmax}
    return sorted(c for c in out if c < (1 << width))


def same(a, b) -> bool:
    ka, kb = type(a).__name__, type(b).__name__
    if ka == "Special" or kb == "Special":
        return ka == kb and repr(a).lower() == repr(b).lower()
    try:
        return a == b
    except (TypeError, ValueError):
        return False


def compare_same_width(oracles, a_name, b_name, width, e, m, sample):
    ma, fa = oracles[a_name]
    mb, fb = oracles[b_name]
    rng = random.Random(20260802)
    codes = structural(width, e, m) + [rng.randrange(1 << width)
                                       for _ in range(sample)]
    bad, notes = 0, []
    for c in codes:
        x, y = decode(ma, fa, c), decode(mb, fb, c)
        if not same(x, y):
            bad += 1
            if len(notes) < 4:
                notes.append(f"0x{c:0{width // 4}X}: {a_name} {x!r} vs {b_name} {y!r}")
    return len(codes), bad, notes


def compare_truncation(oracles, narrow, wide, nw, ww, e, nm, wm, sample):
    """Does narrow(code) equal wide(code << (wm - nm))? Tried, not assumed."""
    mn, fn = oracles[narrow]
    mw, fw = oracles[wide]
    shift = wm - nm
    rng = random.Random(20260802)
    codes = structural(nw, e, nm) + [rng.randrange(1 << nw) for _ in range(sample)]
    bad, notes = 0, []
    for c in codes:
        x = decode(mn, fn, c)
        y = decode(mw, fw, c << shift)
        if not same(x, y):
            bad += 1
            if len(notes) < 4:
                notes.append(f"0x{c:012X}: {narrow} {x!r} vs {wide}(<<{shift}) {y!r}")
    return len(codes), bad, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=100_000)
    args = ap.parse_args()

    o = load_oracles()
    need = ["pdp11_float", "vax_f", "x87_48bit", "x87_fp80", "mxint8", "int8"]
    missing = [n for n in need if n not in o]
    if missing:
        print(f"absent from the oracle set: {', '.join(missing)}")
        return 2

    n1, b1, notes1 = compare_same_width(o, "pdp11_float", "vax_f", 32, 8, 23,
                                        args.sample)
    n2, b2, notes2 = compare_truncation(o, "x87_48bit", "x87_fp80", 48, 80, 15,
                                        32, 64, args.sample)

    # mxint8's ELEMENT decode against int8, which is published. This is not a claim
    # that the two formats are the same: an MX block is one shared e8m0 scale byte
    # plus N elements, as the oracle module's own header states, so the element
    # decode coinciding leaves the formats distinct at the block level. Which level a
    # property lives at is the question the t27-spec skill exists to force.
    mm, fm = o["mxint8"]
    mi, fi = o["int8"]
    b3 = sum(1 for c in range(256)
             if not same(decode(mm, fm, c), decode(mi, fi, c)))
    n3 = 256

    print(f"{'hypothesis':<52} {'compared':>9} {'divergences':>12}")
    print(f"  pdp11_float == vax_f (identical fields){'':<13} {n1:>9} {b1:>12}")
    print(f"  x87_48bit == x87_fp80 with a 32-bit mantissa{'':<8} {n2:>9} {b2:>12}")
    print(f"  mxint8 ELEMENT decode == int8 (exhaustive){'':<10} {n3:>9} {b3:>12}")
    for s in notes1 + notes2:
        print(f"      {s}")

    print()
    if b1 == 0:
        print("pdp11_float and vax_f decode every tested code alike. Both are 1+8E+23M")
        print("with bias 128, and vax_f is among the 83 published packs, so pdp11_float")
        print("inherits its standing. Historically expected -- DEC carried the PDP-11")
        print("F-format into the VAX -- and now measured rather than assumed.")
        print("It also raises the same question bfloat32 raised: two names, one layout.")
    else:
        print("pdp11_float and vax_f DISAGREE, which is the more interesting outcome:")
        print("the two are historically the same format, so a divergence is a defect in")
        print("one of the oracles rather than a difference between the formats.")

    if b2 == 0:
        print("\nx87_48bit is x87_fp80 with a 32-bit mantissa, confirmed on the codes")
        print("tested, so it inherits x87_fp80's standing among the 83.")
    else:
        print("\nThe truncation hypothesis for x87_48bit does NOT hold. That is a")
        print("result, not a failure: it means the format is not a narrowed x87_fp80")
        print("and needs its own reference. x87 extended carries an EXPLICIT integer")
        print("bit rather than a hidden one, so a narrowed mantissa need not line up")
        print("the way it would in an IEEE-style format.")
    if b3 == 0:
        print("\nmxint8's element decode is int8's, on all 256 codes, and int8 is among")
        print("the 83 published packs -- so the element decode inherits that standing.")
        print("It is NOT a third alias. The oracle module's own header describes an MX")
        print("block as one shared e8m0 scale byte plus N elements, so two formats whose")
        print("elements decode alike are still different formats. bfloat32 and")
        print("pdp11_float are aliases because they agree at every level; this one")
        print("agrees at one level and differs at another.")

    return 1 if (b1 or b2 or b3) else 0


if __name__ == "__main__":
    raise SystemExit(main())
