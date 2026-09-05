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


# A placement is a book that INSERTS the sixteenth codeword; campaignB_books
# labels it kind="sig". MX-asym-TOP and JK-asym-TOP instead extend the ladder to
# 16/12 and pay by clipping the negative extreme to -0.75, kind="clip", and are
# not placements. A clipping arm is never ranked beside placements without
# saying so -- hence the tag.
#
# The family size is COUNTED, not written down. A single constant NK_PLACEMENT=3
# was applied to both families while the MX block tests FOUR placements (MID,
# MID2, NEAR0, MIDN) and the JK block tests THREE. The constant was correct for
# one of the two blocks it was used in. It moves no verdict at n = 4 -- every MX
# row is a TIE at 3 and at 4 -- but a family size that has to be re-derived by
# the reader is a family size that will be wrong the next time an arm is added,
# which is exactly how MIDN slipped out of the set below.
_KIND = {n: k for n, k, lv in B.books()}


def placements(arms):
    """The kind='sig' members of `arms` -- the set a placement claim ranges over."""
    return [a for a in arms if _KIND.get(a) == "sig"]


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
    # THE SET THE ARGMIN RANGES OVER, named. It used to be the literal MX_ASYM,
    # which is a DISPLAY list written before MX-asym-MIDN existed: it carried
    # the clipping arm MX-asym-TOP, which is not a placement, and omitted MIDN,
    # which is. So the argmin ran over a set that was neither the placement
    # family nor the Bonferroni family -- a third set, never stated.
    # It is not cosmetic. On the selection model MIDN is 20.8333 and NEAR0
    # 20.8440, so over the placements the pick is MIDN, and two of the three
    # held-out verdicts below change with it. Both picks are therefore printed,
    # because the honest reading is that the selection model does not resolve
    # the choice: MIDN vs NEAR0 on SmolLM2 is -0.05 % [-0.72, +0.62], p = 0.88,
    # better in 19 of 40 windows -- a TIE on the very data that chose.
    for fam, parent, disp in (("MXFP4", "MXFP4", MX_ASYM + ["MX-asym-MIDN"]),
                              ("JOINT-KL", "JOINT-KL", JK_ASYM)):
        cands = placements(disp)
        best = min(cands, key=lambda a: D[SELECT_ON]["ppl"][a])
        shipped = min(MX_ASYM if fam == "MXFP4" else JK_ASYM,
                      key=lambda a: D[SELECT_ON]["ppl"][a])
        # Both, always. Downstream sections take an argmin's winner as "the"
        # arm; when the argmin cannot separate its top two, "the" arm does not
        # exist and a single key would hide that.
        picks[fam] = {"placement_argmin": best, "published": shipped}
        print(f"\n{fam}: argmin over the {len(cands)} PLACEMENTS "
              f"{'{'}{', '.join(a.replace('MX-asym-', '').replace('JK-asym-', '') for a in cands)}{'}'}"
              f" on {LABEL[SELECT_ON]} = {best}")
        print("   ranking there: "
              + ", ".join(f"{a}={D[SELECT_ON]['ppl'][a]:.4f}"
                          for a in sorted(disp, key=lambda a: D[SELECT_ON]['ppl'][a]))
              + f"   ({CLIP_TAG(disp[0]).strip() or 'no clipping arm in this family'})")
        if shipped != best:
            print(f"   NOTE: published as {shipped}, the argmin over the stale "
                  f"display list. Both are reported.")
        for pick, why in ([(best, "argmin over the placements")]
                          + ([(shipped, "the published pick")]
                             if shipped != best else [])):
            oos = [m for m in MODELS
                   if m != SELECT_ON and m not in FITTED_ON[pick]]
            print(f"\n   {pick}  ({why}); held out on "
                  + "+".join(LABEL[m].split("-")[0] for m in oos))
            if not oos:
                print("   NO held-out model remains -- nothing can be claimed OOS.")
                continue
            print(hdr)
            row(D, pick, parent, oos)
            row(D, pick, "MXFP4", oos)
            row(D, pick, "NF4", oos)
            row(D, pick, "NF4-sym", oos)

    # nk is the size of the placement family THIS BLOCK ranges over, counted
    # from the arms actually printed. The MX block tests four placements and the
    # JK block three; one constant served both.
    MXD = MX_ASYM + ["MX-asym-MIDN"]
    nk_mx, nk_jk = len(placements(MXD)), len(placements(JK_ASYM))
    print("\n" + "=" * 108)
    print(f"EVERY ARM ACROSS ALL FOUR MODELS, MODEL-LEVEL  (Bonferroni x{nk_mx} "
          f"over the {nk_mx} MX placements, x{nk_jk} over the {nk_jk} JK ones)")
    print("   n = 4 CHECKPOINTS in every row. A clipping arm is printed but is "
          "not in either family.")
    print("=" * 108)
    print(hdr)
    for arm in MXD:
        row(D, arm, "MXFP4", MODELS, nk=nk_mx, tag=CLIP_TAG(arm))
    print()
    for arm in MXD:
        row(D, arm, "NF4", MODELS, nk=nk_mx, tag=CLIP_TAG(arm))
    print()
    for arm in JK_ASYM:
        row(D, arm, "JOINT-KL", MODELS, nk=nk_jk,
            tag=("3/4 in-sample" + CLIP_TAG(arm)))
    print()
    for arm in JK_ASYM:
        row(D, arm, "NF4", ["opt"], nk=nk_jk,
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
    print("   CROSS-MODEL, so n = 4 CHECKPOINTS, one mean log-ratio each -- the "
          "same unit row() takes.")
    print("=" * 108)
    # `row()` was corrected on 2026-08-12 and these three calls were not: they
    # kept `np.concatenate` over the four models and reported a 140-window
    # interval three lines under a table of four-checkpoint intervals. The point
    # estimates move by hundredths; the residual's verdict moves from BEATS to
    # TIE, which is the verdict POOLED_VERDICTS_RESTATED_2026-08-12 already
    # published for the identical comparison in the table above. The section was
    # contradicting its own file.
    def _ml4(arm, ref):
        return paired(np.array([float(dvec(D, m, arm, ref).mean())
                                for m in MODELS]))

    gap = _ml4("NF4", "MXFP4")
    print(f"  gap NF4 - MXFP4                : {gap['pct']:+.2f} % "
          f"[{gap['lo']:+.2f}, {gap['hi']:+.2f}]  {verdict(gap)}")
    # Both arms the selection model cannot separate, not just the one that
    # happened to win an argmin over a stale list.
    for key, why in (("placement_argmin", "argmin over the placements"),
                     ("published", "the published pick")):
        best_mx = picks["MXFP4"][key]
        if key == "published" and best_mx == picks["MXFP4"]["placement_argmin"]:
            continue
        got = _ml4(best_mx, "MXFP4")
        left = _ml4(best_mx, "NF4")
        frac = got["mean_d"] / gap["mean_d"] if gap["mean_d"] else float("nan")
        print(f"\n  {best_mx}   ({why})")
        print(f"    vs MXFP4                     : {got['pct']:+.2f} % "
              f"[{got['lo']:+.2f}, {got['hi']:+.2f}]  {verdict(got)}")
        print(f"    fraction of the gap recovered: {100*frac:.1f} %   "
              f"(a ratio of two point estimates, and it carries no interval)")
        print(f"    residual vs NF4              : {left['pct']:+.2f} % "
              f"[{left['lo']:+.2f}, {left['hi']:+.2f}]  {verdict(left)}")
    print(f"\n  n = {gap['n']} checkpoints in every line above.")

    out = {"picks": picks, "select_on": SELECT_ON,
           "ppl": {m: D[m]["ppl"] for m in MODELS}}
    json.dump(out, open(os.path.join(HERE, "campaignB_stats.json"), "w"), indent=1)
    print("\nwrote campaignB_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
