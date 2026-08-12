#!/usr/bin/env python3
"""Does a one-model KL FIT transfer the way one-model KL SELECTION did?

Selection picks among ten pre-built candidates.  Fitting searches a
six-dimensional continuum.  PLACEMENT_AND_ASYMMETRY_2026-08-12 measured that
selecting on one model by KL dominates selecting on three by KL; this asks the
same question of the fit, with the same objective and the same held-out unit
(the CHECKPOINT, never the window).

Statistics.  A fit's held-out claim is a CROSS-MODEL claim, so it is quoted at
the MODEL level: n = 3 held-out models per rotation, n = 4 for a book that saw
no checkpoint.  Window-level numbers appear only inside a single model.
`paired` and `verdict` are campaignC_stats' -- not a third implementation.

    python3 onefit_stats.py
"""
import json
import math
import os

import numpy as np

from campaignC_stats import paired, verdict

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
LABEL = {"smollm2": "SmolLM2-135M", "qwen": "Qwen2.5-0.5B",
         "pythia": "Pythia-160M", "opt": "OPT-125M"}
FITS = [f"FIT-{m}" for m in MODELS]

# Books that saw no checkpoint at all, plus the two this campaign is about.
# JOINT-KL was fitted against the SUM of KL over smollm2+qwen+pythia, so OPT is
# the only model it never saw.  KL-opt is the ORIGINAL one-model KL fit on
# smollm2 (KL_CODEBOOK_WITHDRAWN_2026-08-11), seeded from Lloyd-Max.
FITTED_ON = {
    "MXFP4": [], "NF4": [], "NF4-sym": [], "MX-asym-NEAR0": [],
    "JOINT-KL": ["smollm2", "qwen", "pythia"],
    "KL-opt": ["smollm2"],
    **{f"FIT-{m}": [m] for m in MODELS},
}
REFS = ["MXFP4", "NF4", "NF4-sym", "MX-asym-NEAR0", "JOINT-KL", "KL-opt"]
# Campaigns B and C measured the same six arms in two separate processes and
# already disagree by up to 7.9e-05 nats on pythia (0.00e+00 on qwen and opt,
# 7.2e-07 on smollm2): that model's forward is not bit-reproducible run to run.
# 5e-4 nats is 0.05 % of perplexity -- thirty times below the smallest margin
# quoted here -- and the worst observed value is printed, not just gated.
TOL = 5e-4


def load():
    nll, ppl, meta = {}, {}, {}
    for m in MODELS:
        b = json.load(open(os.path.join(HERE, f"campaignB_{m}.json")))
        c = json.load(open(os.path.join(HERE, f"campaignC_{m}.json")))
        o = json.load(open(os.path.join(HERE, f"onefit_ppl_{m}.json")))
        assert b["rulers_reproduce"] and c["rulers_reproduce"], m
        assert o["rulers_reproduce"], m
        d = {k: np.array(v) for k, v in b["per_window_nll"].items()}
        worst = 0.0
        for src in (c, o):
            for k, v in src["per_window_nll"].items():
                v = np.array(v)
                if k in d:
                    worst = max(worst, float(np.abs(v - d[k]).max()))
                else:
                    d[k] = v
        assert worst < TOL, f"{m}: sources disagree on a shared arm by {worst:.2e}"
        meta[m] = {"repro": worst, "nwin": o["nwin"]}
        assert o["nwin"] == b["nwin"] == c["nwin"], m
        nll[m] = d
        ppl[m] = {k: float(np.exp(v.mean())) for k, v in d.items()}
    return nll, ppl, meta


def pct(x):
    return 100 * (math.exp(x) - 1)


