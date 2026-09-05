"""Named answers: which polynomial realises which ratio, and at what cost.

  python3 pm2_query.py minima      # cheapest realisation of the finest ratios, d<=8
  python3 pm2_query.py sparse      # k-adder families at high degree (k <= 3)
  python3 pm2_query.py targets     # nearest ratio to each N-bit optimum
"""

from __future__ import annotations

import sys
from itertools import combinations, product
from pathlib import Path

import numpy as np

from pm2_core import (ALPHABETS, ROOT_HI, coeff_chunk, err_vs_optimum,
                      level_error, optimal_ratio, roots_of_batch)

HERE = Path(__file__).resolve().parent
NBITS = (4, 5, 6, 7, 8, 9, 10)
TARGETS = {n: optimal_ratio(n) for n in NBITS}


def fmt_poly(a) -> str:
    """r^d = a_{d-1} r^{d-1} + ... + a_0, in human form."""
    a = [int(x) for x in a]
    d = len(a)
    terms = []
    for i in range(d - 1, -1, -1):
        c = a[i]
        if c == 0:
            continue
        sign = "+" if c > 0 else "-"
        mag = "" if abs(c) == 1 else "2"
        if i == 0:
            mon = "1" if mag == "" else ""
        else:
            mon = "r" if i == 1 else f"r^{i}"
        terms.append(f"{sign} {mag}{mon}")
    body = " ".join(terms)
    body = body[2:] if body.startswith("+ ") else body.replace("- ", "-", 1)
    return f"r^{d} = {body}" if body else f"r^{d} = 0"


def sweep_keep(d: int, name: str, pred, chunk: int = 150_000):
    """Full sweep at degree d, keeping (root, coeffs) for roots satisfying pred."""
    alph = ALPHABETS[name]
    hi = ROOT_HI[name]
    total = len(alph) ** d
    out = []
    for lo in range(0, total, chunk):
        A = coeff_chunk(d, alph, lo, min(lo + chunk, total))
        r, rows = roots_of_batch(A, hi)
        if r.size:
            m = pred(r)
            for rv, ri in zip(r[m], rows[m]):
                out.append((float(rv), tuple(int(x) for x in A[ri])))
    return out


def sparse_polys(d: int, k: int):
    """All (a_0..a_{d-1}) with exactly k non-zeros among a_1..a_{d-1}."""
    rows = []
    slots = range(1, d)
    for pos in combinations(slots, k):
        for vals in product((1, -1, 2, -2), repeat=k):
            for a0 in (0, 1, -1, 2, -2):
                a = [0] * d
                a[0] = a0
                for p, v in zip(pos, vals):
                    a[p] = v
                rows.append(a)
    return np.array(rows, dtype=np.int64) if rows else np.zeros((0, d), dtype=np.int64)


def best_records(recs, target=None):
    """Deduplicate on root, return sorted list."""
    seen = {}
    for r, a in recs:
        key = round(r, 11)
        cost = int(np.count_nonzero(np.asarray(a)[1:]))
        cur = seen.get(key)
        if cur is None or (cost, len(a)) < (cur[1], len(cur[2])):
            seen[key] = (r, cost, a)
    vals = list(seen.values())
    if target is None:
        vals.sort(key=lambda t: t[0])
    else:
        vals.sort(key=lambda t: abs(np.log(t[0]) - np.log(target)))
    return vals


def cmd_minima():
    print("FINEST RATIOS AT REGISTER BUDGET d <= 8, alphabet {0,+-1,+-2}")
    print("(the 8-bit optimum 1.026159 lies BELOW everything available, so the")
    print(" nearest ratio to it is simply the smallest ratio in the spectrum)\n")
    r8 = optimal_ratio(8)
    recs = []
    for d in range(1, 9):
        recs += sweep_keep(d, "pm2", lambda r: r < 1.10)
    vals = best_records(recs)
    print(f"{'r':>16} {'adders':>7} {'regs':>5} {'err vs 8-bit opt':>17}   polynomial")
    for r, cost, a in vals[:14]:
        print(f"{r:16.12f} {cost:7d} {len(a):5d} {err_vs_optimum(r, r8) * 100:+16.3f}%"
              f"   {fmt_poly(a)}")
    # cheapest realisation at each adder budget
    print("\nCHEAPEST-BY-BUDGET (smallest ratio reachable with <= k adders, d <= 8)")
    for k in range(0, 8):
        sub = [v for v in vals if v[1] <= k]
        if sub:
            r, c, a = min(sub, key=lambda t: t[0])
            print(f"  <= {k} adders: r = {r:.12f}  err {err_vs_optimum(r, r8) * 100:+7.3f}%"
                  f"  ({c} adders, {len(a)} regs)  {fmt_poly(a)}")


