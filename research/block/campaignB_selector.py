#!/usr/bin/env python3
"""Campaign B: when can the KL selector be trusted?

The fact under investigation.  `PLACEMENT_AND_ASYMMETRY_2026-08-12.md` reports
that the joint-KL score ranks the ten arms -- nine placements plus the clipping
arm MX-asym-TOP -- well on OPT (rho = +0.927) and Qwen (+0.758) and not at all
on SmolLM2 (+0.188) and Pythia (-0.030), and calls
this "same objective, same procedure, same corpus".  It is not the same
procedure: the joint score for held-out model h is a sum of KL over a DIFFERENT
set of three donor checkpoints for each h.  Four numbers, four objectives.

So the first thing this measures is the objective on its own checkpoint --
rho(KL on model m, perplexity margin on model m) -- which IS the same procedure
four times.  Everything else is an attempt to kill that result.

The four candidate explanations, and how each is tested:

  1 CALIBRATION SIZE.  Two windows may simply be too few.  Tested by measuring
    per-window KL for sixteen windows on every model and every placement; since
    each window is exactly SEQLEN tokens, the KLWIN = k objective is the mean of
    the first k entries, so one run gives k = 2, 4, 8, 16 as PREFIX MEANS with
    no re-quantisation and no re-forwarding.  The k = 2 prefix is asserted
    against the published campaignA_kl_<model>.json score, which gates the whole
    sweep on reproducing the number it is supposed to explain.

  2 SPREAD OF THE JUDGE.  If the ten arms are nearly tied on a model, no
    selector can rank them there.  Measured as the SD of the ten held-out
    margins over the window-level noise SE of a pairwise margin difference.

  3 KL-PERPLEXITY COUPLING.  Measured as rho(KL on the calibration windows,
    perplexity on THOSE SAME windows) -- if the objective decouples from the
    judge before generalisation enters, it fails at k = 2 on the same text.

  4 WEIGHT DISTRIBUTION.  The models' own signed-bin mass fingerprints
    (campaignD_pred_<model>.json), and whether fingerprint similarity explains
    which models' placement rankings agree.

STATISTICS.  Rank correlations over the ten ARMS are WITHIN-model claims, and
the replicate unit of a rho is the BOOK: n = 10 books, not 10 windows and not
10 models.  Each rho carries a window-level bootstrap CI, which says how well
each book's margin is MEASURED on this text -- NOT how it would transfer to a
fifth checkpoint, which is a different question and is answered at n = 4 below.
The windows are resampled jointly for the three 40-window models because they
read the same text, and separately for Qwen, which has 20.  Any statement
comparing protocols across checkpoints is a CROSS-model claim with n = 4 and is
reported as the tie it is.

    python3 campaignB_selector.py
"""
import json
import os
import sys

import numpy as np
from scipy import stats

import campaignA_books as A
from campaignC_stats import paired, verdict

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
LABEL = {"smollm2": "SmolLM2-135M", "qwen": "Qwen2.5-0.5B",
         "pythia": "Pythia-160M", "opt": "OPT-125M"}
# THE SET THE RANK CORRELATIONS RANGE OVER, named, because it changed once
# already and took this script down with it.
#
# Every rho below was published over TEN arms: the nine kind="sig" placements
# plus the kind="clip" arm MX-asym-TOP. On 2026-08-12 the clipping
# reclassification (CLIPPING_ARM_CORRECTION) removed TOP from
# `campaignA_books.candidates()`, so `CANDS` silently became nine -- and this
# file kept saying "the ten placements", kept `range(10)`, and kept
# PUBLISHED_JOINT_RHO. Its own gate then failed with
# "smollm2: +0.4333 != published +0.188", which reads like a measurement that
# stopped reproducing and was in fact a SET that stopped matching its name.
#
# So the ranking set is spelled out here rather than inherited. It is still the
# ten, because that is what the published numbers describe and what the prose
# below interprets; section 1b already reports every rho with TOP dropped, which
# is the sensitivity this reclassification calls for. What is fixed is that the
# set is now named, counted, and gated -- not implied by an import.
PLACEMENTS = [n for n, k, lv in A.candidates()]
RANKSET = PLACEMENTS + [n for n, k, lv in A.clipping_arms()]
CANDS = RANKSET
NCAND = len(RANKSET)
KS = [2, 4, 8, 16]
B = 4000
SEED = 20260812

