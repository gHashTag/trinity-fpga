#!/usr/bin/env python3
"""LINE D: does T41's crossover predict the measured order of the four models?

n = 4 MODELS.  Windows are replicates of the text, not of the model family, so
every number here is model-level and the only honest test is a rank correlation
over four points.  Its null distribution is enumerated exactly (24 permutations)
rather than approximated, because at n = 4 no asymptotic p-value means anything.

Reads lineD_ruler_*.json (measured, this session), lineD_decompose_*.json and
lineD_probe_*.json (weight statistics, no forward pass).
"""
import itertools
import json
import os

import numpy as np
from scipy.stats import t

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["pythia", "qwen", "opt", "smollm2"]


def rho(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    n = len(a)
    d = ra - rb
    return 1 - 6 * float((d ** 2).sum()) / (n * (n * n - 1))


def exact_p(a, b):
    """One- and two-sided exact permutation p for Spearman at small n."""
    obs = rho(a, b)
    vals = [rho(list(p), b) for p in itertools.permutations(a)]
    n = len(vals)
    hi = sum(1 for v in vals if v >= obs - 1e-12) / n
    two = sum(1 for v in vals if abs(v) >= abs(obs) - 1e-12) / n
    return obs, hi, two


def load(tag):
    out = {}
    for m in MODELS:
        p = os.path.join(HERE, f"lineD_{tag}_{m}.json")
        if os.path.exists(p):
            out[m] = json.load(open(p))
    return out


def main():
    ruler, dec, probe, gate = (load("ruler"), load("decompose"),
                               load("probe"), load("actgate"))
    if len(ruler) < 4:
        raise SystemExit(f"rulers present for {sorted(ruler)} only")

    meas = np.array([ruler[m]["top_vs_mxfp4_pct"] for m in MODELS])
    print("MEASURED, this session (per cent, negative = the clipping arm wins)")
    print(f"  {'model':<10}{'ppl TOP':>10}{'ppl MXFP4':>11}{'delta %':>9}"
          f"{'95% CI':>20}{'t':>8}{'wins':>8}")
    within = {}
    for m in MODELS:
        r = ruler[m]
        d = (np.array(r["per_window_nll"]["MX-asym-TOP"])
             - np.array(r["per_window_nll"]["MXFP4"]))     # paired log-ratio
        n = len(d)
        se = d.std(ddof=1) / np.sqrt(n)
        tc = float(t.ppf(0.975, n - 1))       # per-model df, not a fixed 2.023
        lo, hi = d.mean() - tc * se, d.mean() + tc * se
        within[m] = {"pct": 100 * (np.exp(d.mean()) - 1),
                     "ci": [100 * (np.exp(lo) - 1), 100 * (np.exp(hi) - 1)],
                     "t": float(d.mean() / se), "wins": int((d < 0).sum()), "n": n}
        w = within[m]
        print(f"  {m:<10}{r['ppl']['MX-asym-TOP']:>10.4f}{r['ppl']['MXFP4']:>11.4f}"
              f"{w['pct']:>+9.2f}{f'[{w['ci'][0]:+.2f}, {w['ci'][1]:+.2f}]':>20}"
              f"{w['t']:>8.2f}{f'{w['wins']}/{w['n']}':>8}")
    print("  (window-level, WITHIN model only -- windows replicate the text, "
          "not the model family)")

    preds = {}
    if len(dec) == 4:
        preds["T41 primary: dD / D_MXFP4  (weight MSE ratio - 1)"] = np.array(
            [dec[m]["dD"] / dec[m]["D_MXFP4"] for m in MODELS])
        preds["X / G   (clipping cost per unit granular error)"] = np.array(
            [dec[m]["X_over_G"] for m in MODELS])
        preds["Y / G   (granular gain per unit granular error)"] = np.array(
            [-dec[m]["Y_over_G"] for m in MODELS])
        preds["mean rho = |min y| / max|y| per block"] = np.array(
            [dec[m]["mean_rho"] for m in MODELS])
        preds["frac blocks with a saturated element"] = np.array(
            [dec[m]["frac_blocks_saturating"] for m in MODELS])
        preds["saturated elements per block"] = np.array(
            [dec[m]["sat_per_block"] for m in MODELS])
    if len(probe) == 4:
        preds["coherence ratio  COH_TOP / COH_MXFP4"] = np.array(
            [probe[m]["coh_ratio_TOP_over_MXFP4"] for m in MODELS])
        preds["kappa_TOP (row-sum coherence of the arm's error)"] = np.array(
            [probe[m]["kappa_TOP"] for m in MODELS])
    if len(gate) == 4:
        preds["activation-gated output error ratio (pre-registered)"] = np.array(
            [gate[m]["gated_ratio_TOP_over_MXFP4"] for m in MODELS])
        preds["  its coherent channel only"] = np.array(
            [gate[m]["coh_TOP"] / gate[m]["coh_MXFP4"] for m in MODELS])
        preds["  its incoherent channel only"] = np.array(
            [gate[m]["inc_TOP"] / gate[m]["inc_MXFP4"] for m in MODELS])

    print(f"\n{'predictor':<52}{'values':>4}")
    print(f"{'':<52}{'rho':>8}{'p 1-sided':>12}{'p 2-sided':>12}")
    rows = []
    for name, v in preds.items():
        r, p1, p2 = exact_p(list(v), list(meas))
        rows.append((name, v, r, p1, p2))
        print(f"{name:<52}")
        print(f"{'  ' + '  '.join(f'{m}={x:+.5g}' for m, x in zip(MODELS, v)):<52}")
        print(f"{'':<52}{r:>8.3f}{p1:>12.4f}{p2:>12.4f}")

    print("\nLEAVE-ONE-OUT ROTATION, reported in full "
          "(3 points: rho is +-1 by construction, so only the SIGN is readable)")
    hdr = "".join(f"{'drop ' + m:>16}" for m in MODELS)
    print(f"{'predictor':<52}{hdr}")
    for name, v, r, _, _ in rows:
        cells = ""
        for i in range(4):
            k = [j for j in range(4) if j != i]
            cells += f"{rho(list(v[k]), list(meas[k])):>16.3f}"
        print(f"{name:<52}{cells}")

    json.dump({"models": MODELS, "measured_pct": list(map(float, meas)),
               "predictors": {n: list(map(float, v)) for n, v, _, _, _ in rows},
               "spearman": {n: {"rho": r, "p1": p1, "p2": p2}
                            for n, _, r, p1, p2 in rows}},
              open(os.path.join(HERE, "lineD_predict.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
