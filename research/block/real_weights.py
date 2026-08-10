#!/usr/bin/env python3
"""Closing the load-bearing gap: the derived codebook on REAL trained weights.

Every result so far used synthetic densities. That was the one hole the stop-rule actually
cares about, and no amount of further synthetic work closes it. This script uses real
checkpoints.

Real weights make the method STRONGER, not just more credible, because p_eff can be measured
instead of assumed:

    p_eff(y) is the density of y = x / a  over all non-maximal elements of all blocks,
    where a is that block's maximum.

That is the exact empirical counterpart of the marginalisation integral (*) in design_space.py.
So on real data the pipeline carries NO distributional assumption at all -- collect the
normalised residuals, run Lloyd-Max on their histogram, done.

PROTOCOL (fixed before looking at any result):

  * Quantisation target = 2-D weight matrices of linear layers only, which is what MX
    quantises. Embeddings, biases and norms are excluded.
  * Blocks run along the CONTRACTION axis (the last axis of a [out, in] weight), matching how
    MX blocks are laid out in a matmul.
  * HOLD-OUT: the codebook is derived from the FIRST half of the layers and measured on the
    SECOND half. A codebook fitted and scored on the same tensors would prove nothing.
  * Cross-model: derive on one model, measure on the other. This is the real mismatch test.
  * Sanity gate: report excess kurtosis. Untrained/randomly-initialised tensors sit near 0
    (Gaussian) or -1.2 (uniform); trained LLM weights are leptokurtic. A checkpoint that
    fails this gate is not evidence and is reported as such.
"""
import json
import math
import os
import struct
import sys

import numpy as np

WDIR = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
        "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32
NBIN = 2000


# ------------------------------------------------------------ safetensors
def st_open(path):
    f = open(path, "rb")
    n = struct.unpack("<Q", f.read(8))[0]
    hdr = json.loads(f.read(n))
    return f, hdr, 8 + n


def st_tensor(f, hdr, base, name):
    e = hdr[name]
    s, t = e["data_offsets"]
    f.seek(base + s)
    raw = f.read(t - s)
    dt = e["dtype"]
    if dt == "BF16":
        u = np.frombuffer(raw, dtype="<u2").astype(np.uint32) << 16
        a = u.view(np.float32)
    elif dt == "F16":
        a = np.frombuffer(raw, dtype="<f2").astype(np.float32)
    elif dt == "F32":
        a = np.frombuffer(raw, dtype="<f4")
    else:
        return None
    return a.reshape(e["shape"])


def linear_weights(path):
    """2-D linear-layer weights, in file order, excluding embeddings and the LM head."""
    f, hdr, base = st_open(path)
    names = []
    for nm, e in hdr.items():
        if nm == "__metadata__" or not isinstance(e, dict):
            continue
        if len(e.get("shape", [])) != 2:
            continue
        low = nm.lower()
        if "embed" in low or "lm_head" in low or "wte" in low or "wpe" in low:
            continue
        names.append(nm)
    names.sort()
    return f, hdr, base, names


# ------------------------------------------------------------ statistics
def excess_kurtosis(x):
    x = x.astype(np.float64)
    m = x.mean()
    s = x.std()
    return float(((x - m) ** 4).mean() / (s ** 4) - 3.0) if s > 0 else float("nan")


