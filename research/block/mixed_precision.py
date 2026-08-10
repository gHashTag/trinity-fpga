#!/usr/bin/env python3
"""Exploiting the 42x sensitivity spread where it CAN be exploited: bit allocation.

weighted_dp.py established that sensitivity weighting cannot help CODEBOOK design, and why:
p_eff has essentially the same shape in every layer (the universality result), so re-weighting
layers by 39.5x leaves the aggregate density -- and therefore the optimal codebook -- unchanged
to four decimal places. Codebook shape is the wrong lever for a per-layer effect.

Bit ALLOCATION is the right one. Block 5 costs 0.0097 perplexity to quantise and block 29 costs
0.4070. Spending a bit more on block 29 and a bit less on block 5 is free at constant average
width, and the profile says exactly where.

FAIR ACCOUNTING. Every configuration below uses the SAME average element width. N blocks get
5 bits and N blocks get 3 bits, the rest 4, so the mean is exactly 4.000 bits/element. The block
scale is identical across configurations and cancels. Nothing is being smuggled in.

PRE-REGISTERED PREDICTION: allocation by measured sensitivity beats uniform 4-bit, and beats
allocation by MSE (which the profile showed is nearly uncorrelated with damage, r=+0.13). The
MSE-allocated arm is the control that makes the result meaningful -- if it does just as well,
then any non-uniform allocation would have worked and the profile added nothing.
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
K, SEQLEN, NBIN = 32, 2048, 800
torch.set_grad_enabled(False)

DPPL = np.array([0.0952, 0.0973, 0.1083, 0.0695, 0.0401, 0.0097, 0.0572, 0.0358, 0.0383,
                 0.0256, 0.0469, 0.0960, 0.0706, 0.0691, 0.0993, 0.0661, 0.0812, 0.1113,
                 0.1507, 0.1237, 0.1742, 0.0614, 0.0762, 0.1165, 0.0579, 0.0563, 0.1160,
                 0.0774, 0.1311, 0.4070])
MSE_L = np.array([1438.1943, 1335.6018, 1292.0653, 1306.3311, 1288.1378, 1265.5231, 1302.6299,
                  1273.9641, 1284.8257, 1322.5296, 1346.4854, 1344.9005, 1325.1743, 1318.0615,
                  1283.0718, 1292.2842, 1339.4485, 1299.7285, 1253.3065, 1329.1526, 1307.0804,
                  1315.7523, 1355.9736, 1421.8265, 1403.1751, 1420.1261, 1432.8625, 1397.1226,
                  1432.9144, 1342.9496])


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def dp_pinned(dens, nlev):
    """Ends pinned at +/-1 and the middle cell at 0, as established to matter."""
    pins = {0: -1.0, nlev - 1: 1.0, nlev // 2 - 1: 0.0}
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
    return np.array(sorted(set(np.round(lv, 12))))


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


tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
BASE = {n: m.weight.detach().clone() for n, m in lins}
NL = max(layer_index(n) for n, _ in lins) + 1

hist = np.zeros(NBIN)
for n, m in lins:
    w = BASE[n].double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    hist += np.histogram((b[ok] / a[ok][:, None]).reshape(-1).numpy(),
                         bins=NBIN, range=(-1, 1))[0]
dens = hist / (hist.sum() * (2.0 / NBIN))
CB = {3: dp_pinned(dens, 8), 4: dp_pinned(dens, 16), 5: dp_pinned(dens, 32)}
print("  derived codebooks: "
      + ", ".join(f"{b}-bit -> {len(CB[b])} levels" for b in sorted(CB)))


def ppl(lo, hi):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[lo:hi]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


def apply_alloc(bits_per_block):
    for n, m in lins:
        lv = torch.tensor(CB[bits_per_block[layer_index(n)]], dtype=torch.float64)
        m.weight.copy_(quantise(BASE[n].double(), lv).to(m.weight.dtype))


LO, HI = 6, 18
p0 = ppl(LO, HI)
print(f"\nRULER CHECK -- fp32 baseline {p0:.4f} (windows {LO}-{HI-1})")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible")

print(f"\n  {'allocation':<40}{'avg bits':>10}{'perplexity':>12}{'vs fp32':>10}")
results = {}
for label, key, nswap in (("uniform 4-bit", None, 0),
                          ("by SENSITIVITY  (6 up / 6 down)", DPPL, 6),
                          ("by SENSITIVITY  (10 up / 10 down)", DPPL, 10),
                          ("by MSE  (10 up / 10 down)  [control]", MSE_L, 10),
                          ("by SENSITIVITY, REVERSED  [control]", -DPPL, 10)):
    bits = np.full(NL, 4)
    if nswap:
        order = np.argsort(key)
        bits[order[:nswap]] = 3
        bits[order[-nswap:]] = 5
    apply_alloc(bits)
    p = ppl(LO, HI)
    results[label] = p
    print(f"  {label:<40}{bits.mean():>10.3f}{p:>12.4f}{p - p0:>+10.4f}")
for n, m in lins:
    m.weight.copy_(BASE[n])

u = results["uniform 4-bit"] - p0
best = min(k for k in results if k != "uniform 4-bit")
print("\n  share of uniform-4-bit degradation removed, at IDENTICAL average width:")
for k, v in results.items():
    if k != "uniform 4-bit":
        print(f"    {k:<40}{(1 - (v - p0) / u) * 100:>7.1f}%")
