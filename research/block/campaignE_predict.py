#!/usr/bin/env python3
"""T42's predictions, frozen before any MX-asym-NEAR0 perplexity is looked at.

Two claims, both parameter-free, both falsifiable, neither fitted.

P1  ORDER, weights only.  R = dD / D_MX is the fractional reduction in block
    squared weight error and is computed from the checkpoint's block-normalised
    value distribution alone (campaignE_occupancy.py).  The measured counterpart
    is the fractional reduction of the EXCESS log-perplexity over fp32,

        Rhat = 1 - (log ppl_NEAR0 - log ppl_fp32) / (log ppl_MXFP4 - log ppl_fp32)

    P1 predicts the ORDER of Rhat across checkpoints equals the order of R.

P2  MAGNITUDE, no free parameter.  If the loss penalty of a quantisation arm is
    proportional to its block squared weight error with a per-MODEL constant
    kappa_m -- the standard curvature argument -- then kappa_m CANCELS between
    two arms on the same checkpoint and

        Rhat = R    exactly,   hence   dppl% = 100 (exp(-R * L) - 1)

    with L = log ppl_MXFP4 - log ppl_fp32 read off two rulers that were measured
    long before this theorem existed.  P2 is scored as: |measured / predicted|
    lies in [0.5, 2.0] on every checkpoint.  THE FACTOR IS 2 AND IT IS STATED
    HERE, before the numbers.

P3  SIGN.  g(y) >= 0 pointwise, so dD >= 0 structurally: NEAR0 can never raise
    squared weight error.  P3 predicts NEAR0 never loses to MXFP4 on any
    checkpoint.  One checkpoint where it loses refutes P3.

Note the two orders are DIFFERENT, which is why both are worth stating: R is
largest on OPT, but OPT has the smallest quantisation excess L, so R*L ranks it
last.  P1 and P2 can fail independently.

    python3 campaignE_predict.py            # freeze
    python3 campaignE_predict.py --score    # score against measurement
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OCC = os.path.join(HERE, "campaignE_occupancy.json")
FROZEN = os.path.join(HERE, "campaignE_frozen.json")

# fp32 / MXFP4 rulers.  For the four published checkpoints these are the
# repository's own numbers, reproduced in-process by campaignE_ppl.py.  For a
# new checkpoint the two rulers are measured FIRST and the prediction formed
# from them before its NEAR0 arm is read.
RULERS = {
    "smollm2": {"fp32": 14.4874, "MXFP4": 21.9397},
    "qwen":    {"fp32": 12.6999, "MXFP4": 15.4374},
    "pythia":  {"fp32": 25.9561, "MXFP4": 47.6504},
    "opt":     {"fp32": 27.5678, "MXFP4": 30.7871},
}
FACTOR = 2.0


def rulers_for(name, occ_keys):
    if name in RULERS:
        return RULERS[name], "published"
    p = os.path.join(HERE, f"campaignE_ppl_{name}.json")
    if os.path.exists(p):
        d = json.load(open(p))
        return {"fp32": d["ppl"]["fp32"], "MXFP4": d["ppl"]["MXFP4"]}, "measured-here"
    return None, None


def freeze():
    occ = json.load(open(OCC))
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "factor": FACTOR, "per_model": {}}
    for name, v in occ.items():
        r, src = rulers_for(name, occ)
        rec = {"R": v["R"], "occ_band_s2w": v["occ_band_s2w"],
               "occ_band_raw": v["occ_band_raw"], "ruler_src": src}
        if r:
            L = math.log(r["MXFP4"]) - math.log(r["fp32"])
            rec.update({"fp32": r["fp32"], "MXFP4": r["MXFP4"], "L": L,
                        "pred_pct": 100.0 * (math.exp(-v["R"] * L) - 1.0)})
        out["per_model"][name] = rec
    if os.path.exists(FROZEN):
        old = json.load(open(FROZEN))
        for k, v in old["per_model"].items():
            if k in out["per_model"] and "pred_pct" in v:
                # never overwrite a prediction already on record
                out["per_model"][k] = v
        out["frozen_utc"] = old["frozen_utc"]
        out["amended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(out, open(FROZEN, "w"), indent=1)
    print(f"frozen {out['frozen_utc']}   factor {FACTOR}")
    print(f"{'model':<14}{'R':>10}{'occ_s2w':>10}{'L':>10}{'pred %':>10}  ruler")
    for k, v in sorted(out["per_model"].items(), key=lambda kv: -kv[1]["R"]):
        L = v.get("L")
        print(f"{k:<14}{v['R']:>10.6f}{v['occ_band_s2w']:>10.6f}"
              f"{(f'{L:.5f}' if L else '--'):>10}"
              f"{(f'{v['pred_pct']:+.3f}' if L else '--'):>10}  {v['ruler_src']}")
    return out


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def perm_p(a, b):
    """exact two-sided permutation p for Spearman at small n"""
    from itertools import permutations
    obs = abs(spearman(a, b))
    n = 0; hit = 0
    for p in permutations(range(len(a))):
        n += 1
        if abs(spearman(a, [b[i] for i in p])) >= obs - 1e-12:
            hit += 1
    return hit / n


def score():
    fr = json.load(open(FROZEN))
    rows = []
    for name, v in fr["per_model"].items():
        p = os.path.join(HERE, f"campaignE_ppl_{name}.json")
        if not os.path.exists(p) or "pred_pct" not in v:
            continue
        d = json.load(open(p))
        n0 = np.array(d["per_window_nll"]["MX-asym-NEAR0"])
        mx = np.array(d["per_window_nll"]["MXFP4"])
        f3 = np.array(d["per_window_nll"]["fp32"])
        dd = n0 - mx
        meas = 100.0 * (math.exp(dd.mean()) - 1.0)
        Lm = mx.mean() - f3.mean()
        Rhat = 1.0 - (n0.mean() - f3.mean()) / Lm
        sd = dd.std(ddof=1) / math.sqrt(len(dd))
        rows.append({"model": name, "R": v["R"], "Rhat": Rhat,
                     "L_pub": v["L"], "L_here": Lm,
                     "pred_pct": v["pred_pct"], "meas_pct": meas,
                     "ratio": meas / v["pred_pct"],
                     "nwin": len(dd), "won": int((dd < 0).sum()),
                     "ci_lo": 100 * (math.exp(dd.mean() - 1.96 * sd) - 1),
                     "ci_hi": 100 * (math.exp(dd.mean() + 1.96 * sd) - 1)})
    rows.sort(key=lambda r: r["pred_pct"])
    print(f"{'model':<14}{'R':>9}{'Rhat':>9}{'pred %':>9}{'meas %':>9}"
          f"{'ratio':>8}{'win':>9}   95% CI (windows)")
    for r in rows:
        print(f"{r['model']:<14}{r['R']:>9.5f}{r['Rhat']:>9.5f}"
              f"{r['pred_pct']:>+9.3f}{r['meas_pct']:>+9.3f}{r['ratio']:>8.2f}"
              f"{r['won']:>5}/{r['nwin']:<3}   "
              f"[{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]")
    n = len(rows)
    if n >= 3:
        s1 = spearman([r["R"] for r in rows], [r["Rhat"] for r in rows])
        s2 = spearman([r["pred_pct"] for r in rows], [r["meas_pct"] for r in rows])
        print(f"\nP1  order of R vs Rhat          rho = {s1:+.3f}   "
              f"exact two-sided perm p = {perm_p([r['R'] for r in rows], [r['Rhat'] for r in rows]):.4f}   n = {n} models")
        print(f"P2  order of pred vs meas %     rho = {s2:+.3f}   "
              f"exact two-sided perm p = {perm_p([r['pred_pct'] for r in rows], [r['meas_pct'] for r in rows]):.4f}   n = {n} models")
        bad = [r["model"] for r in rows
               if not (1 / FACTOR <= abs(r["ratio"]) <= FACTOR) or r["ratio"] < 0]
        print(f"P2  magnitude within x{FACTOR:g}       "
              f"{n - len(bad)}/{n} checkpoints"
              + (f"   MISSES: {', '.join(bad)}" if bad else ""))
        lose = [r["model"] for r in rows if r["meas_pct"] > 0]
        print(f"P3  sign, NEAR0 never loses     "
              f"{n - len(lose)}/{n} checkpoints"
              + (f"   LOSSES: {', '.join(lose)}" if lose else ""))
    json.dump(rows, open(os.path.join(HERE, "campaignE_score.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    if "--score" in sys.argv:
        score()
    else:
        freeze()
