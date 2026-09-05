"""Sparse (low-adder) families to high degree.

The full enumeration is 5^d and dies around degree 10.  But the interesting
ratios for hardware are the CHEAP ones, and cheap means sparse: at most k
non-zero coefficients above lane 0.  The count of such polynomials is
4 * sum_{j<=k} 4^j * C(d-1, j), which is polynomial in d, so degree 100 is free.

Root finding here is grid + bisection on sign changes.  That can only MISS a
root (an even-multiplicity one that touches the axis without crossing); it can
never invent one.  Every ratio reported is therefore real.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

NZ = (1, -1, 2, -2)


def sparse_polys(d: int, max_adders: int):
    """Descending integer coefficient rows for degree-d polys with <=max_adders adds."""
    rows = []
    positions = range(1, d)
    for k in range(0, max_adders + 1):
        for pos in itertools.combinations(positions, k):
            for vals in itertools.product(NZ, repeat=k):
                for a0 in NZ:
                    a = [0] * d
                    a[0] = a0
                    for p, v in zip(pos, vals):
                        a[p] = v
                    rows.append(a)
    A = np.array(rows, dtype=np.int64)          # ascending a_0..a_{d-1}
    C = np.empty((A.shape[0], d + 1), dtype=np.float64)
    C[:, 0] = 1.0
    C[:, 1:] = -A[:, ::-1]                      # descending r^d ... r^0
    return A, C


def roots_above_one(C: np.ndarray, lo=1.0, hi=3.0, grid=6000, iters=200):
    """All sign-change roots in (lo, hi) for every row of C. Returns (row, root)."""
    d = C.shape[1] - 1
    g = np.exp(np.linspace(np.log(lo + 1e-12), np.log(hi), grid))
    V = np.vander(g, d + 1, increasing=False).T          # (d+1, grid)
    P = C @ V
    s = np.signbit(P)
    chg = (s[:, :-1] != s[:, 1:]) & (P[:, :-1] != 0.0)
    rows, gi = np.nonzero(chg)
    if rows.size == 0:
        return np.empty(0, dtype=np.int64), np.empty(0)
    a = g[gi].copy()
    b = g[gi + 1].copy()
    fa = P[rows, gi].copy()
    Csub = C[rows]
    for _ in range(iters):
        m = 0.5 * (a + b)
        fm = np.einsum('ij,ij->i', Csub, np.vander(m, d + 1, increasing=False))
        left = np.signbit(fm) == np.signbit(fa)
        a = np.where(left, m, a)
        fa = np.where(left, fm, fa)
        b = np.where(left, b, m)
    return rows, 0.5 * (a + b)


def polish(a_asc: np.ndarray, r0: float, iters: int = 200) -> float:
    """Newton polish in float64 on the exact integer polynomial."""
    d = len(a_asc)
    c = np.empty(d + 1)
    c[0] = 1.0
    c[1:] = -a_asc[::-1]
    dc = np.polyder(c)
    r = float(r0)
    for _ in range(iters):
        fp = float(np.polyval(dc, r))
        if fp == 0.0:
            break
        step = float(np.polyval(c, r)) / fp
        r -= step
        if abs(step) < 1e-16 * max(1.0, abs(r)):
            break
    return r


def scan(dmax: int, max_adders: int, root_hi=3.0, dmin=1):
    """{degree: [(root, adders, coeff_tuple), ...]}"""
    out = {}
    for d in range(dmin, dmax + 1):
        A, C = sparse_polys(d, max_adders)
        rows, roots = roots_above_one(C, hi=root_hi)
        hits = []
        for ri, r0 in zip(rows, roots):
            a = A[ri]
            r = polish(a, float(r0))
            if r <= 1.0 + 1e-12 or r > root_hi:
                continue
            hits.append((r, int(np.count_nonzero(a)) - 1, tuple(int(x) for x in a)))
        out[d] = hits
    return out


if __name__ == "__main__":
    res = scan(dmax=12, max_adders=1)
    for d in sorted(res):
        rs = sorted(res[d])
        print(f"d={d}: {len(rs)} roots>1, min={rs[0][0]:.9f} coef={rs[0][2]}")
