"""Exactness harness for the companion map of the headline ratios.

Three independent instruments, deliberately not sharing a code path:

 A. EXACT, over Z[x].  The map claims y = r * x in Z[r] = Z[x]/(p).  So the
    integer polynomial  x * (sum x_i x^i) - (sum y_i x^i)  must be divisible by
    p(x) with zero remainder over the integers.  Checked with exact integer
    polynomial division -- no floating point anywhere.

 B. HIGH-PRECISION NUMERIC.  Compute the real root r to 120 decimals with
    mpmath, evaluate v = sum x_i r^i and w = sum y_i r^i, and require
    |w - r*v| <= 1e-80 * sum|x_i| r^i.  The denominator is the natural
    conditioning scale, so a value v near zero cannot fake a pass.

 C. EXACT ROOT CERTIFICATE.  Sturm's theorem counts the real roots of p in
    (1, 3] exactly, and an exact rational sign change brackets the reported
    root.  This proves the number we are quoting is a real algebraic number,
    not a numerical artefact.

Run:  python3 pm2_verify.py
"""

from __future__ import annotations

import random
from fractions import Fraction

import mpmath as mp

from pm2_core import (adders, err_vs_optimum, level_error, optimal_ratio,
                      poly_desc, sturm_count)

mp.mp.dps = 120

TRIALS = 3000
SEED = 20260810

# (label, coefficient vector a_0 .. a_{d-1})
CASES = [
    ("r^27 = 2                       (0 adders, 27 regs)",
     [2] + [0] * 26),
    ("r^20 = 2r^19 + r^14 - r - 2    (3 adders, 20 regs)",
     [-2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2]),
    ("r^8 = -2r^7 +2r^5 +2r^4 +r^3 +2r^2 -2r -2   (6 adders, 8 regs)",
     [-2, -2, 2, 1, 2, 2, 0, -2]),
    ("r^7 = 2r^4 - 1                 (1 adder, 7 regs)",
     [-1, 0, 0, 0, 2, 0, 0]),
    ("r^8 = r + 1                    (1 adder, 8 regs, {0,+-1} baseline)",
     [1, 1, 0, 0, 0, 0, 0, 0]),
]


def companion_step(x, a):
    """y = r * x in coordinates. THE circuit under test."""
    d = len(a)
    y = [0] * d
    y[0] = a[0] * x[d - 1]
    for i in range(1, d):
        y[i] = x[i - 1] + a[i] * x[d - 1]
    return y


# ------------------------------------------------------- A: exact over Z[x] ---

def polydiv_exact(num, den):
    """Integer polynomial division, ascending coefficient lists. -> (q, rem)."""
    num = list(num)
    dn = len(den) - 1
    while len(num) > 1 and num[-1] == 0:
        num.pop()
    q = [0] * max(1, len(num) - dn)
    while len(num) - 1 >= dn and any(num):
        shift = len(num) - 1 - dn
        lead = num[-1]
        if lead % den[-1] != 0:
            return q, num          # not divisible over Z
        f = lead // den[-1]
        q[shift] = f
        for i in range(dn + 1):
            num[shift + i] -= f * den[i]
        while len(num) > 1 and num[-1] == 0:
            num.pop()
    return q, num


def exact_map_is_mult_by_x(x, y, a) -> bool:
    """Is x*(sum x_i t^i) - (sum y_i t^i) divisible by p(t) over Z?"""
    d = len(a)
    p_asc = [-c for c in a] + [1]              # p(t) = t^d - sum a_i t^i
    lhs = [0] * (d + 1)
    for i in range(d):
        lhs[i + 1] += x[i]                     # t * v
    for i in range(d):
        lhs[i] -= y[i]                         # - w
    _, rem = polydiv_exact(lhs, p_asc)
    return all(c == 0 for c in rem)


# ------------------------------------------- C: exact root certificate ------

