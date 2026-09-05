#!/usr/bin/env python3
"""Campaign C statistics: every arm against NF4-sym, at equal alphabet.

Paired per-window NLL throughout. d_i = nll_arm,i - nll_ref,i, so
    ppl_arm / ppl_ref = exp(mean_i d_i)
exactly (equal token count per window), and the percentage quoted is
100*(exp(mean d) - 1). Positive = worse than NF4-sym.

THE REPLICATE UNIT, stated once and enforced at both sites below.

  * A per-model row is a WITHIN-model claim -- "on this checkpoint, this arm is
    worth X" -- and windows are its replicates, because they are replicates of
    the text and the text is what varies.
  * A held-out row is a CROSS-model claim -- "on a checkpoint neither of us has
    run, expect X" -- and CHECKPOINTS are its replicates. n = held-out models.

Until 2026-08-12 the second kind concatenated the first kind's windows and
handed 100-140 of them to a paired t-test. That is the same defect
`campaignB_stats.row()` carried, found the same day, and it flipped five of the
six rows here. A margin whose 95 % CI contains zero is reported as a TIE.

    python3 campaignC_stats.py
"""
import json
import math
import os

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
LABEL = {"smollm2": "SmolLM2-135M", "qwen": "Qwen2.5-0.5B",
         "pythia": "Pythia-160M", "opt": "OPT-125M"}
ARMS = ["MXFP4", "Lloyd-Max", "KL-opt", "nSSE-equal", "JOINT-KL", "NF4-sym", "NF4"]
REF = "NF4-sym"
NCMP = 6                      # arms compared against the reference -> Bonferroni

FITTED_ON = {
    "MXFP4":      [],                       # hand-designed, OCP spec
    "Lloyd-Max":  ["smollm2"],
    "KL-opt":     ["smollm2"],
    "nSSE-equal": ["smollm2"],
    "JOINT-KL":   ["smollm2", "qwen", "pythia"],
    "NF4-sym":    [],                       # an N(0,1) prior, no checkpoint
    "NF4":        [],
}


def paired(d):
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    t = mean / se if se > 0 else float("nan")
    p = float(2 * stats.t.sf(abs(t), n - 1)) if se > 0 else float("nan")
    tc = float(stats.t.ppf(0.975, n - 1))
    lo, hi = mean - tc * se, mean + tc * se
    return {"n": n, "pct": 100 * (math.exp(mean) - 1),
            "lo": 100 * (math.exp(lo) - 1), "hi": 100 * (math.exp(hi) - 1),
            "t": t, "p": p, "mean_d": mean,
            "n_better": int((d < 0).sum()), "n_worse": int((d > 0).sum())}


def verdict(r, nk=1):
    if r["lo"] <= 0.0 <= r["hi"] or r["p"] * nk >= 0.05:
        return "TIE"
    return "BEATS" if r["pct"] < 0 else "loses"


def load():
    out = {}
    for m in MODELS:
        out[m] = json.load(open(os.path.join(HERE, f"campaignC_{m}.json")))
        assert out[m]["rulers_reproduce"], f"{m}: rulers did not reproduce"
    return out


def dvec(D, m, a, ref=REF):
    return (np.array(D[m]["per_window_nll"][a])
            - np.array(D[m]["per_window_nll"][ref]))


