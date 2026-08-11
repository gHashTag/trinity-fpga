#!/usr/bin/env python3
"""ATTACK 5(a), strongest form: give squared error the SAME data access KL had.

`attack5_equal_budget.py` matches the search budget but not the *information*.
The KL objective sees the model's logits on real text; plain weight squared error
sees only the weights. If the squared-error arm loses, a defender of the KL
result can say the control was starved, not out-argued.

So this arm gives squared error the data too. The objective is activation-weighted
(diagonal-Hessian) squared error

    sum_layers sum_ij  h_j * ( |w_ij| - s_block * Q(|w_ij|/s_block) )^2 ,
    h_j = E[ x_j^2 ] over calibration text

which is the objective GPTQ/AWQ-family methods actually minimise, collected from
the SAME wikitext windows the KL search used. Same coordinate descent, same two
seeds, same step schedule, same per-seed budget, plus a globally-informed Lloyd
fit on the same weighted distribution.

If a squared-error codebook with equal budget AND equal data access still fails
to beat MXFP4 while the KL codebook beats it, the objective -- not the budget and
not the calibration data -- is what carries the result.

    NWIN=40 EVALS=120 KLWIN=2 python3 attack5_hessian_mse.py
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
_ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"), _ns)
fp_levels, q_e8m0_t, quant = _ns["fp_levels"], _ns["q_e8m0_t"], _ns["quant"]
perplexity, target_modules = _ns["perplexity"], _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]
torch.set_grad_enabled(False)

NWIN = int(os.environ.get("NWIN", "40"))
EVALS = int(os.environ.get("EVALS", "120"))
KLWIN = int(os.environ.get("KLWIN", "2"))     # same calibration text as the KL search
NBINS = int(os.environ.get("NBINS", "2000000"))
OUT = os.path.join(HERE, "attack5_hessian_mse.json")

MXFP4 = sorted(fp_levels(2, 1))
LLOYD = [x / 0.96567 for x in
         [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]]
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
PUB = {"fp32": 14.4874, "MXFP4": 21.9397, "KL-optimised": 20.2587}


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


def main():
    out = {"NWIN": NWIN, "EVALS_per_seed": EVALS, "KLWIN": KLWIN}
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)

    def apply(lv):
        if lv is None:
            for n, m in lins:
                m.weight.copy_(orig[n])
            return
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))

    # ---- ruler --------------------------------------------------------------
    apply(None)
    r = {"fp32": perplexity(model, ids, NWIN)}
    apply(MXFP4)
    r["MXFP4"] = perplexity(model, ids, NWIN)
    apply(KLOPT)
    r["KL-optimised"] = perplexity(model, ids, NWIN)
    ok = all(abs(r[k] - PUB[k]) < 0.02 for k in PUB)
    for k in ("fp32", "MXFP4", "KL-optimised"):
        print(f"RULER {k:<13} {r[k]:9.4f} (published {PUB[k]}) "
              f"{'ok' if abs(r[k]-PUB[k])<0.02 else 'MISMATCH'}", flush=True)
    out["ruler"], out["ruler_ok"] = r, bool(ok)
    json.dump(out, open(OUT, "w"), indent=1)
    if not ok:
        print("RULER BROKEN. Stop.")
        return 1
    apply(None)

    # ---- collect E[x^2] per input feature, on the KL search's own text -------
    print(f"\ncollecting activation second moments on windows 0..{KLWIN-1}…",
          flush=True)
    t0 = time.time()
    acc, cnt = {}, {}
    hooks = []

    def mk(name):
        def hook(mod, inp, _out):
            x = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
            s = (x * x).sum(0)
            if name in acc:
                acc[name] += s
                cnt[name] += x.shape[0]
            else:
                acc[name] = s
                cnt[name] = x.shape[0]
        return hook

    for n, m in lins:
        hooks.append(m.register_forward_hook(mk(n)))
    for i in range(KLWIN):
        model(win[i:i + 1])
    for h in hooks:
        h.remove()
    H = {n: (acc[n] / cnt[n]) for n in acc}
    print(f"  {len(H)} layers, [{time.time()-t0:.0f}s]", flush=True)
    hs = torch.cat([v for v in H.values()])
    print(f"  h_j: min {float(hs.min()):.3e} median {float(hs.median()):.3e} "
          f"max {float(hs.max()):.3e}  (dynamic range "
          f"{float(hs.max()/hs.clamp(min=1e-30).min()):.2e})", flush=True)
    out["h_stats"] = {"min": float(hs.min()), "median": float(hs.median()),
                      "max": float(hs.max())}

    # ---- weighted histogram of y = |w|/s, weight = h_j * s^2 ----------------
    print("building the activation-weighted squared-error objective…", flush=True)
    t0 = time.time()
    A = torch.zeros(NBINS + 1, dtype=torch.float64)
    B = torch.zeros(NBINS + 1, dtype=torch.float64)
    C = torch.zeros(NBINS + 1, dtype=torch.float64)
    for n, _ in lins:
        w = orig[n]
        cols = (w.shape[1] // K) * K
        if cols == 0:
            continue
        a = w[:, :cols].double().abs()                       # [out, cols]
        blk = a.reshape(-1, K)
        s = q_e8m0_t((blk.amax(dim=1) / 1.0).clamp(min=1e-30)).clamp(min=1e-30)
        y = (blk / s[:, None]).reshape(-1)
        wt = ((s[:, None] ** 2).expand_as(blk).reshape(a.shape) *
              H[n][:cols][None, :]).reshape(-1)
        idx = torch.clamp((y * NBINS).long(), 0, NBINS)
        A.scatter_add_(0, idx, wt * y * y)
        B.scatter_add_(0, idx, wt * y)
        C.scatter_add_(0, idx, wt)
        del a, blk, s, y, wt, idx
    cA = torch.cat([torch.zeros(1, dtype=torch.float64), A.cumsum(0)])
    cB = torch.cat([torch.zeros(1, dtype=torch.float64), B.cumsum(0)])
    cC = torch.cat([torch.zeros(1, dtype=torch.float64), C.cumsum(0)])
    del A, B, C
    print(f"  [{time.time()-t0:.0f}s]", flush=True)

    def hsse(lv):
        v = sorted(float(x) for x in lv)
        bnd = [(v[i] + v[i + 1]) / 2 for i in range(len(v) - 1)]
        edges = [0] + [min(NBINS + 1, int(np.ceil(b * NBINS))) for b in bnd] \
                + [NBINS + 1]
        tot = 0.0
        for k in range(len(v)):
            lo, hi = edges[k], edges[k + 1]
            if hi <= lo:
                continue
            tot += (float(cA[hi] - cA[lo]) - 2.0 * v[k] * float(cB[hi] - cB[lo])
                    + v[k] * v[k] * float(cC[hi] - cC[lo]))
        return tot

    def hsse_exact(lv):
        """Ground truth via the real quantiser, h-weighted."""
        tot = 0.0
        for n, _ in lins:
            w = orig[n]
            cols = (w.shape[1] // K) * K
            d = (quant(w, lv)[:, :cols].double() - w[:, :cols].double()) ** 2
            tot += float((d * H[n][:cols][None, :]).sum())
        return tot

    print("\n  instrument check on the h-weighted objective:")
    worst = 0.0
    chk = {}
    for name, lv in (("MXFP4", MXFP4), ("KL-optimised", KLOPT)):
        h_, e_ = hsse(lv), hsse_exact(lv)
        rel = abs(h_ - e_) / e_
        worst = max(worst, rel)
        chk[name] = {"hist": h_, "exact": e_, "rel": rel}
        print(f"    {name:<13} hist {h_:.8e}  quant() {e_:.8e}  rel {rel:.2e}",
              flush=True)
    out["objective_check"] = chk
    if worst > 1e-3:
        print("  objective does not track quant(). Stop.")
        json.dump(out, open(OUT, "w"), indent=1)
        return 1

    # ---- same coordinate descent, same budget, same seeds -------------------
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
            print(f"  [{tag}] from {seed_name:<10} {evals:4d} evals "
                  f"{start:.6e} -> {cur:.6e} ({100*(1-cur/start):+.3f}%)  "
                  f"{[round(x,5) for x in lv]}", flush=True)
            traj[seed_name] = {"start": start, "end": cur, "evals": evals,
                               "levels": [float(x) for x in lv]}
            if best is None or cur < best[0]:
                best = (cur, lv, seed_name)
        return best, traj

    print("\ncoordinate descent on activation-weighted squared error:", flush=True)
    (v_eq, lv_eq, o_eq), t_eq = coord_descent(hsse, "hSSE 1x", EVALS)
    (v_5x, lv_5x, o_5x), t_5x = coord_descent(hsse, "hSSE 5x", 5 * EVALS)
    out["hmse_equal"] = {"levels": lv_eq, "obj": v_eq, "origin": o_eq,
                         "trajectory": t_eq}
    out["hmse_5x"] = {"levels": lv_5x, "obj": v_5x, "origin": o_5x,
                      "trajectory": t_5x}

    # ---- Lloyd fit on the same weighted distribution ------------------------
    centres = (torch.arange(NBINS + 1, dtype=torch.float64) + 0.5) / NBINS
    hB, hC = cB[1:] - cB[:-1], cC[1:] - cC[:-1]

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
            new[0], new[-1] = 0.0, 1.0
            new, _ = torch.sort(new)
            if float((new - lv).abs().max()) < 1e-13:
                return [float(x) for x in new], it
            lv = new
        return [float(x) for x in lv], iters

    print("\n  Lloyd fit on the activation-weighted distribution:", flush=True)
    fits = {}
    for sn, sd in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD),
                   ("uniform", [i / 7 for i in range(8)]), ("KL-optimised", KLOPT)):
        lv, its = lloyd(sd)
        fits[sn] = {"levels": lv, "obj": hsse(lv), "iters": its}
        print(f"    from {sn:<14} obj {fits[sn]['obj']:.6e} ({its} it)  "
              f"{[round(x,5) for x in lv]}", flush=True)
    bf = min(fits, key=lambda k: fits[k]["obj"])
    lv_ll = fits[bf]["levels"]
    out["hlloyd_fits"], out["hlloyd"] = fits, {"levels": lv_ll, "from": bf}

    arms = [("MXFP4 (E2M1)", MXFP4), ("KL-optimised", KLOPT),
            ("hMSE-CD equal budget", lv_eq), ("hMSE-CD 5x budget", lv_5x),
            ("hMSE Lloyd (global)", lv_ll)]
    print(f"\n  {'codebook':<24} {'h-weighted SSE':>16} {'x best':>9}")
    objs = {n: hsse(l) for n, l in arms}
    ref = min(objs.values())
    for n, _ in arms:
        print(f"  {n:<24} {objs[n]:>16.8e} {objs[n]/ref:>8.4f}x")
    out["objective"] = objs
    del cA, cB, cC, hB, hC, centres

    held = win[NWIN:2 * NWIN].reshape(1, -1)
    n_held = held.shape[1] // SEQLEN
    print(f"\n  {'codebook':<24} {'ppl w0-39':>10} {'vs MXFP4':>9} "
          f"{'ppl w40-79':>11} {'vs MXFP4':>9}", flush=True)
    ppl, pph = {}, {}
    for name, lv in arms:
        apply(lv)
        ppl[name] = r["MXFP4"] if name == "MXFP4 (E2M1)" else (
            r["KL-optimised"] if name == "KL-optimised"
            else perplexity(model, ids, NWIN))
        pph[name] = perplexity(model, held, n_held)
        mx, mxh = ppl["MXFP4 (E2M1)"], pph["MXFP4 (E2M1)"]
        print(f"  {name:<24} {ppl[name]:>10.4f} {100*(ppl[name]/mx-1):>+8.2f}% "
              f"{pph[name]:>11.4f} {100*(pph[name]/mxh-1):>+8.2f}%", flush=True)
        out["ppl"], out["ppl_heldout"] = ppl, pph
        json.dump(out, open(OUT, "w"), indent=1)
    apply(None)

    mx = ppl["MXFP4 (E2M1)"]
    out["verdict"] = {
        "hmse_equal_beats_mxfp4": bool(ppl["hMSE-CD equal budget"] < mx),
        "hmse_5x_beats_mxfp4": bool(ppl["hMSE-CD 5x budget"] < mx),
        "hmse_lloyd_beats_mxfp4": bool(ppl["hMSE Lloyd (global)"] < mx),
        "kl_beats_mxfp4": bool(ppl["KL-optimised"] < mx),
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
