#!/usr/bin/env python3
"""Why every error metric said rotation helped while the model got worse.

The chain this closes:

  ROTATION_VERDICT_2026-08-11  a block-wise Hadamard makes perplexity 8.24% worse
  WHY_ROTATION_HURTS_2026-08-11  ...while REDUCING total weight error by 3.31%,
                                 and no weight-magnitude statistic explains it

Three mechanisms were proposed and all three failed. This measures the same
intervention on four instruments at once and finds the disagreement is not in
the network at all — it is between Euclidean distance and Kullback-Leibler
divergence, and only one of them is what perplexity is made of.

    weight error          L2 on the weights
    layer output error    L2 on each layer's output, given clean input
    logit error           L2 on the final logits, full quantised forward pass
    KL(fp32 || quantised) the quantity cross-entropy actually contains

Cross-entropy of the quantised model against the true tokens is the fp32
cross-entropy plus KL(fp32 || quantised) up to the part that does not depend on
the approximation, so a rise in KL is a rise in perplexity by construction. The
arithmetic is checked below rather than asserted: exp(ΔKL) is compared against
the measured perplexity ratio.

The point is not that L2 is a loose proxy. It is that on this intervention L2
moves the other way, on every level of the network, by a lot.

    python3 metric_disagreement.py
"""
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit("metric_disagreement: driver marker not found in block_tnf.py")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

fp_levels = _ns["fp_levels"]
q_e8m0_t = _ns["q_e8m0_t"]
target_modules = _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]

torch.set_grad_enabled(False)
LV = torch.tensor(sorted(fp_levels(2, 1)), dtype=torch.float64)   # MXFP4 E2M1
NWIN = int(os.environ.get("NWIN", "4"))


def hadamard(n):
    h = np.array([[1.0]])
    while h.shape[0] < n:
        h = np.block([[h, h], [h, -h]])
    return torch.tensor(h, dtype=torch.float64)


HN = hadamard(K) / np.sqrt(K)


def quantise(bl):
    s = (bl.abs().amax(dim=1) / LV[-1]).clamp(min=1e-30)
    s = q_e8m0_t(s).clamp(min=1e-30)
    y = (bl / s[:, None]).abs()
    bnd = (LV[:-1] + LV[1:]) / 2
    return torch.sign(bl) * LV[torch.bucketize(y, bnd)] * s[:, None]


def quantised_weight(w, rotated):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w.clone(), 0
    bl = w[:, :n].double().reshape(-1, K)
    q = (quantise(bl @ HN) @ HN.T) if rotated else quantise(bl)
    out = w.clone()
    out[:, :n] = q.reshape(-1, n).to(w.dtype)
    return out, n


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    flat = tok(load_wikitext(), return_tensors="pt").input_ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)[:NWIN]
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"  {len(lins)} layers, {NWIN} windows of {SEQLEN}, MXFP4 E2M1 + E8M0, K={K}")

    # one clean forward, keeping each layer's real input for the layer-level arm
    X = {}

    def mk(name):
        def h(_m, inp, _o):
            if name not in X:
                X[name] = inp[0].detach().double().reshape(-1, inp[0].shape[-1])[:256].clone()
        return h

    handles = [m.register_forward_hook(mk(n)) for n, m in lins]
    ref = torch.cat([model(win[i:i + 1]).logits.double().clone() for i in range(NWIN)])
    for h in handles:
        h.remove()
    logp_ref = F.log_softmax(ref, dim=-1)
    p_ref = logp_ref.exp()

    rows = {}
    for rotated in (False, True):
        ew = ey = 0.0
        for n, mod in lins:
            w = orig[n]
            qw, nn = quantised_weight(w, rotated)
            if nn == 0:
                continue
            W = w[:, :nn].double()
            QW = qw[:, :nn].double()
            ew += float(((QW - W) ** 2).sum())
            if n in X:
                x = X[n][:, :nn]
                ey += float(((x @ QW.T - x @ W.T) ** 2).sum())
            mod.weight.copy_(qw)

        nll = 0.0
        outs = []
        for i in range(NWIN):
            c = win[i:i + 1]
            o = model(c, labels=c)
            nll += float(o.loss)
            outs.append(o.logits.double().clone())
        L = torch.cat(outs)
        logp = F.log_softmax(L, dim=-1)
        rows["rotated" if rotated else "unrotated"] = dict(
            weight=ew, layer=ey,
            logit=float(((L - ref) ** 2).sum()),
            kl=float((p_ref * (logp_ref - logp)).sum(-1).mean()),
            ppl=float(np.exp(nll / NWIN)),
        )
        for n, mod in lins:
            mod.weight.copy_(orig[n])

    a, b = rows["unrotated"], rows["rotated"]
    print(f"\n  {'instrument':<26} {'unrotated':>13} {'rotated':>13} {'change':>10}")
    for key, label in (("weight", "weight L2"),
                       ("layer", "layer-output L2"),
                       ("logit", "logit L2"),
                       ("kl", "KL(fp32 || quantised)"),
                       ("ppl", "perplexity")):
        pct = 100.0 * (b[key] - a[key]) / a[key]
        print(f"  {label:<26} {a[key]:>13.4e} {b[key]:>13.4e} {pct:>+9.2f}%")

    # Does the KL change account for the perplexity change?
    pred = float(np.exp(b["kl"] - a["kl"]))
    meas = b["ppl"] / a["ppl"]
    print(f"\n  exp(ΔKL) = {pred:.4f}   measured perplexity ratio = {meas:.4f}")
    print(f"  agreement: {100 * abs(pred - meas) / (meas - 1):.0f}% of the change unexplained"
          if meas > 1 else "")

    every_l2_down = all(b[k] < a[k] for k in ("weight", "layer", "logit"))
    if every_l2_down and b["kl"] > a["kl"] and b["ppl"] > a["ppl"]:
        print("\nRESULT: every Euclidean instrument says the rotated model is closer to")
        print("        fp32; KL says it is further away, and perplexity follows KL.")
        print("        The disagreement is between the metrics, not inside the network.")
    else:
        print("\nRESULT: the pattern did not reproduce — read the table, not this line.")
    print("\nSCOPE: one model, one codebook, one rotation. NWIN is small by default "
          "because the four instruments must be read on identical inputs; the "
          "perplexity direction here matches the 40-window measurement in "
          "ROTATION_VERDICT_2026-08-11.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
