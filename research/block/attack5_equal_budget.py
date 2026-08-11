#!/usr/bin/env python3
"""ATTACK 5 -- is the KL-codebook comparison fair?

(a) The KL codebook got an optimisation budget MXFP4 and Lloyd-Max never had.
    The honest control is the SAME coordinate descent, SAME two seeds, SAME step
    schedule, SAME per-seed evaluation budget, minimising the objective the
    incumbents were designed for: WEIGHT SQUARED ERROR along the deployed path.
    If squared-error optimisation at equal budget also beats MXFP4, the story is
    "optimisation helps", not "the objective matters".

    Two extra arms guard against "the control lost because it was optimised
    badly":
      - the same coordinate descent at 5x the budget
      - true Lloyd-Max fitted to the distribution the deployed quantiser sees
        (y = |w| / 2^ceil(log2 block_max), weighted by s^2), endpoints pinned at
        0.0 and 1.0 so it lives in the same feasible set (top = 1, phase 0).
        Lloyd is a globally-informed alternating optimiser, not a local probe.

(b) Is the KL codebook a legitimate 8-level codebook (8 magnitudes, sorted,
    first 0.0, last 1.0, finite, strictly increasing, 3 bits + sign = 4 bits)?

The quantiser is block_tnf.py's `quant`, reused verbatim. Every codebook is
normalised to a top of exactly 1.0, so the E8M0 block scale
s = 2^ceil(log2(a_max)) is IDENTICAL for all of them -- which is what makes the
cached squared-error objective legitimate and the comparison phase-neutral
(MXFP4_SCALE_CONVENTION_2026-08-11.md).

    NWIN=40 EVALS=120 python3 attack5_equal_budget.py
"""
import os
import sys
import json
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit("attack5: driver marker not found in block_tnf.py")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

fp_levels = _ns["fp_levels"]
q_e8m0_t = _ns["q_e8m0_t"]
quant = _ns["quant"]
perplexity = _ns["perplexity"]
target_modules = _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]

torch.set_grad_enabled(False)

NWIN = int(os.environ.get("NWIN", "40"))
EVALS = int(os.environ.get("EVALS", "120"))     # per seed, as kl_optimal_codebook
NBINS = int(os.environ.get("NBINS", "2000000"))
OUT = os.path.join(HERE, "attack5_equal_budget.json")

MXFP4 = sorted(fp_levels(2, 1))                 # fp_levels already tops at 1.0
LLOYD = [x / 0.96567 for x in
         [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]]
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
PUBLISHED = {"fp32": 14.4874, "MXFP4": 21.9397, "Lloyd-Max": 22.9166,
             "KL-optimised": 20.2587}


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


def check_codebook(lv):
    """(b) -- structural legitimacy of an 8-level magnitude codebook."""
    r = {}
    r["levels"] = [float(x) for x in lv]
    r["count"] = len(lv)
    r["count_is_8"] = len(lv) == 8
    r["all_finite"] = bool(np.all(np.isfinite(np.asarray(lv, dtype=np.float64))))
    r["sorted_ascending"] = list(lv) == sorted(lv)
    r["strictly_increasing"] = all(b > a for a, b in zip(lv, lv[1:]))
    r["first_exactly_zero"] = float(lv[0]) == 0.0
    r["last_exactly_one"] = float(lv[-1]) == 1.0
    r["distinct_magnitudes"] = len(set(float(x) for x in lv))
    r["nonnegative"] = all(float(x) >= 0.0 for x in lv)
    # 8 magnitudes need 3 index bits; + 1 sign bit = 4 bits per weight.
    r["index_bits"] = 3
    r["bits_with_sign"] = 4
    r["fits_4_bits_with_sign"] = (len(lv) == 8)
    r["all_ok"] = all([r["count_is_8"], r["all_finite"], r["sorted_ascending"],
                       r["strictly_increasing"], r["first_exactly_zero"],
                       r["last_exactly_one"], r["nonnegative"],
                       r["distinct_magnitudes"] == 8])
    return r


