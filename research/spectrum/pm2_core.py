"""Multiply-free scale ratios over the coefficient alphabet {0,+-1,+-2}.

INDEPENDENT re-implementation (does not import spectrum.py / extend.py).

THE OBJECT
----------
A real number r > 1 is a *multiply-free scale* of register count d when r is a
root of a monic integer polynomial

    p(r) = r^d - a_{d-1} r^{d-1} - ... - a_1 r - a_0 = 0,   a_i in ALPHABET.

A value v is held as an integer coordinate vector (x_0 .. x_{d-1}) meaning
v = sum_i x_i r^i.  Multiplication by r is the companion map

    y_0 = a_0 * x_{d-1}
    y_i = x_{i-1} + a_i * x_{d-1}        (i = 1 .. d-1)

COST MODEL  (stated here, defended in the report)
-------------------------------------------------
    lane 0     y_0 = a_0 * x_{d-1}
               a_0 =  0     -> tie to zero                       0 adders
               a_0 = +-1    -> wire (or negate)                  0 adders
               a_0 = +-2    -> hardwired 1-bit left shift        0 adders
    lane i>=1  y_i = x_{i-1} + a_i * x_{d-1}
               a_i =  0     -> wire                              0 adders
               a_i = +-1    -> one add/sub                       1 adder
               a_i = +-2    -> one add/sub of a shifted operand  1 adder

    ADDERS(a) = #{ i >= 1 : a_i != 0 }

So a_0 is FREE at any allowed magnitude, and every other non-zero coefficient
costs exactly one adder/subtractor whether it is +-1 or +-2, because x<<1 is
routing on an FPGA (no LUTs, no carry chain).  This is the *only* place the
model differs from "non-zero count minus one": we do not assume a_0 != 0, we
charge lane 0 zero adders directly, which is the same number whenever a_0 != 0
and the honest number when a_0 == 0.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np

ALPHABETS = {
    "pm1": np.array([0, 1, -1], dtype=np.int64),
    "pm2": np.array([0, 1, -1, 2, -2], dtype=np.int64),
}

# Cauchy: every root of a monic p with |a_i| <= H obeys |r| < 1 + H.
ROOT_HI = {"pm1": 2.0, "pm2": 3.0}

IMAG_TOL = 1e-7      # |Im| below this -> candidate real eigenvalue
ROOT_FLOOR = 1e-7    # reject r <= 1 + this (see justification in report)


def adders(a) -> int:
    """Adder cost of the coefficient vector a = (a_0 .. a_{d-1})."""
    return int(np.count_nonzero(np.asarray(a)[1:]))


def poly_desc(a):
    """Descending integer coefficients of p(r) = r^d - sum a_i r^i."""
    a = np.asarray(a, dtype=np.int64)
    return np.concatenate(([1], -a[::-1]))


def coeff_chunk(d: int, alph: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Rows lo..hi of the full cartesian product ALPHABET^d, as (n, d) int64."""
    k = len(alph)
    rest = np.arange(lo, hi, dtype=np.int64)
    out = np.empty((hi - lo, d), dtype=np.int64)
    for i in range(d):
        out[:, i] = alph[rest % k]
        rest = rest // k
    return out


def companion_batch(A: np.ndarray) -> np.ndarray:
    """(n, d) coefficient rows -> (n, d, d) companion matrices of the map."""
    n, d = A.shape
    M = np.zeros((n, d, d), dtype=np.float64)
    if d > 1:
        i = np.arange(1, d)
        M[:, i, i - 1] = 1.0
    M[:, :, d - 1] += A.astype(np.float64)
    return M


def _newton_vec(P: np.ndarray, r: np.ndarray, iters: int = 60) -> np.ndarray:
    """Vectorised Newton polish. P: (n, m) descending float coeffs, r: (n,)."""
    r = r.astype(np.float64).copy()
    m = P.shape[1]
    for _ in range(iters):
        f = np.repeat(P[:, 0], 1).astype(np.float64)
        fp = np.zeros_like(r)
        for k in range(1, m):
            fp = fp * r + f
            f = f * r + P[:, k]
        step = np.where(fp != 0.0, f / fp, 0.0)
        r = r - step
    return r


def deflate_at_one(P: np.ndarray) -> np.ndarray:
    """Exactly divide out every (x - 1) factor, row-wise, in integer arithmetic.

    P is (n, m) DESCENDING integer coefficients.  Synthetic division by (x - 1)
    is b[k] = cumsum(c)[k]; the remainder is sum(c), so a row is divisible iff
    its coefficients sum to zero.  The quotient is left-padded with a zero so
    the array stays rectangular -- a leading zero is an exact no-op for Horner.
    """
    P = P.astype(np.int64).copy()
    for _ in range(P.shape[1]):
        m = (P.sum(axis=1) == 0) & (np.abs(P).sum(axis=1) != 0)
        if not m.any():
            break
        q = np.cumsum(P[m], axis=1)[:, :-1]
        P[m] = np.concatenate([np.zeros((q.shape[0], 1), dtype=np.int64), q], axis=1)
    return P


