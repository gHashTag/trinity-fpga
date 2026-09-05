#!/usr/bin/env python3
"""The honest re-baseline, after THREE competitor-implementation bugs, all flattering us.

  BUG 1 -- MX scale rule. I used ceiling-rounded E8M0. The reference implementation
    (microsoft/microxcaling) does floor(log2 max) - emax. Ceiling always grows the scale, the
    worst region of D(r).

  BUG 2 -- NF4. I used my own symmetric 8-magnitude reconstruction. Real NF4 (bitsandbytes
    get_4bit_type) is asymmetric with 16 distinct values.

  BUG 3 -- E2M1 ITSELF, and this one is in EVERY table in this document. My level generator
    emits only normal numbers, so it produced

        {0, 1, 1.5, 2, 3, 4, 6}          7 magnitudes, 13 signed values

    where the OCP element format is

        {0, 0.5, 1, 1.5, 2, 3, 4, 6}     8 magnitudes, 15 signed values

    The missing 0.5 is the SUBNORMAL. Every "X% better than MXFP4" figure was measured against
    a crippled E2M1 that had lost a level.

  AND a handicap we imposed on ourselves: a symmetric magnitude codebook spans 15 values, so
  one of the 16 codes is wasted. The DP therefore runs over the SIGNED density with 16 free
  levels, ends pinned at +/-1.

The correct MX scale in normalised units. MX sets X = 2^(floor(log2 amax) - emax) so that
amax/X carries the format's own maximum exponent. With levels normalised to a top of 1, the
equivalent scale is

    s = (max_norm / 2^emax) * 2^floor(log2 amax) = 1.5 * 2^floor(log2 amax)   for E2M1

which reproduces the spec's ratio r = 1.5/m exactly, m being the mantissa of amax. My previous
attempt dropped the max_norm factor entirely, divided every element into [4,8) against levels
topping out at 1, and clipped the whole tensor -- hence perplexity 3e9. That was a bug, not a
measurement, and is not reported as one.
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


def fp_mags(eb, mb):
    """Element magnitudes INCLUDING subnormals -- the bug that cost E2M1 its 0.5."""
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for m in range(1, 1 << mb):                       # subnormals
        out.add((m / (1 << mb)) * 2.0 ** (1 - bias))
    for e in range(1 - bias, (1 << eb) - bias):       # normals
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)


E2M1_MAGS = fp_mags(2, 1)
E2M1_MAXNORM = max(E2M1_MAGS)
E2M1 = np.array(sorted(set([-v / E2M1_MAXNORM for v in E2M1_MAGS]
                           + [v / E2M1_MAXNORM for v in E2M1_MAGS])))
INT4 = np.array(sorted(set([-i / 7 for i in range(8)] + [i / 7 for i in range(8)])))
MX_C = E2M1_MAXNORM / 2.0 ** 2                        # 6/4 = 1.5


def scale_mx(amax, c=MX_C):
    return c * torch.pow(2.0, torch.floor(torch.log2(amax.clamp(min=1e-30))))


def scale_absmax(amax, c=None):
    return amax


def scale_ue4m3(amax, c=None):
    s = amax.clamp(min=1e-30)
    e = torch.floor(torch.log2(s)).clamp(-6, 8)
    m = torch.round((s / torch.pow(2.0, e) - 1.0) * 8).clamp(0, 8)
    e = e + (m == 8).to(e.dtype)
    m = torch.where(m == 8, torch.zeros_like(m), m)
    return (1 + m / 8) * torch.pow(2.0, e)


def quantise(w, lv, scale_fn):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    s = scale_fn(b.abs().amax(dim=1)).clamp(min=1e-30)
    idx = torch.bucketize(b / s[:, None], (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
    out = w.clone()
    out[:, :n] = (lv[idx] * s[:, None]).reshape(-1, n).to(w.dtype)
    return out


def dp_signed(dens, nlev=16):
    y = np.linspace(-1, 1, NBIN, endpoint=False) + 1.0 / NBIN
    dy, w = 2.0 / NBIN, dens * (2.0 / NBIN)
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
    f[0] = cfix(0, np.arange(M + 1), -1.0)
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
            lv.append(-1.0)
        elif c == nlev - 1:
            lv.append(1.0)
        else:
            s0 = S0[b] - S0[a]
            lv.append(float((S1[b] - S1[a]) / s0) if s0 > 0 else float(y[min(a, M - 1)]))
    return np.array(sorted(lv))


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
    h, _ = np.histogram((b[ok] / a[ok][:, None]).reshape(-1).numpy(), bins=NBIN, range=(-1, 1))
    acc += h
DP16 = dp_signed(acc / (acc.sum() * (2.0 / NBIN)), 16)


def ppl():
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[:NW]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


p0 = ppl()
print(f"RULER CHECK -- fp32 baseline {p0:.3f} ({NW} windows)")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible")
print(f"\n  E2M1 magnitudes (subnormal restored): {E2M1_MAGS}")
print(f"  E2M1 signed values: {len(E2M1)}   NF4: {len(NF4)}   DP-16: {len(DP16)}")
print(f"  DP-16: " + " ".join(f"{v:+.3f}" for v in DP16) + "\n")

CASES = [
    ("E2M1 + MX scale rule  [TRUE MXFP4]", E2M1, scale_mx),
    ("E2M1 + UE4M3", E2M1, scale_ue4m3),
    ("E2M1 + absmax (exact scale)", E2M1, scale_absmax),
    ("int4 + absmax", INT4, scale_absmax),
    ("NF4 (real) + absmax", NF4, scale_absmax),
    ("DP-16 + MX scale rule", DP16, scale_mx),
    ("DP-16 + UE4M3", DP16, scale_ue4m3),
    ("DP-16 + absmax", DP16, scale_absmax),
]
print(f"  {'configuration':<38}{'perplexity':>12}{'vs fp32':>10}{'vs MXFP4':>11}")
mx = None
for name, lv, fn in CASES:
    lvt = torch.tensor(lv, dtype=torch.float64)
    for n, m in lins:
        m.weight.copy_(quantise(base[n].double(), lvt, fn).to(m.weight.dtype))
    p = ppl()
    if mx is None:
        mx = p
    print(f"  {name:<38}{p:>12.3f}{p - p0:>+10.3f}{mx - p:>+11.3f}")
for n, m in lins:
    m.weight.copy_(base[n])
