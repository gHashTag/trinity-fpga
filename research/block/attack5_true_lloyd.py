#!/usr/bin/env python3
"""ATTACK 5, strongest form of the squared-error control.

Coordinate descent is a weak optimiser. If the squared-error arm loses only
because it was optimised badly, the "objective matters" reading is unearned.

So: fit Lloyd-Max properly, to the distribution the deployed quantiser actually
sees -- y = |w| / 2^ceil(log2(block_max)), weighted by s^2 so the objective is
weight squared error in the original units, exactly what `quant()` produces --
with the endpoints pinned at 0.0 and 1.0 so it lives in the same feasible set as
every other codebook here (top = 1.0, phase 0).

The published "Lloyd-Max" was fitted to a different distribution: blocks
normalised by their own max, so y_max = 1 for every block. Under the E8M0 scale
y_max lands anywhere in (0.5, 1]. That is why it is not the squared-error
optimum of the path it is being judged on.

Lloyd is a globally-informed alternating optimiser for this objective, not a
120-evaluation local probe. If the resulting codebook still loses to MXFP4 on
perplexity, squared error does not buy perplexity here, whatever the budget.
"""
import os
import sys
import json

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
MXFP4 = sorted(fp_levels(2, 1))
LLOYD = [x / 0.96567 for x in
         [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]]
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}

    # y = |w|/s and the weight s^2, exactly as quant() forms them
    ys, ws = [], []
    for n, _ in lins:
        w = orig[n]
        cols = (w.shape[1] // K) * K
        if cols == 0:
            continue
        head = w[:, :cols].reshape(-1, K).double().abs()
        s = q_e8m0_t((head.amax(dim=1) / 1.0).clamp(min=1e-30)).clamp(min=1e-30)
        ys.append((head / s[:, None]).reshape(-1))
        ws.append((s[:, None] ** 2).expand_as(head).reshape(-1))
    y = torch.cat(ys)
    w2 = torch.cat(ws)
    del ys, ws
    print(f"{y.numel()} values, y in [{float(y.min()):.4f}, {float(y.max()):.4f}], "
          f"y_max median per-block behaviour visible in the range above", flush=True)

    def sse(lv):
        lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
        bnd = (lv_t[:-1] + lv_t[1:]) / 2
        idx = torch.bucketize(y, bnd)
        return float((w2 * (y - lv_t[idx]) ** 2).sum())

    def lloyd(init, iters=200):
        lv = torch.tensor(sorted(init), dtype=torch.float64)
        for it in range(iters):
            bnd = (lv[:-1] + lv[1:]) / 2
            idx = torch.bucketize(y, bnd)
            num = torch.zeros(8, dtype=torch.float64).scatter_add_(0, idx, w2 * y)
            den = torch.zeros(8, dtype=torch.float64).scatter_add_(0, idx, w2)
            new = lv.clone()
            live = den > 0
            new[live] = num[live] / den[live]
            new[0] = 0.0          # zero must stay exactly representable
            new[-1] = 1.0         # top pinned: phase 0, same feasible set
            new, _ = torch.sort(new)
            if float((new - lv).abs().max()) < 1e-12:
                lv = new
                print(f"  converged at iteration {it}", flush=True)
                break
            lv = new
        return [float(x) for x in lv]

    out = {}
    print("\nfitting Lloyd-Max to the deployed path (endpoints pinned)…", flush=True)
    fits = {}
    for seed_name, seed in (("MXFP4", MXFP4), ("published Lloyd-Max", LLOYD),
                            ("uniform", [i / 7 for i in range(8)])):
        lv = lloyd(seed)
        fits[seed_name] = {"levels": [round(x, 6) for x in lv], "sse": sse(lv)}
        print(f"  from {seed_name:<20} SSE {sse(lv):.8e}  "
              f"{[round(x,5) for x in lv]}", flush=True)
    best_name = min(fits, key=lambda k: fits[k]["sse"])
    lv_true = [float(x) for x in fits[best_name]["levels"]]
    out["lloyd_fits"] = fits
    out["true_lloyd"] = lv_true
    out["true_lloyd_from"] = best_name

    print(f"\n  {'codebook':<26} {'weight SSE':>14} {'x true-Lloyd':>13}")
    cands = (("MXFP4 (E2M1)", MXFP4), ("published Lloyd-Max", LLOYD),
             ("KL-optimised", KLOPT), ("true Lloyd (this path)", lv_true))
    sses = {n: sse(l) for n, l in cands}
    ref = sses["true Lloyd (this path)"]
    for n in sses:
        print(f"  {n:<26} {sses[n]:>14.8e} {sses[n]/ref:>12.4f}x")
    out["sse"] = sses
    del y, w2

    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    held = win[NWIN:2 * NWIN].reshape(1, -1)
    n_held = held.shape[1] // SEQLEN

    print(f"\n  {'codebook':<26} {'ppl w0-39':>10} {'vs MXFP4':>9} "
          f"{'ppl w40-79':>11} {'vs MXFP4':>9}")
    ppl, ppl_h = {}, {}
    for name, lv in cands:
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))
        ppl[name] = perplexity(model, ids, NWIN)
        ppl_h[name] = perplexity(model, held, n_held)
    mx, mxh = ppl["MXFP4 (E2M1)"], ppl_h["MXFP4 (E2M1)"]
    for n in ppl:
        print(f"  {n:<26} {ppl[n]:>10.4f} {100*(ppl[n]/mx-1):>+8.2f}% "
              f"{ppl_h[n]:>11.4f} {100*(ppl_h[n]/mxh-1):>+8.2f}%", flush=True)
    out["ppl"] = ppl
    out["ppl_heldout"] = ppl_h
    out["true_lloyd_beats_mxfp4"] = bool(ppl["true Lloyd (this path)"] < mx)
    out["kl_beats_true_lloyd"] = bool(ppl["KL-optimised"] <
                                      ppl["true Lloyd (this path)"])
    json.dump(out, open(os.path.join(HERE, "attack5_true_lloyd.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
