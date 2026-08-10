#!/usr/bin/env python3
"""Testing the stated cause of the refutation: is it the missing exact zero?

rebaseline2.py showed DP-16 has the LOWEST MSE and the WORST perplexity. The hypothesis offered
was that DP-16 has no exact zero -- its innermost levels are -0.048 and +0.051 -- while E2M1 has
exact 0 plus a subnormal at 0.083. LLM weight mass concentrates near zero, so forcing it to
+/-0.05 is a systematic bias that squared error prices cheaply and a language model does not.

That was a hypothesis. This tests it, by building the same DP optimum WITH a zero level.

A symmetric codebook containing zero spans 15 distinct values, so it wastes one of the 16 codes
-- exactly the inefficiency the signed DP-16 was built to remove. So this is a clean two-way
comparison of one property against the other:

    DP-16   uses all 16 codes, NO exact zero        MSE-optimal
    DP-15   wastes one code, HAS exact zero         MSE-suboptimal by construction

If the hypothesis is right, DP-15 should beat DP-16 on perplexity despite being MSE-worse --
which would be a second, independent inversion of the MSE ordering, and would identify
zero-representability as the property that matters.

If DP-15 does NOT beat DP-16, the hypothesis is wrong and the cause lies elsewhere; the honest
outcome is then to say so and stop guessing.
"""
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NBIN = 32, 2048, 1000
NW = int(os.environ.get("NW", "12"))
torch.set_grad_enabled(False)

NF4 = np.array([-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
                -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
                0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
                0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
                0.7229568362236023, 1.0])
MAGS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]          # E2M1 WITH its subnormal
E2M1 = np.array(sorted(set([-v / 6 for v in MAGS] + [v / 6 for v in MAGS])))
DP16 = np.array([-1.000, -0.792, -0.628, -0.488, -0.364, -0.252, -0.148, -0.048,
                 0.051, 0.152, 0.256, 0.367, 0.489, 0.628, 0.792, 1.000])


def dp_folded(dens_half, nlev=8):
    """DP over |y| in [0,1]: level 0 pinned at 0, top pinned at 1. Mirrored -> 15 values."""
    y = (np.arange(NBIN) + 0.5) / NBIN
    w = dens_half * (1.0 / NBIN)
    S0 = np.concatenate([[0.0], np.cumsum(w)])
    S1 = np.concatenate([[0.0], np.cumsum(w * y)])
    S2 = np.concatenate([[0.0], np.cumsum(w * y * y)])
    cfix = lambda a, b, r: (S2[b] - S2[a]) - 2 * r * (S1[b] - S1[a]) + r * r * (S0[b] - S0[a])

    def cfree(a, b):
        s0, s1 = S0[b] - S0[a], S1[b] - S1[a]
        return np.where(s0 > 0, (S2[b] - S2[a]) - s1 * s1 / np.maximum(s0, 1e-300), 0.0)

    M = NBIN
    f = np.full((nlev, M + 1), np.inf)
    bk = np.zeros((nlev, M + 1), dtype=int)
    f[0] = cfix(0, np.arange(M + 1), 0.0)
    for k in range(1, nlev - 1):
        prev = f[k - 1]
        for i in range(1, M + 1):
            j = np.arange(0, i)
            c = prev[j] + cfree(j, i)
            t = int(np.argmin(c))
            f[k][i], bk[k][i] = c[t], t
    j = np.arange(0, M + 1)
    tail = f[nlev - 2][j] + cfix(j, M, 1.0)
    js = int(np.nanargmin(tail))
    bounds, cur, k = [M, js], js, nlev - 2
    while k >= 1:
        cur = bk[k][cur]
        bounds.append(cur)
        k -= 1
    bounds = sorted(set(bounds + [0]))
    while len(bounds) < nlev + 1:
        bounds.append(M)
    bounds = sorted(bounds)
    lv = []
    for c in range(nlev):
        a, b = bounds[c], bounds[c + 1]
        if c == 0:
            lv.append(0.0)
        elif c == nlev - 1:
            lv.append(1.0)
        else:
            s0 = S0[b] - S0[a]
            lv.append(float((S1[b] - S1[a]) / s0) if s0 > 0 else float(y[min(a, M - 1)]))
    return np.array(sorted(set([-v for v in lv] + lv)))


def quantise(w, lv):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    s = b.abs().amax(dim=1).clamp(min=1e-30)
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
base = {n: m.weight.detach().clone() for n, m in lins}

acc = np.zeros(NBIN)
for n, m in lins[: len(lins) // 2]:
    w = m.weight.detach().double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    h, _ = np.histogram((b[ok] / a[ok][:, None]).abs().reshape(-1).numpy(),
                        bins=NBIN, range=(0, 1))
    acc += h
DP15 = dp_folded(acc / (acc.sum() * (1.0 / NBIN)), 8)


def mse_of(lv):
    tot = 0.0
    for n, m in lins[len(lins) // 2:]:
        w = m.weight.detach().double()
        nn_ = (w.shape[1] // K) * K
        if nn_ == 0:
            continue
        b = w[:, :nn_].reshape(-1, K)
        a = b.abs().amax(1)
        ok = a > 0
        b, a = b[ok], a[ok]
        idx = torch.bucketize(b / a[:, None], (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
        tot += float(((lv[idx] * a[:, None] - b) ** 2).mean())
    return tot


def ppl():
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[:NW]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


p0 = ppl()
print(f"RULER CHECK -- fp32 baseline {p0:.3f} ({NW} windows)")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible")
print(f"\n  DP-15 (zero pinned, {len(DP15)} values): "
      + " ".join(f"{v:+.3f}" for v in DP15))
print(f"  DP-16 (no zero, {len(DP16)} values), E2M1 ({len(E2M1)} values), NF4 ({len(NF4)})\n")

CASES = [("E2M1 (correct)", E2M1), ("NF4 (real)", NF4),
         ("DP-16  all codes, NO zero", DP16), ("DP-15  zero pinned, 1 code wasted", DP15)]
print(f"  {'codebook':<36}{'has 0':>7}{'MSE rel E2M1':>14}{'perplexity':>12}{'vs fp32':>10}")
ref = None
for name, lv in CASES:
    lvt = torch.tensor(lv, dtype=torch.float64)
    m_ = mse_of(lvt)
    if ref is None:
        ref = m_
    for n, m in lins:
        m.weight.copy_(quantise(base[n].double(), lvt).to(m.weight.dtype))
    p = ppl()
    hz = "yes" if np.min(np.abs(lv)) < 1e-12 else "NO"
    print(f"  {name:<36}{hz:>7}{m_/ref:>14.4f}{p:>12.3f}{p - p0:>+10.3f}")
for n, m in lins:
    m.weight.copy_(base[n])
print("\n  Hypothesis: DP-15 should beat DP-16 on perplexity DESPITE being MSE-worse.")
