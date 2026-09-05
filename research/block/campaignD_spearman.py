#!/usr/bin/env python3
"""Campaign D, step 4: do any of the three predictors rank the five placements?

Measured score of a placement = -(mean per-window log ppl ratio vs MXFP4), so
LARGER = BETTER.  Every predictor is also oriented larger = "should be better",
which is the conjecture: put the new level where the distortion is.

Spearman rho on n = 5 is a blunt instrument and is treated as one: the p-value
is EXACT (all 120 permutations, one-sided, because the conjecture is
directional), and rho = 1.0 is the only value that reaches p < 0.05.  The test
is therefore effectively "perfect order or nothing", and that is stated rather
than dressed up.

Two things are reported that a single pooled rho would hide:
  * the correlation per model (4 independent replications), and
  * which adjacent pairs of the MEASURED order are actually separated, since a
    predictor cannot be blamed for missing an ordering the data does not assert.
"""
import itertools
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
NAMES = ["NEAR0", "MIDN", "MID", "MID2", "TOP"]
PRED = [("P1  bin mass", "P1_mass"),
        ("P1b captured mass", "P1b_captured"),
        ("P2  mass x width^2", "P2_mass_w2"),
        ("P2b measured SSE share", "P2b_sse_share")]


def rankdata(v):
    a = np.asarray(v, dtype=float)
    r = np.empty(len(v), dtype=float)
    order = np.argsort(a)
    r[order] = np.arange(1, len(v) + 1)
    for x in set(a):                                   # average ties
        m = a == x
        if m.sum() > 1:
            r[m] = r[m].mean()
    return r


def spearman(x, y):
    rx, ry = rankdata(x), rankdata(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    d = math.sqrt(float((rx ** 2).sum()) * float((ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


def exact_p(x, y):
    """One-sided permutation p: P(rho_perm >= rho_obs) over all 5! orders."""
    obs = spearman(x, y)
    hits = tot = 0
    for perm in itertools.permutations(range(len(x))):
        if spearman([x[i] for i in perm], y) >= obs - 1e-12:
            hits += 1
        tot += 1
    return obs, hits / tot


def main():
    rank = json.load(open(os.path.join(HERE, "campaignD_rank.json")))
    have = [m for m in MODELS
            if os.path.exists(os.path.join(HERE, f"campaignD_pred_{m}.json"))]
    pred = {m: json.load(open(os.path.join(HERE, f"campaignD_pred_{m}.json")))
            for m in have}
    kl = {}
    for m in have:
        p = os.path.join(HERE, f"campaignD_kl_{m}.json")
        if os.path.exists(p):
            kl[m] = json.load(open(p))

    print(f"models with predictors measured: {have}")
    print(f"models with P3 (KL) measured   : {sorted(kl)}\n")

    # measured score, larger = better
    score = {m: [-rank["per_model_logratio"][n][m] for n in NAMES] for m in MODELS}
    pooled_score = [float(np.mean([score[m][i] for m in MODELS]))
                    for i in range(len(NAMES))]

    # TOP is not "MXFP4 plus one level": adding 16/12 forces a renormalisation
    # that moves EVERY level and clips the negative extreme to -0.75.  No
    # predictor computed on MXFP4's own bin structure can represent that, so the
    # four true insertions are also reported separately.  The exclusion is
    # structural and decided before looking at any rho, not fitted.
    KEEP4 = [i for i, n in enumerate(NAMES) if n != "TOP"]

    def table(vals, label, per_model_vals=None):
        obs, p = exact_p(vals, pooled_score)
        o4, p4 = exact_p([vals[i] for i in KEEP4],
                         [pooled_score[i] for i in KEEP4])
        order = [NAMES[i] for i in np.argsort(-np.asarray(vals))]
        print(f"{label:<24} rho = {obs:+.3f}   exact one-sided p = {p:.4f}"
              f"    | without TOP (n=4): rho = {o4:+.3f}, p = {p4:.4f}")
        print(f"{'':<24} predicted order: " + " > ".join(order))
        rows = {"rho_pooled": obs, "p_pooled": p, "predicted_order": order,
                "rho_no_top": o4, "p_no_top": p4,
                "values": {n: v for n, v in zip(NAMES, vals)}}
        if per_model_vals:
            per, hits = {}, 0
            for m in MODELS:
                if m not in per_model_vals:
                    continue
                r, pp = exact_p(per_model_vals[m], score[m])
                # Spearman on n = 5 has almost no power; the sharper question is
                # whether the predictor's TOP PICK is the placement that actually
                # won on that model.  Chance is 1 in 5 per model.
                top_pred = NAMES[int(np.argmax(per_model_vals[m]))]
                top_meas = NAMES[int(np.argmax(score[m]))]
                per[m] = {"rho": r, "p": pp, "argmax_pred": top_pred,
                          "argmax_measured": top_meas, "hit": top_pred == top_meas}
                hits += per[m]["hit"]
            if per:
                print(f"{'':<24} per model rho: " +
                      "  ".join(f"{m}={per[m]['rho']:+.2f}" for m in per))
                print(f"{'':<24} top pick vs winner: " +
                      "  ".join(f"{m}:{per[m]['argmax_pred']}"
                                f"{'=' if per[m]['hit'] else '!='}"
                                f"{per[m]['argmax_measured']}" for m in per)
                      + f"   ({hits}/{len(per)})")
                rows["per_model"] = per
                rows["argmax_hits"] = [hits, len(per)]
        print()
        return rows

    out = {"measured_pooled_score": dict(zip(NAMES, pooled_score)),
           "measured_order": rank["measured_order"], "predictors": {}}

    print("MEASURED order (pooled over 4 models, larger score = better): "
          + " > ".join(rank["measured_order"]) + "\n")

    for label, key in PRED:
        pm = {m: [pred[m]["placements"][n][key] for n in NAMES] for m in have}
        vals = [float(np.mean([pm[m][i] for m in have])) for i in range(len(NAMES))]
        out["predictors"][key] = table(vals, label, pm)

    if kl:
        pm = {m: [kl[m]["placements"][n] for n in NAMES] for m in kl}
        vals = [float(np.mean([pm[m][i] for m in kl])) for i in range(len(NAMES))]
        out["predictors"]["P3_kl_share"] = table(vals, "P3  KL share", pm)

    json.dump(out, open(os.path.join(HERE, "campaignD_spearman.json"), "w"), indent=1)
    print("wrote campaignD_spearman.json")


if __name__ == "__main__":
    main()
