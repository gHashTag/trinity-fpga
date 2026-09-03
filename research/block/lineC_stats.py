#!/usr/bin/env python3
"""Line C analysis, exactly as PREREGISTRATION_FIFTH_2026-08-12.md fixed it.

The replicate unit is THE CHECKPOINT. Each checkpoint contributes one number,
d_m = mean over its windows of (nll_arm,i - nll_ref,i), so ppl_arm/ppl_ref =
exp(d_m) exactly. Windows are replicates of the TEXT and are never pooled across
checkpoints in a cross-model row -- that error has been made six times in this
campaign and the seventh is not going to be here.

Nothing is reimplemented: `paired` and `verdict` are campaignC_stats'.

Three sets of figures are printed SEPARATELY and all three always print:
OLD FOUR (selection-contaminated), NEW FOUR (pre-registered, clean), COMBINED
(flagged contaminated, never the headline).

    python3 lineC_stats.py
"""
import itertools
import json
import math
import os

import numpy as np
from scipy import stats

from campaignC_stats import paired, verdict

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = ["smollm2", "qwen", "pythia", "opt"]
NEW = ["gpt2", "gptneo", "bloom", "mamba"]
LABEL = {"smollm2": "SmolLM2-135M", "qwen": "Qwen2.5-0.5B",
         "pythia": "Pythia-160M", "opt": "OPT-125M",
         "gpt2": "GPT-2-124M", "gptneo": "GPT-Neo-125M",
         "bloom": "BLOOM-560M", "mamba": "Mamba-130M"}
NINE = ["NEAR0", "NEAR0N", "MIDN", "MID", "G12", "G23", "G34", "G68", "MID2"]
ARM = {g: f"MX-asym-{g}" for g in NINE}
NK_PRIMARY = 3          # H1, H2, H3
NK_NINE = 9             # the exploratory per-placement matrix


def load_old():
    """campaignB (4 placements + MIDN) + campaignA_ppl (the 4 added gaps +
    NEAR0N). Merged only after asserting both files' fp32 and MXFP4 per-window
    vectors are bit-identical -- otherwise they are two different measurements
    wearing one name."""
    out = {}
    for m in OLD:
        b = json.load(open(os.path.join(HERE, f"campaignB_{m}.json")))
        a = json.load(open(os.path.join(HERE, f"campaignA_ppl_{m}.json")))
        assert b["rulers_reproduce"], m
        for anchor in ("fp32", "MXFP4"):
            assert b["per_window_nll"][anchor] == a["per_window_nll"][anchor], \
                f"{m}: {anchor} not bit-identical between campaigns A and B"
        w = dict(b["per_window_nll"])
        w.update(a["per_window_nll"])
        out[m] = w
    return out


def load_new():
    out = {}
    for m in NEW:
        p = os.path.join(HERE, f"lineC_{m}.json")
        if not os.path.exists(p):
            raise SystemExit(f"missing {p} -- a pre-registered checkpoint may "
                             "not be dropped after the fact")
        d = json.load(open(p))
        assert d["instrument_bit_exact"], m
        assert d["mxfp4_costs_ppl"], m
        assert len(d["per_window_nll"]["MXFP4"]) == d["nwin"], m
        for a in [ARM[g] for g in NINE] + ["NF4"]:
            assert a in d["per_window_nll"], f"{m}: {a} not measured"
        out[m] = d
    return out


def dbar(W, arm, ref):
    """One checkpoint's model-level log-ratio."""
    return float(np.mean(np.array(W[arm]) - np.array(W[ref])))


def ml(D, arm, ref, models):
    return paired(np.array([dbar(D[m], arm, ref) for m in models]))


def spearman_exact(x, y):
    """rho plus the exact two-sided permutation p over all 9! rankings.
    n = 9 makes the asymptotic p a rough approximation; the exact one governs.
    """
    n = len(x)
    rx = stats.rankdata(x)
    ry = stats.rankdata(y)
    rho = float(stats.spearmanr(x, y).statistic)
    base = np.array(sorted(rx))
    hits = tot = 0
    d0 = 1 - 6 * np.sum((rx - ry) ** 2) / (n * (n * n - 1))
    for perm in itertools.permutations(range(n)):
        dv = base[list(perm)] - ry
        r = 1 - 6 * np.sum(dv * dv) / (n * (n * n - 1))
        tot += 1
        if abs(r) >= abs(d0) - 1e-12:
            hits += 1
    return rho, hits / tot, float(stats.spearmanr(x, y).pvalue)


def line(tag, r, nk=1, extra=""):
    ci = f"[{r['lo']:+.2f}, {r['hi']:+.2f}]"
    print(f"  {tag:<34}{r['pct']:>+8.2f}%{ci:>20}{r['t']:>+8.2f}"
          f"{r['p']:>10.2e}{r['n_better']:>4}/{r['n']:<3} "
          f"{verdict(r, nk):<6}{extra}")


