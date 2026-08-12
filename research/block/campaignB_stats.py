#!/usr/bin/env python3
"""Campaign B statistics.

Paired per-window NLL throughout.  d_i = nll_arm,i - nll_ref,i, so
    ppl_arm / ppl_ref = exp(mean_i d_i)
exactly (equal token count in every window), and the quoted percentage is
100*(exp(mean d) - 1).  Negative = arm BEATS ref.  A margin whose 95 % CI
contains zero is a TIE.

Two selection hazards are handled explicitly:

1. The placement of the freed codeword is CHOSEN from four candidates.  Choosing
   it on the same data that then reports the margin is selection on the test
   set.  So the placement is selected on ONE model and the headline is pooled
   over the models that took no part in the selection.
2. JOINT-KL was fitted on smollm2+qwen+pythia, so its asymmetric variants are
   in-sample there; only OPT is out of sample for them.
"""
import json
import math
import os

import numpy as np
from scipy import stats

import campaignB_books as B

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
LABEL = {"smollm2": "SmolLM2-135M", "qwen": "Qwen2.5-0.5B",
         "pythia": "Pythia-160M", "opt": "OPT-125M"}

MX_ASYM = ["MX-asym-TOP", "MX-asym-MID", "MX-asym-MID2", "MX-asym-NEAR0"]
JK_ASYM = ["JK-asym-TOP", "JK-asym-MID", "JK-asym-MID2", "JK-asym-NEAR0"]
ARMS = (["MXFP4", "Lloyd-Max", "JOINT-KL", "NF4-sym", "NF4"]
        + MX_ASYM + ["MX-asym-MIDN"] + JK_ASYM
        + ["MX-sym-NEAR0/6", "MX-sym-NEAR0/3"])

# models whose checkpoint the codebook was fitted against
FITTED_ON = {"MXFP4": [], "Lloyd-Max": ["smollm2"], "NF4-sym": [], "NF4": [],
             "JOINT-KL": ["smollm2", "qwen", "pythia"]}
for a in MX_ASYM + ["MX-asym-MIDN"]:
    FITTED_ON[a] = []
for a in JK_ASYM:
    FITTED_ON[a] = ["smollm2", "qwen", "pythia"]
for a in ["MX-sym-NEAR0/6", "MX-sym-NEAR0/3"]:
    FITTED_ON[a] = []

SELECT_ON = "smollm2"          # the one model allowed to choose the placement


def paired(d):
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    t = mean / se if se > 0 else float("nan")
    p = float(2 * stats.t.sf(abs(t), n - 1)) if se > 0 else float("nan")
    tc = float(stats.t.ppf(0.975, n - 1))
    return {"n": n, "pct": 100 * (math.exp(mean) - 1),
            "lo": 100 * (math.exp(mean - tc * se) - 1),
            "hi": 100 * (math.exp(mean + tc * se) - 1),
            "t": t, "p": p, "mean_d": mean,
            "n_better": int((d < 0).sum())}


def verdict(r, nk=1):
    if r["lo"] <= 0.0 <= r["hi"] or r["p"] * nk >= 0.05:
        return "TIE"
    return "BEATS" if r["pct"] < 0 else "loses"


CONTROLS = ["MX-sym-NEAR0/6", "MX-sym-NEAR0/3"]


def load():
    """Main run + the symmetric near-zero controls, which were measured by a
    SECOND process.  They may be merged only because that process re-measured
    MXFP4 and got a BIT-IDENTICAL per-window vector -- asserted here."""
    out = {}
    for m in MODELS:
        out[m] = json.load(open(os.path.join(HERE, f"campaignB_{m}.json")))
        assert out[m]["rulers_reproduce"], f"{m}: rulers did not reproduce"
        c = json.load(open(os.path.join(HERE, f"campaignB2_{m}.json")))
        assert c["anchor_bit_identical"], f"{m}: control anchor is not bit-exact"
        assert (c["per_window_nll"]["MXFP4"]
                == out[m]["per_window_nll"]["MXFP4"]), m
        for k in CONTROLS:
            out[m]["per_window_nll"][k] = c["per_window_nll"][k]
            out[m]["ppl"][k] = c["ppl"][k]
            out[m]["book_kind"][k] = "mag"
    return out


# The placement family is three: MX-asym-TOP and JK-asym-TOP extend the ladder
# to 16/12 and pay by clipping the negative extreme to -0.75, so campaignB_books
# labels them kind="clip". A Bonferroni family of "the four placements" counted
# a clipping choice as a placement. A clipping arm is also never ranked beside
# placements without saying so -- hence the tag.
NK_PLACEMENT = 3
_KIND = {n: k for n, k, lv in B.books()}


def CLIP_TAG(arm):
    return "  [clipping arm, not a placement]" if _KIND.get(arm) == "clip" else ""


def dvec(D, m, a, ref):
    return (np.array(D[m]["per_window_nll"][a])
            - np.array(D[m]["per_window_nll"][ref]))