def main():
    D = load()
    print("RULERS reproduced on all four models (fp32, MXFP4, Lloyd-Max).\n")

    print("=" * 96)
    print("PERPLEXITY  (block 32, E8M0, lm_head excluded, every book at "
          "max|level| = 1.0, 4.250 b/elem)")
    print("=" * 96)
    hdr = f"{'arm':<12}{'alph':>5}" + "".join(f"{LABEL[m]:>16}" for m in MODELS)
    print(hdr)
    print(f"{'fp32':<12}{'--':>5}"
          + "".join(f"{D[m]['ppl']['fp32']:>16.4f}" for m in MODELS))
    for a in ARMS:
        alph = 16 if D[MODELS[0]]["book_kind"][a] == "sig" else 15
        print(f"{a:<12}{alph:>5}"
              + "".join(f"{D[m]['ppl'][a]:>16.4f}" for m in MODELS))

    print("\n" + "=" * 96)
    print("PER-MODEL, PAIRED, vs NF4-sym    (negative % = BEATS NF4-sym)")
    print("   WITHIN-model claims: the replicate unit is the WINDOW, and 'win' "
          "counts windows.")
    print("   Nothing here generalises to a checkpoint that is not named in the "
          "row.")
    print("=" * 96)
    print(f"{'arm':<12}{'model':<15}{'%':>9}{'95% CI':>22}{'t':>9}"
          f"{'p':>11}{'win':>8}  verdict")
    per = {}
    for a in ARMS:
        if a == REF:
            continue
        for m in MODELS:
            r = paired(dvec(D, m, a))
            per[(a, m)] = r
            tag = "in-sample" if m in FITTED_ON[a] else ""
            print(f"{a:<12}{LABEL[m]:<15}{r['pct']:>+8.2f}%"
                  f"{f"[{r['lo']:+.2f}, {r['hi']:+.2f}]":>22}"
                  f"{r['t']:>+9.2f}{r['p']:>11.2e}"
                  f"{r['n_better']:>4}/{r['n']:<3}  {verdict(r):<6}{tag}")
        print()

    print("=" * 96)
    print("HELD OUT ACROSS CHECKPOINTS  (only models the arm never saw; "
          f"Bonferroni over {NCMP} arms)")
    print("   THE REPLICATE UNIT IS THE CHECKPOINT.  n is the number of held-out "
          "MODELS, and each")
    print("   contributes ONE number: its own mean per-window log-ratio.  "
          "'Better in k of n' counts")
    print("   MODELS, not windows.")
    print("=" * 96)
    print(f"{'arm':<12}{'held-out models':<28}{'%':>9}{'95% CI':>22}{'t':>9}"
          f"{'p':>11}{'models':>8}  verdict")
    pooled = {}
    for a in ARMS:
        if a == REF:
            continue
        oos = [m for m in MODELS if m not in FITTED_ON[a]]
        names = "+".join(LABEL[m].split("-")[0] for m in oos)
        if len(oos) < 2:
            # One held-out checkpoint is one replicate.  The 40 windows behind
            # it are replicates of wikitext-2, and a CI over them says how well
            # this arm is measured ON OPT -- not how it would land on a fifth
            # checkpoint, which is the only thing this section asks.
            v = float(dvec(D, oos[0], a).mean())
            pooled[a] = {"n": 1, "pct": 100 * (math.exp(v) - 1), "mean_d": v}
            print(f"{a:<12}{names:<28}{pooled[a]['pct']:>+8.2f}%"
                  f"{'n=1, no CI':>22}{'--':>9}{'--':>11}{1:>8}  "
                  f"single held-out checkpoint")
            continue
        # This used to be `np.concatenate([dvec(D, m, a) for m in oos])`, which
        # handed `paired` 100 or 140 WINDOWS as if they were that many
        # replicates of the model family.  Windows replicate the TEXT.  Five of
        # the six rows below changed verdict when the unit was corrected, and
        # the section's conclusion went from "JOINT-KL beats NF4-sym pooled out
        # of sample" to "no arm does, and JOINT-KL has one held-out checkpoint".
        d = np.array([float(dvec(D, m, a).mean()) for m in oos])
        r = paired(d)
        pooled[a] = r
        print(f"{a:<12}{names:<28}{r['pct']:>+8.2f}%"
              f"{f"[{r['lo']:+.2f}, {r['hi']:+.2f}]":>22}"
              f"{r['t']:>+9.2f}{r['p']:>11.2e}"
              f"{r['n_better']:>4}/{r['n']:<3}  {verdict(r, NCMP)}")

    print("\n" + "=" * 96)
    print("THE QUESTION")
    print("=" * 96)
    # A row with one held-out checkpoint has no interval, so it cannot clear a
    # bar that is defined by one.  It is listed separately rather than counted.
    beat = [a for a in ARMS if a not in (REF, "NF4") and pooled[a]["n"] > 1
            and verdict(pooled[a], NCMP) == "BEATS"]
    single = [a for a in ARMS if a not in (REF, "NF4") and pooled[a]["n"] == 1]
    beat_any_model = {a: [m for m in MODELS
                          if verdict(per[(a, m)]) == "BEATS"]
                      for a in ARMS if a != REF}
    print("Arms fitted or designed in this repository that beat NF4-sym across "
          "held-out CHECKPOINTS:")
    print("   " + (", ".join(beat) if beat else "NONE"))
    if single:
        print("   (" + ", ".join(single) + ": one held-out checkpoint each -- "
              "no cross-model claim is available)")
    print("\nPer-model wins against NF4-sym (any model, in- or out-of-sample; "
          "WITHIN-model, window-level):")
    for a in ARMS:
        if a == REF:
            continue
        w = beat_any_model[a]
        print(f"   {a:<12} {len(w)}/4  "
              + (", ".join(LABEL[m] for m in w) if w else "-"))

    json.dump({"per_model": {f"{a}|{m}": v for (a, m), v in per.items()},
               "pooled_oos": pooled,
               "ppl": {m: D[m]["ppl"] for m in MODELS}},
              open(os.path.join(HERE, "campaignC_stats.json"), "w"), indent=1)
    print("\nwrote campaignC_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
