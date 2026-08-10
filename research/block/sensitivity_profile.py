#!/usr/bin/env python3
"""What does perplexity actually weight? The missing piece behind three unexplained results.

Three separate findings say per-tensor MSE does not determine model perplexity:

  * DP-16 had the lowest MSE of all codebooks and the worst perplexity (until the zero was added)
  * per-tensor, ours wins 177 of 189 tensors on MSE, yet NF4 wins Qwen on perplexity
  * MSE ordering and perplexity ordering inverted outright among zeroless codebooks

Every one of those is consistent with a single explanation: perplexity weights layers unequally,
and unweighted per-tensor MSE assumes it weights them equally. That is testable directly.

METHOD. Quantise exactly ONE layer at a time -- all seven linear weights of transformer block i,
everything else left in fp32 -- and measure the perplexity increase. Repeat for every block. Then
do the same by LAYER TYPE (all q_proj, all down_proj, ...). This gives the sensitivity profile
without any modelling assumption.

THREE QUESTIONS, each with a clear failure mode:

  (1) Is sensitivity uniform across depth? If it is, unweighted MSE was fine and the divergence
      needs another explanation entirely.
  (2) Does per-layer MSE predict per-layer perplexity damage? If the correlation is high, MSE is
      a good proxy and the divergence is elsewhere. If low, MSE is measuring the wrong thing and
      every MSE table in this programme is answering a question nobody asked.
  (3) Do the per-layer damages ADD UP to the all-layers damage? Quantisation error is often
      assumed additive across layers. If it is not, per-layer evidence cannot be composed at all.

Costs one forward-pass sweep per configuration, so it runs on the small model only.
"""
import os
import re
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from competitors import FP4_E2M1 as E2M1

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN = 32, 2048
NW = int(os.environ.get("NW", "6"))
torch.set_grad_enabled(False)
LV = torch.tensor(E2M1, dtype=torch.float64)


def quantise(w):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    s = b.abs().amax(1).clamp(min=1e-30)
    idx = torch.bucketize(b / s[:, None], (LV[:-1] + LV[1:]) / 2).clamp(0, len(LV) - 1)
    out = w.clone()
    out[:, :n] = (LV[idx] * s[:, None]).reshape(-1, n).to(w.dtype)
    return out


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
base = {n: m.weight.detach().clone() for n, m in lins}
NL = max(layer_index(n) for n, _ in lins) + 1


def ppl():
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[:NW]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


def restore():
    for n, m in lins:
        m.weight.copy_(base[n])


def mse_of(names):
    tot = 0.0
    for n in names:
        w = base[n].double()
        nn_ = (w.shape[1] // K) * K
        if nn_ == 0:
            continue
        b = w[:, :nn_].reshape(-1, K)
        a = b.abs().amax(1)
        ok = a > 0
        b, a = b[ok], a[ok]
        idx = torch.bucketize(b / a[:, None], (LV[:-1] + LV[1:]) / 2).clamp(0, len(LV) - 1)
        tot += float(((LV[idx] * a[:, None] - b) ** 2).sum())
    return tot


p0 = ppl()
print(f"RULER CHECK -- fp32 baseline {p0:.4f} ({NW} windows)")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible")

# all layers at once, for the additivity test
for n, m in lins:
    m.weight.copy_(quantise(base[n].double()).to(m.weight.dtype))
p_all = ppl()
restore()
print(f"  all layers quantised (E2M1): {p_all:.4f}   delta {p_all - p0:+.4f}\n")

print("(1) SENSITIVITY BY DEPTH -- one transformer block quantised at a time\n")
print(f"  {'block':>6}{'delta ppl':>12}{'MSE (sum)':>14}")
deltas, mses = [], []
for i in range(NL):
    names = [n for n, _ in lins if layer_index(n) == i]
    for n, m in lins:
        if n in names:
            m.weight.copy_(quantise(base[n].double()).to(m.weight.dtype))
    d = ppl() - p0
    restore()
    e = mse_of(names)
    deltas.append(d)
    mses.append(e)
    bar = "#" * min(50, int(d / max(1e-9, max(deltas)) * 30))
    print(f"  {i:>6}{d:>12.4f}{e:>14.4f}   {bar}")

deltas = np.array(deltas)
mses = np.array(mses)
print(f"\n  sum of per-block deltas: {deltas.sum():+.4f}")
print(f"  all-at-once delta:       {p_all - p0:+.4f}")
ratio = (p_all - p0) / deltas.sum() if deltas.sum() != 0 else float('nan')
print(f"  (3) ADDITIVITY: all-at-once / sum-of-parts = {ratio:.3f}"
      + ("   -> roughly additive" if 0.8 < ratio < 1.25 else "   -> NOT additive"))

r = float(np.corrcoef(deltas, mses)[0, 1])
sr = float(np.corrcoef(np.argsort(np.argsort(deltas)), np.argsort(np.argsort(mses)))[0, 1])
print(f"\n  (2) does per-layer MSE predict per-layer damage?")
print(f"      Pearson r  = {r:+.3f}")
print(f"      Spearman r = {sr:+.3f}")
print(f"      most damaging block: {int(np.argmax(deltas))} (delta {deltas.max():+.4f})")
print(f"      largest-MSE block:   {int(np.argmax(mses))} (delta {deltas[int(np.argmax(mses))]:+.4f})")
print(f"      damage ratio max/min across blocks: {deltas.max()/max(deltas.min(),1e-9):.1f}x")

print("\n(1b) SENSITIVITY BY LAYER TYPE -- one projection type across all blocks\n")
types = sorted({n.split(".")[-1] for n, _ in lins})
print(f"  {'type':<12}{'delta ppl':>12}{'MSE (sum)':>14}")
for t in types:
    names = [n for n, _ in lins if n.endswith("." + t)]
    for n, m in lins:
        if n in names:
            m.weight.copy_(quantise(base[n].double()).to(m.weight.dtype))
    d = ppl() - p0
    restore()
    print(f"  {t:<12}{d:>12.4f}{mse_of(names):>14.4f}")