def row(D, arm, ref, models, nk=1, tag=""):
    """One comparison, at the level its replicate unit actually supports.

    This used to `np.concatenate` the per-window vectors of every model and hand
    140 windows to `paired` as if they were 140 replicates. They are not: they
    are replicates of the TEXT, and four checkpoints' worth of them says nothing
    about a fifth checkpoint. That inflates every cross-model comparison, and
    here it inflated eleven of fourteen -- every "BEATS MXFP4" and every "loses
    to NF4" in the pooled section was a tie at the model level.

    So: more than one model is a cross-model claim and takes n = models, with
    each model contributing its own mean log-ratio. One model is a within-model
    claim and keeps its windows, which is the level that claim is entitled to.
    """
    if len(models) > 1:
        d = np.array([float(dvec(D, m, arm, ref).mean()) for m in models])
    else:
        d = dvec(D, models[0], arm, ref)
    r = paired(d)
    names = "+".join(LABEL[m].split("-")[0] for m in models)
    print(f"  {arm:<15}vs {ref:<11}{names:<26}{r['pct']:>+8.2f}%"
          f"{f"[{r['lo']:+.2f}, {r['hi']:+.2f}]":>20}{r['t']:>+8.2f}"
          f"{r['p']:>11.2e}{r['n_better']:>4}/{r['n']:<3} {verdict(r, nk):<6}{tag}")
    return r


