#!/usr/bin/env python3
"""Re-deriving the real-weights claim against a CORRECT E2M1, with layer order pinned.

Two defects are fixed here at once.

  * E2M1 was missing its subnormal (0.5), so it measured 37% worse than the real format. The
    "41.9% below MXFP4 on real weights" headline was computed against that crippled version.

  * Layer selection was left to container order. One script enumerated tensors by
    alphabetically-sorted safetensors keys, another by module order; "layers.10" sorts before
    "layers.2", so "the held-out half" meant a different set of layers in each, and two of our
    MSE tables silently disagreed by a factor of 1.6. Here the split is by explicit LAYER INDEX
    parsed from the name, so it is reproducible and means what it says.

Reported alongside is what the same table looked like with the bug, so the size of the
correction is visible rather than quietly absorbed.
"""
import json
import os
import re
import struct

import numpy as np

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K, NBIN = 32, 2000
DY = 1.0 / NBIN


def st_open(p):
    f = open(p, "rb")
    n = struct.unpack("<Q", f.read(8))[0]
    return f, json.loads(f.read(n)), 8 + n


def st_tensor(f, h, b, nm):
    e = h[nm]
    s, t = e["data_offsets"]
    f.seek(b + s)
    raw = f.read(t - s)
    if e["dtype"] == "BF16":
        return ((np.frombuffer(raw, dtype="<u2").astype(np.uint32) << 16)
                .view(np.float32).reshape(e["shape"]))
    if e["dtype"] == "F32":
        return np.frombuffer(raw, dtype="<f4").reshape(e["shape"])
    return np.frombuffer(raw, dtype="<f2").astype(np.float32).reshape(e["shape"])


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def fp_mags(eb, mb, subnormals=True):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    if subnormals:
        for m in range(1, 1 << mb):
            out.add((m / (1 << mb)) * 2.0 ** (1 - bias))
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = np.array(sorted(out))
    return lv / lv.max()


def signed(mags):
    return np.array(sorted(set([-v for v in mags] + list(mags))))


E2M1 = signed(fp_mags(2, 1, True))                 # correct: 15 values
E2M1_BUG = signed(fp_mags(2, 1, False))            # what every earlier table used: 13 values
INT4 = signed(np.array([i / 7 for i in range(8)]))
NF4 = np.array([-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
                -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
                0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
                0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
                0.7229568362236023, 1.0])


def dp_folded(dens, nlev=8):
    y = (np.arange(NBIN) + 0.5) * DY
    w = dens * DY
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
        lv.append(0.0 if c == 0 else 1.0 if c == nlev - 1 else
                  (float((S1[b] - S1[a]) / (S0[b] - S0[a])) if S0[b] > S0[a]
                   else float(y[min(a, NBIN - 1)])))
    return signed(np.array(sorted(lv)))


def mse(t, lv):
    n = (t.shape[1] // K) * K
    b = t[:, :n].reshape(-1, K).astype(np.float64)
    a = np.abs(b).max(1)
    ok = a > 0
    b, a = b[ok], a[ok]
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, b / a[:, None]).clip(0, len(lv) - 1)
    return float(((lv[idx] * a[:, None] - b) ** 2).mean())


f, h, base = st_open(os.path.join(W, "smollm2-135m.safetensors"))
names = [nm for nm, e in h.items() if isinstance(e, dict) and len(e.get("shape", [])) == 2
         and not any(k in nm.lower() for k in ("embed", "lm_head", "wte", "wpe"))]
names.sort(key=lambda nm: (layer_index(nm), nm))          # explicit, reproducible order
nl = max(layer_index(nm) for nm in names) + 1
fit = [nm for nm in names if layer_index(nm) < nl // 2]
test = [nm for nm in names if layer_index(nm) >= nl // 2]
print(f"  {len(names)} tensors over {nl} layers; fit = layers 0..{nl//2-1} "
      f"({len(fit)} tensors), held out = layers {nl//2}..{nl-1} ({len(test)} tensors)\n")

acc = np.zeros(NBIN)
for nm in fit:
    t = st_tensor(f, h, base, nm)
    if t.shape[1] < K:
        continue
    b = t[:, :(t.shape[1] // K) * K].reshape(-1, K)
    a = np.abs(b).max(1)
    ok = a > 0
    hh, _ = np.histogram(np.abs(b[ok] / a[ok][:, None]).ravel(), bins=NBIN, range=(0, 1))
    acc += hh
DP = dp_folded(acc / (acc.sum() * DY))

CANDS = {"E2M1 (CORRECT, 15 vals)": E2M1, "E2M1 (buggy, 13 vals)": E2M1_BUG,
         "int4": INT4, "NF4 (real)": NF4, "DERIVED DP (ours)": DP}
tot = {k: 0.0 for k in CANDS}
for nm in test:
    t = st_tensor(f, h, base, nm)
    if t.shape[1] < K:
        continue
    for k, lv in CANDS.items():
        tot[k] += mse(t, lv)

ref = tot["E2M1 (CORRECT, 15 vals)"]
print("  MSE on held-out layers, relative to the CORRECT E2M1:\n")
for k in sorted(CANDS, key=lambda x: tot[x]):
    print(f"    {k:<26}{tot[k]/ref:>8.4f}   ({(1-tot[k]/ref)*100:+6.1f}% vs correct MXFP4)")

old = tot["E2M1 (buggy, 13 vals)"]
print(f"\n  Against the BUGGY E2M1 the derived codebook scored "
      f"{tot['DERIVED DP (ours)']/old:.4f} "
      f"({(1-tot['DERIVED DP (ours)']/old)*100:+.1f}%) -- the number this programme reported.")
print(f"  Against the CORRECT E2M1 it scores {tot['DERIVED DP (ours)']/ref:.4f} "
      f"({(1-tot['DERIVED DP (ours)']/ref)*100:+.1f}%).")
print(f"  The missing subnormal alone accounts for "
      f"{(old/ref - 1)*100:.0f}% of apparent MXFP4 error.")
print("\n  NOTE: MSE ordering is now known NOT to predict perplexity ordering (see the")
print("  refutation section). These numbers rank squared error and nothing more.")
