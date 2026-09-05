#!/usr/bin/env python3
"""LINE B: the outcome of the pre-registered X/G test, on the NEW checkpoints alone.

X/G was found by inspecting T41's components after its primary predictor failed,
on the four checkpoints whose margins were already known.  Quoting a rank
correlation over those four plus new ones would inflate it, because the old four
are exactly where the ordering was read off.  The honest number is the one
computed on the checkpoints registered in lineB_prereg.json and nowhere else, and
that is what this file prints first.

REPLICATE UNITS, stated at the site rather than implied by a reshape:
  * the rank test and the sign test take n = MODELS.  Each checkpoint is one
    point.  Windows are replicates of wikitext-2, not of the model family, so
    they cannot enlarge n here.
  * the per-model confidence interval on a margin takes n = WINDOWS and is a
    WITHIN-model statement only: it says that model's effect is not noise, and
    says nothing about the cross-model comparison.

Nothing is reimplemented: Spearman and its exact permutation null come from
lineD_predict, the paired window statistics from campaignC_stats.

    python3 lineB_test.py
"""
import glob
import json
import os

import numpy as np
from scipy.stats import binomtest

import campaignC_stats as CS
import lineD_predict as LD

HERE = os.path.dirname(os.path.abspath(__file__))
DISCOVERY = ["pythia", "qwen", "opt", "smollm2"]
ARM = "MX-asym-TOP"


def margins(models, pattern):
    out = {}
    for m in models:
        p = os.path.join(HERE, pattern.format(m))
        if os.path.exists(p):
            out[m] = json.load(open(p))
    return out


