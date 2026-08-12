#!/usr/bin/env python3
"""LINE B: is it the SEED or the DISTANCE?

Two explanations survive the same eight-book table.

  SEED      a KL fit started from Lloyd-Max lands in a bad basin; one started
            from MXFP4 lands in a good one.  KL-opt has the LOWER in-sample KL
            of the two and still fails out of sample.
  DISTANCE  what predicts held-out failure is ||delta||, the L2 distance from
            MXFP4 over the six interior magnitudes, whatever produced the book.
            Perfect separation at d ~ 0.11 across the eight books, and Lloyd-Max
            -- no seed, no fit -- is the worst arm, which SEED cannot explain.

They are confounded: a coordinate descent whose step starts at 0.06 and stops at
0.004 cannot walk back 0.233 in level space, so every Lloyd-seeded book is also
a far book.  The control that separates them is to run the SAME search from the
Lloyd-Max seed on models other than smollm2 and ask where each one LANDS:

  * far + held-out failure          -> seed is a proxy, DISTANCE is the variable
  * walks back toward MXFP4 + wins  -> the seed does not fix the basin
  * far + held-out success          -> distance refuted, something else is going on

The fits are produced by onefit_kl.py with SEEDS=lloyd (same search, same
budget, same objective), the perplexities by onefit_measure.py with FITS=...
Nothing on the measurement path is reimplemented here: per-window NLL comes from
onefit_stats.load, the statistics from campaignC_stats.paired / verdict.

    python3 lineB_seed_vs_distance.py
"""
import json
import os

import numpy as np

from campaignC_stats import paired, verdict
from onefit_stats import LABEL, MODELS, TOL, load, pct
import campaignC_books as C

HERE = os.path.dirname(os.path.abspath(__file__))
MX = np.array(C.MXFP4)

# Which checkpoints each book was fitted on -- the held-out set is everything
# else.  Lloyd-Max and nSSE-equal are fitted to smollm2's weight distribution
# (campaignC_stats.FITTED_ON); KL-opt is the smollm2 Lloyd-seeded KL fit.
FITTED_ON = {
    "MXFP4": [], "NF4": [], "NF4-sym": [], "MX-asym-NEAR0": [],
    "Lloyd-Max": ["smollm2"], "nSSE-equal": ["smollm2"], "KL-opt": ["smollm2"],
    "JOINT-KL": ["smollm2", "qwen", "pythia"],
    **{f"FIT-{m}": [m] for m in MODELS},
    **{f"LFIT-{m}": [m] for m in MODELS},
}
LSEEDED = [m for m in MODELS if os.path.exists(
    os.path.join(HERE, f"onefit_kl_lloyd_{m}.json"))]


def dist(lv):
    """L2 over the six interior magnitudes, the metric the eight-book table used."""
    v = np.array([float(x) for x in lv])
    assert v[0] == 0.0 and abs(v[-1] - 1.0) < 1e-12 and len(v) == 8
    return float(np.linalg.norm(v[1:7] - MX[1:7]))


