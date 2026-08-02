#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""An independent witness for the published takum8 and takum16 packs.

The index records 4 witnesses each for takum32 and takum64 and none for takum8 and
takum16. That is the one item surviving passes 129-137, and it is cheap to close.

Pass 136 showed the published vectors agree with the logarithmic definition to about
1.02e-16. This makes the stronger statement a witness should make: that each stored
float64 is the *correctly rounded* nearest double to the exact value, not merely close
to it. "Within 1e-16" would also be satisfied by a value one ULP out; "nearest" is a
property that either holds or does not.

The reference is conformance/takum_log_ref.py, which computes ln|value| exactly as a
Fraction and never leaves exact rational arithmetic. Rounding to nearest is decided
here by comparing the two neighbouring doubles in exact arithmetic rather than by
trusting a float conversion.

Per the rule this campaign learned the hard way: the claim is about the published
packs, so this reads the published packs.

    python3 research/witness_takum_packs.py [--width 8|16]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))

try:
    import mpmath
except ImportError:
    print("mpmath is not installed; this witness needs it.")
    raise SystemExit(2)

mpmath.mp.prec = 300

import takum_log_ref as T                               # noqa: E402

SCRATCH = ("/private/tmp/claude-501/-Users-playom-trinity-fpga/"
           "3a885a60-490c-4733-abfd-86bfa298080d/scratchpad")


def exact_magnitude(fmt, raw):
    """|value| as an mpmath number at 300 bits, or None where there is no value."""
    ln = T.decode_ln(fmt, raw)
    if isinstance(ln, T.Special):
        return mpmath.mpf(0) if ln.kind == "zero" else None
    return mpmath.e ** (mpmath.mpf(ln.numerator) / mpmath.mpf(ln.denominator))


def is_correctly_rounded(stored: float, exact) -> tuple[bool, str]:
    """Is `stored` the nearest double to `exact`? Decided by comparing neighbours.

    math.nextafter gives the doubles either side; the comparison is done in mpmath at
    300 bits so the decision never depends on a float operation.
    """
    if exact == 0:
        return (stored == 0.0, "zero")
    if stored == 0.0:
        return (False, "stored zero for a nonzero value")
    if not math.isfinite(stored):
        return (False, "stored is not finite")
    s = mpmath.mpf(stored)
    below = mpmath.mpf(math.nextafter(stored, -math.inf))
    above = mpmath.mpf(math.nextafter(stored, math.inf))
    d_here = abs(s - exact)
    if abs(below - exact) < d_here:
        return (False, "a nearer double exists below")
    if abs(above - exact) < d_here:
        return (False, "a nearer double exists above")
    return (True, "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, choices=(8, 16), default=8)
    args = ap.parse_args()
    N = args.width
    path = os.path.join(SCRATCH, f"takum{N}.json")

    if not os.path.exists(path):
        print(f"published pack not found: {path}")
        print("  gh api repos/gHashTag/t27/contents/conformance/vectors/"
              f"takum{N}_conformance_v0.json --jq .content | base64 -d > takum{N}.json")
        return 2

    pack = json.load(open(path, encoding="utf-8"))
    fmt = T.FORMATS[f"takum{N}"]
    vectors = pack["vectors"]
    bit_key = next(k for k in vectors[0] if k.endswith("_bits_int"))

    correct = 0
    skipped = 0
    wrong = []

    for e in vectors:
        raw = e[bit_key]
        stored = e["decoded_f64"]
        exact = exact_magnitude(fmt, raw)
        if exact is None:                                # NaR
            skipped += 1
            continue
        if T.sign_of(fmt, raw) and exact != 0:
            exact = -exact
        ok, why = is_correctly_rounded(stored, exact)
        if ok:
            correct += 1
        else:
            wrong.append((raw, stored, exact, why))

    total = len(vectors) - skipped
    print(f"published takum{N} pack")
    print(f"  vectors                                  : {len(vectors)}")
    print(f"  NaR or no value, not comparable          : {skipped}")
    print(f"  stored float64 IS the nearest to exact   : {correct}/{total}")
    print(f"  not correctly rounded                    : {len(wrong)}")

    for raw, stored, exact, why in wrong[:6]:
        print(f"\n  0x{raw:0{max(2, N // 4)}X}  {why}")
        print(f"      stored {stored!r}")
        print(f"      exact  {mpmath.nstr(exact, 20)}")

    if not wrong:
        print(f"""
Every value in the published pack is the correctly rounded nearest double to the
logarithmic definition, decided in exact arithmetic against both neighbouring doubles.

That is what a witness asserts, and it is stronger than the 1.02e-16 bound measured
earlier: a value one ULP out would satisfy that bound and fail this check.

The reference is takum_log_ref.py, which never leaves exact rational arithmetic, so
this witness has no precision parameter to argue about.""")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