# the four numbers this campaign has to reproduce before it may explain them
PUBLISHED_JOINT_RHO = {"opt": +0.927, "qwen": +0.758,
                       "smollm2": +0.188, "pythia": -0.030}


def S(n):
    return n.replace("MX-asym-", "")


def rho(x, y):
    return float(stats.spearmanr(x, y)[0])


def load():
    """kl2 = published 2-window KL; klw = 16 per-window KL where measured;
    nll = per-window NLL of every arm; pred = weight-space fingerprints."""
    kl2, klw, nll, pred, kl_gate = {}, {}, {}, {}, {}
    for m in MODELS:
        j = json.load(open(os.path.join(HERE, f"campaignA_kl_{m}.json")))
        assert j["ruler_reproduces"] and j["klwin"] == 2, m
        kl2[m] = j["kl"]
        b = json.load(open(os.path.join(HERE, f"campaignB_{m}.json")))
        assert b["rulers_reproduce"], m
        nll[m] = {k: np.array(v) for k, v in b["per_window_nll"].items()}
        e = json.load(open(os.path.join(HERE, f"campaignA_ppl_{m}.json")))
        for k, v in e["per_window_nll"].items():
            if k in nll[m]:
                d = float(np.abs(np.array(v) - nll[m][k]).max())
                assert d < 1e-5, f"{m}/{k}: ppl pass disagrees {d:.2e}"
            else:
                nll[m][k] = np.array(v)
        pred[m] = json.load(open(os.path.join(HERE, f"campaignD_pred_{m}.json")))
        p = ([q for q in (os.path.join(HERE, f"campaignB_sel_kl_{m}_{w}w.json")
                          for w in (16, 8)) if os.path.exists(q)] or [None])[0]
        if p:
            s = json.load(open(p))
            assert s["ruler_reproduces"] and s["klwin"] in KS, m
            klw[m] = {k: np.array(v) for k, v in s["kl_per_window"].items()}
            assert abs(float(np.mean(s["self_kl_per_window"]))) < 1e-9, m
            # GATE: the 2-window prefix must BE the published objective.  The
            # tolerance is not a constant -- it is set by what the ranking has
            # to resolve.  Reproduction error must be at least 1000x below the
            # SMALLEST gap between two books' published KL, since that gap is
            # the finest distinction any Spearman here depends on.  On three
            # models the error is 1e-16 (exact); on SmolLM2 it is 4.6e-08,
            # because that checkpoint's forward is not bit-reproducible across
            # thread counts -- the same 4.8e-07 nats of NLL jitter campaign A
            # already recorded against campaign B.
            err = max(abs(float(klw[m][c][:2].mean()) - kl2[m][c]) for c in CANDS)
            v = sorted(kl2[m][c] for c in CANDS)
            gap = min(v[i + 1] - v[i] for i in range(len(v) - 1))
            assert err * 1000 < gap, \
                f"{m}: prefix error {err:.2e} not << smallest KL gap {gap:.2e}"
            kl_gate[m] = {"err": err, "smallest_gap": gap, "ratio": gap / max(err, 1e-18)}
    return kl2, klw, nll, pred, kl_gate


