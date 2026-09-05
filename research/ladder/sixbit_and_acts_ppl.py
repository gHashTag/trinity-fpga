"""A: does the fitted lambda predict a budget it was never fitted on?  B: activations, measured.

A -- SIX BITS. lambda was tuned against six outcomes: two models x {3,4,5} bits. Six bits is a
budget the fit never saw, so the two-term score makes a genuine out-of-sample prediction there.
Measuring it is the difference between "reproduces six fitted outcomes" and a law.

B -- ACTIVATIONS, MEASURED. shape_and_acts.py PREDICTED that activations want the coarsest rung
at every budget (shift), while weights want phi at 4 bits and plastic at 5. That prediction came
from a criterion whose only validation is on weights. Here activations are actually quantised in
the forward pass and perplexity is measured, so the prediction can fail.

Both parts print the prediction BEFORE the measurement, so the comparison cannot be rewritten
after the fact.
"""
import json
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
SEQLEN = 2048
WINDOWS = int(os.environ.get("NW", "8"))
LAM = 0.01
torch.set_grad_enabled(False)

RATIOS = {"shift  (2^k,   deg 1)": 2.0,
          "phi    (1.618, deg 2)": (1 + 5 ** 0.5) / 2,
          "supergold (1.4656, d3)": 1.465571231876768,
          "plastic(1.3247, deg 3)": 1.324717957244746}


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


def score_of(x, r, bits):
    n = (2 ** bits - 1) // 2
    cb = codebook(r, bits)
    mid = (cb[:-1] + cb[1:]) / 2
    mse = float(((cb[np.searchsorted(mid, x)] - x) ** 2).mean())
    flush = float((np.abs(x) < r ** (-(n - 1)) / 2).mean())
    return mse + LAM * flush


def q_tensor(t, cb_t, mid_t, dim=-1):
    s = t.abs().amax(dim=dim, keepdim=True).clamp_min(1e-12)
    return cb_t[torch.bucketize(t / s, mid_t)] * s


tok = AutoTokenizer.from_pretrained(os.path.join(W, "smollm2"))
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())


def load(md):
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, md), dtype=torch.float32)
    m.eval()
    return m


def ppl(model, ids):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].reshape(-1, SEQLEN)[:WINDOWS]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


# ---------------------------------------------------------------- A: six bits
print("=" * 72)
print("A -- SIX BITS: a budget the lambda fit never saw\n")
for md in ("smollm2", "qwen"):
    tk = AutoTokenizer.from_pretrained(os.path.join(W, md))
    ids = tk(text, return_tensors="pt").input_ids[0]
    m = load(md)
    parts = []
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
            w = mod.weight.data.to(torch.float64)
            s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            z = (w / s).cpu().numpy().ravel()
            parts.append(z[:: max(1, z.size // 120000)])
    x = np.concatenate(parts)
    pred = min(RATIOS, key=lambda k: score_of(x, RATIOS[k], 6))
    print(f"  {md}: PREDICTION at 6 bits = {pred.split()[0]}")
    base = ppl(m, ids)
    del m
    res = []
    for name, r in RATIOS.items():
        mm = load(md)
        cb = codebook(r, 6)
        cb_t = torch.tensor(cb, dtype=torch.float64)
        mid_t = torch.tensor((cb[:-1] + cb[1:]) / 2, dtype=torch.float64)
        for nm, mod in mm.named_modules():
            if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
                mod.weight.data = q_tensor(mod.weight.data.to(torch.float64),
                                           cb_t, mid_t, dim=1).to(mod.weight.dtype)
        p = ppl(mm, ids)
        res.append((name, p))
        del mm
        print(f"    {name:24} ppl={p:10.4f}")
    win = min(res, key=lambda t: t[1])[0]
    print(f"  {md}: fp32={base:.4f}  MEASURED winner = {win.split()[0]}   "
          f"{'PREDICTION HELD' if win == pred else 'PREDICTION FAILED'}\n")

# ---------------------------------------------------------------- B: activations
print("=" * 72)
print("B -- ACTIVATIONS QUANTISED IN THE FORWARD PASS (SmolLM2)\n")
ids = tok(text, return_tensors="pt").input_ids[0]
m = load("smollm2")
caps = []
hs = []


def mk():
    def h(mod, inp):
        if len(caps) < 40:
            a = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
            s = a.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            caps.append((a / s).cpu().numpy().ravel()[::53])
        return None
    return h


for nm, mod in m.named_modules():
    if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
        hs.append(mod.register_forward_pre_hook(mk()))
base_a = ppl(m, ids[:SEQLEN])
for h in hs:
    h.remove()
xa = np.concatenate(caps)
for bits in (3, 4, 5):
    print(f"  {bits} bits: PREDICTION for activations = "
          f"{min(RATIOS, key=lambda k: score_of(xa, RATIOS[k], bits)).split()[0]}")
print()

base = ppl(m, ids)
del m
for bits in (3, 4, 5):
    res = []
    for name, r in RATIOS.items():
        mm = load("smollm2")
        cb = codebook(r, bits)
        cb_t = torch.tensor(cb, dtype=torch.float64)
        mid_t = torch.tensor((cb[:-1] + cb[1:]) / 2, dtype=torch.float64)

        def mkq(cb_t=cb_t, mid_t=mid_t):
            def h(mod, inp):
                return (q_tensor(inp[0].to(torch.float64), cb_t, mid_t,
                                 dim=-1).to(inp[0].dtype),) + inp[1:]
            return h

        for nm, mod in mm.named_modules():
            if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
                mod.register_forward_pre_hook(mkq())
        p = ppl(mm, ids)
        res.append((name, p))
        del mm
    win = min(res, key=lambda t: t[1])[0]
    pred = min(RATIOS, key=lambda k: score_of(xa, RATIOS[k], bits))
    print(f"  {bits} bits (weights fp32, ACTIVATIONS quantised), fp32 ppl={base:.4f}")
    for name, p in sorted(res, key=lambda t: t[1]):
        print(f"    {name:24} ppl={p:12.4f}")
    print(f"    predicted={pred.split()[0]:10} measured={win.split()[0]:10} "
          f"{'HELD' if win == pred else 'FAILED'}\n")