def cmd_sparse():
    print("LOW-ADDER FAMILIES AT HIGH REGISTER COUNT, alphabet {0,+-1,+-2}\n")
    dmax = {0: 64, 1: 64, 2: 40, 3: 20}
    store = {}
    for k in (0, 1, 2, 3):
        recs = []
        for d in range(1, dmax[k] + 1):
            A = sparse_polys(d, k)
            if A.size == 0:
                continue
            r, rows = roots_of_batch(A, ROOT_HI["pm2"])
            for rv, ri in zip(r, rows):
                recs.append((float(rv), tuple(int(x) for x in A[ri])))
        store[k] = recs
        print(f"  k={k} adders: {len(recs):,} roots > 1 up to d={dmax[k]}")
    print()
    for n in NBITS:
        t = TARGETS[n]
        print(f"--- {n} bits, optimum r* = {t:.7f} "
              f"(needs 2^(9.5/{2**n - 1}))")
        for k in (0, 1, 2, 3):
            vals = best_records(store[k], target=t)
            if not vals:
                continue
            r, cost, a = vals[0]
            print(f"    {k} adders: r = {r:.12f}  err {err_vs_optimum(r, t) * 100:+8.3f}%"
                  f"   regs={len(a):3d}   {fmt_poly(a)}")
        print()

    print("ZERO-ADDER FAMILY r^d = 2 versus ONE-ADDER FAMILY r^d = r + 1")
    print(f"{'d':>4} {'root of r^d=2':>18} {'root of r^d=r+1':>18} {'2^(1/d)':>18}  finer?")
    for d in range(2, 33):
        A = np.zeros((2, d), dtype=np.int64)
        A[0, 0] = 2                      # r^d = 2
        A[1, 0] = 1
        if d > 1:
            A[1, 1] = 1                  # r^d = r + 1
        r, rows = roots_of_batch(A, ROOT_HI["pm2"])
        got = {}
        for rv, ri in zip(r, rows):
            got[int(ri)] = float(rv)
        r0, r1 = got.get(0, float("nan")), got.get(1, float("nan"))
        print(f"{d:4d} {r0:18.12f} {r1:18.12f} {2 ** (1 / d):18.12f}"
              f"  {'yes' if r0 < r1 else 'NO':>5}")


def cmd_targets():
    print("NEAREST AVAILABLE RATIO TO EACH N-BIT OPTIMUM, register budget d <= 8")
    print("metric: relative error in worst-case rounding error (r-1)/(r+1)\n")
    tab = {}
    for name in ("pm1", "pm2"):
        z = np.load(HERE / f"{name}_d8.npz")
        tab[name] = (z["r"], z["adders"], z["deg"])
    for n in NBITS:
        t = TARGETS[n]
        print(f"--- {n} bits, optimum r* = {t:.7f}")
        for name in ("pm1", "pm2"):
            r, ad, dg = tab[name]
            i = int(np.argmin(np.abs(np.log(r) - np.log(t))))
            print(f"    {name}: r = {r[i]:.12f}  err {err_vs_optimum(float(r[i]), t) * 100:+9.4f}%"
                  f"   adders={int(ad[i])}  regs={int(dg[i])}")
            # cheapest ratio within 1% of the optimum
            close = np.abs(np.log(r) - np.log(t)) < np.log(1.0 + 0.02)
            if close.any():
                j = np.flatnonzero(close)
                j = j[np.lexsort((dg[j], ad[j]))][0]
                print(f"         cheapest within 2%: r = {r[j]:.12f} "
                      f"err {err_vs_optimum(float(r[j]), t) * 100:+8.4f}%  "
                      f"adders={int(ad[j])} regs={int(dg[j])}")
        print()


if __name__ == "__main__":
    {"minima": cmd_minima, "sparse": cmd_sparse, "targets": cmd_targets}[
        sys.argv[1] if len(sys.argv) > 1 else "minima"]()
