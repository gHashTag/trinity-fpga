#!/usr/bin/env python3
"""Does per-layer damage scale as 2^(-2b)? The assumption the break-even criterion died on.

mixed_precision.py proposed: swapping one bit between two groups pays iff the promoted group's
damage exceeds the demoted group's by more than 2^(2*1) = 4. It predicted correctly at n=10 and
FAILED at n=6 (ratio 5.62 > 4, predicted a 0.238 gain, lost 0.280).

The criterion rests on one unmeasured assumption: that changing a layer's bit-width by one scales
its perplexity damage by four, the classical 6 dB/bit rule. If demotion to 3 bits instead crosses
a CLIFF -- damage growing far faster than 4x -- then mixed precision failed because the demotion
side is far more expensive than the promotion side is cheap, and the criterion needs the real
scaling curve rather than 2^(2*db).

This measures that curve directly: eight blocks spanning the whole sensitivity range, each
quantised alone at 3, 4 and 5 bits.

WHAT WOULD RESCUE MIXED PRECISION: if the ratio D(3)/D(4) is close to 4 and D(5)/D(4) close to
1/4, the classical rule holds and mixed precision genuinely cannot pay at this spread. If instead
D(3)/D(4) is much larger than 4, the demotion penalty is the culprit -- and allocating between
4 and 5 bits only (never demoting below 4) would be worth testing.

WHAT WOULD KILL IT FOR GOOD: ratios that are large AND erratic across layers, meaning no simple
allocation rule exists.
"""
import os
import re
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NBIN = 32, 2048, 800
torch.set_grad_enabled(False)

# blocks spanning the measured sensitivity range, least to most sensitive
BLOCKS = [5, 9, 7, 24, 12, 16, 20, 29]


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def dp_pinned(dens, nlev):
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
CB = {b: dp_pinned(dens, 1 << b) for b in (3, 4, 5)}
print("  codebooks: " + ", ".join(f"{b}-bit={len(CB[b])} levels" for b in sorted(CB)))


def ppl(lo=0, hi=6):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[lo:hi]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


p0 = ppl()
print(f"\nRULER CHECK -- fp32 baseline {p0:.4f}")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible")

print(f"\n  {'block':>6}{'D(3bit)':>10}{'D(4bit)':>10}{'D(5bit)':>10}"
      f"{'D3/D4':>9}{'D4/D5':>9}")
r34, r45 = [], []
for bi in BLOCKS:
    names = [n for n, _ in lins if layer_index(n) == bi]
    d = {}
    for bits in (3, 4, 5):
        lv = torch.tensor(CB[bits], dtype=torch.float64)
        for n, m in lins:
            if n in names:
                m.weight.copy_(quantise(BASE[n].double(), lv).to(m.weight.dtype))
        d[bits] = ppl() - p0
        for n, m in lins:
            m.weight.copy_(BASE[n])
    a = d[3] / d[4] if d[4] > 1e-9 else float("nan")
    b_ = d[4] / d[5] if d[5] > 1e-9 else float("nan")
    r34.append(a)
    r45.append(b_)
    print(f"  {bi:>6}{d[3]:>10.4f}{d[4]:>10.4f}{d[5]:>10.4f}{a:>9.2f}{b_:>9.2f}")

r34 = np.array(r34)
r45 = np.array(r45)
print(f"\n  classical 6 dB/bit rule predicts both ratios = 4.00")
print(f"  D3/D4  median {np.nanmedian(r34):.2f}   range {np.nanmin(r34):.2f}-{np.nanmax(r34):.2f}")
print(f"  D4/D5  median {np.nanmedian(r45):.2f}   range {np.nanmin(r45):.2f}-{np.nanmax(r45):.2f}")
asym = np.nanmedian(r34) / np.nanmedian(r45)
print(f"\n  demotion/promotion asymmetry: {asym:.2f}x")
if asym > 1.3:
    print("  => DEMOTION IS THE CULPRIT. Dropping a bit costs more than gaining one saves,")
    print("     so any constant-width swap starts behind. Allocating only between 4 and 5")
    print("     bits (never demoting) is the version worth testing.")
elif asym < 0.77:
    print("  => promotion is worth more than demotion costs; the failure lies elsewhere.")
else:
    print("  => roughly symmetric: the classical rule holds and mixed precision genuinely")
    print("     cannot pay at this sensitivity spread. The criterion's failure is elsewhere.")
