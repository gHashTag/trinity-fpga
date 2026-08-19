#!/usr/bin/env python3
"""Recompute `tab:ladderacc` in exact rationals, as its caption promises.

The published table cannot be reproduced from the shipped oracle: the 16-bit row
carries the unfilled M=9 rung while the fill study adopts M=11, the TNF32 row is
four decimal orders better than a 21-bit mantissa can be, and the decade column
does not follow from `exp_trits` on any rung above 16. So every number here is
recomputed from `tnf_ref` with the mantissa width printed alongside it, and the
workload is built in exact rationals -- a double-precision workload cannot even
express an error of 1e-300, which is why the wide rungs must not be measured with
one.
"""
import sys
from fractions import Fraction as F
sys.path.insert(0, "../../conformance")
import tnf_ref as T
import random
from math import log10

BINS = [(0, 8), (8, 20), (20, 38)]
RUNGS = dict(T.LADDER)
RUNGS[16] = T.TNFFormat(4, 11)          # adopted in the fill study
PREC = 1200                              # significand bits of the workload

rnd = random.Random(20260809)
WORK = []                                # (value, |e|) with value an exact Fraction
for _ in range(600):
    e = rnd.randint(-38, 38)
    frac = F(rnd.getrandbits(PREC), 1 << PREC)          # in [0,1)
    m = 1 + frac                                        # significand in [1,2)
    s = rnd.choice([-1, 1])
    v = s * m * (F(2) ** e if e >= 0 else F(1, 2 ** -e))
    WORK.append((v, abs(e)))

def decades(fmt):
    """Decimal decades the exponent field spans."""
    return int(round(2 * fmt.exp_offset * log10(2)))

for w in sorted(RUNGS):
    fmt = RUNGS[w]
    cells = []
    for lo, hi in BINS:
        tot, n, out = F(0), 0, 0
        for v, ae in WORK:
            if not lo <= ae < hi:
                continue
            try:
                d = T.decode(fmt, T.encode(fmt, v))
            except Exception:
                out += 1
                continue
            if d is None or d == 0:
                out += 1
                continue
            if isinstance(d, float) and d in (float("inf"), float("-inf")):
                out += 1
                continue
            rel = abs(F(d) - v) / abs(v)
            if rel > F(1, 2):
                out += 1
                continue
            tot += rel
            n += 1
        cells.append(("%.2e" % float(tot / n) if n else "out", out))
    print("TNF%-5d M=%-5d dec=%-7d" % (w, fmt.mant_bits, decades(fmt)), cells)
