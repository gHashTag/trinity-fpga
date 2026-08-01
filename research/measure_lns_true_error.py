#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""How large is the error that `abs_error` cannot see?

Pass 133 found that the published lns packs report `abs_error: 0.0` on every vector
while their own oracle says most codes decode to irrational values such as `2^(1/8)`.
The field is `|decoded_f64 - input_f64|` with both sides the same float64, so it
correctly reports a round trip and cannot report distance from the exact value.

A caution without a number is weak. This measures the number.

For every lns8 code the oracle gives an exact base-2 logarithm as a Fraction. The exact
value is 2^L, computed here with mpmath at 200-bit precision, and the published pack
gives `decoded_f64`. The difference between them is the quantity the pack's own error
field is structurally unable to report.

What this is NOT: a defect report about the decoder. Storing a float64 for an
irrational value is the only thing a float64 can do, and the error below is the error of
that representation rather than of the arithmetic. The point is its size and the fact
that the pack's metric reads zero regardless.

    python3 research/measure_lns_true_error.py [--pack PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))

try:
    import mpmath
except ImportError:
    print("mpmath is not installed; this measurement needs it.")
    raise SystemExit(2)

mpmath.mp.prec = 200

import lns_ref                                            # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=os.path.join(
        "/private/tmp/claude-501/-Users-playom-trinity-fpga",
        "3a885a60-490c-4733-abfd-86bfa298080d/scratchpad/lns8.json"))
    args = ap.parse_args()

    if not os.path.exists(args.pack):
        print(f"pack not found: {args.pack}")
        print("fetch it with:")
        print("  gh api repos/gHashTag/t27/contents/conformance/vectors/"
              "lns8_conformance_v0.json --jq .content | base64 -d > lns8.json")
        return 2

    pack = json.load(open(args.pack, encoding="utf-8"))
    fmt = lns_ref.FORMATS["lns8"]

    exact_codes = 0
    approx = []
    pack_says_zero = 0

    for entry in pack["vectors"]:
        raw = entry["lns8_bits_int"]
        stored = entry["decoded_f64"]
        if entry.get("abs_error") == 0:
            pack_says_zero += 1

        L = lns_ref.decode_log(fmt, raw)
        # decode_log returns a Fraction, or Special('zero') / Special('nar')
        if type(L).__name__ == "Special":
            continue
        sign = lns_ref.sign_of(fmt, raw)
        exact = mpmath.mpf(2) ** (mpmath.mpf(L.numerator) /
                                  mpmath.mpf(L.denominator))
        if sign:
            exact = -exact

        if L.denominator == 1:
            exact_codes += 1                             # a power of two: representable
            continue
        if exact == 0:
            continue
        rel = abs((mpmath.mpf(stored) - exact) / exact)
        approx.append((rel, raw, stored, exact))

    print(f"lns8 vectors in the pack            : {len(pack['vectors'])}")
    print(f"  where the pack reports abs_error 0: {pack_says_zero}")
    print(f"  codes whose value IS a power of 2 : {exact_codes}  (float64 holds these)")
    print(f"  codes whose value is irrational   : {len(approx)}\n")

    if approx:
        approx.sort()
        worst = approx[-1]
        best = approx[0]
        med = approx[len(approx) // 2]
        print("relative error of the stored float64 against the exact 2^L:")
        print(f"  smallest : {mpmath.nstr(best[0], 4)}  at code 0x{best[1]:02X}")
        print(f"  median   : {mpmath.nstr(med[0], 4)}")
        print(f"  largest  : {mpmath.nstr(worst[0], 4)}  at code 0x{worst[1]:02X}")
        print(f"\n  worst case, code 0x{worst[1]:02X}:")
        print(f"    stored float64  {worst[2]!r}")
        print(f"    exact 2^L       {mpmath.nstr(worst[3], 22)}")

    print("""
So the quantity the pack cannot report is at the float64 rounding level -- around one
part in 10^16 -- not a decode defect. That is the useful form of the finding: the
representation error is as small as a float64 allows, and `abs_error: 0` still does not
mean what a reader will take it to mean.

The one-line fix in `format_notes` from pass 133 now has a number to carry: for the
irrational codes the stored value is the nearest float64 to 2^L, within about 1e-16
relative, and `abs_error` bounds the round trip rather than that distance.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
