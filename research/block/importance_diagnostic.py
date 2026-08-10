#!/usr/bin/env python3
"""Resolving a contradiction in the measured-importance result.

perplexity.py PART A reported two statistics that disagree:

    best-fit gamma over log-bins of E[h|y] :  -0.5356      (a strong trend)
    corr(log|y|, log h) over samples       :  -0.0136      (essentially none)

Both cannot describe the same data. Leaving both in the notes would be exactly the failure the
debugging doctrine forbids -- a second truth appended next to a first. So this measures E[h|y]
directly, at y quantiles, with the count in each bin shown, and settles it.

The suspicion is that the log-bin regression is the broken instrument: it weights every bin
equally regardless of how much probability mass it holds, so the sparsely-populated bins near
y -> 0 (where p_eff has little mass but still clears a raw count threshold) can dominate a fit
that says nothing about the bulk of the data. A mass-weighted fit is the honest version.

Whichever statistic is right, the theorem is unaffected -- it says the codebook moves only
through corr(h, |x|), and reports the consequence either way. What is at stake is the factual
claim about where real models sit.
"""
import os

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN = 32, 2048
torch.set_grad_enabled(False)

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0][: 2 * SEQLEN].view(2, SEQLEN)

acts = {}
lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]


def mk(name):
    def h(mod, inp, out):
        a = inp[0].detach().abs().double().reshape(-1, inp[0].shape[-1]).mean(0)
        acts[name] = acts.get(name, 0.0) + a
    return h


hs_ = [m.register_forward_hook(mk(n)) for n, m in lins]
for i in range(2):
    model(ids[i: i + 1])
for h in hs_:
    h.remove()

ys, hs = [], []
for n, m in lins:
    if n not in acts:
        continue
    w = m.weight.detach().double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    b, a = b[ok], a[ok]
    y = (b / a[:, None]).abs()
    him = (acts[n][:nn_] ** 2).reshape(1, -1).expand(w.shape[0], -1).reshape(-1, K)[ok]
    ys.append(y.reshape(-1).numpy()[::11])
    hs.append(him.reshape(-1).numpy()[::11])
ys, hs = np.concatenate(ys), np.concatenate(hs)
hs = hs / hs.mean()

print(f"samples: {len(ys):,}\n")
print("Direct measurement of E[h | y] at y quantiles (h normalised to mean 1)\n")
print(f"  {'y range':<22}{'count':>12}{'E[h|y]':>10}{'mass share':>12}")
qs = np.quantile(ys, np.linspace(0, 1, 11))
tot = len(ys)
means = []
mids = []
for i in range(10):
    lo, hi = qs[i], qs[i + 1]
    sel = (ys >= lo) & (ys < hi if i < 9 else ys <= hi)
    c = int(sel.sum())
    if c == 0:
        continue
    mh = float(hs[sel].mean())
    means.append(mh)
    mids.append(float(np.sqrt(max(lo, 1e-6) * max(hi, 1e-6))))
    print(f"  [{lo:.4f}, {hi:.4f}){c:>12,}{mh:>10.4f}{c/tot*100:>11.1f}%")

lm = np.polyfit(np.log(mids), np.log(means), 1)[0]
corr = float(np.corrcoef(np.log(np.maximum(ys, 1e-6)), np.log(np.maximum(hs, 1e-12)))[0, 1])
spread = max(means) / min(means)

print(f"\n  mass-weighted gamma (equal-mass bins): {lm:+.4f}")
print(f"  corr(log|y|, log h) over samples:      {corr:+.4f}")
print(f"  E[h|y] spread across deciles:          {spread:.3f}x")
print()
if abs(lm) < 0.05 and spread < 1.2:
    print("  VERDICT: E[h|y] is FLAT. Weight magnitude and AWQ importance are effectively")
    print("  independent in this model. The -0.5356 from the raw log-bin fit was an artefact")
    print("  of weighting near-empty bins equally with the bulk -- a broken instrument, and it")
    print("  is retracted. By the importance-invariance theorem the optimal codebook is")
    print("  therefore essentially UNCHANGED by AWQ-style importance, which is exactly what the")
    print("  perplexity measurement showed (16.504 -> 16.487, a 0.017 difference).")
else:
    print("  VERDICT: a real trend is present; the sample correlation was attenuated by the")
    print("  heavy variance of log h. The tilt is genuine and the codebook does move.")
