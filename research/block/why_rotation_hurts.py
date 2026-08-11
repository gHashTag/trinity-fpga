#!/usr/bin/env python3
"""Why does a block-wise rotation make block quantisation worse?

`ROTATION_VERDICT_2026-08-11.md` measured that it does — every arm worse, ours
worse by more — and wrote down a mechanism as a *hypothesis*, explicitly not a
finding:

    a Hadamard mix within a 32-element block raises the typical magnitude
    relative to the block maximum that sets the shared scale, so more elements
    land in the coarse part of the codebook.

This tests it, and is built so it can fail. Three candidate mechanisms are
measured on the same blocks, and each makes a different prediction about which
blocks get worse:

  H1  CONCENTRATION. Rotation raises mean(|w|)/max(|w|) within a block. If the
      codebook's relative precision is worse for elements near the top of its
      range than for small ones, concentration hurts. Prediction: the per-block
      increase in error correlates with the per-block increase in mean/max.

  H2  SCALE QUANTISATION. The shared scale is E8M0 — a power of two, rounded up.
      What matters is not max itself but where max sits inside its binade:
      max/2^ceil(log2 max). Rotation changes the max, so it moves that ratio, and
      a max just above a power of two wastes almost a full bit of the element
      range. Prediction: error tracks the change in that headroom, not in mean/max.

  H3  SPARSITY. Weight blocks contain near-zero elements that cost nothing to
      encode. A Hadamard mix spreads energy into them, so the count of elements
      that must be represented rises even if no magnitude statistic moves much.
      Prediction: error tracks the change in participation ratio.

A mechanism that explains the sign but not the per-block variation is not the
mechanism. The ranking below is by correlation with the measured per-block error
change, and the script prints all three so a weak winner is visible as weak.

Falsifiability: the same three predictors are also correlated against a SHUFFLED
error-change vector. Those correlations must collapse to near zero, or the
correlation machinery is finding structure in noise and none of the numbers
above it mean anything.

    python3 why_rotation_hurts.py
"""
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")

MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit("why_rotation_hurts: driver marker not found in block_tnf.py")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

fp_levels = _ns["fp_levels"]
tnf_levels = _ns["tnf_levels"]
q_e8m0_t = _ns["q_e8m0_t"]
target_modules = _ns["target_modules"]
MODEL, K = _ns["MODEL"], _ns["K"]

torch.set_grad_enabled(False)


def hadamard(n):
    h = np.array([[1.0]])
    while h.shape[0] < n:
        h = np.block([[h, h], [h, -h]])
    return torch.tensor(h, dtype=torch.float64)


HN = hadamard(K) / np.sqrt(K)


def blocks_of(w):
    """Every full K-block of a weight matrix, as rows of a 2-D tensor."""
    n = (w.shape[1] // K) * K
    if n == 0:
        return None
    return w[:, :n].double().reshape(-1, K)


def quant_err(bl, lv_t):
    """Per-block mean squared error under the project's own E8M0 + codebook rule."""
    s = (bl.abs().amax(dim=1) / lv_t[-1]).clamp(min=1e-30)
    s = q_e8m0_t(s).clamp(min=1e-30)
    y = (bl / s[:, None]).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    rec = torch.sign(bl) * lv_t[torch.bucketize(y, bnd)] * s[:, None]
    return ((rec - bl) ** 2).mean(dim=1)


def stats(bl):
    """The three candidate predictors, per block."""
    a = bl.abs()
    mx = a.amax(dim=1).clamp(min=1e-30)
    concentration = (a.mean(dim=1) / mx)                       # H1
    # H2: where the block max sits inside its binade. 1.0 means max is exactly a
    # power of two (no waste); just above 0.5 means almost a full bit thrown away.
    headroom = mx / torch.pow(2.0, torch.ceil(torch.log2(mx)))
    # H3: participation ratio — how many elements actually carry the energy.
    participation = (a.sum(dim=1) ** 2) / (K * (a ** 2).sum(dim=1).clamp(min=1e-30))
    return concentration, headroom, participation


def pearson(x, y):
    x = x - x.mean()
    y = y - y.mean()
    d = (x.norm() * y.norm()).clamp(min=1e-30)
    return float((x @ y) / d)


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()

    lv_t = torch.tensor(sorted(fp_levels(2, 1)), dtype=torch.float64)   # MXFP4
    print(f"  codebook MXFP4 E2M1, {len(lv_t)} levels, block K={K}")

    de, dc, dh, dp = [], [], [], []
    nblocks = 0
    for _name, mod in target_modules(model):
        w = mod.weight.detach()
        raw = blocks_of(w)
        if raw is None:
            continue
        rot = (raw @ HN)
        e0, e1 = quant_err(raw, lv_t), quant_err(rot, lv_t)
        c0, h0, p0 = stats(raw)
        c1, h1, p1 = stats(rot)
        # Normalise the error by block energy: a block of larger weights has a
        # larger absolute error for reasons that have nothing to do with shape.
        n0 = (raw ** 2).mean(dim=1).clamp(min=1e-30)
        n1 = (rot ** 2).mean(dim=1).clamp(min=1e-30)
        de.append((e1 / n1) - (e0 / n0))
        dc.append(c1 - c0)
        dh.append(h1 - h0)
        dp.append(p1 - p0)
        nblocks += raw.shape[0]

    de = torch.cat(de); dc = torch.cat(dc); dh = torch.cat(dh); dp = torch.cat(dp)
    print(f"  {nblocks:,} blocks across {len(list(target_modules(model)))} layers\n")

    worse = float((de > 0).double().mean())
    print(f"relative error rises in {worse * 100:.1f}% of blocks "
          f"(median change {float(de.median()):+.4e})")
    print(f"mean concentration change  {float(dc.mean()):+.4f}")
    print(f"mean headroom change       {float(dh.mean()):+.4f}")
    print(f"mean participation change  {float(dp.mean()):+.4f}\n")

    cand = [("H1 concentration mean/max", dc),
            ("H2 E8M0 headroom max/2^ceil", dh),
            ("H3 participation ratio", dp)]
    print(f"  {'predictor':<30} {'r with Δerror':>14} {'r with shuffled':>16}")
    g = torch.Generator().manual_seed(11)
    de_shuf = de[torch.randperm(de.numel(), generator=g)]
    rows = []
    for label, v in cand:
        r = pearson(v, de)
        rs = pearson(v, de_shuf)
        rows.append((abs(r), label, r, rs))
        print(f"  {label:<30} {r:>14.4f} {rs:>16.4f}")

    if max(abs(rs) for _, _, _, rs in rows) > 0.05:
        print("\nFALSIFIED INSTRUMENT — a shuffled target still correlates. "
              "The correlations above are not evidence.")
        return 1

    rows.sort(reverse=True)
    best_abs, best_label, best_r, _ = rows[0]
    runner = rows[1][0]
    print(f"\nstrongest: {best_label}  (r = {best_r:+.4f})")
    if best_abs < 0.2:
        print("VERDICT: no candidate explains the per-block variation. The "
              "hypothesis in ROTATION_VERDICT is not supported, and the "
              "mechanism remains unknown.")
    elif best_abs - runner < 0.05:
        print("VERDICT: the top two are not separated. Reported as inconclusive "
              "rather than picking one.")
    else:
        print(f"VERDICT: {best_label} is the one that tracks it.")
    print("\nSCOPE: one model, one codebook (MXFP4 E2M1), weights only. This "
          "explains the per-block variation of the error change; it does not by "
          "itself establish the perplexity consequence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
