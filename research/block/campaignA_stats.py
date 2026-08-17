#!/usr/bin/env python3
"""Campaign A: is the placement choice stable when it is made JOINTLY?

The rotation in SIXTEENTH_CODEWORD_SPENT_2026-08-12.md picked the placement on
ONE model and got a different answer for each model it picked on.  JOINT-KL was
fitted against three models at once and that acted as a regulariser, so the same
regulariser is applied to the placement choice here:

    for each held-out model h:
        joint_h(book) = sum over the OTHER three models of KL(fp32 || book)
        winner_h      = argmin over placements of joint_h
        verdict       = winner_h measured on h, against MXFP4 / NF4 / NF4-sym

The held-out model takes no part in the selection: neither its KL nor its
perplexity.  The TEXT is not held out -- wikitext-2 is the calibration set for
every model and the evaluation set for every model, exactly as in the fit this
copies -- so the claim is about generalisation across CHECKPOINTS, not corpora.

STATISTICS.  A margin on one held-out model is a within-model claim and is
quoted at the window level.  "Joint selection beats X out of sample" is a
cross-model claim with n = 4 rotations, and is quoted at the model level.
`paired` and `verdict` are campaignC_stats' -- not a third implementation.

    python3 campaignA_stats.py
"""
import json
import math
import os

import numpy as np
from scipy import stats

import campaignA_books as A
from campaignC_stats import paired, verdict

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
LABEL = {"smollm2": "SmolLM2-135M", "qwen": "Qwen2.5-0.5B",
         "pythia": "Pythia-160M", "opt": "OPT-125M"}
REFS = ["MXFP4", "NF4", "NF4-sym"]
CANDS = [n for n, k, lv in A.candidates()]


TOL = 1e-5


def load():
    kl, nll, repro = {}, {}, {}
    books = {n: [float(x) for x in lv] for n, k, lv in A.all_books()}
    for m in MODELS:
        j = json.load(open(os.path.join(HERE, f"campaignA_kl_{m}.json")))
        assert j["ruler_reproduces"], m
        kl[m] = j["kl"]
        for n, lv in j["books"].items():
            assert [float(x) for x in lv] == books[n], f"{m}: {n} book drifted"
        b = json.load(open(os.path.join(HERE, f"campaignB_{m}.json")))
        assert b["rulers_reproduce"], m
        nll[m] = {k: np.array(v) for k, v in b["per_window_nll"].items()}
        for n, lv in b["books"].items():
            if n in books:
                assert [float(x) for x in lv] == books[n], f"{m}: {n} book drifted"
        # per-window NLL reproduced in this campaign's own process.  TOL is far
        # below anything this campaign discusses: 1e-5 nats is 1e-3 % of
        # perplexity, three orders below the smallest margin quoted.
        for k, v in j["per_window_nll"].items():
            d = float(np.abs(np.array(v) - nll[m][k]).max())
            repro[(m, k)] = d
            assert d < TOL, f"{m}/{k}: campaign A vs B per-window NLL differ {d:.2e}"
        p = os.path.join(HERE, f"campaignA_ppl_{m}.json")
        if os.path.exists(p):
            e = json.load(open(p))
            for k, v in e["per_window_nll"].items():
                if k in nll[m]:
                    d = float(np.abs(np.array(v) - nll[m][k]).max())
                    repro[(m, k)] = max(repro.get((m, k), 0.0), d)
                    assert d < TOL, f"{m}/{k}: ppl pass disagrees {d:.2e}"
                else:
                    nll[m][k] = np.array(v)
    return kl, nll, repro


