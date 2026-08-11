#!/usr/bin/env python3
"""CAMPAIGN C, phase 5 -- what the correction to T39 actually is.

The freely-fitted optimal grids came back EQUAL-SPACED but ROTATED:
  SmolLM2 m=3  [0.0005 0.1238 0.2503 0.3751 0.4998 0.6246 0.7493 0.8704]
gaps 0.125 to three figures, offset ~-0.125 from the geometric grid anchored at
the octave boundary.  So T39's SHAPE result survives the failure of its
assumption; what fails is that T39 cannot see the rotation at all, because under
a log-uniform p every rotation of a geometric grid ties.

This decomposes the measured gain into
    ROTATION   geometric shape, best offset      (1 free parameter)
    SHAPE      fully free gaps                   (2^m free parameters)
each fitted on one half of a model's blocks and scored on the other half, and
each fitted on other models and scored on the held-out one.
"""
import os, sys, math, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from loguniform_verdict import (grid_geometric, waste_vec, W as Wm, Exact,
                                fit_grid, MODELS)


def best_rot(ex, m, n=2001):
    rs = np.linspace(0, 1, n)[:-1]
    c = [ex.cost(grid_geometric(m, r)) for r in rs]
    return float(rs[int(np.argmin(c))])


def gain(evx, m, G):
    a, b = waste_vec(evx, grid_geometric(m)), waste_vec(evx, G)
    d = b - a
    se = d.std(ddof=1) / math.sqrt(len(d))
    return -float(d.mean()) / float(a.mean()), -float(d.mean() / se)


def main():
    X = {k: np.load(os.path.join(HERE, f"loguniform_x_{k}.npy"))
         for k, _, _ in MODELS}
    rng = np.random.default_rng(20260811)
    HALF = {}
    for k, _, _ in MODELS:
        i = rng.permutation(len(X[k]))
        h = len(i) // 2
        HALF[k] = (X[k][i[:h]], X[k][i[h:]])
    out = {}

    print("=" * 86)
    print("R1.  ROTATION vs SHAPE, held out inside each model")
    print("     fit on a random half, score by exact round-up on the other half.")
    print("     'rotation' = geometric gaps, one fitted offset.")
    print("     'free' = all 2^m gaps fitted.  Gain is versus the geometric grid")
    print("     anchored at the octave boundary, which is what T39 blesses.")
    print("=" * 86)
    print(f"{'model':<15}{'m':>2}{'geometric':>11}{'rot gain':>10}{'t':>8}"
          f"{'free gain':>11}{'t':>8}{'best offset':>13}")
    tabR1 = {}
    for k, lb, _ in MODELS:
        fx, ev = HALF[k]
        ex = Exact(fx)
        for m in (0, 1, 2, 3, 4):
            r = best_rot(ex, m)
            gr, tr = gain(ev, m, grid_geometric(m, r))
            Gf = fit_grid(ex, m)
            gf, tf = gain(ev, m, Gf)
            tabR1[f"{k}_m{m}"] = dict(geo=Wm(ev, grid_geometric(m)), rot=r,
                                      rot_gain=gr, rot_t=tr, free_gain=gf,
                                      free_t=tf)
            print(f"{lb if m==0 else '':<15}{m:>2}{Wm(ev,grid_geometric(m)):>11.6f}"
                  f"{gr*100:>9.3f}%{tr:>8.1f}{gf*100:>10.3f}%{tf:>8.1f}{r:>13.4f}")
    out["R1_within"] = tabR1

    print()
    print("=" * 86)
    print("R2.  DOES THE OFFSET TRANSFER?  fit the offset on the other three")
    print("     models, apply it to the held-out one.  A format has to pick ONE.")
    print("=" * 86)
    print(f"{'held out':<15}{'m':>2}{'own best':>10}{'own gain':>10}"
          f"{'LOO offset':>12}{'LOO gain':>10}{'t':>9}")
    tabR2 = {}
    for k, lb, _ in MODELS:
        rest = [kk for kk, _, _ in MODELS if kk != k]
        pool = np.concatenate([X[r][::max(1, len(X[r]) // 1500000)] for r in rest])
        exl, exo = Exact(pool), Exact(X[k])
        for m in (0, 1, 2, 3, 4):
            ro, rl = best_rot(exo, m), best_rot(exl, m)
            go, _ = gain(X[k], m, grid_geometric(m, ro))
            gl, tl = gain(X[k], m, grid_geometric(m, rl))
            tabR2[f"{k}_m{m}"] = dict(own_rot=ro, own_gain=go, loo_rot=rl,
                                      loo_gain=gl, loo_t=tl)
            print(f"{lb if m==0 else '':<15}{m:>2}{ro:>10.4f}{go*100:>9.3f}%"
                  f"{rl:>12.4f}{gl*100:>9.3f}%{tl:>9.1f}")
    out["R2_transfer"] = tabR2
    wins = sum(1 for v in tabR2.values() if v["loo_gain"] > 0 and v["loo_t"] > 3)
    loss = sum(1 for v in tabR2.values() if v["loo_gain"] < 0 and v["loo_t"] < -3)
    print(f"\n     out of {len(tabR2)} held-out cells: {wins} significant WINS,"
          f" {loss} significant LOSSES")
    tot = np.mean([v["loo_gain"] for v in tabR2.values()])
    print(f"     mean held-out gain from importing another model's offset:"
          f" {tot*100:+.3f}%")

    print()
    print("=" * 86)
    print("R3.  IS THE SHAPE STILL GEOMETRIC?  gaps of the freely fitted grids,")
    print("     as a multiple of the geometric gap 2^-m.  All-ones == geometric.")
    print("=" * 86)
    for k, lb, _ in MODELS:
        fx, _ = HALF[k]
        ex = Exact(fx)
        for m in (2, 3):
            G = np.sort(fit_grid(ex, m))
            g = np.diff(np.concatenate([G, [G[0] + 1.0]])) * (1 << m)
            print(f"     {lb:<15} m={m}  " + " ".join(f"{v:5.3f}" for v in g)
                  + f"   max|g-1| = {np.abs(g-1).max():.3f}")
    print("     (a float grid at m=3 would read 1.06 1.00 0.94 0.89 0.85 0.81"
          " 0.78 0.75)")

    with open(os.path.join(HERE, "loguniform_rotation.json"), "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
