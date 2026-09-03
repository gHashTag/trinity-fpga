#!/usr/bin/env python3
"""lattice_accumulation.py — does exactness buy accuracy at depth?

Z[phi] accumulates without rounding: a layer output is a pair of integers and
nothing is lost at any depth. That is a real property and it has been the last
standing claim for the golden lattice after the area claim was withdrawn on
DSP-bearing parts (fpga/phiscale/ON_A_PART_WITH_DSP.md).

This measures what it is worth. Four paths compute the same sum of
`phi^k * <w_row, x_row>` over many rows; Z[phi] is the reference and is exact by
construction.

Run: python3 conformance/lattice_accumulation.py
"""

import random
import sys
from decimal import Decimal, getcontext

import numpy as np

getcontext().prec = 60
PHI_D = (1 + Decimal(5).sqrt()) / 2
PHI = float(PHI_D)


def zphi_pow(a, b, k):
    """Multiply a + b*phi by phi^k. Integer only; nothing rounds."""
    for _ in range(k):
        a, b = b, a + b
    return a, b


def run(rows, taps, const_bits, seed=1):
    random.seed(seed)
    ea = eb = 0
    trunc = 0
    rnd = 0
    f32 = np.float32(0)
    f64 = 0.0
    q = 1 << const_bits
    for _ in range(rows):
        w = [random.choice((-1, 0, 1)) for _ in range(taps)]
        x = [random.randrange(-120, 121) for _ in range(taps)]
        s = sum(wi * xi for wi, xi in zip(w, x))
        k = random.randrange(1, 9)
        a, b = zphi_pow(s, 0, k)
        ea += a
        eb += b
        c = round((PHI ** k) * q)
        trunc += (s * c) // q                 # floor: the strawman
        rnd += int(round(s * c / q))          # round-to-nearest: the real thing
        f32 = np.float32(f32 + np.float32(s) * np.float32(PHI ** k))
        f64 += s * (PHI ** k)
    truth = Decimal(ea) + Decimal(eb) * PHI_D

    def rel(v):
        return float(abs(Decimal(float(v)) - truth) / abs(truth)) if truth else 0.0

    return rel(trunc), rel(rnd), rel(float(f32)), rel(f64)


def main():
    print(__doc__.split("\n\n")[0])
    print()
    print("Reference: Z[phi], exact at every depth. Errors are relative to it.\n")
    print(f"  {'rows':>7} {'trunc 16b':>11} {'round 16b':>11} {'fp32':>11} {'fp64':>11}")
    for rows in (16, 256, 4096, 16384):
        t, r, a, b = run(rows, 64, 16)
        print(f"  {rows:>7} {t:>11.2e} {r:>11.2e} {a:>11.2e} {b:>11.2e}")
    print()
    print("Read honestly, because this narrows the last standing claim.")
    print()
    print("Truncation is a strawman. Flooring biases every row the same way and")
    print("the bias accumulates: 1.9% at 16384 rows. Nothing careful does that.")
    print()
    print("With ROUNDING the fixed-point path improves with depth -- 2.1e-4 at 16")
    print("rows falling to 3.5e-5 at 16384 -- because independent roundings")
    print("average. fp32 sits between 1e-7 and 4e-6 throughout.")
    print()
    print("So the exactness of Z[phi] is real and, at every depth measured here,")
    print("worth nothing against a correctly-rounded competitor. The margin it")
    print("showed in the first draft of this file was the competitor's bug.")
    print()
    print("What this does NOT establish: no training was run, where errors feed")
    print("back rather than averaging out, and no gradient path was measured.")
    print("Sixty-four taps, one distribution, one seed per row count.")


if __name__ == "__main__":
    sys.exit(main())
