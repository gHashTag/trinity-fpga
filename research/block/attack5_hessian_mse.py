#!/usr/bin/env python3
"""ATTACK 5(a), strongest form: give squared error the SAME data access KL had,
and judge every arm per-window so the margins get an error bar.

`attack5_equal_budget.py` matched the search budget but not the *information*.
The KL objective sees the model's logits on real text; plain weight squared error
sees only the weights. If the squared-error arm loses, a defender can say the
control was starved rather than out-argued. So this arm gives squared error the
data too:

    sum_layers sum_ij  h_j * ( |w_ij| - s_blk * Q(|w_ij|/s_blk) )^2 ,
    h_j = E[x_j^2] over the SAME wikitext windows the KL search used

-- the diagonal-Hessian / activation-weighted squared error that the GPTQ/AWQ
family actually minimises. Same coordinate descent, same two seeds, same step
schedule, same per-seed budget, plus a globally-informed Lloyd fit on the same
weighted distribution.

It also fixes a weakness in the first run: that run compared two aggregate
perplexities per arm and the unweighted-MSE arm changed SIGN between window sets
(+2.72 % on w0-39, -3.41 % on w40-79). Aggregates cannot say whether that is a
real effect. Here every arm is scored per window over windows 0..79, which yields
both aggregates AND a paired t-test against MXFP4 on the same windows.

    NWIN=40 EVALS=120 KLWIN=2 python3 attack5_hessian_mse.py
"""
import os
import sys
import json
import math
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"), _ns)
fp_levels, q_e8m0_t, quant = _ns["fp_levels"], _ns["q_e8m0_t"], _ns["quant"]
target_modules, load_wikitext = _ns["target_modules"], _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]
torch.set_grad_enabled(False)

NWIN = int(os.environ.get("NWIN", "40"))
NTOT = int(os.environ.get("NTOT", "80"))      # windows scored per arm
EVALS = int(os.environ.get("EVALS", "120"))
KLWIN = int(os.environ.get("KLWIN", "2"))
NBINS = int(os.environ.get("NBINS", "2000000"))
OUT = os.path.join(HERE, "attack5_hessian_mse.json")

MXFP4 = sorted(fp_levels(2, 1))
LLOYD = [x / 0.96567 for x in
         [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]]
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
# reproduced by attack5_equal_budget.py, this machine, this run of the ruler
MSE_CD = [0.0, 0.08451, 0.17328, 0.26896, 0.38311, 0.5288, 0.70824, 1.0]
MSE_LL = [0.0, 0.07744, 0.16076, 0.25518, 0.36837, 0.51443, 0.6949, 1.0]
PUB = {"MXFP4 (E2M1)": 21.9397, "KL-optimised": 20.2587}


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


