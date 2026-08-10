"""Answers to the five questions, with the numbers that back them."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from mpmath import mp, mpf, findroot, log as mlog, power

import sparse
from spectrum import level_error, optimal_ratio, err_vs_optimum

mp.dps = 60
HERE = Path(__file__).resolve().parent

BITS = (4, 5, 6, 7, 8, 9, 10)
TARGET = {n: optimal_ratio(n) for n in BITS}


def hp_root(a_asc, r0):
    """High-precision root of r^d = sum a_i r^i near r0, with (r-1) deflated."""
    d = len(a_asc)
    c = [1] + [-int(x) for x in a_asc[::-1]]        # descending, integer
    while len(c) > 1 and sum(c) == 0:               # exact deflation of (x-1)
        out = [c[0]]
        for k in range(1, len(c) - 1):
            out.append(out[-1] + c[k])
        c = out
    cm = [mpf(x) for x in c]

    def f(x):
        v = mpf(0)
        for k in cm:
            v = v * x + k
        return v

    return findroot(f, mpf(repr(r0)))


def fmt_poly(a):
    d = len(a)
    terms = []
    for i in range(d - 1, -1, -1):
        if a[i] == 0:
            continue
        s = "+" if a[i] > 0 else "-"
        m = abs(a[i])
        pw = "" if i == 0 else ("r" if i == 1 else f"r^{i}")
        coef = "" if (m == 1 and i > 0) else str(m)
        terms.append(f" {s} {coef}{pw}".replace("  ", " "))
    body = "".join(terms).strip()
    if body.startswith("+"):
        body = body[1:].strip()
    return f"r^{d} = {body}"


def load_spectrum():
    return json.loads((HERE / "spectrum.json").read_text())


def nearest(rows, target, max_adders=None):
    """Nearest ratio to `target` in log distance; rows are dicts with r/adders."""
    best = None
    lt = np.log(target)
    for v in rows:
        if max_adders is not None and v["adders"] > max_adders:
            continue
        dist = abs(np.log(v["r"]) - lt)
        if best is None or dist < best[0]:
            best = (dist, v)
    return None if best is None else best[1]


def section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main():
    spec = load_spectrum()

    section("0. CROSS-CHECK: reproduce the established {0,+-1} numbers, d <= 8")
    pm1 = spec["pm1"]
    print(f"distinct ratios > 1 : {len(pm1):,}   (established: 1568)")
    print(f"smallest ratio      : {pm1[0]['r']:.6f}  (established: 1.049852)")
    print(f"{'bits':>4} {'optimum r*':>12} {'nearest {0,+-1}':>16} {'err':>9} {'adds':>5} {'deg':>4}")
    for n in (4, 5, 6, 7, 8):
        t = TARGET[n]
        v = nearest(pm1, t)
        print(f"{n:>4} {t:>12.6f} {v['r']:>16.6f} "
              f"{100 * err_vs_optimum(v['r'], t):>8.2f}% {v['adders']:>5} {v['deg']:>4}")

    section("1./2. THE {0,+-1,+-2} SPECTRUM, d <= 8")
    pm2 = spec["pm2"]
    print(f"distinct ratios > 1 : {len(pm2):,}   ({len(pm2) / len(pm1):.1f}x the "
          f"{{0,+-1}} count)")
    print(f"range               : [{pm2[0]['r']:.9f}, {pm2[-1]['r']:.9f}]")
    print("\nratios reachable at each adder cost (d <= 8):")
    print(f"{'adds':>5} {'count':>9} {'min ratio':>13} {'realising polynomial':>34}")
    for k in range(0, 8):
        rows = [v for v in pm2 if v["adders"] == k]
        if not rows:
            continue
        m = min(rows, key=lambda v: v["r"])
        print(f"{k:>5} {len(rows):>9,} {m['r']:>13.9f}   {fmt_poly(m['coef'])}")

    print("\nsmallest ratio at each degree, {0,+-1} vs {0,+-1,+-2}:")
    print(f"{'d':>3} {'min {0,+-1}':>14} {'min {0,+-1,+-2}':>18} {'2^(1/d)':>12}")
    for d in range(1, 9):
        a = [v["r"] for v in pm1 if v["min_deg"] <= d]
        b = [v["r"] for v in pm2 if v["min_deg"] <= d]
        sa = f"{min(a):.9f}" if a else "-"
        print(f"{d:>3} {sa:>14} {min(b):>18.9f} {2 ** (1 / d):>12.9f}")

    section("3. THE TARGETS")
    print("metric: err = |lvl(r)/lvl(r*) - 1|, lvl(x) = (x-1)/(x+1)   [same as "
          "research/frontier/ONE_ADDER_FAMILY]")
    for n in BITS:
        t = TARGET[n]
        print(f"\n--- {n} bits, optimum r* = {t:.6f} "
              f"({2 ** n - 1} steps over 9.5 binades) ---")
        v1 = nearest(pm1, t)
        print(f"  {{0,+-1}}   d<=8 : {v1['r']:.9f}  err {100 * err_vs_optimum(v1['r'], t):7.2f}%"
              f"  adds={v1['adders']} deg={v1['deg']}")
        v2 = nearest(pm2, t)
        print(f"  {{0,+-1,+-2}} d<=8 : {v2['r']:.9f}  err {100 * err_vs_optimum(v2['r'], t):7.2f}%"
              f"  adds={v2['adders']} deg={v2['deg']}   {fmt_poly(v2['coef'])}")
        for k in (0, 1, 2, 3):
            vk = nearest(pm2, t, max_adders=k)
            if vk is None:
                continue
            print(f"      at <={k} adds : {vk['r']:.9f}  err "
                  f"{100 * err_vs_optimum(vk['r'], t):7.2f}%  deg={vk['deg']}")

    section("4. ONE-ADDER FAMILIES BEYOND DEGREE 8")
    print("sparse scan, at most 1 adder, degree 1..40\n")
    sp = sparse.scan(dmax=40, max_adders=1)
    best_by_d = {}
    for d, hits in sp.items():
        if hits:
            best_by_d[d] = min(hits, key=lambda h: h[0])
    print(f"{'d':>3} {'r^d=r+1':>12} {'2^(1/d)':>12} {'finest <=1 adder':>18} "
          f"{'adds':>5}  polynomial")
    for d in range(2, 41):
        if d not in best_by_d:
            continue
        r_fib = hp_root([1, 1] + [0] * (d - 2), 1.0 + 0.7 / d) if d >= 2 else None
        r, adds, coef = best_by_d[d]
        rp = hp_root(coef, r)
        print(f"{d:>3} {float(r_fib):>12.9f} {2 ** (1 / d):>12.9f} {float(rp):>18.9f} "
              f"{adds:>5}  {fmt_poly(coef)}")

    section("4b. THE TWO NEW FAMILIES, ASYMPTOTICALLY")
    print("zero adders : r^d = 2                  -> r = 2^(1/d)      ~ 1 + 0.6931/d")
    print("one adder   : r^d = 2r^((d+1)/2) - 1   -> r               ~ 1 + 4/(d-1)^2")
    print("one adder   : r^d = r + 1              -> r               ~ 1 + 0.6931/d\n")
    print(f"{'d':>4} {'r^d=2r^j-1':>14} {'1+4/(d-1)^2':>14} {'2^(1/d)':>12} {'r^d=r+1':>12}")
    for d in (7, 9, 11, 13, 15, 17, 21, 27, 33, 41, 55, 81, 109):
        j = (d + 1) // 2
        a = [0] * d
        a[0] = -1
        a[j] = 2
        r = hp_root(a, 1.0 + 4.0 / (d - 1) ** 2)
        r_fib = hp_root([1, 1] + [0] * (d - 2), 1.0 + 0.7 / d)
        print(f"{d:>4} {float(r):>14.9f} {1 + 4 / (d - 1) ** 2:>14.9f} "
              f"{2 ** (1 / d):>12.9f} {float(r_fib):>12.9f}")

    section("4c. BEST CHEAP RATIO FOR EACH TARGET, ANY DEGREE <= 60")
    sp2 = sparse.scan(dmax=60, max_adders=1)
    pool = []
    for d, hits in sp2.items():
        for r, adds, coef in hits:
            pool.append({"r": float(hp_root(coef, r)), "adders": adds,
                         "deg": d, "coef": coef})
    for n in BITS:
        t = TARGET[n]
        print(f"\n--- {n} bits, r* = {t:.9f} ---")
        for k in (0, 1):
            v = nearest([p for p in pool if p["adders"] <= k], t)
            cover = (2 ** n - 1) * np.log2(v["r"])
            print(f"  <={k} adds : r={v['r']:.9f}  err "
                  f"{100 * err_vs_optimum(v['r'], t):6.3f}%  regs={v['deg']:>3}  "
                  f"covers {cover:.3f} binades   {fmt_poly(v['coef'])}")
    json.dump(pool, (HERE / "sparse_pool.json").open("w"))


if __name__ == "__main__":
    main()
