#!/usr/bin/env python3
"""The 6-9% margin on a SECOND model, and the transfer question.

Everything rests on one 135M checkpoint, with an effect only ~2x the measurement resolution.
A second model is the cheapest way to find out whether the margin is real or a property of
SmolLM2. Qwen2.5-0.5B is a different family, a different tokenizer, 4x the size, and 60% more
excess kurtosis.

Three codebooks are compared on Qwen, all against correctly-implemented competitors:

    E2M1 (with its subnormal)      the MXFP4 element
    NF4 (bitsandbytes values)      the strongest incumbent on weights
    DP-16+zero derived from QWEN   fitted to this model's own first-half layers
    DP-16+zero derived from SMOL   the transfer test -- does a codebook fitted to a 135M
                                   model carry over to a 0.5B model of another family?

The transfer row is the one that matters for a deployable claim. A codebook that needs
per-model calibration is a research artefact; one fixed table that works everywhere is a format.

Held-out split is by explicit LAYER INDEX, so "first half" means layers 0..N/2-1 and not
whatever order the container yields.
"""
import json
import os
import re
import struct
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K, SEQLEN, NBIN = 32, 2048, 800
NW = int(os.environ.get("NW", "16"))
torch.set_grad_enabled(False)

MAGS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
E2M1 = np.array(sorted(set([-v / 6 for v in MAGS] + [v / 6 for v in MAGS])))
NF4 = np.array([-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
                -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
                0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
                0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
                0.7229568362236023, 1.0])
DP16Z_SMOL = np.array([-1.0000, -0.7805, -0.6094, -0.4645, -0.3361, -0.2183, -0.1066, 0.0000,
                       0.0944, 0.1901, 0.2908, 0.3987, 0.5162, 0.6491, 0.8053, 1.0000])


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def dp_pinned(dens, pins, nlev=16):
    y = np.linspace(-1, 1, NBIN, endpoint=False) + 1.0 / NBIN
    w = dens * (2.0 / NBIN)
    S0 = np.concatenate([[0.0], np.cumsum(w)])
    S1 = np.concatenate([[0.0], np.cumsum(w * y)])
    S2 = np.concatenate([[0.0], np.cumsum(w * y * y)])

    def cost(a, b, k):
        s0, s1, s2 = S0[b] - S0[a], S1[b] - S1[a], S2[b] - S2[a]
        if k in pins:
            r = pins[k]
            return s2 - 2 * r * s1 + r * r * s0
        return np.where(s0 > 0, s2 - s1 * s1 / np.maximum(s0, 1e-300), 0.0)

    M = NBIN
    f = np.full((nlev, M + 1), np.inf)
    bk = np.zeros((nlev, M + 1), dtype=int)
    f[0] = cost(0, np.arange(M + 1), 0)
    for k in range(1, nlev):
        prev = f[k - 1]
        for i in range(1, M + 1):
            j = np.arange(0, i)
            c = prev[j] + cost(j, i, k)
            t = int(np.argmin(c))
            f[k][i], bk[k][i] = c[t], t
    bounds, cur = [M], M
    for k in range(nlev - 1, 0, -1):
        cur = bk[k][cur]
        bounds.append(cur)
    bounds = sorted(set(bounds + [0]))
    while len(bounds) < nlev + 1:
        bounds.append(M)
    bounds = sorted(bounds)
    lv = []
    for c in range(nlev):
        a, b = bounds[c], bounds[c + 1]
        if c in pins:
            lv.append(pins[c])
        else:
            s0 = S0[b] - S0[a]
            lv.append(float((S1[b] - S1[a]) / s0) if s0 > 0 else float(y[min(a, M - 1)]))
    return np.array(sorted(lv)), float(f[nlev - 1][M])


def quantise(w, lv):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    s = b.abs().amax(1).clamp(min=1e-30)
    idx = torch.bucketize(b / s[:, None], (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
    out = w.clone()
    out[:, :n] = (lv[idx] * s[:, None]).reshape(-1, n).to(w.dtype)
    return out


MODEL = os.path.join(W, os.environ.get("MDIR", "qwen"))
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
base = {n: m.weight.detach().clone() for n, m in lins}
nl = max(layer_index(n) for n, _ in lins) + 1
fit = [(n, m) for n, m in lins if layer_index(n) < nl // 2]
test_ct = len(lins) - len(fit)
print(f"  model dir {os.path.basename(MODEL)}: {len(lins)} linear tensors over {nl} layers "
      f"({len(fit)} fit / {test_ct} held out)")

acc = np.zeros(NBIN)
kur = []
for n, m in fit:
    w = m.weight.detach().double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    h, _ = np.histogram((b[ok] / a[ok][:, None]).reshape(-1).numpy(), bins=NBIN, range=(-1, 1))
    acc += h
    x = w.reshape(-1)[:200000]
    kur.append(float(((x - x.mean()) ** 4).mean() / x.std() ** 4 - 3))
print(f"  median excess kurtosis of fit tensors: {float(np.median(kur)):+.2f}")

best = None
for j in range(6, 10):
    lv, d = dp_pinned(acc / (acc.sum() * (2.0 / NBIN)), {0: -1.0, 15: 1.0, j: 0.0})
    if best is None or d < best[1]:
        best = (lv, d, j)
DP16Z_OWN = best[0]
print(f"  DP-16+zero fitted to THIS model (zero at cell {best[2]}):")
print("    " + " ".join(f"{v:+.4f}" for v in DP16Z_OWN))
print(f"  max level difference vs the SmolLM2-derived table: "
      f"{float(np.max(np.abs(DP16Z_OWN - DP16Z_SMOL))):.4f}\n")


def ppl():
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[:NW]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


p0 = ppl()
print(f"RULER CHECK -- fp32 baseline {p0:.3f} ({NW} windows)")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible; refusing to compare.")
print(f"\n  {'codebook':<34}{'perplexity':>12}{'vs fp32':>10}{'vs best incumbent':>19}")
res = {}
for name, lv in (("E2M1 (correct)", E2M1), ("NF4 (real)", NF4),
                 ("DP-16+zero  from THIS model", DP16Z_OWN),
                 ("DP-16+zero  from SmolLM2 [transfer]", DP16Z_SMOL)):
    lvt = torch.tensor(lv, dtype=torch.float64)
    for n, m in lins:
        m.weight.copy_(quantise(base[n].double(), lvt).to(m.weight.dtype))
    p = ppl()
    res[name] = p
    inc = min(res.get("E2M1 (correct)", 9e9), res.get("NF4 (real)", 9e9))
    d = (inc - p) / (inc - p0) * 100 if inc < 9e9 and inc > p0 else float("nan")
    print(f"  {name:<34}{p:>12.3f}{p - p0:>+10.3f}"
          + (f"{d:>18.1f}%" if name.startswith("DP") else f"{'':>19}"))
for n, m in lins:
    m.weight.copy_(base[n])
print("\n  'vs best incumbent' = share of the better incumbent's degradation removed.")
