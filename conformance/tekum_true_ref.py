#!/usr/bin/env python3
"""tekum_true_ref.py — tekum as the paper defines it, at last.

Implemented from arXiv:2512.10964 (Hunhold, Dec 2025), Definitions 7 and 8,
extracted from the paper's HTML on 2026-08-18 in three consistent passes
(research/TEKUM_SPEC_EXTRACT_2026-08-18.md). This file supersedes the tekum
claims of `tekum_ref.py`, which its own header now describes truthfully: a
linear binary model of takum's field layout, sharing with tekum neither base,
nor code space, nor width unit, nor sign convention.

The format, per the paper:

  * a code is an n-trit balanced-ternary string, n even, n >= 8 -- equivalently
    an integer v in [-(3^n-1)/2, +(3^n-1)/2]
  * sign:  s = sign(v). Negation is digit inversion; no sign trit.
  * anchor (Def. 7):  a = |v| - A_n,  A_n = int("1T" * n/2) = (9^(n/2)-1)/4
  * the anchored a, written as n balanced trits, splits directly:
      regime   r = value of the top 3 trits, in {-7..7} (emerges from the
               anchor: |a| <= A_n gives |a|/3^(n-3) <= 6.75)
      exponent c = max(0, |r|-2) trits, value E
      fraction p = n-3-c trits, value F, f = F/3^p in (-1/2, 1/2)
  * bias b = sign(r) * floor(3^(|r|-2) + 1), i.e. |r|: 0..7 -> 0,1,2,4,10,28,82,244
  * value = s * (1 + f) * 3^(E + b)      -- BASE THREE, exact in Fraction

Verified in __main__:
  * the paper's worked example: n=4 string 1T1T (v = 20) decodes to exactly 1.0
  * negation symmetry on every n=8 code
  * strict monotonicity in v on every n=8 code, which is what makes encode a
    bisection

Known ambiguity, carried rather than hidden: the extractions disagree on
whether NaR/zero/inf are the all-T/all-0/all-1 strings of t or of the anchored
string. This file puts them on t (the first extraction, and the only reading
consistent with the worked example, whose ANCHORED string is all zeros yet
decodes to 1.0, not to the zero special). Two codes per width are affected.
"""

import sys
from fractions import Fraction

BIAS = [0, 1, 2, 4, 10, 28, 82, 244]


def a_const(n):
    return (9 ** (n // 2) - 1) // 4


def vmax(n):
    return (3 ** n - 1) // 2


def to_trits(a, n):
    """Canonical balanced-ternary digits of a, little-endian, n trits."""
    t = []
    for _ in range(n):
        d = a % 3
        if d == 2:
            d = -1
        t.append(d)
        a = (a - d) // 3
    return t


def decode(n, v):
    """Integer code v -> exact Fraction, or the strings 'nar'/'inf'."""
    if v == 0:
        return Fraction(0)
    if v == vmax(n):
        return "inf"
    if v == -vmax(n):
        return "nar"
    s = 1 if v > 0 else -1
    a = abs(v) - a_const(n)
    t = to_trits(a, n)                     # little-endian
    r = t[n - 1] * 9 + t[n - 2] * 3 + t[n - 3]
    c = max(0, abs(r) - 2)
    E = 0
    for i in range(c):
        E = E * 3 + t[n - 4 - i]
    p = n - 3 - c
    F = 0
    for i in range(p):
        F = F * 3 + t[p - 1 - i]
    f = Fraction(F, 3 ** p)
    b = (1 if r > 0 else -1) * BIAS[abs(r)] if r != 0 else 0
    e = E + b
    return s * (1 + f) * (Fraction(3) ** e)


def encode(n, x):
    """Nearest code to the exact value x, by bisection over the monotone map."""
    x = Fraction(x)
    if x == 0:
        return 0
    lo, hi = -vmax(n) + 1, vmax(n) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if decode(n, mid) < x:
            lo = mid + 1
        else:
            hi = mid
    # lo is the smallest code with value >= x; compare with its neighbour
    cands = [lo]
    if lo - 1 > -vmax(n):
        cands.append(lo - 1)
    return min(cands, key=lambda v: abs(decode(n, v) - x))


def _selftest():
    # the paper's worked example: 1T1T = 27 - 9 + 3 - 1 = 20 -> exactly 1.0
    assert decode(4, 20) == 1, decode(4, 20)
    assert decode(4, -20) == -1

    n = 8
    prev = None
    for v in range(-vmax(n) + 1, vmax(n)):
        val = decode(n, v)
        neg = decode(n, -v)
        assert neg == -val, (v, val, neg)          # digit-inversion symmetry
        if prev is not None:
            assert val > prev, (v, prev, val)      # strict monotonicity
        prev = val
    # encode inverts decode on every code
    for v in range(-vmax(n) + 1, vmax(n), 7):
        assert encode(n, decode(n, v)) == v, v
    print(f"selftest: worked example exact; symmetry, monotonicity and "
          f"encode-inverts-decode on all {2 * vmax(n) - 1} tekum8 codes")


if __name__ == "__main__":
    _selftest()
    sys.exit(0)
