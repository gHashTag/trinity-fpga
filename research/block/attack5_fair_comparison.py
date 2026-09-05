#!/usr/bin/env python3
"""ATTACK 5 -- is the KL-codebook comparison fair?

(a) The KL codebook got an optimisation budget the incumbents did not. The honest
    control is the SAME coordinate descent, SAME budget, SAME seeds, SAME step
    schedule, optimising the objective the incumbents were designed for -- WEIGHT
    SQUARED ERROR. If that also beats MXFP4, the story is "optimisation helps",
    not "the objective matters".

(b) Is the KL codebook a legitimate 8-level codebook, and what does it cost in
    silicon relative to E2M1?

Reuses block_tnf.py's quantiser verbatim (source exec'd up to the driver marker).

    NWIN=40 EVALS=120 python3 attack5_fair_comparison.py
"""
import os
import sys
import json
import math

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
EVALS = int(os.environ.get("EVALS", "120"))

MXFP4 = sorted(fp_levels(2, 1))                    # already normalised, top 1.0
LLOYD = [x / 0.96567 for x in
         [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]]
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
PUBLISHED = {"MXFP4": 21.9397, "Lloyd-Max": 22.9166, "fp32": 14.4874,
             "KL-optimised": 20.2587}


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


def main():
    out = {}
    print("loading model…", flush=True)
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

    # ---- ruler ------------------------------------------------------------
    apply(None)
    base = perplexity(model, ids, NWIN)
    print(f"\nRULER fp32      = {base:.4f}  (published {PUBLISHED['fp32']})",
          flush=True)
    ruler = {"fp32": base}
    ok = abs(base - PUBLISHED["fp32"]) < 0.02
    for name, lv in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD),
                     ("KL-optimised", KLOPT)):
        apply(lv)
        p = perplexity(model, ids, NWIN)
        ruler[name] = p
        good = abs(p - PUBLISHED[name]) < 0.02
        ok = ok and good
        print(f"RULER {name:<13} = {p:.4f}  (published {PUBLISHED[name]})  "
              f"{'ok' if good else 'MISMATCH'}", flush=True)
    out["ruler"] = ruler
    out["ruler_ok"] = bool(ok)
    if not ok:
        print("\nRULER BROKEN. Stop.")
        json.dump(out, open(os.path.join(HERE, "attack5_fair_comparison.json"),
                            "w"), indent=1)
        return 1

    # ---- squared-error objective ------------------------------------------
    # Every codebook here is normalised to top 1.0, so the E8M0 scale
    #   s = 2^ceil(log2(a_max / 1.0))
    # does NOT depend on the codebook. Cache the per-block scaled magnitudes
    # once; the resulting SSE is then bit-comparable to recomputing quant().
    print("\ncaching block-normalised magnitudes for the squared-error objective…",
          flush=True)
    cache = []
    for n, m in lins:
        w = orig[n]
        cols = (w.shape[1] // K) * K
        if cols == 0:
            continue
        head = w[:, :cols].reshape(-1, K).double()
        s = (head.abs().amax(dim=1) / 1.0).clamp(min=1e-30)
        s = q_e8m0_t(s).clamp(min=1e-30)
        cache.append((head.abs(), s[:, None]))
    n_cached = sum(a.numel() for a, _ in cache)
    print(f"  {n_cached} weights in {len(cache)} tensors", flush=True)

    def sse_fast(lv):
        lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
        bnd = (lv_t[:-1] + lv_t[1:]) / 2
        tot = 0.0
        for a, s in cache:
            y = a / s
            rec = lv_t[torch.bucketize(y, bnd)] * s
            tot += float(((a - rec) ** 2).sum())
        return tot

    def sse_slow(lv):
        """Ground truth: actual quant() output vs original weight."""
        tot = 0.0
        for n, m in lins:
            d = (quant(orig[n], lv).double() - orig[n].double())
            tot += float((d ** 2).sum())
        return tot

    # instrument check on the fast objective
    chk = {}
    for name, lv in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
        f, s_ = sse_fast(lv), sse_slow(lv)
        rel = abs(f - s_) / s_
        chk[name] = {"fast": f, "slow": s_, "rel_diff": rel}
        print(f"  SSE check {name:<10} fast {f:.6e}  slow {s_:.6e}  "
              f"rel {rel:.2e}", flush=True)
    out["sse_objective_check"] = chk
    # 1e-3 not 1e-8: quant() casts its output to float32 before the difference is
    # taken, the fast path stays in float64, and the residual is ~1e-2 relative,
    # so a float32 ulp on the reconstruction shows up at ~1e-5 in the SSE.
    if max(v["rel_diff"] for v in chk.values()) > 1e-3:
        print("SSE objective does not match quant(). Stop.")
        return 1

    # ---- the control search: identical machinery, squared-error objective ---
    def coord_descent(objective, tag, budget=None):
        EV = EVALS if budget is None else budget
        best = None
        traj = {}
        for seed_name, seed in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
            lv = normalise(seed)
            cur = objective(lv)
            start = cur
            print(f"\n[{tag}] from {seed_name}: {cur:.6e}", flush=True)
            evals = 0
            step = 0.06
            while evals < EV and step > 0.004:
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
                        if v < cur - 1e-7 * abs(cur):
                            lv, cur, improved = cand, v, True
                        if evals >= EV:
                            break
                    if evals >= EV:
                        break
                if not improved:
                    step /= 2
            print(f"  {evals} evaluations, {start:.6e} -> {cur:.6e} "
                  f"({100*(1-cur/start):.2f}% reduction)", flush=True)
            traj[seed_name] = {"start": start, "end": cur, "evals": evals,
                               "levels": [round(x, 6) for x in lv]}
            if best is None or cur < best[0]:
                best = (cur, lv, seed_name)
        return best, traj

    (sse_best, lv_mse, mse_origin), mse_traj = coord_descent(sse_fast, "SSE")
    print(f"\nMSE-optimised codebook (from {mse_origin}): "
          f"{[round(x,5) for x in lv_mse]}", flush=True)
    out["mse_search"] = {"trajectory": mse_traj,
                         "best_levels": [round(x, 6) for x in lv_mse],
                         "best_sse": sse_best, "origin": mse_origin}

    # generous control: 5x the budget on the cheap objective. If squared-error
    # optimisation still fails to beat MXFP4 with five times the search, the
    # equal-budget result is not an artefact of the budget being too small.
    (sse_b5, lv_mse5, org5), traj5 = coord_descent(sse_fast, "SSE x5", 5 * EVALS)
    print(f"\nMSE-optimised x5 budget (from {org5}): "
          f"{[round(x,5) for x in lv_mse5]}", flush=True)
    out["mse_search_5x"] = {"trajectory": traj5,
                            "best_levels": [round(x, 6) for x in lv_mse5],
                            "best_sse": sse_b5, "origin": org5}

    # ---- squared error of every codebook, same instrument ------------------
    print(f"\n  {'codebook':<24} {'weight SSE':>14} {'x Lloyd':>9}")
    sses = {}
    for name, lv in (("MXFP4 (E2M1)", MXFP4), ("Lloyd-Max", LLOYD),
                     ("KL-optimised", KLOPT), ("MSE-optimised (control)", lv_mse),
                     ("MSE-optimised x5", lv_mse5)):
        sses[name] = sse_fast(lv)
    ref = sses["Lloyd-Max"]
    for name in sses:
        print(f"  {name:<24} {sses[name]:>14.6e} {sses[name]/ref:>8.3f}x")
    out["sse"] = sses

    # ---- the judge ---------------------------------------------------------
    # Two window sets. The KL search used windows 0-1 as its signal, and those
    # sit INSIDE the published 40-window judge set; the squared-error control
    # saw no data at all. Windows 40..79 are held out from both.
    flat = ids.reshape(-1)
    nfull = (flat.numel() // SEQLEN) * SEQLEN
    win = flat[:nfull].view(-1, SEQLEN)
    print(f"\n{win.shape[0]} windows of {SEQLEN} available", flush=True)
    held = win[NWIN:2 * NWIN].reshape(1, -1)
    n_held = held.shape[1] // SEQLEN
    print(f"held-out = windows {NWIN}..{NWIN + n_held - 1}", flush=True)

    print(f"\n  {'codebook':<24} {'ppl w0-39':>11} {'vs MXFP4':>9} "
          f"{'ppl held':>10} {'vs MXFP4':>9}")
    ppl, ppl_h = {}, {}
    for name, lv in (("MXFP4 (E2M1)", MXFP4), ("Lloyd-Max", LLOYD),
                     ("KL-optimised", KLOPT), ("MSE-optimised (control)", lv_mse),
                     ("MSE-optimised x5", lv_mse5)):
        apply(lv)
        ppl[name] = perplexity(model, ids, NWIN)
        ppl_h[name] = perplexity(model, held, n_held)
    mx, mxh = ppl["MXFP4 (E2M1)"], ppl_h["MXFP4 (E2M1)"]
    for name in ppl:
        print(f"  {name:<24} {ppl[name]:>11.4f} {100*(ppl[name]/mx-1):>+8.2f}% "
              f"{ppl_h[name]:>10.4f} {100*(ppl_h[name]/mxh-1):>+8.2f}%", flush=True)
    out["ppl"] = ppl
    out["ppl_heldout"] = ppl_h
    apply(None)

    kl_p, mse_p = ppl["KL-optimised"], ppl["MSE-optimised (control)"]
    print()
    if mse_p < mx:
        print("VERDICT (a): the squared-error search ALSO beats MXFP4 at equal")
        print("             budget -> the story is 'optimisation helps'.")
    else:
        print("VERDICT (a): the squared-error search does NOT beat MXFP4 at equal")
        print("             budget, while the KL search does -> the OBJECTIVE is")
        print("             what carries the result, not the budget.")
    out["verdict_a_mse_beats_mxfp4"] = bool(mse_p < mx)
    out["verdict_a_mse5x_beats_mxfp4"] = bool(ppl["MSE-optimised x5"] < mx)
    out["verdict_a_kl_beats_mse"] = bool(kl_p < mse_p)

    json.dump(out, open(os.path.join(HERE, "attack5_fair_comparison.json"), "w"),
              indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