def main():
    D = load()
    print("RULERS reproduced on all four models (fp32, MXFP4, Lloyd-Max).\n")

    print("=" * 108)
    print("PERPLEXITY   block 32, E8M0, lm_head excluded, 4.250 b/elem; every "
          "book at max|level| = 1.0 on BOTH tails except the two clipping arms, "
          "\n             MX-asym-TOP and JK-asym-TOP, which are +1.000 / -0.750")
    print("=" * 108)
    print(f"{'arm':<16}{'alph':>5}" + "".join(f"{LABEL[m]:>16}" for m in MODELS))
    print(f"{'fp32':<16}{'--':>5}"
          + "".join(f"{D[m]['ppl']['fp32']:>16.4f}" for m in MODELS))
    for a in ARMS:
        # 'mag' is a symmetric magnitude ladder (15 signed values); every signed
        # book -- 'sig' placement or 'clip' arm -- spends all 16 codewords.
        alph = 15 if D[MODELS[0]]["book_kind"][a] == "mag" else 16
        print(f"{a:<16}{alph:>5}"
              + "".join(f"{D[m]['ppl'][a]:>16.4f}" for m in MODELS))

    hdr = (f"  {'arm':<15}{'ref':<14}{'models':<26}{'%':>9}{'95% CI':>20}"
           f"{'t':>8}{'p':>11}{'win':>8} verdict")

    print("\n" + "=" * 108)
    print("T40 REPRODUCED  (the result this campaign is built on)")
    print("=" * 108)
    print(hdr)
    row(D, "NF4-sym", "MXFP4", MODELS)
    row(D, "NF4", "NF4-sym", MODELS)
    row(D, "NF4", "MXFP4", MODELS)
    # Model-level, so the composition quotes the same numbers as the three rows
    # printed above it. The identity a + b = c holds at either level -- it is
    # arithmetic, not statistics -- but a section that shows +0.46 % in a row and
    # +0.335 % two lines below is a section that will be misquoted.
    def _ml(arm, ref):
        return paired(np.array([float(dvec(D, m, arm, ref).mean()) for m in MODELS]))

    a, b, c = _ml("NF4-sym", "MXFP4"), _ml("NF4", "NF4-sym"), _ml("NF4", "MXFP4")
    resid = a["mean_d"] + b["mean_d"] - c["mean_d"]
    print(f"\n  composition: (1{a['pct']/100:+.5f}) x (1{b['pct']/100:+.5f}) = "
          f"1{(math.exp(a['mean_d']+b['mean_d'])-1):+.5f}   "
          f"measured 1{c['pct']/100:+.5f}   residual {resid:.2e}")

    print("\n" + "=" * 108)
    print("PLACEMENT OF THE FREED CODEWORD -- every asym arm vs its SYMMETRIC "
          "PARENT, per model")
    print("=" * 108)
    for fam, parent in (("MX", "MXFP4"), ("JK", "JOINT-KL")):
        arms = MX_ASYM + ["MX-asym-MIDN"] if fam == "MX" else JK_ASYM
        print(f"\n-- {parent} family --")
        print(hdr)
        for arm in arms:
            for m in MODELS:
                tg = "in-sample" if m in FITTED_ON[arm] else ""
                row(D, arm, parent, [m], tag=tg)
            print()

    print("=" * 108)
    print("SELECTION, HELD OUT.  Placement chosen on "
          f"{LABEL[SELECT_ON]} ALONE; margin reported on the models that took "
          "no part in the choice.")
    print("=" * 108)
    picks = {}
    for fam, parent, arms in (("MXFP4", "MXFP4", MX_ASYM),
                              ("JOINT-KL", "JOINT-KL", JK_ASYM)):
        best = min(arms, key=lambda a: D[SELECT_ON]["ppl"][a])
        picks[fam] = best
        oos = [m for m in MODELS if m != SELECT_ON and m not in FITTED_ON[best]]
        print(f"\n{fam}: chosen on {LABEL[SELECT_ON]} = {best}   "
              f"(ranking there: "
              + ", ".join(f"{a}={D[SELECT_ON]['ppl'][a]:.4f}"
                          for a in sorted(arms, key=lambda a: D[SELECT_ON]['ppl'][a]))
              + ")")
        if not oos:
            print("   NO held-out model remains -- nothing can be claimed OOS.")
            continue
        print(hdr)
        row(D, best, parent, oos)
        row(D, best, "MXFP4", oos)
        row(D, best, "NF4", oos)
        row(D, best, "NF4-sym", oos)

    print("\n" + "=" * 108)
    print("EVERY ARM ACROSS ALL FOUR MODELS, MODEL-LEVEL "
          "(Bonferroni x3 over the three placements)")
    print("=" * 108)
    print(hdr)
    # nk is the size of the PLACEMENT family. MX-asym-TOP and JK-asym-TOP are
    # not placements -- they extend the ladder to 16/12 and pay by clipping the
    # negative extreme to -0.75 (campaignB_books labels them kind="clip"), so a
    # family of "the four placements" counted a clipping choice as one. Three.
    # The reclassification was made on structural grounds a day before anyone
    # computed which way it moved a verdict; at model level it moves none.
    for arm in MX_ASYM + ["MX-asym-MIDN"]:
        row(D, arm, "MXFP4", MODELS, nk=NK_PLACEMENT, tag=CLIP_TAG(arm))
    print()
    for arm in MX_ASYM:
        row(D, arm, "NF4", MODELS, nk=NK_PLACEMENT, tag=CLIP_TAG(arm))
    print()
    for arm in JK_ASYM:
        row(D, arm, "JOINT-KL", MODELS, nk=NK_PLACEMENT,
            tag=("3/4 in-sample" + CLIP_TAG(arm)))
    print()
    for arm in JK_ASYM:
        row(D, arm, "NF4", ["opt"], nk=NK_PLACEMENT,
            tag=("only OOS model" + CLIP_TAG(arm)))

    print("\n" + "=" * 108)
    print("MIRROR CONTROL -- the codeword, or its sign?")
    print("=" * 108)
    print(hdr)
    row(D, "MX-asym-MIDN", "MX-asym-MID", MODELS)
    for m in MODELS:
        row(D, "MX-asym-MIDN", "MX-asym-MID", [m])

    print("\n" + "=" * 108)
    print("DISENTANGLING CONTROL -- is the win the CODEWORD, or just a level "
          "near zero?")
    print("   MX-sym-NEAR0/6 and /3 carry the SAME 1/24 level but stay "
          "SYMMETRIC (15 values):")
    print("   they buy it by dropping 2/3 and 1/4 respectively, instead of "
          "spending the 16th codeword.")
    print("=" * 108)
    print(hdr)
    for a in CONTROLS:
        row(D, a, "MXFP4", MODELS, nk=2)
    print()
    for a in CONTROLS:
        row(D, a, "MX-asym-NEAR0", MODELS, nk=2)

    print("\n" + "=" * 108)
    print("THE CONTROL THAT MATTERS: does spending the codeword on E2M1's SHAPE "
          "close the gap to NF4?")
    print("=" * 108)
    gap = paired(np.concatenate([dvec(D, m, "NF4", "MXFP4") for m in MODELS]))
    best_mx = picks["MXFP4"]
    got = paired(np.concatenate([dvec(D, m, best_mx, "MXFP4") for m in MODELS]))
    left = paired(np.concatenate([dvec(D, m, best_mx, "NF4") for m in MODELS]))
    frac = got["mean_d"] / gap["mean_d"] if gap["mean_d"] else float("nan")
    print(f"  gap NF4 - MXFP4                : {gap['pct']:+.2f} %")
    print(f"  {best_mx} - MXFP4          : {got['pct']:+.2f} %")
    print(f"  fraction of the gap recovered  : {100*frac:.1f} %")
    print(f"  residual {best_mx} vs NF4  : {left['pct']:+.2f} % "
          f"[{left['lo']:+.2f}, {left['hi']:+.2f}]  {verdict(left)}")

    out = {"picks": picks, "select_on": SELECT_ON,
           "ppl": {m: D[m]["ppl"] for m in MODELS}}
    json.dump(out, open(os.path.join(HERE, "campaignB_stats.json"), "w"), indent=1)
    print("\nwrote campaignB_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