def main():
    out = {"NWIN": NWIN, "NTOT": NTOT, "EVALS_per_seed": EVALS, "KLWIN": KLWIN}
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
    print(f"{len(lins)} linear layers, {win.shape[0]} windows", flush=True)

    def apply(lv):
        for n, m in lins:
            m.weight.copy_(orig[n] if lv is None else quant(orig[n], lv))

    # ---- activation second moments, on the KL search's own calibration text --
    apply(None)
    print(f"\ncollecting E[x^2] on windows 0..{KLWIN-1}…", flush=True)
    t0 = time.time()
    acc, cnt, hooks = {}, {}, []

    def mk(name):
        def hook(_m, inp, _o):
            x = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
            s = (x * x).sum(0)
            if name in acc:
                acc[name] += s
                cnt[name] += x.shape[0]
            else:
                acc[name], cnt[name] = s, x.shape[0]
        return hook

    for n, m in lins:
        hooks.append(m.register_forward_hook(mk(n)))
    for i in range(KLWIN):
        model(win[i:i + 1])
    for h in hooks:
        h.remove()
    H = {n: acc[n] / cnt[n] for n in acc}
    hs = torch.cat(list(H.values()))
    print(f"  {len(H)} layers [{time.time()-t0:.0f}s]; h_j min {float(hs.min()):.3e} "
          f"med {float(hs.median()):.3e} max {float(hs.max()):.3e}", flush=True)
    out["h_stats"] = {"min": float(hs.min()), "median": float(hs.median()),
                      "max": float(hs.max())}

    # ---- activation-weighted histogram of y = |w|/s -------------------------
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
        a = w[:, :cols].double().abs()
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
        e = [0] + [min(NBINS + 1, int(np.ceil(b * NBINS))) for b in bnd] + [NBINS + 1]
        tot = 0.0
        for k in range(len(v)):
            lo, hi = e[k], e[k + 1]
            if hi > lo:
                tot += (float(cA[hi] - cA[lo]) - 2 * v[k] * float(cB[hi] - cB[lo])
                        + v[k] * v[k] * float(cC[hi] - cC[lo]))
        return tot

    def hsse_exact(lv):
        tot = 0.0
        for n, _ in lins:
            w = orig[n]
            cols = (w.shape[1] // K) * K
            d = (quant(w, lv)[:, :cols].double() - w[:, :cols].double()) ** 2
            tot += float((d * H[n][:cols][None, :]).sum())
        return tot

    print("\n  instrument check on the h-weighted objective:")
    chk, worst = {}, 0.0
    for name, lv in (("MXFP4", MXFP4), ("KL-optimised", KLOPT)):
        h_, e_ = hsse(lv), hsse_exact(lv)
        rel = abs(h_ - e_) / e_
        worst = max(worst, rel)
        chk[name] = {"hist": h_, "exact": e_, "rel": rel}
        print(f"    {name:<13} hist {h_:.8e} quant() {e_:.8e} rel {rel:.2e}",
              flush=True)
    out["objective_check"] = chk
    if worst > 1e-3:
        print("  objective does not track quant(). Stop.")
        json.dump(out, open(OUT, "w"), indent=1)
        return 1

    # ---- same machinery, same budget, same seeds ----------------------------
    def coord_descent(obj, tag, budget):
        best, traj = None, {}
        for sn, sd in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
            lv = normalise(sd)
            cur = start = obj(lv)
            evals, step = 0, 0.06
            while evals < budget and step > 0.004:
                improved = False
                for i in range(1, len(lv) - 1):
                    for d in (+step, -step):
                        cand = list(lv)
                        cand[i] += d
                        if not (cand[i - 1] + 1e-3 < cand[i] < cand[i + 1] - 1e-3):
                            continue
                        v = obj(cand)
                        evals += 1
                        if v < cur - 1e-9 * abs(cur):
                            lv, cur, improved = cand, v, True
                        if evals >= budget:
                            break
                    if evals >= budget:
                        break
                if not improved:
                    step /= 2
            print(f"  [{tag}] from {sn:<10} {evals:4d} evals {start:.6e} -> "
                  f"{cur:.6e} ({100*(1-cur/start):+.3f}%)  "
                  f"{[round(x,5) for x in lv]}", flush=True)
            traj[sn] = {"start": start, "end": cur, "evals": evals,
                        "levels": [float(x) for x in lv]}
            if best is None or cur < best[0]:
                best = (cur, lv, sn)
        return best, traj

    print("\ncoordinate descent on activation-weighted squared error:", flush=True)
    (v_eq, lv_eq, o_eq), t_eq = coord_descent(hsse, "hSSE 1x", EVALS)
    (v_5x, lv_5x, o_5x), t_5x = coord_descent(hsse, "hSSE 5x", 5 * EVALS)
    out["hmse_equal"] = {"levels": lv_eq, "obj": v_eq, "origin": o_eq, "traj": t_eq}
    out["hmse_5x"] = {"levels": lv_5x, "obj": v_5x, "origin": o_5x, "traj": t_5x}

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

    arms = [("MXFP4 (E2M1)", MXFP4),
            ("KL-optimised", KLOPT),
            ("MSE-CD (unweighted)", MSE_CD),
            ("MSE-Lloyd (unweighted)", MSE_LL),
            ("hMSE-CD equal budget", lv_eq),
            ("hMSE-Lloyd (global)", lv_ll)]
    print(f"\n  {'codebook':<24} {'h-weighted SSE':>16} {'x best':>9}")
    objs = {n: hsse(l) for n, l in arms}
    ref = min(objs.values())
    for n, _ in arms:
        print(f"  {n:<24} {objs[n]:>16.8e} {objs[n]/ref:>8.4f}x")
    out["h_objective"] = objs
    del cA, cB, cC, hB, hC, centres
    json.dump(out, open(OUT, "w"), indent=1)

    # ---- per-window NLL: one pass gives both window sets AND paired tests ----
    print(f"\nscoring {NTOT} windows per arm (per-window NLL)…", flush=True)
    nll = {}
    for name, lv in arms:
        apply(lv)
        t0 = time.time()
        v = []
        for i in range(NTOT):
            c = win[i:i + 1]
            v.append(float(model(c, labels=c).loss.double()))
        nll[name] = v
        a = float(np.exp(np.mean(v[:NWIN])))
        b = float(np.exp(np.mean(v[NWIN:NTOT])))
        print(f"  {name:<24} ppl w0-{NWIN-1} {a:8.4f}   "
              f"ppl w{NWIN}-{NTOT-1} {b:8.4f}   [{time.time()-t0:.0f}s]", flush=True)
        out["nll"] = nll
        json.dump(out, open(OUT, "w"), indent=1)
    apply(None)

    # ---- report -------------------------------------------------------------
    ref_nll = np.array(nll["MXFP4 (E2M1)"])
    ppl_a = {n: float(np.exp(np.mean(nll[n][:NWIN]))) for n, _ in arms}
    ppl_b = {n: float(np.exp(np.mean(nll[n][NWIN:NTOT]))) for n, _ in arms}
    ppl_all = {n: float(np.exp(np.mean(nll[n]))) for n, _ in arms}
    mx_a, mx_b, mx_all = (ppl_a["MXFP4 (E2M1)"], ppl_b["MXFP4 (E2M1)"],
                          ppl_all["MXFP4 (E2M1)"])
    ruler_ok = (abs(mx_a - PUB["MXFP4 (E2M1)"]) < 0.02 and
                abs(ppl_a["KL-optimised"] - PUB["KL-optimised"]) < 0.02)
    print(f"\nRULER on w0-{NWIN-1}: MXFP4 {mx_a:.4f} (pub {PUB['MXFP4 (E2M1)']}), "
          f"KL {ppl_a['KL-optimised']:.4f} (pub {PUB['KL-optimised']}) -> "
          f"{'ok' if ruler_ok else 'MISMATCH'}")
    out["ruler_ok"] = bool(ruler_ok)

    print(f"\n  {'codebook':<24} {'w0-39':>9} {'Δ%':>7} {'w40-79':>9} {'Δ%':>7} "
          f"{'w0-79':>9} {'Δ%':>7} {'t(79)':>8} {'p':>10} {'wins':>7}")
    stats = {}
    for n, _ in arms:
        d = np.array(nll[n]) - ref_nll          # >0 means worse than MXFP4
        t = float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))) if d.std() > 0 else 0.0
        # two-sided p from the normal approximation (n=80)
        p = math.erfc(abs(t) / math.sqrt(2))
        wins = int((d < 0).sum())
        stats[n] = {"ppl_w0_39": ppl_a[n], "ppl_w40_79": ppl_b[n],
                    "ppl_w0_79": ppl_all[n], "t": t, "p_approx": p,
                    "windows_better_than_mxfp4": wins, "n_windows": len(d)}
        print(f"  {n:<24} {ppl_a[n]:>9.4f} {100*(ppl_a[n]/mx_a-1):>+6.2f}% "
              f"{ppl_b[n]:>9.4f} {100*(ppl_b[n]/mx_b-1):>+6.2f}% "
              f"{ppl_all[n]:>9.4f} {100*(ppl_all[n]/mx_all-1):>+6.2f}% "
              f"{t:>8.2f} {p:>10.2e} {wins:>4d}/{len(d)}")
    out["stats"] = stats
    out["verdict"] = {
        n: {"beats_mxfp4_w0_39": bool(ppl_a[n] < mx_a),
            "beats_mxfp4_w40_79": bool(ppl_b[n] < mx_b),
            "beats_mxfp4_all80": bool(ppl_all[n] < mx_all),
            "consistent_sign": bool((ppl_a[n] < mx_a) == (ppl_b[n] < mx_b))}
        for n, _ in arms if n != "MXFP4 (E2M1)"}
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