def main():
    out = {"NWIN": NWIN, "EVALS_per_seed": EVALS, "NBINS": NBINS}

    # ---------- (b) first: pure arithmetic, no model needed ------------------
    print("=" * 72)
    print("(b) codebook legitimacy")
    print("=" * 72)
    struct = {}
    for name, lv in (("MXFP4 (E2M1)", MXFP4), ("Lloyd-Max (published)", LLOYD),
                     ("KL-optimised", KLOPT)):
        struct[name] = check_codebook(lv)
        c = struct[name]
        print(f"  {name:<22} n={c['count']} finite={c['all_finite']} "
              f"strict_inc={c['strictly_increasing']} "
              f"first0={c['first_exactly_zero']} last1={c['last_exactly_one']} "
              f"-> {'LEGITIMATE' if c['all_ok'] else 'NOT LEGITIMATE'}")
    out["structural"] = struct
    # E2M1 magnitudes in units of 0.5 are integers -> no table needed
    e2m1_raw = sorted({(1 + m / 2) * 2.0 ** (e - 1)
                       for e in range(1, 4) for m in range(2)} |
                      {0.0, 0.5 * 2.0 ** 0})
    out["e2m1_raw_magnitudes"] = e2m1_raw
    print(f"  E2M1 raw magnitudes: {e2m1_raw}")
    print(f"  E2M1 x2 (integers) : {[x * 2 for x in e2m1_raw]}")

    # ---------- model ---------------------------------------------------------
    print("\nloading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"{len(lins)} linear layers, "
          f"{sum(v.numel() for v in orig.values())} weights", flush=True)

    def apply(lv):
        if lv is None:
            for n, m in lins:
                m.weight.copy_(orig[n])
            return
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))

    # ---------- ruler ---------------------------------------------------------
    print("\n" + "=" * 72)
    print("RULER -- must reproduce the published table or nothing below counts")
    print("=" * 72, flush=True)
    ruler, ok = {}, True
    apply(None)
    t0 = time.time()
    ruler["fp32"] = perplexity(model, ids, NWIN)
    good = abs(ruler["fp32"] - PUBLISHED["fp32"]) < 0.02
    ok = ok and good
    print(f"  fp32         {ruler['fp32']:9.4f}  (published {PUBLISHED['fp32']})"
          f"  {'ok' if good else 'MISMATCH'}   [{time.time()-t0:.0f}s]", flush=True)
    for name, lv in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD),
                     ("KL-optimised", KLOPT)):
        apply(lv)
        t0 = time.time()
        ruler[name] = perplexity(model, ids, NWIN)
        good = abs(ruler[name] - PUBLISHED[name]) < 0.02
        ok = ok and good
        print(f"  {name:<12} {ruler[name]:9.4f}  (published {PUBLISHED[name]})"
              f"  {'ok' if good else 'MISMATCH'}   [{time.time()-t0:.0f}s]",
              flush=True)
    out["ruler"], out["ruler_ok"] = ruler, bool(ok)
    json.dump(out, open(OUT, "w"), indent=1)
    if not ok:
        print("\nRULER BROKEN. Stop.")
        return 1

    # ---------- squared-error objective along the deployed path ---------------
    # All codebooks top at 1.0, so s is codebook-independent. Build a weighted
    # histogram of y = |w|/s with weights s^2 once; every SSE evaluation is then
    # seven prefix-sum lookups instead of a pass over 10^8 weights.
    print("\nbuilding the squared-error objective (weighted histogram of y)…",
          flush=True)
    t0 = time.time()
    A = torch.zeros(NBINS + 1, dtype=torch.float64)   # sum w2 * y^2
    B = torch.zeros(NBINS + 1, dtype=torch.float64)   # sum w2 * y
    C = torch.zeros(NBINS + 1, dtype=torch.float64)   # sum w2
    ncov = 0
    ntot = 0
    ymax = 0.0
    for n, _ in lins:
        w = orig[n]
        ntot += w.numel()
        cols = (w.shape[1] // K) * K
        if cols == 0:
            continue
        head = w[:, :cols].reshape(-1, K).double().abs()
        s = q_e8m0_t((head.amax(dim=1) / 1.0).clamp(min=1e-30)).clamp(min=1e-30)
        y = (head / s[:, None]).reshape(-1)
        w2 = (s[:, None] ** 2).expand_as(head).reshape(-1)
        ymax = max(ymax, float(y.max()))
        idx = torch.clamp((y * NBINS).long(), 0, NBINS)
        A.scatter_add_(0, idx, w2 * y * y)
        B.scatter_add_(0, idx, w2 * y)
        C.scatter_add_(0, idx, w2)
        ncov += y.numel()
        del head, s, y, w2, idx
    cA = torch.cat([torch.zeros(1, dtype=torch.float64), A.cumsum(0)])
    cB = torch.cat([torch.zeros(1, dtype=torch.float64), B.cumsum(0)])
    cC = torch.cat([torch.zeros(1, dtype=torch.float64), C.cumsum(0)])
    del A, B, C
    print(f"  {ncov} of {ntot} weights covered by whole blocks "
          f"({100*ncov/ntot:.2f}%), max y = {ymax:.6f}   [{time.time()-t0:.0f}s]",
          flush=True)
    out["weights_total"], out["weights_in_blocks"] = ntot, ncov
    out["max_y"] = ymax

    def sse_hist(lv):
        v = sorted(float(x) for x in lv)
        bnd = [(v[i] + v[i + 1]) / 2 for i in range(len(v) - 1)]
        edges = [0] + [min(NBINS + 1, int(np.ceil(b * NBINS))) for b in bnd] \
                + [NBINS + 1]
        tot = 0.0
        for k in range(len(v)):
            lo, hi = edges[k], edges[k + 1]
            if hi <= lo:
                continue
            a = float(cA[hi] - cA[lo])
            b = float(cB[hi] - cB[lo])
            c = float(cC[hi] - cC[lo])
            tot += a - 2.0 * v[k] * b + v[k] * v[k] * c
        return tot

    def sse_exact(lv):
        """Ground truth: what quant() actually produces, vs the fp32 weights."""
        tot = 0.0
        for n, _ in lins:
            d = quant(orig[n], lv).double() - orig[n].double()
            tot += float((d ** 2).sum())
        return tot

    print("\n  instrument check on the squared-error objective:")
    chk, worst = {}, 0.0
    for name, lv in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD),
                     ("KL-optimised", KLOPT)):
        h, e = sse_hist(lv), sse_exact(lv)
        rel = abs(h - e) / e
        worst = max(worst, rel)
        chk[name] = {"hist": h, "exact_via_quant": e, "rel_diff": rel}
        print(f"    {name:<13} hist {h:.8e}  quant() {e:.8e}  rel {rel:.2e}",
              flush=True)
    out["sse_objective_check"] = chk
    # quant() casts to float32 before the difference is taken; the histogram
    # stays float64. A float32 ulp on a ~1e-2 relative residual shows at ~1e-5.
    if worst > 1e-3:
        print("  objective does not track quant(). Stop.")
        json.dump(out, open(OUT, "w"), indent=1)
        return 1
    print("  objective tracks quant(). ok", flush=True)

    # ---------- the control search -------------------------------------------
    def coord_descent(objective, tag, budget):
        best, traj = None, {}
        for seed_name, seed in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
            lv = normalise(seed)
            cur = start = objective(lv)
            evals, step = 0, 0.06
            while evals < budget and step > 0.004:
                improved = False
                for i in range(1, len(lv) - 1):
                    for d in (+step, -step):
                        cand = list(lv)
                        cand[i] = cand[i] + d
                        lo, hi = cand[i - 1] + 1e-3, cand[i + 1] - 1e-3
                        if not (lo < cand[i] < hi):
                            continue
                        v = objective(cand)
                        evals += 1
                        if v < cur - 1e-9 * abs(cur):
                            lv, cur, improved = cand, v, True
                        if evals >= budget:
                            break
                    if evals >= budget:
                        break
                if not improved:
                    step /= 2
            print(f"  [{tag}] from {seed_name:<10} {evals:4d} evals  "
                  f"{start:.8e} -> {cur:.8e}  ({100*(1-cur/start):+.3f}%)  "
                  f"{[round(x,5) for x in lv]}", flush=True)
            traj[seed_name] = {"start": start, "end": cur, "evals": evals,
                               "levels": [float(x) for x in lv]}
            if best is None or cur < best[0]:
                best = (cur, lv, seed_name)
        return best, traj

    print("\n" + "=" * 72)
    print("(a) control: identical machinery, squared-error objective")
    print("=" * 72, flush=True)
    (sse_eq, lv_eq, org_eq), traj_eq = coord_descent(sse_hist, "SSE 1x", EVALS)
    (sse_5x, lv_5x, org_5x), traj_5x = coord_descent(sse_hist, "SSE 5x", 5 * EVALS)
    out["mse_equal_budget"] = {"levels": [float(x) for x in lv_eq],
                               "sse": sse_eq, "origin": org_eq,
                               "trajectory": traj_eq}
    out["mse_5x_budget"] = {"levels": [float(x) for x in lv_5x],
                            "sse": sse_5x, "origin": org_5x,
                            "trajectory": traj_5x}

    # ---------- true Lloyd-Max on the deployed path ---------------------------
    print("\n  true Lloyd-Max fitted to the deployed path (endpoints pinned):",
          flush=True)
    centres = (torch.arange(NBINS + 1, dtype=torch.float64) + 0.5) / NBINS
    hC = (cC[1:] - cC[:-1])
    hB = (cB[1:] - cB[:-1])

    def lloyd(init, iters=500):
        lv = torch.tensor(sorted(init), dtype=torch.float64)
        for it in range(iters):
            bnd = (lv[:-1] + lv[1:]) / 2
            idx = torch.bucketize(centres, bnd)
            num = torch.zeros(8, dtype=torch.float64).scatter_add_(0, idx, hB)
            den = torch.zeros(8, dtype=torch.float64).scatter_add_(0, idx, hC)
            new = lv.clone()
            live = den > 0
            new[live] = num[live] / den[live]
            new[0] = 0.0            # zero stays exactly representable
            new[-1] = 1.0           # top pinned -> same feasible set, phase 0
            new, _ = torch.sort(new)
            if float((new - lv).abs().max()) < 1e-13:
                return [float(x) for x in new], it
            lv = new
        return [float(x) for x in lv], iters

    fits = {}
    for seed_name, seed in (("MXFP4", MXFP4), ("published Lloyd-Max", LLOYD),
                            ("uniform", [i / 7 for i in range(8)]),
                            ("KL-optimised", KLOPT)):
        lv, its = lloyd(seed)
        fits[seed_name] = {"levels": lv, "sse": sse_hist(lv), "iters": its}
        print(f"    from {seed_name:<20} SSE {fits[seed_name]['sse']:.8e} "
              f"({its} iters)  {[round(x,5) for x in lv]}", flush=True)
    best_fit = min(fits, key=lambda k: fits[k]["sse"])
    lv_lloyd = fits[best_fit]["levels"]
    out["true_lloyd_fits"] = fits
    out["true_lloyd"] = {"levels": lv_lloyd, "from": best_fit,
                         "sse": fits[best_fit]["sse"]}

    # ---------- squared error of every arm, one instrument -------------------
    arms = [("MXFP4 (E2M1)", MXFP4),
            ("Lloyd-Max (published)", LLOYD),
            ("KL-optimised", KLOPT),
            ("MSE-CD equal budget", lv_eq),
            ("MSE-CD 5x budget", lv_5x),
            ("true Lloyd (deployed path)", lv_lloyd)]
    print(f"\n  {'codebook':<28} {'weight SSE':>16} {'x best':>9}")
    sses = {n: sse_hist(l) for n, l in arms}
    ref = min(sses.values())
    for n, _ in arms:
        print(f"  {n:<28} {sses[n]:>16.8e} {sses[n]/ref:>8.4f}x")
    out["sse"] = sses
    json.dump(out, open(OUT, "w"), indent=1)

    # ---------- the judge -----------------------------------------------------
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    held = win[NWIN:2 * NWIN].reshape(1, -1)
    n_held = held.shape[1] // SEQLEN
    print(f"\n{win.shape[0]} windows available; held-out = "
          f"{NWIN}..{NWIN + n_held - 1}", flush=True)
    print("\n" + "=" * 72)
    print("JUDGE -- perplexity, the axis BLOCK_AXIS_CLOSED used")
    print("=" * 72)
    print(f"  {'codebook':<28} {'ppl w0-39':>10} {'vs MXFP4':>9} "
          f"{'ppl w40-79':>11} {'vs MXFP4':>9}", flush=True)
    ppl, ppl_h = {}, {}
    for name, lv in arms:
        apply(lv)
        ppl[name] = ruler.get({"MXFP4 (E2M1)": "MXFP4",
                               "Lloyd-Max (published)": "Lloyd-Max",
                               "KL-optimised": "KL-optimised"}.get(name, "_"),
                              None)
        if ppl[name] is None:
            ppl[name] = perplexity(model, ids, NWIN)
        ppl_h[name] = perplexity(model, held, n_held)
        mx = ppl["MXFP4 (E2M1)"]
        mxh = ppl_h["MXFP4 (E2M1)"]
        print(f"  {name:<28} {ppl[name]:>10.4f} {100*(ppl[name]/mx-1):>+8.2f}% "
              f"{ppl_h[name]:>11.4f} {100*(ppl_h[name]/mxh-1):>+8.2f}%",
              flush=True)
        out["ppl"], out["ppl_heldout"] = ppl, ppl_h
        json.dump(out, open(OUT, "w"), indent=1)
    apply(None)

    mx = ppl["MXFP4 (E2M1)"]
    kl = ppl["KL-optimised"]
    eq = ppl["MSE-CD equal budget"]
    x5 = ppl["MSE-CD 5x budget"]
    tl = ppl["true Lloyd (deployed path)"]
    out["verdict"] = {
        "mse_equal_budget_beats_mxfp4": bool(eq < mx),
        "mse_5x_beats_mxfp4": bool(x5 < mx),
        "true_lloyd_beats_mxfp4": bool(tl < mx),
        "kl_beats_mxfp4": bool(kl < mx),
        "kl_beats_every_mse_arm": bool(kl < min(eq, x5, tl)),
    }
    print()
    if eq < mx or x5 < mx or tl < mx:
        print("VERDICT (a): squared-error optimisation ALSO beats MXFP4 -> the")
        print("             story is 'optimisation helps', not 'objective matters'.")
    else:
        print("VERDICT (a): squared-error optimisation does NOT beat MXFP4 at equal")
        print("             budget, at 5x budget, or with a global Lloyd fit, while")
        print("             the KL search does -> on THIS model the objective is")
        print("             what carries the result, not the budget.")
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
