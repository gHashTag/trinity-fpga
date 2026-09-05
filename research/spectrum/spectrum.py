"""Enumerate multiply-free scale ratios: real roots r > 1 of

    r^d = a_{d-1} r^{d-1} + ... + a_1 r + a_0 ,      a_i in ALPHABET

together with the adder cost of the companion map they induce.

THE MAP.  A value v = sum_i x_i r^i is held as an integer coordinate vector
(x_0 .. x_{d-1}).  Multiplying v by r gives

    y_0 = a_0 * x_{d-1}
    y_i = x_{i-1} + a_i * x_{d-1}          (i = 1 .. d-1)

COST MODEL (adders).
    a_i = 0   ->  y_i = x_{i-1}                     : a wire.               0
    a_i = +-1 ->  y_i = x_{i-1} +- x_{d-1}          : one add/sub.          1
    a_i = +-2 ->  y_i = x_{i-1} +- (x_{d-1} << 1)   : one add/sub, the
                  shift being pure routing on an FPGA.                      1
    lane 0    ->  y_0 = a_0 * x_{d-1}, a bare negate and/or 1-bit shift.    0

So adders = #{ i >= 1 : a_i != 0 } = (number of non-zero a_i) - 1, provided
a_0 != 0.  We enforce a_0 != 0 without loss of generality: a_0 = 0 means r
divides the relation out, and the identical r reappears at degree d-1 with the
coefficients shifted down.  Every ratio therefore has a representative with
a_0 != 0 at its own minimal degree, and the "-1" in the cost formula is always
legitimate.

Registers = d (the coordinate vector).
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

ALPHABETS = {
    "pm1": (0, 1, -1),
    "pm2": (0, 1, -1, 2, -2),
}

# roots live in (1, 1 + max|a_i|]; Cauchy bound on r^d = sum a_i r^i
ROOT_HI = {"pm1": 2.0 + 1e-9, "pm2": 3.0 + 1e-9}

IMAG_TOL = 1e-7          # eigenvalue imaginary part below this -> treat as real
ABOVE_ONE = 1e-9         # eigenvalue screen: r must exceed 1 by this much
DEDUP_DECIMALS = 10      # ratios agreeing to 1e-10 are the same algebraic number

# After exact deflation of every (r-1) factor the remaining polynomial q has
# q(1) a non-zero integer, so |q(1)| >= 1.  With |q'| bounded on [1,3] by
# sum i*|c_i|*3^(i-1) < 1e6 for our degrees and heights, any true root obeys
# r - 1 >= |q(1)| / max|q'| > 1e-6.  Anything closer to 1 than this is float
# noise around the removed root at exactly 1.
TRUE_ROOT_GAP = 1e-6


def deflate_at_one(c: list[int]) -> list[int]:
    """Exactly divide out every (x - 1) factor. `c` is descending, integer."""
    c = list(c)
    while len(c) > 1 and sum(c) == 0:
        # synthetic division by (x - 1); remainder is sum(c) == 0
        out = [c[0]]
        for k in range(1, len(c) - 1):
            out.append(out[-1] + c[k])
        c = out
    return c


def coeff_table(d: int, alphabet) -> np.ndarray:
    """All coefficient vectors (a_0 .. a_{d-1}) over `alphabet` with a_0 != 0."""
    alph = np.array(alphabet, dtype=np.int64)
    nz = alph[alph != 0]
    k, m = len(alph), len(nz)
    total = m * k ** (d - 1)
    idx = np.arange(total, dtype=np.int64)
    out = np.empty((total, d), dtype=np.int64)
    out[:, 0] = nz[idx % m]
    rest = idx // m
    for i in range(1, d):
        out[:, i] = alph[rest % k]
        rest //= k
    return out


def companion_batch(A: np.ndarray) -> np.ndarray:
    """(B, d) coefficient rows -> (B, d, d) companion matrices of the map above."""
    B, d = A.shape
    M = np.zeros((B, d, d), dtype=np.float64)
    if d > 1:
        rows = np.arange(1, d)
        M[:, rows, rows - 1] = 1.0
    M[:, :, d - 1] += A.astype(np.float64)
    return M


def poly_desc(a: np.ndarray) -> np.ndarray:
    """Descending coefficients of p(r) = r^d - sum a_i r^i."""
    d = len(a)
    c = np.empty(d + 1, dtype=np.float64)
    c[0] = 1.0
    c[1:] = -np.asarray(a, dtype=np.float64)[::-1]
    return c


def newton_refine(c_int: list[int], r0: float, iters: int = 80) -> float:
    """Polish a root of the (deflated) integer polynomial `c_int`, descending."""
    c = np.array(c_int, dtype=np.float64)
    dc = np.polyder(c)
    r = float(r0)
    for _ in range(iters):
        f = float(np.polyval(c, r))
        fp = float(np.polyval(dc, r))
        if fp == 0.0:
            break
        step = f / fp
        r -= step
        if abs(step) < 1e-16 * max(1.0, abs(r)):
            break
    return r


def enumerate_degree(d: int, alphabet_name: str, chunk: int = 120_000, verbose=True):
    """Yield (root, adders, coeff_tuple) for every real root > 1 at degree d."""
    alphabet = ALPHABETS[alphabet_name]
    hi = ROOT_HI[alphabet_name]
    A = coeff_table(d, alphabet)
    total = A.shape[0]
    t0 = time.time()
    hits = []
    for s in range(0, total, chunk):
        blk = A[s:s + chunk]
        M = companion_batch(blk)
        w = np.linalg.eigvals(M)
        good = (np.abs(w.imag) < IMAG_TOL) & (w.real > 1.0 + ABOVE_ONE) & (w.real < hi)
        rows, cols = np.nonzero(good)
        if rows.size:
            roots = w.real[rows, cols]
            defl_cache: dict[int, list[int]] = {}
            for ridx, r0 in zip(rows, roots):
                ridx = int(ridx)
                q = defl_cache.get(ridx)
                if q is None:
                    a = blk[ridx]
                    q = deflate_at_one([int(x) for x in poly_desc(a)])
                    defl_cache[ridx] = q
                if len(q) < 2:
                    continue
                r = newton_refine(q, float(r0))
                if r <= 1.0 + TRUE_ROOT_GAP or r > hi:
                    continue
                a = blk[ridx]
                nnz = int(np.count_nonzero(a))
                hits.append((r, nnz - 1, tuple(int(x) for x in a)))
    if verbose:
        print(f"  d={d}: {total:,} polynomials -> {len(hits):,} root hits "
              f"({time.time() - t0:.1f}s)")
    return hits


def build_spectrum(alphabet_name: str, dmax: int, verbose=True) -> dict:
    """Distinct ratios > 1 up to degree dmax, each with its cheapest realisation."""
    best: dict[float, dict] = {}
    for d in range(1, dmax + 1):
        for r, adders, a in enumerate_degree(d, alphabet_name, verbose=verbose):
            key = round(r, DEDUP_DECIMALS)
            cur = best.get(key)
            cand = (adders, d)
            if cur is None:
                best[key] = {"r": r, "adders": adders, "deg": d, "coef": a,
                             "min_deg": d, "min_deg_adders": adders}
            else:
                # cheapest = fewest adders, then fewest registers
                if cand < (cur["adders"], cur["deg"]):
                    cur["r"], cur["adders"], cur["deg"], cur["coef"] = r, adders, d, a
                if d < cur["min_deg"]:
                    cur["min_deg"], cur["min_deg_adders"] = d, adders
                elif d == cur["min_deg"] and adders < cur["min_deg_adders"]:
                    cur["min_deg_adders"] = adders
    return best


# ---------------------------------------------------------------- metrics ---

def level_error(r: float) -> float:
    """Worst-case relative rounding error of a geometric grid of ratio r."""
    return (r - 1.0) / (r + 1.0)


def optimal_ratio(nbits: int, binades: float = 9.5) -> float:
    return 2.0 ** (binades / (2 ** nbits - 1))


def err_vs_optimum(r: float, r_star: float) -> float:
    """The metric used in research/frontier/ONE_ADDER_FAMILY: |lvl(r)/lvl(r*) - 1|."""
    return abs(level_error(r) / level_error(r_star) - 1.0)


def main():
    out = {}
    for name, dmax in (("pm1", 8), ("pm2", 8)):
        print(f"alphabet {name}, degrees 1..{dmax}")
        spec = build_spectrum(name, dmax)
        print(f"  distinct ratios > 1: {len(spec):,}")
        out[name] = spec
        rows = sorted(spec.values(), key=lambda v: v["r"])
        print(f"  smallest ratio  : {rows[0]['r']:.9f} "
              f"(adders={rows[0]['adders']}, deg={rows[0]['deg']}, coef={rows[0]['coef']})")
        print(f"  largest  ratio  : {rows[-1]['r']:.9f}")
    payload = {
        name: sorted(
            ({"r": v["r"], "adders": v["adders"], "deg": v["deg"],
              "coef": list(v["coef"]), "min_deg": v["min_deg"],
              "min_deg_adders": v["min_deg_adders"]} for v in spec.values()),
            key=lambda v: v["r"],
        )
        for name, spec in out.items()
    }
    (HERE / "spectrum.json").write_text(json.dumps(payload))
    print(f"\nwrote {HERE / 'spectrum.json'}")


if __name__ == "__main__":
    main()