def roots_of_batch(A: np.ndarray, hi: float):
    """All real roots in (1+ROOT_FLOOR, hi] of the batch of polynomials A.

    Returns (root_values, row_index_into_A).  Roots at exactly 1 are removed by
    EXACT integer deflation before polishing, so no float noise around r = 1
    can survive as a spurious ratio.
    """
    M = companion_batch(A)
    w = np.linalg.eigvals(M)
    ok = (np.abs(w.imag) < IMAG_TOL) & (w.real > 1.0 + ROOT_FLOOR / 1e4) & (w.real <= hi)
    rows, cols = np.nonzero(ok)
    if rows.size == 0:
        return np.empty(0), np.empty(0, dtype=np.int64)
    r0 = w.real[rows, cols]
    sel = A[rows]
    P = deflate_at_one(np.concatenate(
        [np.ones((sel.shape[0], 1), dtype=np.int64), -sel[:, ::-1]], axis=1))
    alive = np.abs(P).sum(axis=1) != 0
    Pf = P.astype(np.float64)
    r = _newton_vec(Pf, r0)
    # residual gate: reject anything Newton did not actually drive to a root
    rr = np.where(np.isfinite(r) & (r > 0), r, 1.0)
    val = np.zeros_like(rr)
    scale = np.zeros_like(rr)
    for k in range(Pf.shape[1]):
        val = val * rr + Pf[:, k]
        scale = scale * rr + np.abs(Pf[:, k])
    converged = np.abs(val) <= 1e-9 * np.maximum(scale, 1.0)
    keep = alive & converged & np.isfinite(r) & (r > 1.0 + ROOT_FLOOR) & (r <= hi)
    return r[keep], rows[keep]


# ------------------------------------------------------------------ exact ---

def poly_eval_exact(c_desc, x: Fraction) -> Fraction:
    """Horner over exact rationals. c_desc: descending integer coefficients."""
    acc = Fraction(0)
    for co in c_desc:
        acc = acc * x + int(co)
    return acc


def certify_root(c_desc, r: float, rel: float = 1e-9) -> bool:
    """Exact IVT certificate: p changes sign across a tiny bracket around r.

    Uses exact rational arithmetic, so a True here is a proof that a real root
    of the integer polynomial lies inside the bracket.
    """
    lo = Fraction(r).limit_denominator(10 ** 15) * (1 - Fraction(rel).limit_denominator(10 ** 15))
    hi = Fraction(r).limit_denominator(10 ** 15) * (1 + Fraction(rel).limit_denominator(10 ** 15))
    a = poly_eval_exact(c_desc, lo)
    b = poly_eval_exact(c_desc, hi)
    return (a < 0 < b) or (b < 0 < a)


def _trim(p):
    """Strip leading (highest-degree) zero coefficients from a descending list."""
    i = 0
    while i < len(p) and p[i] == 0:
        i += 1
    return p[i:]


def _divmod_poly(a, b):
    """(quotient, remainder) of a / b, descending lists of Fractions.

    The quotient coefficient is placed by DEGREE, not by loop count: a single
    subtraction can cancel several leading coefficients at once, and indexing
    the quotient positionally silently drops the corresponding zeros.
    """
    a, b = _trim(list(a)), _trim(list(b))
    if not b:
        raise ZeroDivisionError
    if not a or len(a) < len(b):
        return [], a
    db = len(b) - 1
    q = [Fraction(0)] * (len(a) - db)
    while a and len(a) - 1 >= db:
        shift = (len(a) - 1) - db
        f = a[0] / b[0]
        q[len(q) - 1 - shift] = f
        for i in range(len(b)):
            a[i] -= f * b[i]
        a = _trim(a)
    return q, a


def _prem(a, b):
    """Remainder of a / b, both descending lists of Fractions."""
    return _divmod_poly(a, b)[1]


def _deriv(p):
    n = len(p) - 1
    return _trim([p[i] * (n - i) for i in range(n)])


def _gcd_poly(a, b):
    a, b = _trim(list(a)), _trim(list(b))
    while b:
        a, b = b, _prem(a, b)
    return a


def sturm_chain(c_desc):
    """Canonical Sturm chain of the SQUAREFREE PART, exact rationals."""
    p = _trim([Fraction(int(x)) for x in c_desc])
    g = _gcd_poly(p, _deriv(p))
    if len(g) > 1:                       # divide out repeated factors
        p = _trim(_divmod_poly(p, g)[0])
    chain = [p, _deriv(p)]
    while len(chain[-1]) > 1:
        r = _prem(chain[-2], chain[-1])
        if not r:
            break
        chain.append([-x for x in r])
    return chain


def sturm_count(c_desc, lo: Fraction, hi: Fraction) -> int:
    """Exact number of DISTINCT real roots in (lo, hi]."""
    chain = sturm_chain(c_desc)

    def sign_changes(x):
        s = []
        for p in chain:
            v = poly_eval_exact(p, x)
            if v != 0:
                s.append(1 if v > 0 else -1)
        return sum(1 for i in range(len(s) - 1) if s[i] != s[i + 1])

    n = sign_changes(lo) - sign_changes(hi)
    assert n >= 0, f"Sturm returned {n}: chain is wrong, do not trust this count"
    return n


# ----------------------------------------------------------------- metrics ---

def level_error(r: float) -> float:
    """Worst-case relative rounding error of a geometric grid of ratio r."""
    return (r - 1.0) / (r + 1.0)


def optimal_ratio(nbits: int, binades: float = 9.5) -> float:
    return 2.0 ** (binades / (2 ** nbits - 1))


def err_vs_optimum(r: float, r_star: float) -> float:
    """Relative error in worst-case rounding error; the established metric."""
    return level_error(r) / level_error(r_star) - 1.0
