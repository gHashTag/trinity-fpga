"""Full enumeration of the multiply-free ratio spectrum.

  python3 pm2_full.py pm1 8
  python3 pm2_full.py pm2 8

Writes <alphabet>_d<dmax>.npz holding, for every DISTINCT ratio r > 1 found at
degree <= dmax, the cheapest realisation (fewest adders, then fewest registers).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

from pm2_core import ALPHABETS, ROOT_HI, adders, coeff_chunk, roots_of_batch

HERE = Path(__file__).resolve().parent

# Two polished roots closer than this are treated as the same algebraic number.
CLUSTER_REL = 1e-11


def sweep_degree(d: int, name: str, chunk: int = 150_000, verbose: bool = True):
    """Return (roots, adder_costs) as float64/int8 arrays for degree exactly d."""
    alph = ALPHABETS[name]
    hi = ROOT_HI[name]
    total = len(alph) ** d
    R, C = [], []
    t0 = time.time()
    for lo in range(0, total, chunk):
        A = coeff_chunk(d, alph, lo, min(lo + chunk, total))
        r, rows = roots_of_batch(A, hi)
        if r.size:
            R.append(r)
            C.append(np.count_nonzero(A[rows][:, 1:], axis=1).astype(np.int8))
    r = np.concatenate(R) if R else np.empty(0)
    c = np.concatenate(C) if C else np.empty(0, dtype=np.int8)
    if verbose:
        print(f"  d={d:2d}  {total:>12,} polys -> {r.size:>10,} real roots>1"
              f"   ({time.time() - t0:.1f}s)", flush=True)
    return r, c


def dedup(roots: np.ndarray, cost: np.ndarray, deg: np.ndarray):
    """Cluster near-equal roots; keep min (adders, degree) per cluster."""
    o = np.argsort(roots, kind="stable")
    roots, cost, deg = roots[o], cost[o], deg[o]
    new = np.empty(roots.size, dtype=bool)
    new[0] = True
    new[1:] = (roots[1:] - roots[:-1]) > CLUSTER_REL * roots[1:]
    gid = np.cumsum(new) - 1
    n = gid[-1] + 1
    best_r = np.zeros(n)
    best_c = np.full(n, 127, dtype=np.int16)
    best_d = np.full(n, 127, dtype=np.int16)
    np.minimum.at(best_c, gid, cost.astype(np.int16))
    # among realisations with the minimal adder count, take the smallest degree
    ok = cost.astype(np.int16) == best_c[gid]
    np.minimum.at(best_d, gid[ok], deg[ok].astype(np.int16))
    best_r[gid] = roots            # any member; they agree to CLUSTER_REL
    return best_r, best_c, best_d


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "pm2"
    dmax = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    print(f"alphabet {name} = {list(ALPHABETS[name])}, degrees 1..{dmax}")
    R, C, D = [], [], []
    for d in range(1, dmax + 1):
        r, c = sweep_degree(d, name)
        R.append(r)
        C.append(c)
        D.append(np.full(r.size, d, dtype=np.int16))
    roots = np.concatenate(R)
    cost = np.concatenate(C)
    deg = np.concatenate(D)
    print(f"  total real roots > 1 (with multiplicity across polys): {roots.size:,}")
    br, bc, bd = dedup(roots, cost, deg)
    print(f"  DISTINCT ratios > 1: {br.size:,}")
    gaps = np.diff(br)
    print(f"  smallest gap between distinct ratios: {gaps.min():.3e}"
          f"  (cluster tolerance {CLUSTER_REL:.0e} relative)")
    print(f"  smallest ratio: {br[0]:.12f}  adders={bc[0]}  registers={bd[0]}")
    print(f"  largest  ratio: {br[-1]:.12f}")
    for k in range(0, int(bc.max()) + 1):
        m = bc == k
        if m.any():
            print(f"    adders={k}: {m.sum():>6,} ratios, min r = {br[m].min():.12f}")
    np.savez_compressed(HERE / f"{name}_d{dmax}.npz", r=br, adders=bc, deg=bd)
    print(f"wrote {HERE / f'{name}_d{dmax}.npz'}")


if __name__ == "__main__":
    main()
