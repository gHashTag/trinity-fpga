#!/usr/bin/env python3
"""Pool the per-window paired tests written by joint_kl_judge.py.

IN-SAMPLE  = the three models the joint fit saw (SmolLM2, Qwen, Pythia).
OUT-OF-SAMPLE = the held-out model the fit never touched (OPT-125M).

Pooling concatenates per-window dNLL across models, the same construction the
nSSE campaign used for its pooled figure (t=-0.221, p=0.826,
95% CI [-1.56%,+1.27%]). A margin whose CI straddles zero is a TIE.
"""
import glob
import json
import math
import os

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
FIT = ("smollm2", "qwen", "pythia")
HELD = ("opt",)
ARMS = ("JOINT-KL (3-model fit)", "KL-opt (SmolLM2-only fit)",
        "nSSE-equal (SmolLM2-only fit)", "Lloyd-Max (MSE opt)")


def stat(d):
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    t = mean / se
    p = float(stats.t.sf(abs(t), n - 1) * 2)
    tc = float(stats.t.ppf(0.975, n - 1))
    return {"n": n, "mean_dnll": mean, "sd": sd, "se": se, "t": t, "p": p,
            "df": n - 1, "n_better": int((d < 0).sum()),
            "n_worse": int((d > 0).sum()),
            "ppl_ratio_pct": 100 * (math.exp(mean) - 1),
            "ci95_pct": [100 * (math.exp(mean - tc * se) - 1),
                         100 * (math.exp(mean + tc * se) - 1)]}


def main():
    data = {}
    for f in sorted(glob.glob(os.path.join(HERE, "joint_kl_judge_*.json"))):
        j = json.load(open(f))
        if j.get("win0", 0) != 0:
            continue          # disjoint-window robustness runs are judged separately
        data[j["model"]] = j
    print(f"loaded: {list(data)}")

    out = {"per_model": {}, "pooled": {}}
    print(f"\n{'model':<10}{'arm':<32}{'vs MXFP4':>10}{'t':>9}{'p':>9}"
          f"{'better/worse':>14}   95% CI")
    for m, j in data.items():
        out["per_model"][m] = {"ppl": j["ppl"], "paired": j["paired_vs_mxfp4"],
                               "ruler_status": j["ruler_status"]}
        for arm in ARMS:
            s = j["paired_vs_mxfp4"][arm]
            print(f"{m:<10}{arm:<32}{s['ppl_ratio_pct']:>+9.2f}%{s['t']:>+9.3f}"
                  f"{s['p']:>9.4f}{s['n_better']:>7}/{s['n_worse']:<6}"
                  f"[{s['ci95_pct'][0]:+.2f}%,{s['ci95_pct'][1]:+.2f}%]")

    for label, group in (("in_sample_3models", FIT), ("out_of_sample_held", HELD),
                         ("all_models", FIT + HELD)):
        have = [m for m in group if m in data]
        if not have:
            continue
        print(f"\nPOOLED {label}  ({', '.join(have)})")
        out["pooled"][label] = {"models": have}
        for arm in ARMS:
            d = np.concatenate([
                np.asarray(data[m]["per_window_nll"][arm]) -
                np.asarray(data[m]["per_window_nll"]["MXFP4 (E2M1)"])
                for m in have])
            s = stat(d)
            out["pooled"][label][arm] = s
            verdict = ("TIE (CI straddles 0)"
                       if s["ci95_pct"][0] < 0 < s["ci95_pct"][1]
                       else ("BEATS MXFP4" if s["mean_dnll"] < 0
                             else "LOSES TO MXFP4"))
            print(f"  {arm:<32} {s['ppl_ratio_pct']:>+7.2f}%  t={s['t']:+.3f} "
                  f"p={s['p']:.4f}  n={s['n']} ({s['n_better']}/{s['n_worse']})"
                  f"  CI [{s['ci95_pct'][0]:+.2f}%,{s['ci95_pct'][1]:+.2f}%]"
                  f"  -> {verdict}")

    dst = os.path.join(HERE, "joint_kl_pooled.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")

    # decisive question
    arm = "JOINT-KL (3-model fit)"
    beats = {m: data[m]["ppl"][arm] < data[m]["ppl"]["MXFP4 (E2M1)"]
             for m in data}
    print("\nDECISION")
    print(f"  beats MXFP4 on fitting models: "
          f"{ {m: beats[m] for m in FIT if m in beats} }")
    print(f"  beats MXFP4 on held-out:       "
          f"{ {m: beats[m] for m in HELD if m in beats} }")
    all_fit = all(beats[m] for m in FIT if m in beats)
    all_held = all(beats[m] for m in HELD if m in beats)
    if all_fit and all_held:
        print("  -> KL objective GENERALISES; the single-model fit was the problem")
    elif all_fit:
        print("  -> still fitting: wins where it was fitted, not where it was not")
    else:
        print("  -> the objective has no codebook that beats MXFP4 on all three "
              "models it was fitted to at once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