def main():
    kl, nll, repro = load()
    print(f"rulers reproduce on all four models.  Campaign B's per-window NLL "
          f"re-measured in this campaign's own process: worst disagreement "
          f"{max(repro.values()):.2e} nats over {len(repro)} vectors "
          f"(tolerance {TOL:.0e}).\n")

    print("=" * 100)
    print("0.  MEASURED PERPLEXITY  (block 32, E8M0, lm_head excluded, "
          "every book at max|level| = 1.0)")
    print("=" * 100)
    print(f"{'arm':<16}" + "".join(f"{LABEL[m]:>17}" for m in MODELS))
    for a in ["fp32", "MXFP4", "NF4", "NF4-sym"] + CANDS:
        cells = []
        for m in MODELS:
            cells.append(f"{float(np.exp(nll[m][a].mean())):>17.4f}"
                         if a in nll[m] else f"{'--':>17}")
        print(f"{a:<16}" + "".join(cells))

    print("\n" + "=" * 100)
    print("1.  KL(fp32 || quantised), 2 calibration windows per model "
          "(joint_kl_codebook.py's objective)")
    print("=" * 100)
    print(f"{'book':<16}" + "".join(f"{LABEL[m]:>17}" for m in MODELS)
          + f"{'sum(4)':>12}")
    order = sorted(CANDS + REFS, key=lambda b: sum(kl[m][b] for m in MODELS))
    for b in order:
        tot = sum(kl[m][b] for m in MODELS)
        mark = "  <- reference" if b in REFS else ""
        print(f"{b:<16}" + "".join(f"{kl[m][b]:>17.6f}" for m in MODELS)
              + f"{tot:>12.6f}{mark}")

    print("\n" + "=" * 100)
    print("2.  ROTATION: choose the placement on THREE models, judge on the fourth")
    print("=" * 100)
    rot = {}
    for h in MODELS:
        fit = [m for m in MODELS if m != h]
        joint = {b: sum(kl[m][b] for m in fit) for b in CANDS}
        rank = sorted(joint, key=joint.get)
        w = rank[0]
        rot[h] = {"fit_models": fit, "winner": w, "joint": joint,
                  "rank": rank}
        gap = 100 * (joint[rank[1]] / joint[w] - 1)
        print(f"\nheld out {LABEL[h]:<14} fitted on {'+'.join(fit)}")
        print(f"   winner = {w}   joint KL {joint[w]:.6f}   "
              f"runner-up {rank[1]} +{gap:.3f}%")
        print("   full ranking: " + " < ".join(r.replace("MX-asym-", "")
                                               for r in rank))

    winners = [rot[h]["winner"] for h in MODELS]
    stable = len(set(winners)) == 1
    print(f"\nSTABILITY: {len(set(winners))} distinct winner(s) over four "
          f"rotations -> {'STABLE' if stable else 'UNSTABLE'}")

    print("\n" + "=" * 100)
    print("3.  THE WINNER ON THE HELD-OUT MODEL  (within-model claim -> "
          "WINDOW-level statistics)")
    print("=" * 100)
    print(f"{'held out':<15}{'winner':<16}{'vs':<9}{'%':>9}{'95% CI':>21}"
          f"{'t':>9}{'p':>11}{'win':>9}  verdict")
    held = {}
    for h in MODELS:
        w = rot[h]["winner"]
        for ref in REFS:
            assert w in nll[h], f"{h}: {w} has no measured per-window NLL"
            d = nll[h][w] - nll[h][ref]
            r = paired(d)
            held[(h, ref)] = r
            print(f"{LABEL[h]:<15}{w.replace('MX-asym-',''):<16}{ref:<9}"
                  f"{r['pct']:>+8.2f}%"
                  f"{('[%+.2f, %+.2f]' % (r['lo'], r['hi'])):>21}"
                  f"{r['t']:>+9.2f}{r['p']:>11.2e}"
                  f"{r['n_better']:>5}/{r['n']:<3}  {verdict(r)}")
        print()

    print("=" * 100)
    print("4.  DOES JOINT SELECTION BEAT THE REFERENCES OUT OF SAMPLE?  "
          "(cross-model claim -> n = 4)")
    # A rotation whose four folds pick the SAME book is not a rotation. Its
    # "held-out mean" is then the plain four-model mean of that one book --
    # algebraically identical, not merely close -- and the words "held out"
    # carry no information at all. That is exactly what happened to
    # MX-asym-NEAR0's "-4.74 %, 4/4" (NEAR0_HELD_OUT_LABEL_EMPTY_2026-08-12).
    # Today the rotation is genuine, so the label is earned; the guard prints
    # itself rather than waiting for a reader to re-derive it.
    if stable:
        print("   !! ALL FOUR FOLDS PICKED " + winners[0] + ". A unanimous")
        print("   !! rotation is not a rotation: the row below is the plain "
              "four-model mean of")
        print("   !! that one book, and 'held out' is an empty label on it.")
    else:
        print(f"   Rotation is genuine: {len(set(winners))} distinct winners "
              f"over four folds, so no row below")
        print("   is the in-sample mean wearing a held-out label.")
    print("=" * 100)
    print(f"{'vs':<10}{'%':>9}{'95% CI':>23}{'t':>9}{'p':>11}{'models':>9}"
          f"  verdict   per-rotation %")
    cross = {}
    for ref in REFS:
        md = np.array([float((nll[h][rot[h]['winner']] - nll[h][ref]).mean())
                       for h in MODELS])
        r = paired(md)
        cross[ref] = r
        each = "  ".join(f"{100*(math.exp(x)-1):+.2f}" for x in md)
        print(f"{ref:<10}{r['pct']:>+8.2f}%"
              f"{('[%+.2f, %+.2f]' % (r['lo'], r['hi'])):>23}"
              f"{r['t']:>+9.2f}{r['p']:>11.2e}{r['n_better']:>5}/{r['n']:<3}"
              f"  {verdict(r):<9} {each}")

    print("\n" + "=" * 100)
    print("5.  IS KL A HONEST PROXY?  joint KL rank vs held-out perplexity rank")
    print("=" * 100)
    for h in MODELS:
        have = [b for b in CANDS if b in nll[h]]
        if len(have) < 3:
            print(f"{LABEL[h]:<15} only {len(have)} placements measured, skipped")
            continue
        x = [rot[h]["joint"][b] for b in have]
        y = [float((nll[h][b] - nll[h]["MXFP4"]).mean()) for b in have]
        rho, p = stats.spearmanr(x, y)
        best_ppl = have[int(np.argmin(y))]
        print(f"{LABEL[h]:<15} n={len(have):2d}  spearman rho = {rho:+.3f} "
              f"(p={p:.3f})   joint-KL pick = "
              f"{rot[h]['winner'].replace('MX-asym-',''):<7} "
              f"best measured = {best_ppl.replace('MX-asym-','')}")

    print("\n" + "=" * 100)
    print("6.  CONTROL: what ONE model picks, under the same criterion and "
          "under perplexity")
    print("=" * 100)
    print(f"{'selection model':<16}{'argmin KL (1 model)':<24}"
          f"{'argmin measured ppl':<24}  joint winner when this model is HELD OUT")
    single_kl, single_ppl = {}, {}
    for m in MODELS:
        a = min(CANDS, key=lambda b: kl[m][b])
        have = [b for b in CANDS if b in nll[m]]
        p = min(have, key=lambda b: float(nll[m][b].mean()))
        single_kl[m], single_ppl[m] = a, p
        print(f"{LABEL[m]:<16}{a.replace('MX-asym-',''):<24}"
              f"{p.replace('MX-asym-',''):<24}  "
              f"{rot[m]['winner'].replace('MX-asym-','')}")
    allj = {b: sum(kl[m][b] for m in MODELS) for b in CANDS}
    deploy = min(allj, key=allj.get)
    print(f"\ndistinct winners: joint-of-3 {len(set(winners))}   "
          f"single-model KL {len(set(single_kl.values()))}   "
          f"single-model perplexity {len(set(single_ppl.values()))}")
    print(f"joint over ALL FOUR models (the deployment choice, no held-out "
          f"model left): {deploy}")

    print("\n" + "=" * 100)
    print("7.  THE PROTOCOL THIS REPLACES: select on ONE model by perplexity, "
          "judge on the other three")
    print("=" * 100)
    print(f"{'selected on':<16}{'winner':<10}"
          + "".join(f"{'vs MXFP4 on ' + LABEL[m].split('-')[0]:>22}" for m in MODELS))
    single_rows = {}
    for s in MODELS:
        w = single_ppl[s]
        cells, keep = [], []
        for m in MODELS:
            v = 100 * (math.exp(float((nll[m][w] - nll[m]["MXFP4"]).mean())) - 1)
            if m == s:
                cells.append(f"{'(in-sample) %+.2f' % v:>22}")
            else:
                cells.append(f"{v:>+21.2f}%")
                keep.append(v)
        single_rows[s] = {"winner": w, "held_out_pct": keep}
        print(f"{LABEL[s]:<16}{w.replace('MX-asym-',''):<10}" + "".join(cells))
    flat = [v for s in MODELS for v in single_rows[s]["held_out_pct"]]
    joint_flat = [100 * (math.exp(float((nll[h][rot[h]['winner']]
                                         - nll[h]["MXFP4"]).mean())) - 1)
                  for h in MODELS]
    print(f"\nvs MXFP4, held-out model-level results that are WINS:")
    print(f"   select on one model, by perplexity : "
          f"{sum(1 for v in flat if v < 0)}/{len(flat)}   worst {max(flat):+.2f}%")
    print(f"   select jointly on three, by KL     : "
          f"{sum(1 for v in joint_flat if v < 0)}/{len(joint_flat)}   "
          f"worst {max(joint_flat):+.2f}%")

    out = {"models": MODELS, "candidates": CANDS, "kl": kl,
           "single_model_protocol": single_rows,
           "single_model_kl_pick": single_kl, "single_model_ppl_pick": single_ppl,
           "joint_all_four": {"levels_pick": deploy, "joint": allj},
           "ppl_vs_mxfp4_pct": {
               m: {b: 100 * (math.exp(float((nll[m][b] - nll[m]["MXFP4"]).mean())) - 1)
                   for b in CANDS + ["NF4", "NF4-sym"] if b in nll[m]}
               for m in MODELS},
           "rotation": {h: {"fit_models": rot[h]["fit_models"],
                            "winner": rot[h]["winner"],
                            "joint": rot[h]["joint"],
                            "rank": rot[h]["rank"]} for h in MODELS},
           "stable": bool(stable), "winners": winners,
           "held_out_window_level": {f"{h}|{r}": v for (h, r), v in held.items()},
           "cross_model": cross}
    json.dump(out, open(os.path.join(HERE, "campaignA_stats.json"), "w"), indent=1)
    print("\nwrote campaignA_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
