#!/usr/bin/env python3
"""Re-baselining honestly, after two competitor implementations were found to be wrong.

TWO ERRORS FOUND BY AUDITING COMPETITORS AGAINST THEIR SOURCES INSTEAD OF MEMORY:

  (1) The MX scale rule. I implemented ceiling-rounded E8M0 and called it the spec. The
      reference implementation (microsoft/microxcaling, mx/mx_ops.py) does:

          shared_exp = floor(log2(max|A|));  shared_exp -= emax;  A = A / 2**shared_exp

      A FLOOR, then minus emax (2 for E2M1, whose max normal is 6 = 1.5*2^2), with elements
      clamped to max_norm afterwards. So amax/X lands in [4,8) and clips whenever it exceeds
      6. My ceiling version always grew the scale -- the worst region of D(r) -- and therefore
      overstated MXFP4's cost.

  (2) NF4. I used my own SYMMETRIC 8-magnitude reconstruction of "the NF4 principle". Real NF4
      (bitsandbytes get_4bit_type) is ASYMMETRIC with 16 distinct values:

          -1.0, -0.6961928, -0.5250731, -0.3949175, -0.2844414, -0.1847734, -0.0910500, 0.0,
           0.0795803, 0.1609302, 0.2461123, 0.3379152, 0.4407098, 0.5626170, 0.7229568, 1.0

      My reconstruction was a different, weaker format.

AND AN ERROR IN OUR OWN FAVOUR'S OPPOSITE DIRECTION -- a handicap we imposed on ourselves:
a symmetric 8-magnitude codebook spans only 15 distinct values, so one of the 16 codes is
WASTED. NF4 uses all 16 by being asymmetric. To compare fairly, the DP must run over the
SIGNED density with 16 free levels, ends pinned at -1 and +1 (either sign can be the block
maximum, so both must be representable).

This script rebuilds the headline comparison with all three fixed.
"""
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN = 32, 2048
NW = int(os.environ.get("NW", "16"))
NBIN = 1200                                   # bins over [-1, 1]
torch.set_grad_enabled(False)

NF4 = np.array([-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
                -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
                0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
                0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
                0.7229568362236023, 1.0])


def fp_levels_signed(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    pos = sorted(out)
    top = max(pos)
    lv = sorted(set([-v / top for v in pos] + [v / top for v in pos]))
    return np.array(lv)


E2M1 = fp_levels_signed(2, 1)                 # 15 distinct values; one code unused
INT4 = np.array(sorted(set([-i / 7 for i in range(8)] + [i / 7 for i in range(8)])))


# ------------------------------------------------------------------ scales
def scale_ocp(amax, top, emax):
    """OCP MX: X = 2^(floor(log2 amax) - emax). Elements clamp to the format max afterwards."""
    E = torch.floor(torch.log2(amax.clamp(min=1e-30)))
    return torch.pow(2.0, E - emax) * top     # expressed in units where the top level is 1


def scale_absmax(amax, top, emax):
    return amax


def scale_ue4m3(amax, top, emax):
    s = amax.clamp(min=1e-30)
    e = torch.floor(torch.log2(s)).clamp(-6, 8)
    m = torch.round((s / torch.pow(2.0, e) - 1.0) * 8).clamp(0, 8)
    e = e + (m == 8).to(e.dtype)
    m = torch.where(m == 8, torch.zeros_like(m), m)
    return (1 + m / 8) * torch.pow(2.0, e)


def quantise(w, lv, scale_fn, emax=2.0):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    amax = b.abs().amax(dim=1)
    s = scale_fn(amax, float(lv.max()), emax).clamp(min=1e-30)
    y = b / s[:, None]
    idx = torch.bucketize(y, (lv[:-1] + lv[1:]) / 2)
    rec = lv[idx.clamp(0, len(lv) - 1)] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


# ------------------------------------------------------------------ signed DP
def dp_signed(dens, nlev=16):
    """Exact optimum over the SIGNED density on [-1,1], ends pinned at -1 and +1."""
    y = np.linspace(-1, 1, NBIN, endpoint=False) + 1.0 / NBIN
    dy = 2.0 / NBIN
    w = dens * dy
    S0 = np.concatenate([[0.0], np.cumsum(w)])
    S1 = np.concatenate([[0.0], np.cumsum(w * y)])
    S2 = np.concatenate([[0.0], np.cumsum(w * y * y)])

    def cfix(a, b, r):
        return (S2[b] - S2[a]) - 2 * r * (S1[b] - S1[a]) + r * r * (S0[b] - S0[a])

    def cfree(a, b):
        s0 = S0[b] - S0[a]
        s1 = S1[b] - S1[a]
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

# signed p_eff from the first half of the layers; measured on the rest via perplexity
acc = np.zeros(NBIN)
for n, m in lins[: len(lins) // 2]:
    w = m.weight.detach().double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    y = (b[ok] / a[ok][:, None]).reshape(-1).numpy()
    h, _ = np.histogram(y, bins=NBIN, range=(-1, 1))
    acc += h
acc = acc / (acc.sum() * (2.0 / NBIN))
DP16 = dp_signed(acc, 16)


def ppl():
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[:NW]
    nll = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += model(c, labels=c).loss.double().item()
    return float(np.exp(nll / x.shape[0]))


p0 = ppl()
print(f"RULER CHECK -- fp32 baseline perplexity {p0:.3f} ({NW} windows)")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible; refusing to compare.")
print(f"\n  DP-16 signed optimum (all 16 codes used):")
print("   " + " ".join(f"{v:+.4f}" for v in DP16))
print(f"  E2M1 has {len(E2M1)} distinct values (one code wasted); NF4 has {len(NF4)}\n")

CASES = [
    ("E2M1 + OCP MX rule  [TRUE MXFP4]", E2M1, scale_ocp),
    ("E2M1 + UE4M3 scale", E2M1, scale_ue4m3),
    ("int4 + absmax", INT4, scale_absmax),
    ("NF4 (real, bitsandbytes) + absmax", NF4, scale_absmax),
    ("DP-16 + OCP MX rule", DP16, scale_ocp),
    ("DP-16 + absmax", DP16, scale_absmax),
    ("DP-16 + UE4M3 scale", DP16, scale_ue4m3),
]
print(f"  {'configuration':<38}{'perplexity':>12}{'vs fp32':>10}{'vs TRUE MXFP4':>15}")
mx = None
for name, lv, fn in CASES:
    lvt = torch.tensor(lv, dtype=torch.float64)
    for n, m in lins:
        m.weight.copy_(quantise(base[n].double(), lvt, fn).to(m.weight.dtype))
    p = ppl()
    if mx is None:
        mx = p
    print(f"  {name:<38}{p:>12.3f}{p - p0:>+10.3f}{mx - p:>+15.3f}")
for n, m in lins:
    m.weight.copy_(base[n])
print("\n  'vs TRUE MXFP4' is perplexity recovered against the correctly-implemented spec.")