def main():
    nll, ppl, meta = load()
    fit = {m: json.load(open(os.path.join(HERE, f"onefit_kl_{m}.json")))
           for m in MODELS}
    print(f"Shared arms re-measured in this campaign's own process against "
          f"campaign B: worst disagreement "
          f"{max(v['repro'] for v in meta.values()):.2e} nats (tolerance "
          f"{TOL:.0e}).  All rulers reproduce.\n")

    # ---------------------------------------------------------------- 1 -----
    print("=" * 104)
    print("1.  THE FOUR ONE-MODEL KL FITS  (six free interior magnitudes, top "
          "pinned 1.0, step 0.06 -> 0.004)")
    print("=" * 104)
    print(f"{'book':<14}{'seed':<10}{'evals':>6}{'KL start':>11}{'KL end':>11}"
          f"{'vs MXFP4 KL':>13}{'moves':>7}   levels")
    mx = [0.0, 1 / 12, 1 / 6, 0.25, 1 / 3, 0.5, 2 / 3, 1.0]
    print(f"{'MXFP4':<14}{'--':<10}{'--':>6}{'--':>11}{'--':>11}{'--':>13}"
          f"{'--':>7}   [{', '.join(f'{x:.5f}' for x in mx)}]")
    for m in MODELS:
        j = fit[m]
        run = min(j["runs"], key=lambda r: r["kl"])
        assert abs(max(j["fitted"]) - 1.0) < 1e-12 and j["fitted"][0] == 0.0
        print(f"{'FIT-' + m:<14}{run['seed']:<10}{run['evals']:>6}"
              f"{run['kl_start']:>11.6f}{run['kl']:>11.6f}"
              f"{100 * (run['kl'] / j['kl_mxfp4'] - 1):>+12.2f}%"
              f"{len(run['trace']):>7}   "
              f"[{', '.join(f'{x:.5f}' for x in j['fitted'])}]")
    print(f"\n{'JOINT-KL':<14}{'(published, fitted on smollm2+qwen+pythia)':<52}"
          "[0.00000, 0.06833, 0.16667, 0.25000, 0.35583, 0.50000, 0.66667, 1.00000]")
    print(f"{'KL-opt':<14}{'(published, fitted on smollm2, Lloyd-Max seed)':<52}"
          "[0.00000, 0.07701, 0.18828, 0.31396, 0.46561, 0.61130, 0.79074, 1.00000]")

    # ---------------------------------------------------------------- 2 -----
    print("\n" + "=" * 104)
    print("2.  PERPLEXITY  (block 32, E8M0, lm_head excluded, every book at "
          "max|level| = 1.0)")
    print("=" * 104)
    print(f"{'arm':<16}" + "".join(f"{LABEL[m]:>18}" for m in MODELS))
    for a in ["fp32"] + REFS + FITS:
        print(f"{a:<16}" + "".join(
            (f"{ppl[m][a]:>17.4f}*" if m in FITTED_ON.get(a, []) else
             f"{ppl[m][a]:>18.4f}") if a in ppl[m] else f"{'--':>18}"
            for m in MODELS))
    print("* = this model was in the book's fit set")

    # ---------------------------------------------------------------- 3 -----
    print("\n" + "=" * 104)
    print("3.  EVERY ROTATION vs MXFP4, held out at the CHECKPOINT level "
          "(negative = beats MXFP4)")
    print("=" * 104)
    print(f"{'book':<14}" + "".join(f"{LABEL[m].split('-')[0]:>16}" for m in MODELS)
          + f"{'held-out mean':>15}{'worst':>9}{'wins':>7}")
    rows = {}
    for a in FITS + ["JOINT-KL", "KL-opt", "MX-asym-NEAR0", "NF4", "NF4-sym"]:
        cells, held = [], []
        for m in MODELS:
            v = pct(float((nll[m][a] - nll[m]["MXFP4"]).mean()))
            if m in FITTED_ON[a]:
                cells.append(f"{('(' + f'{v:+.2f}' + ')'):>16}")
            else:
                cells.append(f"{v:>+15.2f}%")
                held.append(v)
        rows[a] = held
        print(f"{a:<14}" + "".join(cells)
              + f"{np.mean(held):>+14.2f}%{max(held):>+8.2f}%"
              + f"{sum(1 for v in held if v < 0):>4}/{len(held)}")
    print("(x) = in-sample, excluded from the held-out summary")

    # ---------------------------------------------------------------- 4 -----
    print("\n" + "=" * 104)
    print("4.  MODEL-LEVEL STATISTICS PER ROTATION  (n = 3 held-out "
          "checkpoints; a margin inside its CI is a TIE)")
    print("=" * 104)
    print(f"{'book':<14}{'held out':<28}{'vs':<10}{'%':>9}{'95% CI':>22}"
          f"{'t':>9}{'p':>10}{'n':>6}  verdict")
    stats_out = {}
    for a in FITS + ["JOINT-KL", "KL-opt"]:
        oos = [m for m in MODELS if m not in FITTED_ON[a]]
        names = "+".join(LABEL[m].split("-")[0] for m in oos)
        for ref in ("MXFP4", "NF4"):
            if len(oos) < 2:
                v = float((nll[oos[0]][a] - nll[oos[0]][ref]).mean())
                print(f"{a:<14}{names:<28}{ref:<10}{pct(v):>+8.2f}%"
                      f"{'n=1, no CI':>22}{'--':>9}{'--':>10}{1:>6}  "
                      f"single held-out checkpoint")
                stats_out[f"{a}|{ref}"] = {"n": 1, "pct": pct(v)}
                continue
            d = np.array([float((nll[m][a] - nll[m][ref]).mean()) for m in oos])
            r = paired(d)
            stats_out[f"{a}|{ref}"] = r
            print(f"{a:<14}{names:<28}{ref:<10}{r['pct']:>+8.2f}%"
                  f"{('[%+.2f, %+.2f]' % (r['lo'], r['hi'])):>22}"
                  f"{r['t']:>+9.2f}{r['p']:>10.3f}{r['n']:>6}  {verdict(r)}")
        print()
    for a in ("NF4", "NF4-sym", "MX-asym-NEAR0"):
        d = np.array([float((nll[m][a] - nll[m]["MXFP4"]).mean()) for m in MODELS])
        r = paired(d)
        stats_out[f"{a}|MXFP4"] = r
        print(f"{a:<14}{'all four (saw no checkpoint)':<28}{'MXFP4':<10}"
              f"{r['pct']:>+8.2f}%{('[%+.2f, %+.2f]' % (r['lo'], r['hi'])):>22}"
              f"{r['t']:>+9.2f}{r['p']:>10.3f}{r['n']:>6}  {verdict(r)}")

    # ---------------------------------------------------------------- 5 -----
    print("\n" + "=" * 104)
    print("5.  THE PROTOCOL COMPARISON, in the FORM yesterday's table used")
    print("=" * 104)
    flat_fit = [v for a in FITS for v in rows[a]]
    print(f"{'protocol':<48}{'held-out wins vs MXFP4':>24}{'worst':>10}{'mean':>10}")
    print(f"{'fit on one model, by KL (this campaign)':<48}"
          f"{f'{sum(1 for v in flat_fit if v < 0)} / {len(flat_fit)}':>24}"
          f"{max(flat_fit):>+9.2f}%{np.mean(flat_fit):>+9.2f}%")
    jk = rows["JOINT-KL"]
    print(f"{'fit on three models, by KL (JOINT-KL)':<48}"
          f"{f'{sum(1 for v in jk if v < 0)} / {len(jk)}':>24}"
          f"{max(jk):>+9.2f}%{np.mean(jk):>+9.2f}%")
    ko = rows["KL-opt"]
    print(f"{'fit on one model, by KL, Lloyd seed (KL-opt)':<48}"
          f"{f'{sum(1 for v in ko if v < 0)} / {len(ko)}':>24}"
          f"{max(ko):>+9.2f}%{np.mean(ko):>+9.2f}%")

    # the published SELECTION protocols, recomputed from campaignA_stats.json
    A = json.load(open(os.path.join(HERE, "campaignA_stats.json")))
    p = A["ppl_vs_mxfp4_pct"]
    sel1 = [p[m][A["single_model_kl_pick"][s]]
            for s in MODELS for m in MODELS if m != s]
    sel3 = [p[h][A["rotation"][h]["winner"]] for h in MODELS]
    selp = [v for s in MODELS for v in A["single_model_protocol"][s]["held_out_pct"]]
    for tag, v in (("select among 10, one model, by KL", sel1),
                   ("select among 10, three models, by KL", sel3),
                   ("select among 10, one model, by perplexity", selp)):
        print(f"{tag:<48}{f'{sum(1 for x in v if x < 0)} / {len(v)}':>24}"
              f"{max(v):>+9.2f}%{np.mean(v):>+9.2f}%")
    print("\nThe last three rows are PLACEMENT_AND_ASYMMETRY_2026-08-12's, "
          "recomputed here from campaignA_stats.json.")

    # ---------------------------------------------------------------- 6 -----
    print("\n" + "=" * 104)
    print("6.  HEAD TO HEAD ON THE ONE CHECKPOINT JOINT-KL NEVER SAW (OPT-125M)")
    print("=" * 104)
    print(f"{'book':<16}{'fit set':<34}{'vs MXFP4 on OPT':>18}"
          f"{'vs JOINT-KL on OPT':>21}")
    for a in ["JOINT-KL"] + [f"FIT-{m}" for m in MODELS if m != "opt"] + \
             ["KL-opt", "NF4", "MX-asym-NEAR0"]:
        s = "+".join(FITTED_ON[a]) or "none (saw no checkpoint)"
        v1 = pct(float((nll["opt"][a] - nll["opt"]["MXFP4"]).mean()))
        v2 = pct(float((nll["opt"][a] - nll["opt"]["JOINT-KL"]).mean()))
        print(f"{a:<16}{s:<34}{v1:>+17.2f}%{v2:>+20.2f}%")

    # ---------------------------------------------------------------- 7 -----
    print("\n" + "=" * 104)
    print("7.  IN-SAMPLE MINUS HELD-OUT: how much of each fit is fit")
    print("=" * 104)
    print(f"{'book':<14}{'in-sample % vs MXFP4':>22}{'held-out mean %':>18}"
          f"{'collapse (pp)':>16}")
    for a in FITS + ["JOINT-KL", "KL-opt"]:
        ins = [pct(float((nll[m][a] - nll[m]["MXFP4"]).mean()))
               for m in FITTED_ON[a]]
        print(f"{a:<14}{np.mean(ins):>+21.2f}%{np.mean(rows[a]):>+17.2f}%"
              f"{np.mean(rows[a]) - np.mean(ins):>+15.2f}")

    # ---------------------------------------------------------------- 8 -----
    print("\n" + "=" * 104)
    print("8.  DO THE FOUR FITS AGREE?  (the fitting analogue of "
          "'three distinct winners in four rotations')")
    print("=" * 104)
    L = np.array([fit[m]["fitted"] for m in MODELS])
    print(f"{'interior level':<16}" + "".join(f"{'FIT-' + m:>14}" for m in MODELS)
          + f"{'MXFP4':>10}{'spread':>10}{'/ MXFP4 gap':>13}")
    gaps = [mx[i + 1] - mx[i] for i in range(7)]
    for i in range(1, 7):
        sp = float(L[:, i].max() - L[:, i].min())
        loc = min(gaps[i - 1], gaps[i])
        print(f"{'x' + str(i):<16}" + "".join(f"{L[j, i]:>14.5f}"
                                              for j in range(4))
              + f"{mx[i]:>10.5f}{sp:>10.5f}{sp / loc:>12.2f}x")
    print(f"\nmax over coordinates of (spread between the four fits) = "
          f"{float(np.max(L[:, 1:7].max(0) - L[:, 1:7].min(0))):.5f}; "
          f"the smallest MXFP4 rung gap is {min(gaps):.5f}.")

    json.dump({"models": MODELS, "fitted_on": FITTED_ON,
               "levels": {f"FIT-{m}": fit[m]["fitted"] for m in MODELS},
               "fit_runs": {f"FIT-{m}": min(fit[m]["runs"], key=lambda r: r["kl"])
                            for m in MODELS},
               "kl_mxfp4": {m: fit[m]["kl_mxfp4"] for m in MODELS},
               "ppl": ppl,
               "pct_vs_mxfp4": {a: {m: pct(float((nll[m][a] - nll[m]["MXFP4"]).mean()))
                                    for m in MODELS}
                                for a in FITS + REFS},
               "held_out_pct_vs_mxfp4": rows,
               "model_level": stats_out,
               "protocols": {"fit_one_model_kl": flat_fit,
                             "fit_three_models_kl": jk,
                             "fit_one_model_kl_lloyd_seed": ko,
                             "select_one_model_kl": sel1,
                             "select_three_models_kl": sel3,
                             "select_one_model_ppl": selp}},
              open(os.path.join(HERE, "onefit_stats.json"), "w"), indent=1)
    print("\nwrote onefit_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