def root_high_precision(a, approx):
    """The root nearest `approx`, to mp.dps digits, by BRACKETED bisection.

    A polynomial here may have several roots above 1 (r^20 = 2r^19 + ... has
    two), so bisecting the whole of (1, 3] and assuming one sign change is
    unsound.  Instead grow a bracket around the approximation until the sign
    genuinely changes, then bisect inside it.
    """
    c_desc = [int(v) for v in poly_desc(a)]

    def val(t):
        acc = mp.mpf(0)
        for co in c_desc:
            acc = acc * t + co
        return acc

    r0 = mp.mpf(approx)
    w = mp.mpf(10) ** -9
    for _ in range(60):
        lo, hi = r0 - w, r0 + w
        if val(lo) * val(hi) < 0:
            break
        w *= 2
    else:
        raise RuntimeError("no sign change bracket found around the approximation")
    flo = val(lo)
    for _ in range(600):
        mid = (lo + hi) / 2
        if val(mid) * flo > 0:
            lo, flo = mid, val(mid)
        else:
            hi = mid
    return (lo + hi) / 2


def certify(a):
    c_desc = [int(v) for v in poly_desc(a)]
    n_roots = sturm_count(c_desc, Fraction(1000001, 1000000), Fraction(3))
    r = root_high_precision(a)
    frac = Fraction(float(r)).limit_denominator(10 ** 12)
    lo, hi = frac * Fraction(999999, 1000000), frac * Fraction(1000001, 1000000)

    def ev(t):
        acc = Fraction(0)
        for co in c_desc:
            acc = acc * t + co
        return acc

    sign_change = (ev(lo) < 0 < ev(hi)) or (ev(hi) < 0 < ev(lo))
    return n_roots, sign_change, r


def house(a):
    """max |conjugate| -- the per-step growth factor of the coordinates."""
    c_desc = [int(v) for v in poly_desc(a)]
    return max(abs(z) for z in mp.polyroots([mp.mpf(c) for c in c_desc],
                                           maxsteps=200, extraprec=400))


def main():
    rng = random.Random(SEED)
    r8 = optimal_ratio(8)
    print(f"mpmath precision: {mp.mp.dps} decimal digits, {TRIALS} random vectors each")
    print(f"coordinates drawn uniformly from [-10^6, 10^6]\n")
    for label, a in CASES:
        d = len(a)
        n_roots, sign_change, r = certify(a)
        h = house(a)
        print("=" * 78)
        print(label)
        print(f"  registers d = {d}   adders = {adders(a)}")
        print(f"  r  = {mp.nstr(r, 30)}")
        print(f"  Sturm: {n_roots} real root(s) in (1.000001, 3]; "
              f"exact sign-change bracket: {'YES' if sign_change else 'NO'}")
        print(f"  err vs 8-bit optimum: {err_vs_optimum(float(r), r8) * 100:+.4f}%   "
              f"house (coord growth/step) = {mp.nstr(h, 8)}")

        bad_exact = bad_num = 0
        worst = mp.mpf(0)
        for _ in range(TRIALS):
            x = [rng.randint(-10 ** 6, 10 ** 6) for _ in range(d)]
            y = companion_step(x, a)
            if not exact_map_is_mult_by_x(x, y, a):
                bad_exact += 1
            v = w = s = mp.mpf(0)
            for i in range(d):
                pw = r ** i
                v += x[i] * pw
                w += y[i] * pw
                s += abs(x[i]) * pw
            resid = abs(w - r * v)
            rel = resid / s
            worst = max(worst, rel)
            if rel > mp.mpf(10) ** -80:
                bad_num += 1
        print(f"  A. exact Z[x] divisibility : {TRIALS - bad_exact}/{TRIALS} pass, "
              f"MISMATCHES = {bad_exact}")
        print(f"  B. 120-digit numeric r*v=w : {TRIALS - bad_num}/{TRIALS} pass, "
              f"MISMATCHES = {bad_num}   (worst relative residual {mp.nstr(worst, 6)})")


if __name__ == "__main__":
    main()
