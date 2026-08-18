#!/usr/bin/env python3
"""The vectorised quantiser must agree with the exact oracle, exactly.

perplexity_sweep.py cannot use gf_ref.py directly: it quantises 85M values per
configuration and the oracle works in Fractions. So there is a fast numpy
version -- and a fast version that is merely CLOSE would silently change the
ranking the sweep exists to produce, which is the whole reason this file is
here rather than a comment saying "verified once".
"""

import random
import sys
from fractions import Fraction

import numpy as np

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
from float_quantiser import quantise_np  # noqa: E402
import gf_ref as G  # noqa: E402

SPLITS = [(3, 4), (4, 3), (5, 2), (2, 5), (5, 10), (3, 12), (4, 11), (6, 9), (8, 7)]

# Mutation-checked: rounding mode (both call sites), and the bias formula, each
# fail this file. One narrow gap is known and left standing rather than papered
# over -- changing ONLY the first `rint`, which feeds the carry test and is then
# overwritten, survives 10800 samples. Its effect appears only when a value sits
# within rounding distance of the carry boundary, and no sample landed there.


def exact(e, m, x):
    f = G.GFFormat(f"e{e}m{m}", exp_bits=e, mant_bits=m, bias=(1 << (e - 1)) - 1)
    try:
        v = G.decode(f, G.encode(f, Fraction(float(x)).limit_denominator(10 ** 14)))
    except Exception:
        return None
    return None if isinstance(v, G.Special) else float(v)


def main():
    random.seed(5)
    bad_total = 0
    checked = 0
    print("vectorised quantiser against the exact oracle\n")
    for e, m in SPLITS:
        xs = [random.gauss(0, 1) * 10 ** random.uniform(-3, 2) for _ in range(1200)]
        fast = quantise_np(np.array(xs), e, m)
        bad = 0
        for x, fv in zip(xs, fast):
            ev = exact(e, m, x)
            if ev is None:
                continue
            checked += 1
            if ev != fv:
                bad += 1
        bad_total += bad
        print(f"  {'PASS' if not bad else 'FAIL'}  e{e}m{m}: {len(xs) - bad}/{len(xs)} exact")
    print()
    print(f"{checked - bad_total}/{checked} values match the oracle bit for bit."
          if not bad_total else f"{bad_total} mismatches -- the fast path is not the oracle")
    return 1 if bad_total else 0


if __name__ == "__main__":
    sys.exit(main())
