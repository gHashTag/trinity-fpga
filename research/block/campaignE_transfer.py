#!/usr/bin/env python3
"""T42's transfer statement, made numerical.

T42 says the margin is a functional of the checkpoint's block-normalised value
distribution rho.  Three things follow that this file measures:

1. HOW SIMILAR ARE THE rho's?  Total-variation distance between the s^2-weighted
   normalised-magnitude histograms of every pair of checkpoints.  If rho were
   universal the margin would be universal too and there would be nothing to
   explain.

2. WHICH TERM MOVES THE MARGIN?  The predicted margin is -R*L.  R is the
   codebook-and-rho term; L = log ppl_MXFP4 - log ppl_fp32 is how much damage the
   PARENT already does to that checkpoint.  Decompose the cross-checkpoint spread
   of log|margin| into the two.

3. DOES rho-SIMILARITY BUY MARGIN-SIMILARITY?  Correlate pairwise d_TV with
   pairwise |R_i - R_j| and with pairwise |margin_i - margin_j|.  Pairs are NOT
   independent -- n(n-1)/2 pairs come from n checkpoints -- so this is reported
   with a Mantel-style permutation over checkpoint labels, not a naive p.

    python3 campaignE_transfer.py
"""
import json
import math
import os
from itertools import combinations, permutations

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    occ = json.load(open(os.path.join(HERE, "campaignE_occupancy.json")))
    rows = json.load(open(os.path.join(HERE, "campaignE_score.json")))
    by = {r["model"]: r for r in rows}
    names = [r["model"] for r in rows]
    return occ, by, names


def spearman(a, b):
    ra = np.argsort(np.argsort(np.asarray(a, float)))
    rb = np.argsort(np.argsort(np.asarray(b, float)))
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    occ, by, names = load()
    n = len(names)
    H = {m: np.array(occ[m]["hist_abs"]) for m in names}

    print("=" * 84)
    print("1. HOW DIFFERENT ARE THE BLOCK-NORMALISED DISTRIBUTIONS?")
    print("   total-variation distance between s^2-weighted |y| histograms")
    print("=" * 84)
    print(f"{'':<13}" + "".join(f"{m[:9]:>10}" for m in names))
    tv = {}
    for a in names:
        row = ""
        for b in names:
            d = 0.5 * float(np.abs(H[a] - H[b]).sum())
            tv[(a, b)] = d
            row += f"{d:>10.4f}"
        print(f"{a:<13}{row}")
    off = [tv[(a, b)] for a, b in combinations(names, 2)]
    print(f"\n   pairwise d_TV: min {min(off):.4f}  median {np.median(off):.4f}"
          f"  max {max(off):.4f}   over {len(off)} pairs")

    print("\n" + "=" * 84)
    print("2. WHICH TERM MOVES THE MARGIN?   predicted margin = -R * L")
    print("=" * 84)
    R = np.array([by[m]["R"] for m in names])
    L = np.array([by[m]["L_here"] for m in names])
    meas = np.array([by[m]["meas_pct"] for m in names])
    print(f"{'model':<13}{'R':>10}{'L':>10}{'-R*L (pred %)':>16}{'meas %':>10}")
    for i, m in enumerate(names):
        print(f"{m:<13}{R[i]:>10.5f}{L[i]:>10.5f}"
              f"{100*(math.exp(-R[i]*L[i])-1):>16.3f}{meas[i]:>10.3f}")
    print(f"\n   spread(R)    max/min = {R.max()/R.min():.3f}"
          f"   sd(log R) = {np.std(np.log(R), ddof=1):.4f}")
    print(f"   spread(L)    max/min = {L.max()/L.min():.3f}"
          f"   sd(log L) = {np.std(np.log(L), ddof=1):.4f}")
    print(f"   spread(meas) max/min = {abs(meas).max()/abs(meas).min():.3f}"
          f"   sd(log|meas|) = {np.std(np.log(np.abs(meas)), ddof=1):.4f}")
    vR = np.var(np.log(R), ddof=1)
    vL = np.var(np.log(L), ddof=1)
    print(f"\n   var(log R) = {vR:.5f}   var(log L) = {vL:.5f}"
          f"   -> L carries {100*vL/(vR+vL):.1f} % of the predicted spread")
    print(f"   rho(L, |meas|)  = {spearman(L, np.abs(meas)):+.3f}")
    print(f"   rho(R, |meas|)  = {spearman(R, np.abs(meas)):+.3f}")
    print(f"   rho(R*L, |meas|)= {spearman(R*L, np.abs(meas)):+.3f}")

    print("\n" + "=" * 84)
    print("3. DOES rho-SIMILARITY BUY MARGIN-SIMILARITY?  (Mantel, labels permuted)")
    print("=" * 84)
    idx = {m: i for i, m in enumerate(names)}
    pairs = list(combinations(names, 2))
    d_tv = np.array([tv[p] for p in pairs])
    d_R = np.array([abs(R[idx[a]] - R[idx[b]]) for a, b in pairs])
    d_m = np.array([abs(meas[idx[a]] - meas[idx[b]]) for a, b in pairs])

    def mantel(x, key):
        obs = spearman(d_tv, x)
        cnt = tot = 0
        for p in permutations(range(n)):
            xp = np.array([abs(key[p[idx[a]]] - key[p[idx[b]]]) for a, b in pairs])
            if abs(spearman(d_tv, xp)) >= abs(obs) - 1e-12:
                cnt += 1
            tot += 1
        return obs, cnt / tot

    o1, p1 = mantel(d_R, R)
    o2, p2 = mantel(d_m, meas)
    print(f"   d_TV vs |dR|      rho = {o1:+.3f}   Mantel p = {p1:.4f}"
          f"   ({len(pairs)} pairs from n = {n} checkpoints)")
    print(f"   d_TV vs |dmargin| rho = {o2:+.3f}   Mantel p = {p2:.4f}")

    print("\n" + "=" * 84)
    print("4. LEAVE-ONE-OUT ROTATION, WHOLE  (nothing here was chosen on data;")
    print("   the campaign reports the rotation anyway)")
    print("=" * 84)
    pred = np.array([by[m]["pred_pct"] for m in names])
    print(f"{'dropped':<14}{'rho(pred,meas)':>16}{'rho(R,Rhat)':>14}")
    Rh = np.array([by[m]["Rhat"] for m in names])
    for i, m in enumerate(names):
        k = [j for j in range(n) if j != i]
        print(f"{m:<14}{spearman(pred[k], meas[k]):>+16.3f}"
              f"{spearman(R[k], Rh[k]):>+14.3f}")
    print(f"{'(none)':<14}{spearman(pred, meas):>+16.3f}{spearman(R, Rh):>+14.3f}")

    json.dump({"tv": {f"{a}|{b}": tv[(a, b)] for a, b in pairs},
               "var_logR": vR, "var_logL": vL,
               "mantel_R": [o1, p1], "mantel_margin": [o2, p2]},
              open(os.path.join(HERE, "campaignE_transfer.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