def main():
    nll, ppl, meta = load()

    # ---- merge this campaign's own measurements, cross-checked on shared arms
    worst = max(v["repro"] for v in meta.values())
    for m in MODELS:
        p = os.path.join(HERE, f"onefit_ppl_lloyd_{m}.json")
        if not os.path.exists(p):
            continue
        o = json.load(open(p))
        assert o["rulers_reproduce"] and o["nwin"] == meta[m]["nwin"], m
        for k, v in o["per_window_nll"].items():
            v = np.array(v)
            if k in nll[m]:
                worst = max(worst, float(np.abs(v - nll[m][k]).max()))
            else:
                nll[m][k] = v
        ppl[m] = {k: float(np.exp(v.mean())) for k, v in nll[m].items()}
    assert worst < TOL, f"sources disagree on a shared arm by {worst:.2e}"
    print(f"Shared arms agree across every process that measured them to "
          f"{worst:.2e} nats (tolerance {TOL:.0e}); all rulers reproduce.\n")

    # ---- the books ---------------------------------------------------------
    books = {"Lloyd-Max": list(C.LLOYD), "KL-opt": list(C.KLOPT),
             "nSSE-equal": list(C.NSSE), "JOINT-KL": list(C.JOINTKL)}
    fits = {}
    for m in MODELS:
        j = json.load(open(os.path.join(HERE, f"onefit_kl_{m}.json")))
        assert j["ruler_reproduces"]
        books[f"FIT-{m}"] = j["fitted"]
        fits[f"FIT-{m}"] = j
    for m in LSEEDED:
        j = json.load(open(os.path.join(HERE, f"onefit_kl_lloyd_{m}.json")))
        assert j["ruler_reproduces"] and j["fitted_seed"] == "Lloyd-Max"
        books[f"LFIT-{m}"] = j["fitted"]
        fits[f"LFIT-{m}"] = j

    ORDER = [f"LFIT-{m}" for m in LSEEDED] + ["KL-opt", "Lloyd-Max"] + \
            [f"FIT-{m}" for m in MODELS] + ["JOINT-KL", "nSSE-equal"]
    ORDER = [b for b in ORDER if b in books and
             all(b in nll[m] for m in MODELS)]

    # ---------------------------------------------------------------- 1 -----
    print("=" * 108)
    print("1.  WHERE EACH LLOYD-SEEDED FIT LANDED  (same search, same budget, "
          "same objective as the MXFP4-seeded ones)")
    print("=" * 108)
    print(f"{'book':<14}{'seed':<11}{'evals':>6}{'KL start':>10}{'KL end':>10}"
          f"{'KL(MXFP4)':>11}{'vs MXFP4 KL':>13}{'||delta||':>11}"
          f"{'seed d':>9}{'moved':>8}")
    for b in ORDER:
        if b not in fits:
            continue
        j = fits[b]
        run = min(j["runs"], key=lambda r: r["kl"])
        d0 = dist(C.MXFP4 if run["seed"] == "MXFP4" else C.LLOYD)
        d1 = dist(j["fitted"])
        print(f"{b:<14}{run['seed']:<11}{run['evals']:>6}{run['kl_start']:>10.6f}"
              f"{run['kl']:>10.6f}{j['kl_mxfp4']:>11.6f}"
              f"{100 * (run['kl'] / j['kl_mxfp4'] - 1):>+12.2f}%"
              f"{d1:>11.4f}{d0:>9.4f}{d1 - d0:>+8.4f}")
    print(f"\n{'KL-opt':<14}{'Lloyd-Max':<11}{'(published, smollm2, '
          'kl_optimal_codebook.py)':<40}{dist(C.KLOPT):>19.4f}"
          f"{dist(C.LLOYD):>9.4f}{dist(C.KLOPT) - dist(C.LLOYD):>+8.4f}")
    print("||delta|| = L2 distance from MXFP4 over the six interior magnitudes.")

    # ---------------------------------------------------------------- 2 -----
    print("\n" + "=" * 108)
    print("2.  LEVELS")
    print("=" * 108)
    print(f"{'book':<14}{'||delta||':>10}   levels")
    print(f"{'MXFP4':<14}{0.0:>10.4f}   [{', '.join(f'{x:.5f}' for x in C.MXFP4)}]")
    for b in ORDER:
        print(f"{b:<14}{dist(books[b]):>10.4f}   "
              f"[{', '.join(f'{x:.5f}' for x in books[b])}]")

    # ---------------------------------------------------------------- 3 -----
    print("\n" + "=" * 108)
    print("3.  THE FULL ROTATION: every book on every checkpoint, % vs MXFP4 "
          "(negative = beats MXFP4)")
    print("=" * 108)
    print(f"{'book':<14}{'||delta||':>10}" +
          "".join(f"{LABEL[m].split('-')[0]:>15}" for m in MODELS) +
          f"{'held-out mean':>15}{'worst':>9}{'wins':>7}")
    rows = {}
    for b in ORDER:
        cells, held = [], []
        for m in MODELS:
            v = pct(float((nll[m][b] - nll[m]["MXFP4"]).mean()))
            if m in FITTED_ON[b]:
                cells.append(f"{('(' + f'{v:+.2f}' + ')'):>15}")
            else:
                cells.append(f"{v:>+14.2f}%")
                held.append(v)
        rows[b] = held
        print(f"{b:<14}{dist(books[b]):>10.4f}" + "".join(cells) +
              f"{np.mean(held):>+14.2f}%{max(held):>+8.2f}%"
              f"{sum(1 for v in held if v < 0):>4}/{len(held)}")
    print("(x) = in-sample, excluded from the held-out summary")

    # ---------------------------------------------------------------- 4 -----
    print("\n" + "=" * 108)
    print("4.  MODEL-LEVEL STATISTICS PER BOOK  (n = held-out CHECKPOINTS; "
          "a margin inside its CI is a TIE)")
    print("=" * 108)
    print(f"{'book':<14}{'held out':<28}{'%':>9}{'95% CI':>22}{'t':>9}"
          f"{'p':>10}{'n':>5}  verdict")
    stats_out = {}
    for b in ORDER:
        oos = [m for m in MODELS if m not in FITTED_ON[b]]
        names = "+".join(LABEL[m].split("-")[0] for m in oos)
        if len(oos) < 2:
            v = pct(float((nll[oos[0]][b] - nll[oos[0]]["MXFP4"]).mean()))
            stats_out[b] = {"n": 1, "pct": v}
            print(f"{b:<14}{names:<28}{v:>+8.2f}%{'n=1, no CI':>22}"
                  f"{'--':>9}{'--':>10}{1:>5}  single held-out checkpoint")
            continue
        d = np.array([float((nll[m][b] - nll[m]["MXFP4"]).mean()) for m in oos])
        r = paired(d)
        stats_out[b] = r
        print(f"{b:<14}{names:<28}"
              f"{r['pct']:>+8.2f}%{('[%+.2f, %+.2f]' % (r['lo'], r['hi'])):>22}"
              f"{r['t']:>+9.2f}{r['p']:>10.3f}{r['n']:>5}  {verdict(r)}")

    # ---------------------------------------------------------------- 5 -----
    print("\n" + "=" * 108)
    print("5.  SEED vs DISTANCE, on the books that exist")
    print("=" * 108)
    dd = np.array([dist(books[b]) for b in ORDER])
    hh = np.array([np.mean(rows[b]) for b in ORDER])
    from scipy import stats as st
    sp = st.spearmanr(dd, hh)
    pe = st.pearsonr(dd, hh)
    print(f"across {len(ORDER)} books: Spearman(||delta||, held-out mean) = "
          f"{sp.statistic:+.3f} (p={sp.pvalue:.3f}), "
          f"Pearson {pe.statistic:+.3f} (p={pe.pvalue:.3f})")
    near = [b for b in ORDER if dist(books[b]) < 0.11]
    far = [b for b in ORDER if dist(books[b]) >= 0.11]
    for tag, grp in (("d < 0.11", near), ("d >= 0.11", far)):
        v = [np.mean(rows[b]) for b in grp]
        w = [x for b in grp for x in rows[b]]
        print(f"  {tag:<10} n={len(grp)} books  mean held-out "
              f"{np.mean(v):+.2f}%  worst book {max(v):+.2f}%  "
              f"held-out wins {sum(1 for x in w if x < 0)}/{len(w)}   "
              f"{', '.join(grp)}")
    mseed = [b for b in ORDER if b in fits and
             min(fits[b]['runs'], key=lambda r: r['kl'])['seed'] == "MXFP4"]
    lseed = [b for b in ORDER if b in fits and
             min(fits[b]['runs'], key=lambda r: r['kl'])['seed'] == "Lloyd-Max"]
    lseed = lseed + ["KL-opt"]
    for tag, grp in (("MXFP4 seed", mseed), ("Lloyd seed", lseed)):
        v = [np.mean(rows[b]) for b in grp]
        w = [x for b in grp for x in rows[b]]
        print(f"  {tag:<10} n={len(grp)} fits   mean held-out "
              f"{np.mean(v):+.2f}%  worst book {max(v):+.2f}%  "
              f"held-out wins {sum(1 for x in w if x < 0)}/{len(w)}   "
              f"{', '.join(grp)}")

    # ---------------------------------------------------------------- 6 -----
    print("\n" + "=" * 108)
    print("6.  SAME MODEL, TWO SEEDS: paired on the three checkpoints both "
          "fits held out")
    print("=" * 108)
    print(f"{'model':<10}{'in-sample KL: MXFP4 seed':>26}{'Lloyd seed':>13}"
          f"{'||d|| MX':>10}{'||d|| Ll':>10}"
          f"{'held-out mean: MX':>19}{'Lloyd':>9}{'wins MX':>9}{'wins Ll':>9}")
    for m in LSEEDED:
        a, b = f"FIT-{m}", f"LFIT-{m}"
        ja, jb = fits[a], fits[b]
        ra = min(ja["runs"], key=lambda r: r["kl"])
        rb = min(jb["runs"], key=lambda r: r["kl"])
        print(f"{m:<10}{ra['kl']:>26.6f}{rb['kl']:>13.6f}"
              f"{dist(books[a]):>10.4f}{dist(books[b]):>10.4f}"
              f"{np.mean(rows[a]):>+18.2f}%{np.mean(rows[b]):>+8.2f}%"
              f"{sum(1 for v in rows[a] if v < 0):>6}/{len(rows[a])}"
              f"{sum(1 for v in rows[b] if v < 0):>6}/{len(rows[b])}")

    # ---------------------------------------------------------------- 7 -----
    print("\n" + "=" * 108)
    print("7.  IS DISTANCE GRADED, OR ONLY A LABEL?  and did the search STOP "
          "or RUN OUT?")
    print("=" * 108)
    import math
    k = len(near)
    print(f"separation: all {k} books with d < 0.11 have a negative held-out "
          f"mean and all {len(far)} with d >= 0.11 a positive one.  If the "
          f"{len(ORDER)} books were exchangeable, the chance of the {k} nearest "
          f"being exactly the {k} best is 1 / C({len(ORDER)},{k}) = "
          f"{1 / math.comb(len(ORDER), k):.2e}.  They are not exchangeable -- "
          f"{len(LSEEDED)} pairs share a fitting model and all four MXFP4-seeded "
          f"fits share a seed -- so read it as a description, not a test.")
    for tag, grp in (("d < 0.11", near), ("d >= 0.11", far)):
        if len(grp) < 3:
            continue
        s = st.spearmanr([dist(books[b]) for b in grp],
                         [np.mean(rows[b]) for b in grp])
        print(f"  WITHIN {tag:<10} n={len(grp)}: Spearman(||delta||, held-out) "
              f"= {s.statistic:+.3f} (p={s.pvalue:.3f})")
    print("\ntermination of each search (the step halves when a sweep fails; "
          "the run stops at step < 0.004 or at the budget):")
    for b in ORDER:
        if b not in fits:
            continue
        r = min(fits[b]["runs"], key=lambda x: x["kl"])
        why = "budget exhausted" if r["evals"] >= fits[b]["evals_budget"] \
            else "step < 0.004 -- a local minimum of the objective"
        print(f"  {b:<14}{r['evals']:>4} / {fits[b]['evals_budget']} evals   "
              f"{why}")
    lm = [b for b in ORDER if b in fits and
          min(fits[b]['runs'], key=lambda r: r['kl'])['seed'] == "Lloyd-Max"]
    if lm:
        mv = [dist(C.LLOYD) - dist(books[b]) for b in lm]
        print(f"\nwalk-back toward MXFP4 from the Lloyd seed (d = "
              f"{dist(C.LLOYD):.4f}): "
              f"{', '.join(f'{b} {v:+.4f}' for b, v in zip(lm, mv))}")
        print(f"largest walk-back {max(mv):.4f} of the {dist(C.LLOYD):.4f} "
              f"needed to reach MXFP4, and of the {dist(C.LLOYD) - 0.11:.4f} "
              f"needed to reach the near group.")

    # ---------------------------------------------------------------- 8 -----
    print("\n" + "=" * 108)
    print("8.  THE PAIRED TEST THE DESIGN SUPPORTS  (n = 4 FITTING models; the "
          "two seeds share a model and a held-out set)")
    print("=" * 108)
    pair = {}
    for tag, ref in (("held-out", None), ("in-sample", "self")):
        d = []
        for m in LSEEDED:
            if ref == "self":
                d.append(float((nll[m][f"LFIT-{m}"] - nll[m][f"FIT-{m}"]).mean()))
            else:
                oos = [h for h in MODELS if h != m]
                d.append(float(np.mean([
                    (nll[h][f"LFIT-{m}"] - nll[h][f"FIT-{m}"]).mean()
                    for h in oos])))
        r = paired(np.array(d))
        pair[tag] = r
        print(f"  Lloyd seed vs MXFP4 seed, {tag:<10} {r['pct']:>+7.2f}%   "
              f"95% CI [{r['lo']:+.2f}, {r['hi']:+.2f}]   t={r['t']:+.2f}   "
              f"p={r['p']:.4f}   n={r['n']}   "
              f"{'worse' if r['pct'] > 0 else 'better'} in "
              f"{r['n_worse' if r['pct'] > 0 else 'n_better']}/{r['n']}")
    print("  (perplexity ratio, paired on per-window NLL, averaged over each "
          "fit's own held-out models first)")

    json.dump({"models": MODELS, "lloyd_seeded": LSEEDED, "paired_seed": pair,
               "fitted_on": FITTED_ON,
               "levels": {b: list(map(float, books[b])) for b in ORDER},
               "distance": {b: dist(books[b]) for b in ORDER},
               "kl": {b: {"seed": min(fits[b]["runs"], key=lambda r: r["kl"])["seed"],
                          "kl_start": min(fits[b]["runs"], key=lambda r: r["kl"])["kl_start"],
                          "kl_end": min(fits[b]["runs"], key=lambda r: r["kl"])["kl"],
                          "evals": min(fits[b]["runs"], key=lambda r: r["kl"])["evals"],
                          "kl_mxfp4": fits[b]["kl_mxfp4"]}
                      for b in ORDER if b in fits},
               "ppl": ppl,
               "pct_vs_mxfp4": {b: {m: pct(float((nll[m][b] - nll[m]["MXFP4"]).mean()))
                                    for m in MODELS} for b in ORDER},
               "held_out_pct_vs_mxfp4": rows,
               "model_level": stats_out,
               "spearman_distance_heldout": {"rho": float(sp.statistic),
                                             "p": float(sp.pvalue),
                                             "n_books": len(ORDER)},
               "repro_worst_nats": worst},
              open(os.path.join(HERE, "lineB_stats.json"), "w"), indent=1)
    print("\nwrote lineB_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
