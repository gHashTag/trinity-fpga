#!/usr/bin/env python3
"""Testing the prediction the universality correction generated -- and a claim of mine that
looks backwards.

The corrected universality statement says p_eff varies smoothly but SLOWLY with tail weight,
and real LLM weights merely occupy a narrow band of it. Its falsifiable consequence: on data
that is genuinely heavy-tailed, the fixed weight-derived table should visibly degrade.

Two things to settle.

(A) A CLAIM OF MINE THAT IS PROBABLY WRONG. The correction section offered "post-rotation
    tensors" as the example of heavy-tailed data. That is almost certainly backwards: a
    Hadamard rotation mixes coordinates, and by the central limit heuristic that makes a
    distribution MORE Gaussian, not less -- which is precisely why QuaRot/QuIP use it to
    REMOVE outliers before quantisation. If so, rotation LOWERS kurtosis and my example was
    exactly inverted. Measured here rather than argued.

(B) WHERE THE HEAVY TAILS ACTUALLY ARE: ACTIVATIONS. LLM activations are famously
    outlier-dominated -- that is the entire motivation for LLM.int8(), SmoothQuant and AWQ.
    MX quantises activations too, so this is a real deployment surface and not a synthetic
    stress test. If the fixed table degrades anywhere, it degrades here.

The test that could falsify the corrected claim: if the weight-derived table does just as well
on heavy-tailed activations as an activation-derived table, then p_eff really is insensitive to
tail weight, the correction was too pessimistic, and the original contraction claim deserves
revisiting.
"""
import math
import os

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NBIN = 32, 2048, 2000
DY = 1.0 / NBIN
Y = (np.arange(NBIN) + 0.5) * DY
torch.set_grad_enabled(False)


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for m in range(1, 1 << mb):                      # SUBNORMALS -- the level E2M1 was missing
        out.add((m / (1 << mb)) * 2.0 ** (1 - bias))
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = np.array(sorted(out))
    return lv / lv.max()


def nf4_levels():
    from statistics import NormalDist
    nd = NormalDist()
    lv = np.array([0.0] + [nd.inv_cdf(0.5 + 0.5 * (i + 0.5) / 8) for i in range(1, 8)])
    return lv / lv.max()


def dp_optimum(w, nlev=8):
    """Exact constrained optimum for a discretised density (see exact_optimum.py)."""
    Wt = w * DY
    S0 = np.concatenate([[0.0], np.cumsum(Wt)])
    S1 = np.concatenate([[0.0], np.cumsum(Wt * Y)])
    S2 = np.concatenate([[0.0], np.cumsum(Wt * Y * Y)])

    def cf(a, b, r):
        return (S2[b] - S2[a]) - 2 * r * (S1[b] - S1[a]) + r * r * (S0[b] - S0[a])

    def cfree(a, b):
        s0 = S0[b] - S0[a]
        s1 = S1[b] - S1[a]
        return np.where(s0 > 0, (S2[b] - S2[a]) - s1 * s1 / np.maximum(s0, 1e-300), 0.0)

    M = NBIN
    idx = np.arange(M + 1)
    f = np.full((nlev, M + 1), np.inf)
    bk = np.zeros((nlev, M + 1), dtype=int)
    f[0] = cf(0, idx, 0.0)
    for k in range(1, nlev - 1):
        prev = f[k - 1]
        for i in range(1, M + 1):
            j = np.arange(0, i)
            c = prev[j] + cfree(j, i)
            t = int(np.argmin(c))
            f[k][i] = c[t]
            bk[k][i] = t
    j = np.arange(0, M + 1)
    tail = f[nlev - 2][j] + cf(j, M, 1.0)
    js = int(np.nanargmin(tail))
    bounds = [M, js]
    cur, k = js, nlev - 2
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
            lv.append(float((S1[b] - S1[a]) / s0) if s0 > 0 else float(Y[min(a, NBIN - 1)]))
    return np.array(lv)


def residual_density(t):
    """p_eff from a 2-D tensor, blocks along the last axis."""
    n = (t.shape[1] // K) * K
    if n == 0:
        return None
    b = t[:, :n].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    b, a = b[ok], a[ok]
    y = (b / a[:, None]).abs().reshape(-1).numpy()
    h, _ = np.histogram(y, bins=NBIN, range=(0, 1))
    h = h.astype(np.float64)
    return h / (h.sum() * DY)


def mse(t, lv):
    n = (t.shape[1] // K) * K
    b = t[:, :n].reshape(-1, K).double()
    a = b.abs().amax(1)
    ok = a > 0
    b, a = b[ok], a[ok]
    s = a / lv[-1]
    mag = (b / s[:, None]).abs().numpy()
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, mag)
    rec = np.sign(b.numpy()) * lv[idx] * s[:, None].numpy()
    return float(((rec - b.numpy()) ** 2).mean())


def kurt(x):
    x = x.reshape(-1).double()
    m, s = x.mean(), x.std()
    return float(((x - m) ** 4).mean() / s ** 4 - 3) if s > 0 else float("nan")


def hadamard(n):
    assert n & (n - 1) == 0
    H = np.array([[1.0]])
    while H.shape[0] < n:
        H = np.block([[H, H], [H, -H]])
    return torch.tensor(H / math.sqrt(n))


tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0][: 2 * SEQLEN].view(2, SEQLEN)

lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]

# ---------------------------------------------------------------- (A) rotation direction
print("(A) Does a Hadamard rotation make weights heavier- or lighter-tailed?\n")
print(f"  {'tensor':<34}{'kurt before':>13}{'kurt after':>12}{'direction':>12}")
rows = 0
dk = []
for n, m in lins[:8]:
    w = m.weight.detach().double()
    d = w.shape[1]
    # SmolLM2's dims (576, 1536) are not powers of two, so an exact-size Hadamard does not
    # exist. The first version skipped every layer and printed an empty table -- a silent
    # skip that looks identical to "no effect". Rotate the largest power-of-two prefix instead.
    p = 1 << (d.bit_length() - 1)
    H = hadamard(p)
    wr = w[:, :p] @ H
    k0, k1 = kurt(w[:, :p]), kurt(wr)
    dk.append(k1 - k0)
    print(f"  {n[-32:]:<34}{k0:>13.3f}{k1:>12.3f}{'LIGHTER' if k1 < k0 else 'heavier':>12}")
    rows += 1
if rows:
    md = float(np.median(dk))
    print(f"\n  median kurtosis change: {md:+.3f}")
    if md < 0:
        print("  => Rotation makes weights LIGHTER-tailed, as QuaRot/QuIP intend.")
        print("     My correction section named 'post-rotation tensors' as an example of")
        print("     HEAVY-tailed data. That was exactly backwards and is retracted.")
    else:
        print("  => Rotation increased kurtosis here; the original example stands.")

# ---------------------------------------------------------------- (B) activations
print("\n(B) The real heavy tails: ACTIVATIONS\n")
caps = {}
hooks = []


def mk(name):
    def h(mod, inp, out):
        if name not in caps:
            a = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
            caps[name] = a[: 4096].clone()
    return h


for n, m in lins:
    hooks.append(m.register_forward_hook(mk(n)))
model(ids[0:1])
for h in hooks:
    h.remove()

wdens = np.zeros(NBIN)
for n, m in lins:
    d = residual_density(m.weight.detach().double())
    if d is not None:
        wdens += d
wdens /= (wdens.sum() * DY)
LV_WEIGHT = dp_optimum(wdens)

adens = np.zeros(NBIN)
for n, a in caps.items():
    d = residual_density(a)
    if d is not None:
        adens += d
adens /= (adens.sum() * DY)
LV_ACT = dp_optimum(adens)

kw = float(np.median([kurt(m.weight.detach()) for _, m in lins]))
ka = float(np.median([kurt(a) for a in caps.values()]))
print(f"  median excess kurtosis -- weights {kw:+.2f}   activations {ka:+.2f}")
print(f"  weight-derived table      " + " ".join(f"{v:.4f}" for v in LV_WEIGHT))
print(f"  activation-derived table  " + " ".join(f"{v:.4f}" for v in LV_ACT))
print(f"  table distance (interior levels): "
      f"{float(np.mean(np.abs(LV_WEIGHT[1:7] - LV_ACT[1:7]))):.5f}")

E2M1, NF4, INT4 = fp_levels(2, 1), nf4_levels(), np.array([i / 7 for i in range(8)])
tot = {k: 0.0 for k in ("e2m1", "int4", "nf4", "weight-table", "activation-table")}
for n, a in caps.items():
    if a.shape[1] < K:
        continue
    tot["e2m1"] += mse(a, E2M1)
    tot["int4"] += mse(a, INT4)
    tot["nf4"] += mse(a, NF4)
    tot["weight-table"] += mse(a, LV_WEIGHT)
    tot["activation-table"] += mse(a, LV_ACT)
ref = tot["e2m1"]
print(f"\n  MSE on ACTIVATIONS, relative to E2M1:")
for k, v in tot.items():
    print(f"    {k:<20}{v/ref:>8.4f}")
pen = (tot["weight-table"] - tot["activation-table"]) / tot["activation-table"] * 100
print(f"\n  penalty for reusing the WEIGHT table on activations: {pen:+.3f}%")
if pen > 2.0:
    print("  => the fixed table DOES degrade on heavy-tailed data, as the corrected")
    print("     universality claim predicts. Per-surface tables are needed.")
else:
    print("  => the fixed table does NOT meaningfully degrade even on heavy-tailed")
    print("     activations. The corrected claim was too pessimistic; p_eff is more robust")
    print("     to tail weight than the kurtosis-slope calibration suggested.")