def main():
    kl2, klw, nll, pred, kl_gate = load()
    marg = {m: np.array([nll[m][b] - nll[m]["MXFP4"] for b in CANDS])
            for m in MODELS}                       # 10 x NWIN, log-ratio
    pt = {m: marg[m].mean(axis=1) for m in MODELS}
    nwin = {m: marg[m].shape[1] for m in MODELS}

    rng = np.random.default_rng(SEED)
    n40 = nwin["smollm2"]
    assert nwin["pythia"] == nwin["opt"] == n40 == 40 and nwin["qwen"] == 20
    boot = {m: [] for m in MODELS}
    for _ in range(B):
        i40, i20 = rng.integers(0, n40, n40), rng.integers(0, 20, 20)
        for m in MODELS:
            boot[m].append(marg[m][:, i20 if m == "qwen" else i40].mean(axis=1))
    boot = {m: np.array(v) for m, v in boot.items()}

    def ci(x, m):
        v = np.array([rho(x, boot[m][i]) for i in range(B)])
        return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), \
            float((v > 0).mean())

    out = {"models": MODELS, "candidates": CANDS, "bootstrap": B, "seed": SEED}

    print("=" * 100)
    print("GATE.  Reproduce the four joint-KL Spearmans this campaign exists to explain")
    print("=" * 100)
    print(f"{'model':<15}{'joint-KL rho':>14}{'published':>12}{'':>6}")
    for h in MODELS:
        fit = [m for m in MODELS if m != h]
        x = [sum(kl2[m][b] for m in fit) for b in CANDS]
        r = rho(x, pt[h])
        ok = abs(r - PUBLISHED_JOINT_RHO[h]) < 5e-4
        print(f"{LABEL[h]:<15}{r:>+14.3f}{PUBLISHED_JOINT_RHO[h]:>+12.3f}"
              f"{'  OK' if ok else '  MISS':>6}")
        assert ok, f"{h}: {r:+.4f} != published {PUBLISHED_JOINT_RHO[h]:+.3f}"
    print("all four reproduce.\n")

    print("=" * 100)
    print(f"1.  THE OBJECTIVE ON ITS OWN CHECKPOINT vs THE JOINT SUM  "
          f"(n = {NCAND} books: {len(PLACEMENTS)} placements + "
          f"{NCAND - len(PLACEMENTS)} clipping arm)")
    print("    own-KL   = rho( KL(fp32||book) on model m , perplexity margin on model m )")
    print("    joint-KL = rho( sum of KL over the OTHER three checkpoints , same margin )")
    print("=" * 100)
    print(f"{'model':<15}{'own-KL rho':>11}{'95% CI':>18}{'p':>9}   "
          f"{'joint-KL rho':>13}{'95% CI':>18}{'P(>0)':>8}")
    own = {}
    for m in MODELS:
        x = [kl2[m][b] for b in CANDS]
        lo, hi, _ = ci(x, m)
        p = float(stats.spearmanr(x, pt[m])[1])
        fit = [q for q in MODELS if q != m]
        xj = [sum(kl2[q][b] for q in fit) for b in CANDS]
        jlo, jhi, jpos = ci(xj, m)
        own[m] = {"own_rho": rho(x, pt[m]), "own_ci": [lo, hi], "own_p": p,
                  "joint_rho": rho(xj, pt[m]), "joint_ci": [jlo, jhi],
                  "joint_p_gt0": jpos}
        print(f"{LABEL[m]:<15}{rho(x, pt[m]):>+11.3f}"
              f"{('[%+.2f, %+.2f]' % (lo, hi)):>18}{p:>9.4f}   "
              f"{rho(xj, pt[m]):>+13.3f}{('[%+.2f, %+.2f]' % (jlo, jhi)):>18}"
              f"{jpos:>8.3f}")
    out["own_vs_joint"] = own
    print("\nThe two models where the joint score is noise are the two where the objective on"
          "\nits own checkpoint is STRONGEST.  The CIs do not overlap on either of them.")

    print("\n" + "=" * 100)
    print("1b. ROBUSTNESS: does the gap survive dropping the structurally odd arms?")
    print("    TOP is not an insertion -- it extends the ladder to 16/12, and the forced")
    print("    renormalisation moves every level and clips the negative extreme to -0.75.")
    print("=" * 100)
    SUBSETS = [(f"all {NCAND}", RANKSET),
               (f"without TOP ({len(PLACEMENTS)} placements)", PLACEMENTS),
               ("seven positive-gap insertions only",
                [c for c in CANDS if c.split("-")[-1]
                 in ("NEAR0", "G12", "G23", "G34", "MID2", "G68", "MID")])]
    print(f"{'candidate set':<36}{'n':>3}  " + "".join(
        f"{LABEL[m].split('-')[0]:>24}" for m in MODELS))
    rob = {}
    for tag, keep in SUBSETS:
        cells = ""
        rob[tag] = {}
        for m in MODELS:
            y = [float(marg[m][CANDS.index(b)].mean()) for b in keep]
            o = rho([kl2[m][b] for b in keep], y)
            fit = [q for q in MODELS if q != m]
            j = rho([sum(kl2[q][b] for q in fit) for b in keep], y)
            rob[tag][m] = {"own": o, "joint": j}
            cells += f"{('own %+.2f  joint %+.2f' % (o, j)):>24}"
        print(f"{tag:<36}{len(keep):>3}  {cells}")
    print("\nDropping TOP roughly halves the gap on both failing models (+0.19 -> +0.43 on")
    print("SmolLM2, -0.03 -> +0.33 on Pythia) without closing it.  Own-model KL never falls")
    print("below +0.62 in any subset on any model; the joint score ranges -0.03 to +0.93.")
    print("The honest effect size therefore depends on the candidate set; the SIGN and the")
    print("ordering own >= joint on the failing models do not.")
    out["robustness_subsets"] = rob

    print("\n" + "=" * 100)
    print("2.  TRANSFER MATRIX: rho( KL measured on ROW model , perplexity margin on COLUMN )")
    print("=" * 100)
    print(f"{'KL from':<15}" + "".join(f"{LABEL[m].split('-')[0]:>14}" for m in MODELS))
    tm = {}
    for a in MODELS:
        xs = [kl2[a][b] for b in CANDS]
        tm[a] = {m: rho(xs, pt[m]) for m in MODELS}
        print(f"{LABEL[a]:<15}" + "".join(
            f"{('*' if m == a else ' ')}{tm[a][m]:>+13.3f}" for m in MODELS))
    print("  (* = own model)")
    out["transfer_matrix"] = tm

    print("\n" + "=" * 100)
    print("3.  WHO AGREES WITH WHOM: rho between two models' perplexity-margin rankings")
    print("=" * 100)
    print(f"{'pair':<26}{'ppl-rank agree':>15}{'95% CI':>18}{'P(>0)':>8}"
          f"{'KL-rank agree':>15}")
    pairs = [(MODELS[i], MODELS[j]) for i in range(4) for j in range(i + 1, 4)]
    agree = {}
    for a, b in pairs:
        v = np.array([rho(boot[a][i], boot[b][i]) for i in range(B)])
        kg = rho([kl2[a][c] for c in CANDS], [kl2[b][c] for c in CANDS])
        agree[f"{a}|{b}"] = {"ppl": rho(pt[a], pt[b]), "kl": kg,
                             "ci": [float(np.percentile(v, 2.5)),
                                    float(np.percentile(v, 97.5))],
                             "p_gt0": float((v > 0).mean())}
        print(f"{a + ' vs ' + b:<26}{rho(pt[a], pt[b]):>+15.3f}"
              f"{('[%+.2f, %+.2f]' % (np.percentile(v, 2.5), np.percentile(v, 97.5))):>18}"
              f"{(v > 0).mean():>8.3f}{kg:>+15.3f}")
    ap = [agree[f'{a}|{b}']["ppl"] for a, b in pairs]
    ak = [agree[f'{a}|{b}']["kl"] for a, b in pairs]
    print(f"\nrho( ppl-rank agreement , KL-rank agreement ) over the six pairs = "
          f"{rho(ap, ak):+.3f}")
    print("The objective's cross-model disagreement TRACKS the target's.  KL is not")
    print("failing to transfer; it is correctly reporting that these checkpoints want")
    print("different placements.")
    out["pairwise_agreement"] = agree
    out["agreement_ppl_vs_kl_rho"] = rho(ap, ak)

    print("\n" + "=" * 100)
    print("4.  DONOR-SUBSET CONTROL: hold the TARGET fixed, vary only whose KL is summed")
    print("=" * 100)
    import itertools
    print(f"{'held out':<15}{'own':>8}   subsets of the three donors, best -> worst")
    subs = {}
    for h in MODELS:
        fit = [m for m in MODELS if m != h]
        rows = []
        for r in (1, 2, 3):
            for c in itertools.combinations(fit, r):
                x = [sum(kl2[q][b] for q in c) for b in CANDS]
                rows.append(("+".join(q[:2] for q in c), rho(x, pt[h])))
        rows.sort(key=lambda t: -t[1])
        subs[h] = dict(rows)
        print(f"{LABEL[h]:<15}{own[h]['own_rho']:>+8.3f}   " +
              "  ".join(f"{n}={v:+.2f}" for n, v in rows))
    print("\nEvery number in a row is the same objective judged against the same target;")
    print("only the donor checkpoint changes.  The spread WITHIN a row is the whole effect.")
    out["donor_subsets"] = subs

    print("\n" + "=" * 100)
    print("EXPLANATION 2.  SPREAD OF THE JUDGE -- is the target rankable at all?")
    print("=" * 100)
    print(f"{'model':<15}{'spread (pp)':>12}{'SD (pp)':>10}{'noise SE (pp)':>15}"
          f"{'SD/SE':>8}{'joint rho':>11}")
    sp = {}
    for m in MODELS:
        v = 100 * (np.exp(pt[m]) - 1)
        ses = [100 * (marg[m][i] - marg[m][j]).std(ddof=1) / np.sqrt(nwin[m])
               for i in range(NCAND) for j in range(i + 1, NCAND)]
        se = float(np.median(ses))
        sp[m] = {"spread_pp": float(v.max() - v.min()), "sd_pp": float(v.std(ddof=1)),
                 "noise_se_pp": se, "sd_over_se": float(v.std(ddof=1) / se)}
        print(f"{LABEL[m]:<15}{sp[m]['spread_pp']:>12.3f}{sp[m]['sd_pp']:>10.3f}"
              f"{se:>15.4f}{sp[m]['sd_over_se']:>8.2f}"
              f"{own[m]['joint_rho']:>+11.3f}")
    r2 = rho([sp[m]["sd_over_se"] for m in MODELS],
             [own[m]["joint_rho"] for m in MODELS])
    print(f"\nrho( separability , joint-KL rho ) over the four models = {r2:+.3f}  (n = 4, "
          "the conjecture's direction, and not significant at this n)")
    print("The conjecture is refuted by a CONTROL, not by this correlation: on both failing")
    print("models the SAME held-out perplexity vector is ranked at +0.988 and +0.806 by that")
    print("model's own KL.  The target is demonstrably rankable, so a property of the target")
    print("cannot explain a failure that vanishes when only the donor checkpoint changes.")
    print("Qwen, where the joint selector works, is also the LEAST separable of the four.")
    out["spread"] = sp
    out["spread_vs_joint_rho"] = r2

    print("\n" + "=" * 100)
    print("EXPLANATION 3.  KL-PERPLEXITY COUPLING ON THE SAME TEXT")
    print("=" * 100)
    print(f"{'model':<15}{'rho(KL, ppl on the 2 calib windows)':>38}"
          f"{'rho(KL, ppl on all windows)':>30}")
    cp = {}
    for m in MODELS:
        x = [kl2[m][b] for b in CANDS]
        yc = [float((nll[m][b][:2] - nll[m]["MXFP4"][:2]).mean()) for b in CANDS]
        cp[m] = {"calib": rho(x, yc), "full": rho(x, pt[m])}
        print(f"{LABEL[m]:<15}{rho(x, yc):>+38.3f}{rho(x, pt[m]):>+30.3f}")
    print("\nThe two 'failing' models are the two with the HIGHEST coupling. The objective")
    print("does not decouple from perplexity on the calibration text.")
    out["coupling"] = cp

    print("\n" + "=" * 100)
    print("EXPLANATION 4.  WEIGHT DISTRIBUTION -- does fingerprint similarity explain agreement?")
    print("=" * 100)
    print(f"{'model':<15}{'zero-bin mass':>15}{'mass |bin|>=5':>15}{'own-KL rho':>12}"
          f"{'joint rho':>11}")
    for m in MODELS:
        bm = pred[m]["bin_mass"]
        print(f"{LABEL[m]:<15}{bm[7]:>15.5f}"
              f"{sum(bm[i] for i in range(15) if abs(i - 7) >= 5):>15.5f}"
              f"{own[m]['own_rho']:>+12.3f}{own[m]['joint_rho']:>+11.3f}")
    print(f"\n{'pair':<26}{'L1 bin-mass distance':>22}{'ppl-rank agreement':>20}")
    d1, ag = [], []
    for a, b in pairs:
        d = float(np.abs(np.array(pred[a]["bin_mass"])
                         - np.array(pred[b]["bin_mass"])).sum())
        d1.append(d)
        ag.append(agree[f"{a}|{b}"]["ppl"])
        print(f"{a + ' vs ' + b:<26}{d:>22.4f}{agree[f'{a}|{b}']['ppl']:>+20.3f}")
    # n = 6 is the number of PAIRS, which is not the number of independent
    # things: four models generate six pairs and every model appears in three of
    # them, so the six rows are not exchangeable and no p-value is quoted for
    # this rho or for the one two sections above. Both are read as descriptions
    # of the table printed beside them, and the conjecture is refuted by its
    # SIGN plus the named counterexample, not by this correlation.
    print(f"\nrho( fingerprint distance , agreement ) = {rho(d1, ag):+.3f}  "
          f"(6 pairs of 4 models -- not 6 independent units; no p). The")
    print("conjecture predicts NEGATIVE. The pair with the most similar weight distributions")
    print("(SmolLM2/Pythia) is the pair whose placement rankings agree LEAST.")
    out["fingerprint"] = {"l1_bin_mass": dict(zip([f"{a}|{b}" for a, b in pairs], d1)),
                          "rho_distance_vs_agreement": rho(d1, ag)}

    print("\n" + "=" * 100)
    print("EXPLANATION 1.  CALIBRATION SIZE -- the sweep")
    print("=" * 100)
    if len(klw) < len(MODELS):
        print(f"per-window KL measured on {sorted(klw)}; missing "
              f"{sorted(set(MODELS) - set(klw))} -- the joint sweep needs every donor.")
    print("SWEEP GATE: the k=2 prefix of the per-window run vs the published 2-window KL")
    for m in MODELS:
        if m in kl_gate:
            g = kl_gate[m]
            print(f"   {LABEL[m]:<15} worst error {g['err']:.2e} nats, smallest between-book"
                  f" gap {g['smallest_gap']:.2e}, ratio {g['ratio']:.3g}x")
    print()
    kmax = {m: len(next(iter(klw[m].values()))) for m in klw}
    kjoint = [k for k in KS if len(klw) == len(MODELS) and k <= min(kmax.values())]
    print(f"{'model':<15}" + "".join(f"{'own k=' + str(k):>10}" for k in KS)
          + "   " + "".join(f"{'joint k=' + str(k):>12}" for k in kjoint))
    sweep = {}
    for m in MODELS:
        if m not in klw:
            continue
        ks = [k for k in KS if k <= kmax[m]]
        row_own = [rho([float(klw[m][b][:k].mean()) for b in CANDS], pt[m]) for k in ks]
        cells = "".join(f"{v:>+10.3f}" for v in row_own) + "".join(
            f"{'--':>10}" for _ in KS[len(ks):])
        row_j = []
        fit = [q for q in MODELS if q != m]
        for k in kjoint:
            xj = [sum(float(klw[q][b][:k].mean()) for q in fit) for b in CANDS]
            row_j.append(rho(xj, pt[m]))
        if row_j:
            cells += "   " + "".join(f"{v:>+12.3f}" for v in row_j)
        sweep[m] = {"own": dict(zip(map(str, ks), row_own)),
                    "joint": dict(zip(map(str, kjoint), row_j))}
        print(f"{LABEL[m]:<15}{cells}")
    print("\nCalibration size is REAL but is not the split.  Own-model rho climbs with k on")
    print("Pythia (+0.81 -> +0.93) and OPT (+0.72 -> +0.83), and on Pythia the argmin-KL pick")
    print("moves to that model's true oracle at k >= 8.  But the joint columns do NOT climb")
    print("on either failing model -- SmolLM2 +0.19 -> +0.21 -> +0.03, Pythia -0.03 -> -0.14")
    print("-- and SmolLM2's own-model rho is already +0.988 at k = 2 and flat thereafter, so")
    print("on the worst-joint model there is no calibration deficit left for k to repair.")
    out["calibration_sweep"] = sweep
    out["kmax"] = kmax

    print("\n" + "=" * 100)
    print("WHAT EACH PROTOCOL DEPLOYS  (% vs MXFP4 on the model it is deployed on)")
    print("=" * 100)
    print(f"{'model':<15}{'own-KL':<9}{'%':>9}   {'joint-KL':<9}{'%':>9}   "
          f"{'oracle':<9}{'%':>9}{'regret':>10}")
    P = lambda m, b: 100 * (np.exp(float(marg[m][CANDS.index(b)].mean())) - 1)
    picks = {}
    for m in MODELS:
        a = min(CANDS, key=lambda b: kl2[m][b])
        fit = [q for q in MODELS if q != m]
        j = min(CANDS, key=lambda b: sum(kl2[q][b] for q in fit))
        o = CANDS[int(np.argmin(pt[m]))]
        picks[m] = {"own": a, "joint": j, "oracle": o, "own_pct": P(m, a),
                    "joint_pct": P(m, j), "oracle_pct": P(m, o)}
        print(f"{LABEL[m]:<15}{S(a):<9}{P(m, a):>+9.3f}   {S(j):<9}{P(m, j):>+9.3f}   "
              f"{S(o):<9}{P(m, o):>+9.3f}{P(m, a) - P(m, o):>+10.3f}")
    for tag, key in (("own-KL vs MXFP4", "own"), ("joint-KL vs MXFP4", "joint")):
        d = np.array([float(marg[m][CANDS.index(picks[m][key])].mean()) for m in MODELS])
        r = paired(d)
        print(f"\n{tag:<20} n=4 checkpoints: {r['pct']:+.2f}%  "
              f"CI [{r['lo']:+.2f}, {r['hi']:+.2f}]  p={r['p']:.4f}  "
              f"{r['n_better']}/{r['n']}  {verdict(r)}")
    d = np.array([float((marg[m][CANDS.index(picks[m]['own'])]
                         - marg[m][CANDS.index(picks[m]['joint'])]).mean())
                  for m in MODELS])
    r = paired(d)
    print(f"{'own-KL vs joint-KL':<20} n=4 checkpoints: {r['pct']:+.2f}%  "
          f"CI [{r['lo']:+.2f}, {r['hi']:+.2f}]  p={r['p']:.4f}  "
          f"{r['n_better']}/{r['n']}  {verdict(r)}")
    print("\nThe MECHANISM is a within-model claim at n = 10 placements and is resolved.")
    print("The PROTOCOL comparison is a cross-model claim at n = 4 checkpoints and is a TIE.")
    out["protocols"] = picks

    json.dump(out, open(os.path.join(HERE, "campaignB_selector.json"), "w"), indent=1)
    print("\nwrote campaignB_selector.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
