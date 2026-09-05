#!/usr/bin/env python3
"""The last untested version of our claim: 16 levels, asymmetric, WITH an exact zero.

The audit leaves a clean gap. Three codebook designs have been measured:

    DP-15   symmetric, HAS zero, wastes one of 16 codes   -> loses to NF4 on MSE
    DP-16   asymmetric, uses all 16, NO zero              -> best MSE, worst perplexity
    NF4     asymmetric, uses all 16, HAS zero             -> good at both

NF4 achieves both properties by being asymmetric: seven negative levels, zero, eight positive.
Our DP has never been run in that configuration -- it was either symmetric (and therefore
15 values) or unconstrained (and therefore zeroless). So the fair fight has not happened.

This runs the DP over the signed density with 16 cells and THREE pinned reconstruction points:
cell 0 at -1, cell 15 at +1, and one interior cell j at 0, sweeping j to find the best split.
Everything else stays free.

If this still loses to NF4, the codebook line of attack is finished on its own preferred metric
and should be closed. If it wins on MSE, the perplexity question is still open, because MSE
ordering has already been shown not to transfer.
"""
import json
import os
import re
import struct

import numpy as np

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K, NBIN = 32, 800


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
    return np.frombuffer(raw, dtype="<f4").reshape(e["shape"])


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def fp_mags(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for m in range(1, 1 << mb):
        out.add((m / (1 << mb)) * 2.0 ** (1 - bias))
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = np.array(sorted(out))
    return lv / lv.max()


def signed(m):
    return np.array(sorted(set([-v for v in m] + list(m))))


E2M1 = signed(fp_mags(2, 1))
NF4 = np.array([-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
                -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
                0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
                0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
                0.7229568362236023, 1.0])


def dp_pinned(dens, pins, nlev=16):
    """DP over [-1,1]; pins maps cell index -> fixed reconstruction value, others free."""
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
    # reconstruct
    bounds = [M]
    cur = M
    for k in range(nlev - 1, 0, -1):
        cur = bk[k][cur]
        bounds.append(cur)
    bounds.append(0)
    bounds = sorted(set(bounds))
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
names.sort(key=lambda nm: (layer_index(nm), nm))
nl = max(layer_index(nm) for nm in names) + 1
fit = [nm for nm in names if layer_index(nm) < nl // 2]
test = [nm for nm in names if layer_index(nm) >= nl // 2]

acc = np.zeros(NBIN)
for nm in fit:
    t = st_tensor(f, h, base, nm)
    if t.shape[1] < K:
        continue
    b = t[:, :(t.shape[1] // K) * K].reshape(-1, K)
    a = np.abs(b).max(1)
    ok = a > 0
    hh, _ = np.histogram((b[ok] / a[ok][:, None]).ravel(), bins=NBIN, range=(-1, 1))
    acc += hh
dens = acc / (acc.sum() * (2.0 / NBIN))

print("Sweeping which cell carries the pinned zero\n")
best = None
for j in range(5, 11):
    lv, d = dp_pinned(dens, {0: -1.0, 15: 1.0, j: 0.0})
    ok = abs(np.min(np.abs(lv))) < 1e-12
    print(f"  zero at cell {j:2d}:  fit distortion {d:.6e}   zero present: {ok}")
    if ok and (best is None or d < best[1]):
        best = (lv, d, j)
DP16Z = best[0]
print(f"\n  best: zero at cell {best[2]}")
print("  DP-16+zero: " + " ".join(f"{v:+.4f}" for v in DP16Z))
print(f"  distinct values: {len(set(np.round(DP16Z, 9)))}\n")

CANDS = {"E2M1 (correct)": E2M1, "NF4 (real)": NF4, "DP-16 + zero (new)": DP16Z}
tot = {k: 0.0 for k in CANDS}
for nm in test:
    t = st_tensor(f, h, base, nm)
    if t.shape[1] < K:
        continue
    for k, lv in CANDS.items():
        tot[k] += mse(t, lv)
ref = tot["E2M1 (correct)"]
print("  MSE on held-out layers, relative to correct E2M1:\n")
for k in sorted(CANDS, key=lambda x: tot[x]):
    print(f"    {k:<24}{tot[k]/ref:>8.4f}")
w = "DP-16 + zero (new)"
print(f"\n  vs NF4: {tot[w]/tot['NF4 (real)']:.4f} "
      f"({'BEATS NF4' if tot[w] < tot['NF4 (real)'] else 'still loses to NF4'})")
