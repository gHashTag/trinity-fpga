#!/usr/bin/env python3
"""Campaign D, step 1: reproduce the MEASURED ranking of the five placements.

The predictors are tested against this ranking, so it must be reproduced from
the per-window NLL that campaignB_measure.py wrote, not copied from prose.

Paired per-window NLL against MXFP4 on the same model:
    d_i = nll_arm,i - nll_MXFP4,i     ->  ppl ratio = exp(mean_i d_i)
Model-level statistics are the n = 4 replicates of mean_i d_i (one per model);
window-level statistics are quoted only WITHIN a model.
"""
import json
import math
import os

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
PLACEMENTS = ["MX-asym-NEAR0", "MX-asym-MIDN", "MX-asym-MID",
              "MX-asym-MID2", "MX-asym-TOP"]
SHORT = {"MX-asym-NEAR0": "NEAR0", "MX-asym-MIDN": "MIDN", "MX-asym-MID": "MID",
         "MX-asym-MID2": "MID2", "MX-asym-TOP": "TOP"}
RULERS = {"smollm2": (14.4874, 21.9397), "qwen": (12.6999, 15.4374),
          "pythia": (25.9561, 47.6504), "opt": (27.5678, 30.7871)}


def load():
    out = {}
    for m in MODELS:
        d = json.load(open(os.path.join(HERE, f"campaignB_{m}.json")))
        f, x = RULERS[m]
        assert abs(d["ppl"]["fp32"] - f) < 5e-4, (m, d["ppl"]["fp32"])
        assert abs(d["ppl"]["MXFP4"] - x) < 5e-4, (m, d["ppl"]["MXFP4"])
        out[m] = d
    return out


def pct_ci(d, alpha=0.05):
    d = np.asarray(d, dtype=float)
    n = len(d)
    mean, se = float(d.mean()), float(d.std(ddof=1) / math.sqrt(n))
    tc = float(stats.t.ppf(1 - alpha / 2, n - 1))
    t = mean / se if se > 0 else float("nan")
    return dict(n=n, pct=100 * (math.exp(mean) - 1),
                lo=100 * (math.exp(mean - tc * se) - 1),
                hi=100 * (math.exp(mean + tc * se) - 1),
                p=float(2 * stats.t.sf(abs(t), n - 1)) if se > 0 else float("nan"))


def main():
    D = load()
    print("rulers reproduced from campaignB_*.json (fp32 and MXFP4)\n")

    per_model, wins = {}, {}
    for a in PLACEMENTS:
        per_model[a], wins[a] = {}, {}
        for m in MODELS:
            pw = D[m]["per_window_nll"]
            d = np.array(pw[a]) - np.array(pw["MXFP4"])
            per_model[a][m] = float(d.mean())          # log ppl ratio
            wins[a][m] = (int((d < 0).sum()), len(d))

    print(f"{'placement':<8}" + "".join(f"{m:>12}" for m in MODELS)
          + f"{'pooled(n=4)':>14}{'95% CI':>22}{'windows':>10}")
    rows = []
    for a in PLACEMENTS:
        v = [per_model[a][m] for m in MODELS]
        s = pct_ci(v)
        w = sum(wins[a][m][0] for m in MODELS), sum(wins[a][m][1] for m in MODELS)
        rows.append((a, s, w))
        cells = "".join(f"{100*(math.exp(per_model[a][m])-1):>11.2f}%" for m in MODELS)
        print(f"{SHORT[a]:<8}{cells}{s['pct']:>13.2f}%"
              f"  [{s['lo']:>6.2f},{s['hi']:>6.2f}]{w[0]:>7}/{w[1]}")

    order = [a for a, _, _ in sorted(rows, key=lambda r: r[1]["pct"])]
    print("\nMEASURED ORDER (best first): " + " > ".join(SHORT[a] for a in order))

    # Are adjacent placements actually separated?  Paired at the model level.
    print("\nadjacent-pair separation, paired over the 4 models (n = 4):")
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        d = np.array([per_model[a][m] - per_model[b][m] for m in MODELS])
        s = pct_ci(d)
        sep = "SEPARATED" if s["hi"] < 0 or s["lo"] > 0 else "TIE"
        print(f"  {SHORT[a]:>6} vs {SHORT[b]:<6} {s['pct']:>7.2f}%"
              f"  [{s['lo']:>7.2f},{s['hi']:>7.2f}]  p={s['p']:.3f}  {sep}")

    # within-model ranking of the five, used later for a per-model Spearman
    per_model_rank = {}
    for m in MODELS:
        o = sorted(PLACEMENTS, key=lambda a: per_model[a][m])
        per_model_rank[m] = [SHORT[a] for a in o]
        print(f"\n{m:>8} order: " + " > ".join(SHORT[a] for a in o))

    json.dump({"per_model_logratio": {SHORT[a]: per_model[a] for a in PLACEMENTS},
               "pooled": {SHORT[a]: s for a, s, _ in rows},
               "measured_order": [SHORT[a] for a in order],
               "per_model_order": per_model_rank,
               "windows": {SHORT[a]: wins[a] for a in PLACEMENTS}},
              open(os.path.join(HERE, "campaignD_rank.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