HDR = (f"  {'comparison':<34}{'margin':>9}{'95% CI':>20}{'t':>8}{'p':>10}"
       f"{'sign':>8} verdict")


def main():
    O, N = load_old(), load_new()
    D = dict(O)
    for m in NEW:
        D[m] = N[m]["per_window_nll"]

    print("=" * 104)
    print("LINE C -- four checkpoints from families this campaign had never "
          "measured, pre-registered")
    print("=" * 104)
    print(f"{'checkpoint':<16}{'SEQLEN':>7}{'win':>5}{'tensors':>9}{'%params':>9}"
          f"{'fp32':>10}{'MXFP4':>10}   NEW RULERS")
    for m in NEW:
        d = N[m]
        print(f"{LABEL[m]:<16}{d['seqlen']:>7}{d['nwin']:>5}"
              f"{d['n_target_tensors']:>9}{100*d['frac_params_quantised']:>8.1f}%"
              f"{d['ppl']['fp32']:>10.4f}{d['ppl']['MXFP4']:>10.4f}"
              f"   {'Conv1D x'+str(d['n_conv1d']) if d['n_conv1d'] else ''}")

    print("\n" + "=" * 104)
    print("H1  MX-asym-NEAR0 vs MXFP4      (model-level; n = checkpoints, "
          "never windows)")
    print("=" * 104)
    print(HDR)
    h1_new = ml(D, ARM["NEAR0"], "MXFP4", NEW)
    h1_old = ml(D, ARM["NEAR0"], "MXFP4", OLD)
    h1_all = ml(D, ARM["NEAR0"], "MXFP4", OLD + NEW)
    line("NEW FOUR  (pre-registered)", h1_new, NK_PRIMARY, "  <- H1, Bonf x3")
    line("old four  (contaminated)", h1_old)
    line("combined n=8 (contaminated)", h1_all, NK_PRIMARY,
         "  4/8 chose the arm")
    print("\n  per-checkpoint margin vs MXFP4:")
    for m in NEW + OLD:
        v = 100 * (math.exp(dbar(D[m], ARM["NEAR0"], "MXFP4")) - 1)
        w = np.array(D[m][ARM["NEAR0"]]) - np.array(D[m]["MXFP4"])
        print(f"     {LABEL[m]:<16}{v:>+8.2f}%   windows better "
              f"{int((w < 0).sum())}/{len(w)}"
              f"{'   [new]' if m in NEW else ''}")

    print("\n" + "=" * 104)
    print("H2  MX-asym-NEAR0 vs NF4        (predicted direction: negative)")
    print("=" * 104)
    print(HDR)
    h2_new = ml(D, ARM["NEAR0"], "NF4", NEW)
    h2_old = ml(D, ARM["NEAR0"], "NF4", OLD)
    h2_all = ml(D, ARM["NEAR0"], "NF4", OLD + NEW)
    line("NEW FOUR  (pre-registered)", h2_new, NK_PRIMARY, "  <- H2, Bonf x3")
    line("old four", h2_old)
    line("combined n=8", h2_all, NK_PRIMARY)
    print("\n  per-checkpoint margin vs NF4:")
    for m in NEW + OLD:
        print(f"     {LABEL[m]:<16}"
              f"{100*(math.exp(dbar(D[m], ARM['NEAR0'], 'NF4'))-1):>+8.2f}%"
              f"{'   [new]' if m in NEW else ''}")
    print("\n  reference: NF4 vs MXFP4")
    print(HDR)
    line("NF4 vs MXFP4, new four", ml(D, "NF4", "MXFP4", NEW))
    line("NF4 vs MXFP4, old four", ml(D, "NF4", "MXFP4", OLD))

    print("\n" + "=" * 104)
    print("H3  does the NINE-PLACEMENT ORDER transport?   (Spearman, exact "
          "permutation p over 9! rankings)")
    print("=" * 104)
    rows = []
    for g in NINE:
        rn = ml(D, ARM[g], "MXFP4", NEW)
        ro = ml(D, ARM[g], "MXFP4", OLD)
        rows.append((g, ro["pct"], rn["pct"], rn))
    old_v = [r[1] for r in rows]
    new_v = [r[2] for r in rows]
    rho, p_exact, p_asym = spearman_exact(old_v, new_v)
    o_rank = {g: i + 1 for i, (g, _, _, _) in
              enumerate(sorted(rows, key=lambda r: r[1]))}
    n_rank = {g: i + 1 for i, (g, _, _, _) in
              enumerate(sorted(rows, key=lambda r: r[2]))}
    print(f"{'placement':<10}{'old rank':>9}{'old mean':>10}"
          f"{'new rank':>10}{'new mean':>10}{'new 95% CI':>22}"
          f"{'p x9':>9}  verdict")
    for g, ov, nv, rn in sorted(rows, key=lambda r: r[1]):
        ci = f"[{rn['lo']:+.2f}, {rn['hi']:+.2f}]"
        print(f"{g:<10}{o_rank[g]:>9}{ov:>+9.2f}%{n_rank[g]:>10}{nv:>+9.2f}%"
              f"{ci:>22}{min(1.0, rn['p']*NK_NINE):>9.3f}  "
              f"{verdict(rn, NK_NINE)}")
    print(f"\n  Spearman rho = {rho:+.4f}   exact permutation p = {p_exact:.4f}"
          f"   (asymptotic p = {p_asym:.4f})   "
          f"{'CLEARS' if p_exact*NK_PRIMARY < 0.05 else 'TIE'} at Bonferroni x3")

    print("\n" + "=" * 104)
    print("PREDICTION vs OUTCOME    (predictions fixed in "
          "PREREGISTRATION_FIFTH_2026-08-12.md before any model was loaded)")
    print("=" * 104)
    nneg_new = sum(1 for m in NEW if dbar(D[m], ARM["NEAR0"], "MXFP4") < 0)
    nneg_h2 = sum(1 for m in NEW if dbar(D[m], ARM["NEAR0"], "NF4") < 0)
    worst2 = sorted(rows, key=lambda r: -r[2])[:2]
    preds = [
        ("P1 H1 mean, new four", "-3.0 %", f"{h1_new['pct']:+.2f} %"),
        ("P1 H1 verdict, new four", "TIE",
         verdict(h1_new, NK_PRIMARY) + f" (Bonf x3, p x3 = "
         f"{min(1.0, h1_new['p']*NK_PRIMARY):.4f})"),
        ("P2 H1 sign pattern", "4/4 negative", f"{nneg_new}/4 negative"),
        ("P3 H1 uncorrected p", "~0.05 (0.02-0.15)", f"{h1_new['p']:.4f}"),
        ("P4 H1 combined n=8", "-3.9 %, BEATS uncorr.",
         f"{h1_all['pct']:+.2f} %, {verdict(h1_all)}"),
        ("P5 H2 mean, new four", "-1.0 %, TIE, 3/4 neg",
         f"{h2_new['pct']:+.2f} %, {verdict(h2_new, NK_PRIMARY)}, "
         f"{nneg_h2}/4 neg"),
        ("P6 H3 Spearman rho", "+0.75, exact p < 0.05",
         f"{rho:+.4f}, exact p = {p_exact:.4f}"),
        ("P7 H3 NEAR0 rank 1 or 2", "yes", f"rank {n_rank['NEAR0']}"),
        ("P7 H3 G23/G34 the two worst", "yes",
         "yes" if {w[0] for w in worst2} == {"G23", "G34"}
         else "no: " + "+".join(w[0] for w in worst2)),
        ("P8 mamba not the outlier", "NEAR0 beats MXFP4 there",
         f"{100*(math.exp(dbar(D['mamba'], ARM['NEAR0'], 'MXFP4'))-1):+.2f} %"),
    ]
    print(f"  {'prediction':<32}{'predicted':<26}outcome")
    for a, b, c in preds:
        print(f"  {a:<32}{b:<26}{c}")

    out = {
        "preregistration_sha256":
            "44e8c58b46ce9d12491e02686507e1492f77ed4ff7b0677fbe7e1aa9631e6bff",
        "new_checkpoints": NEW, "old_checkpoints": OLD,
        "new_rulers": {m: N[m]["ppl"] for m in NEW},
        "new_protocol": {m: {k: N[m][k] for k in
                             ("seqlen", "nwin", "n_target_tensors", "n_conv1d",
                              "frac_params_quantised", "instrument_bit_exact")}
                         for m in NEW},
        "H1": {"new": h1_new, "old": h1_old, "combined": h1_all},
        "H2": {"new": h2_new, "old": h2_old, "combined": h2_all},
        "H3": {"rho": rho, "p_exact": p_exact, "p_asymptotic": p_asym,
               "old_mean_pct": {g: v for g, v, _, _ in rows},
               "new_mean_pct": {g: v for g, _, v, _ in rows}},
        "nine_new": {g: r for g, _, _, r in rows},
        "per_checkpoint_NEAR0_vs_MXFP4":
            {m: 100 * (math.exp(dbar(D[m], ARM["NEAR0"], "MXFP4")) - 1)
             for m in OLD + NEW},
        "per_checkpoint_NEAR0_vs_NF4":
            {m: 100 * (math.exp(dbar(D[m], ARM["NEAR0"], "NF4")) - 1)
             for m in OLD + NEW},
    }
    json.dump(out, open(os.path.join(HERE, "lineC_stats.json"), "w"), indent=1)
    print("\nwrote lineC_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