def main():
    reg = json.load(open(os.path.join(HERE, "lineB_prereg.json")))
    new_all = sorted(reg["registered"])
    meas = margins(new_all, "lineB_ruler_{}.json")
    new = [m for m in new_all if m in meas]
    old = margins(DISCOVERY, "lineD_ruler_{}.json")

    print("=" * 88)
    print("TABLE 1 -- THE PREDICTION, registered from weights alone before any "
          "perplexity existed")
    print("=" * 88)
    print(f"{'checkpoint':<15}{'X/G':>13}{'B2 predicts':>13}"
          f"{'dD/D_B':>11}{'C1 predicts':>13}   registered (UTC)")
    for m in sorted(new_all, key=lambda k: reg["registered"][k]["X_over_G"]):
        e = reg["registered"][m]
        print(f"{m:<15}{e['X_over_G']:>+13.6f}"
              f"{('arm loses' if e['pred_sign_B2'] > 0 else 'arm WINS'):>13}"
              f"{e['dD_over_DB']:>+11.4%}"
              f"{('arm loses' if e['pred_sign_C1'] > 0 else 'arm WINS'):>13}"
              f"   {e['registered_utc']}")
    order = [m for m in sorted(new_all,
                               key=lambda k: reg["registered"][k]["X_over_G"])]
    print(f"\nB1 predicted rank order, arm's best checkpoint first:\n  "
          f"{' < '.join(order)}")
    if not new:
        print("\nnothing measured yet.")
        return 0

    print("\n" + "=" * 88)
    print("TABLE 2 -- THE OUTCOME, measured after registration")
    print("=" * 88)
    print(f"{'checkpoint':<15}{'fp32':>9}{'MXFP4':>9}{'TOP':>9}{'margin %':>10}"
          f"{'95% CI (windows)':>22}{'win':>8}")
    mvals = {}
    for m in new:
        r = meas[m]
        d = (np.array(r["per_window_nll"][ARM])
             - np.array(r["per_window_nll"]["MXFP4"]))
        s = CS.paired(d)
        mvals[m] = r["top_vs_mxfp4_pct"]
        print(f"{m:<15}{r['ppl']['fp32']:>9.4f}{r['ppl']['MXFP4']:>9.4f}"
              f"{r['ppl'][ARM]:>9.4f}{s['pct']:>+10.2f}"
              f"{f'[{s['lo']:+.2f}, {s['hi']:+.2f}]':>22}"
              f"{f'{s['n_better']}/{s['n']}':>8}")
    print("  (those CIs take n = WINDOWS and are WITHIN-model only)")

    print("\n" + "=" * 88)
    print(f"TABLE 3 -- THE TEST, on the {len(new)} NEW checkpoints ALONE "
          f"(n = MODELS)")
    print("=" * 88)
    y = [mvals[m] for m in new]
    rows = []
    for label, v in (
            ("B1  X/G                     (pre-registered)",
             [reg["registered"][m]["X_over_G"] for m in new]),
            ("C1  dD/D_B  = T41 primary   (control)",
             [reg["registered"][m]["dD_over_DB"] for m in new]),
            ("C2  -Y/G    = granular gain (control)",
             [-reg["registered"][m]["Y_over_G"] for m in new])):
        r, p1, p2 = LD.exact_p(list(v), list(y))
        rows.append((label, r, p1, p2))
        print(f"{label:<46}rho = {r:+.3f}   p1 = {p1:.4f}   p2 = {p2:.4f}")
    best = 1.0 / np.math.factorial(len(new)) if hasattr(np, "math") else None
    import math as _m
    print(f"\n  at n = {len(new)} a PERFECT order is p1 = "
          f"{1.0/_m.factorial(len(new)):.4f} one-sided -- this design can "
          f"{'refute and confirm' if 1.0/_m.factorial(len(new)) < 0.05 else 'REFUTE a predictor but CANNOT confirm one'}")

    nb2 = sum(1 for m in new
              if np.sign(mvals[m]) == reg["registered"][m]["pred_sign_B2"])
    nc1 = sum(1 for m in new
              if np.sign(mvals[m]) == reg["registered"][m]["pred_sign_C1"])
    print(f"\n  B2 sign correct: {nb2}/{len(new)}   "
          f"exact binomial p = {binomtest(nb2, len(new), 0.5, 'greater').pvalue:.4f}")
    print(f"  C1 sign correct: {nc1}/{len(new)}   "
          f"exact binomial p = {binomtest(nc1, len(new), 0.5, 'greater').pvalue:.4f}")
    for m in new:
        e = reg["registered"][m]
        print(f"    {m:<14} predicted B2 {'+' if e['pred_sign_B2']>0 else '-'} "
              f"C1 {'+' if e['pred_sign_C1']>0 else '-'}   "
              f"measured {mvals[m]:+.2f} %  "
              f"B2 {'HIT' if np.sign(mvals[m])==e['pred_sign_B2'] else 'MISS'}  "
              f"C1 {'HIT' if np.sign(mvals[m])==e['pred_sign_C1'] else 'MISS'}")

    print("\n" + "=" * 88)
    print("TABLE 4 -- old + new pooled.  INFLATED: the old four are where X/G "
          "was read off.")
    print("=" * 88)
    allm = DISCOVERY + new
    if len(old) == 4:
        ya = [old[m]["top_vs_mxfp4_pct"] for m in DISCOVERY] + y
        xa = ([reg["discovery"][m]["X_over_G"] for m in DISCOVERY]
              + [reg["registered"][m]["X_over_G"] for m in new])
        r, p1, p2 = LD.exact_p(list(xa), list(ya))
        print(f"  X/G over all {len(allm)}: rho = {r:+.3f}  p1 = {p1:.4f}  "
              f"-- quoted only to show it is NOT the honest number")

    json.dump({"new_models": new,
               "measured_pct": {m: mvals[m] for m in new},
               "spearman_new_only": {lab: {"rho": r, "p1": p1, "p2": p2}
                                     for lab, r, p1, p2 in rows},
               "sign_B2_correct": nb2, "sign_C1_correct": nc1,
               "n_new": len(new)},
              open(os.path.join(HERE, "lineB_test.json"), "w"), indent=1)
    print(f"\nwrote {os.path.join(HERE, 'lineB_test.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
