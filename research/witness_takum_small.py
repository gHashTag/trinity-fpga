#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Witness takum8 and takum16 against the logarithmic reference the tree already has.

Pass 131 narrowed a three-pass thread to one open item. The published takum8 and
takum16 packs are generated from conformance/takum_ref.py, which states in its own
header that it implements a LINEAR structural model because real takum is logarithmic
and therefore irrational — and they carry no witnesses, where takum32 and takum64 carry
four each.

The tree already holds the logarithmic path: conformance/takum16_decode_conformance_ax7203.py
computes ell = (1-2S)(c + m) with mpmath at 120-bit precision and takes exp(ell/2),
describing itself as replicating the t27 verified second-witness. So the witness is a
comparison, not new work.

What this expects to find is a difference, since the two compute different functions.
The question is how large, and whether the linear model is a usable approximation of
takum or a different format wearing its field layout. Either answer is worth having and
neither is assumed here.

    python3 research/witness_takum_small.py [--width 8|16]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))

try:
    import mpmath
except ImportError:
    print("mpmath is not installed; this witness needs it.")
    print("  python3 -m pip install mpmath")
    raise SystemExit(2)

mpmath.mp.prec = 120

from crossval_unpublished import load_oracles, decode        # noqa: E402

_C_BIAS = (-255, -127, -63, -31, -15, -7, -3, -1,
           0, 1, 3, 7, 15, 31, 63, 127)


def logarithmic_value(b: int, N: int):
    """Real takum: value = (-1)^S * exp(ell/2). Transcribed from the conformance
    script's second-witness decode, parameterised by width."""
    if b == 0:
        return mpmath.mpf(0)
    if b == (1 << (N - 1)):
        return None                                    # NaR
    S = (b >> (N - 1)) & 1
    D = (b >> (N - 2)) & 1
    R_uint = (b >> (N - 5)) & 7
    c_bias = _C_BIAS[(D << 3) | R_uint]
    r_eff = (7 - R_uint) if D == 0 else R_uint
    p = N - r_eff - 5
    if p < 0:
        p = 0
    lower = b & ((1 << (r_eff + p)) - 1)
    M_uint = (lower & ((1 << p) - 1)) if p > 0 else 0
    C_uint = ((lower >> p) & ((1 << r_eff) - 1)) if r_eff > 0 else 0
    c = c_bias + C_uint
    m = mpmath.mpf(M_uint) / mpmath.mpf(2 ** p) if p > 0 else mpmath.mpf(0)
    ell = (1 - 2 * S) * (mpmath.mpf(c) + m)
    # value = (-1)^S * exp(ell/2). The sign is applied OUTSIDE the exponential --
    # exp is always positive, so folding S only into ell produces a positive value
    # for every negative code. That was this tool's first result, and a comparison
    # disagreeing by 437 binades with a sign flip is a signal about the tool.
    return ((-1) ** S) * (mpmath.e ** (ell / 2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, choices=(8, 16), default=8)
    args = ap.parse_args()
    N = args.width
    name = f"takum{N}"

    oracles = load_oracles()
    if name not in oracles:
        print(f"{name} absent from the oracle set")
        return 2
    mod, fmt = oracles[name]

    exact = 0
    finite = 0
    ratios = []
    worst = None
    special_mismatch = 0

    for b in range(1 << N):
        lin = decode(mod, fmt, b)
        log = logarithmic_value(b, N)

        lin_special = type(lin).__name__ == "Special"
        if log is None or lin_special:
            # both should call the same code NaR / special
            if not (log is None and lin_special):
                special_mismatch += 1
            continue
        if lin == 0 and log == 0:
            exact += 1
            continue
        try:
            lv = mpmath.mpf(lin.numerator) / mpmath.mpf(lin.denominator)
        except AttributeError:
            lv = mpmath.mpf(float(lin))
        if lv == 0 or log == 0:
            continue
        finite += 1
        r = lv / log
        if r == 1:
            exact += 1
        ratios.append(r)
        d = abs(mpmath.log(r, 2))
        if worst is None or d > worst[0]:
            worst = (d, b, lv, log)

    print(f"{name}: {1 << N} codes")
    print(f"  special-class mismatches (NaR/zero)   : {special_mismatch}")
    print(f"  finite codes compared                 : {finite}")
    print(f"  linear value == logarithmic value     : {exact}")
    if ratios:
        lo = min(ratios)
        hi = max(ratios)
        print(f"  ratio linear/logarithmic, min         : {mpmath.nstr(lo, 6)}")
        print(f"  ratio linear/logarithmic, max         : {mpmath.nstr(hi, 6)}")
        print(f"  worst disagreement, in binades        : "
              f"{mpmath.nstr(worst[0], 6)}  at code 0x{worst[1]:0{N // 4}X}")
        print(f"      linear      {mpmath.nstr(worst[2], 10)}")
        print(f"      logarithmic {mpmath.nstr(worst[3], 10)}")

    print("""
Read this as a measurement of the gap, not a verdict. The two paths compute different
functions by design: takum_ref.py says so in its header, and the corpus's own
comparison document says so repeatedly. What the numbers settle is whether the packs
generated from the linear path can be described as takum conformance vectors without
qualification -- and if the gap is wide, they cannot.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