def residuals(mat):
    """y = x/a for every non-maximal element; a = block max along the contraction axis."""
    v = mat.astype(np.float32)
    n = (v.shape[1] // K) * K
    if n == 0:
        return None, None
    b = v[:, :n].reshape(-1, K)
    a = np.abs(b).max(axis=1)
    ok = a > 0
    b, a = b[ok], a[ok]
    y = b / a[:, None]
    # drop exactly one maximal element per block (it is pinned to +-1 by construction)
    idx = np.abs(y).argmax(axis=1)
    m = np.ones_like(y, dtype=bool)
    m[np.arange(y.shape[0]), idx] = False
    return np.abs(y[m]), a


def hist_density(y):
    h, _ = np.histogram(y, bins=NBIN, range=(0.0, 1.0))
    dy = 1.0 / NBIN
    h = h.astype(np.float64)
    s = h.sum() * dy
    return (h / s if s > 0 else h), dy


# ------------------------------------------------------------ codebooks
def lloyd(vals, dy, nlev=8, iters=300):
    lv = np.array([i / (nlev - 1) for i in range(nlev)], dtype=np.float64)
    y = (np.arange(NBIN) + 0.5) * dy
    w = vals * dy
    for _ in range(iters):
        bnd = (lv[:-1] + lv[1:]) / 2
        j = np.searchsorted(bnd, y)
        num = np.bincount(j, weights=w * y, minlength=nlev)
        den = np.bincount(j, weights=w, minlength=nlev)
        new = np.where(den > 0, num / np.maximum(den, 1e-300), lv)
        new[0] = 0.0
        new[-1] = 1.0
        new = np.sort(new)
        if np.max(np.abs(new - lv)) < 1e-13:
            lv = new
            break
        lv = new
    return lv


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
    """The NF4 principle: quantiles of the UNCONDITIONAL Normal (our symmetric construction)."""
    from statistics import NormalDist
    nd = NormalDist()
    lv = [0.0] + [nd.inv_cdf(0.5 + 0.5 * (i + 0.5) / 8) for i in range(1, 8)]
    lv = np.array(lv)
    return lv / lv.max()


def mse_rel(mat, lv):
    """Block-scaled MSE per element for a level set, vectorised."""
    v = mat.astype(np.float32)
    n = (v.shape[1] // K) * K
    b = v[:, :n].reshape(-1, K).astype(np.float64)
    a = np.abs(b).max(axis=1)
    ok = a > 0
    b, a = b[ok], a[ok]
    s = a / lv.max()
    y = b / s[:, None]
    sign = np.sign(y)
    mag = np.abs(y)
    bnd = (lv[:-1] + lv[1:]) / 2
    idx = np.searchsorted(bnd, mag)
    rec = sign * lv[idx] * s[:, None]
    return float(((rec - b) ** 2).mean())


# ------------------------------------------------------------ run
def analyse(path, label):
    f, hdr, base, names = linear_weights(path)
    half = len(names) // 2
    fit_names, test_names = names[:half], names[half:]
    print(f"  {label}: {len(names)} linear weight tensors "
          f"({len(fit_names)} fit / {len(test_names)} held out)")

    acc = []
    kurt = []
    for nm in fit_names:
        t = st_tensor(f, hdr, base, nm)
        if t is None:
            continue
        y, _ = residuals(t)
        if y is not None:
            acc.append(y[:: max(1, len(y) // 200000)])
        kurt.append(excess_kurtosis(t.ravel()[:200000]))
    y_all = np.concatenate(acc)
    vals, dy = hist_density(y_all)
    lv_derived = lloyd(vals, dy)
    mk = float(np.median(kurt))
    print(f"    median excess kurtosis of fit tensors: {mk:+.2f}"
          + ("   [trained: leptokurtic]" if mk > 0.5 else
             "   [WARNING: not clearly trained -- treat as non-evidence]"))
    print(f"    derived codebook (empirical p_eff, no density assumed):")
    print(f"      " + " ".join(f"{v:.4f}" for v in lv_derived))
    return f, hdr, base, test_names, lv_derived, mk


def analytic_gaussian_codebook(kk):
    """The codebook from design_space.py -- derived from the integral (*) under a Gaussian
    assumption, having seen no data whatsoever. If THIS wins on real weights, the theory
    transfers on its own and the empirical fit is a refinement, not the source of the win."""
    from design_space import lloyd as l2, p_eff, DISTS
    return np.array(l2(*p_eff(DISTS["gaussian"], kk), nlev=8))


CANDS_STATIC = {
    "e2m1 (MXFP4)": fp_levels(2, 1),
    "e1m2": fp_levels(1, 2),
    "e3m0": fp_levels(3, 0),
    "int4": np.array([i / 7 for i in range(8)]),
    "nf4-style": nf4_levels(),
    "ANALYTIC (gaussian, no data)": analytic_gaussian_codebook(K),
}

def complete(path):
    """A truncated download still parses its header and yields plausible tensors.

    That is the same false-green shape that produced a valid-looking 9.7 MB bitstream from a
    failed fasm2frames run. So check the header's own declared extent against the file size
    instead of trusting that the file opened.
    """
    try:
        f, hdr, base = st_open(path)
        need = base + max(e["data_offsets"][1] for e in hdr.values()
                          if isinstance(e, dict) and "data_offsets" in e)
        f.close()
        return os.path.getsize(path) >= need, need
    except Exception:
        return False, -1


models = []
for fn, label in (("smollm2-135m.safetensors", "SmolLM2-135M"),
                  ("qwen25-05b.safetensors", "Qwen2.5-0.5B")):
    p = os.path.join(WDIR, fn)
    if not os.path.exists(p):
        continue
    ok, need = complete(p)
    if ok:
        models.append((p, label))
    else:
        print(f"  skipping {label}: incomplete "
              f"({os.path.getsize(p)/1e6:.0f} MB of {need/1e6:.0f} MB)\n")

if not models:
    sys.exit("no checkpoints present yet")

print("Derived codebook on REAL trained weights (block size K=32, held-out layers)\n")
info = {}
for p, label in models:
    info[label] = analyse(p, label)
    print()

print("MSE per element on HELD-OUT layers, relative to E2M1 (MXFP4). Lower is better.\n")
for p, label in models:
    f, hdr, base, test_names, lv_own, mk = info[label]
    cands = dict(CANDS_STATIC)
    cands["DERIVED (this model)"] = lv_own
    for other in info:
        if other != label:
            cands[f"DERIVED ({other})"] = info[other][4]
    tot = {n: 0.0 for n in cands}
    cnt = 0
    for nm in test_names:
        t = st_tensor(f, hdr, base, nm)
        if t is None or t.shape[1] < K:
            continue
        for n, lv in cands.items():
            tot[n] += mse_rel(t, lv)
        cnt += 1
    ref = tot["e2m1 (MXFP4)"]
    print(f"  {label}  ({cnt} held-out tensors)")
    for n in cands:
        d = (1 - tot[n] / ref) * 100
        print(f"    {n:<24} {tot[n]/ref:>7.3f}   ({d:+.1f}% vs MXFP4)")
    print()
