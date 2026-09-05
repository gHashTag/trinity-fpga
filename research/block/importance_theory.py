#!/usr/bin/env python3
"""Trying to break the result by changing the objective: importance-weighted distortion.

GPTQ and AWQ do not minimise plain MSE. They minimise a per-weight IMPORTANCE-weighted
distortion -- diagonal-Hessian for GPTQ, squared activation magnitude for AWQ:

    D_h = E[ h * (x_hat - x)^2 ]

Since every result so far optimised plain MSE, the derived codebook could be an artefact of
the wrong objective. This is the most likely way the whole thing is wrong, so it is worth
attacking directly.

DERIVATION.

Conditional on the block maximum a, working in the normalised domain y = x/a:

    D_h = E_a[ a^2 * E[ h * (Q(y) - y)^2 | a ] ]

THEOREM (importance invariance). If h is statistically independent of the weight value x,
then E[h(Q(y)-y)^2] = E[h] * E[(Q(y)-y)^2], so D_h = E[h] * D and THE OPTIMAL CODEBOOK IS
UNCHANGED. Importance weighting rescales the distortion but does not move a single level.

COROLLARY. The codebook can only change through the CORRELATION between h and |x|. Define the
importance-tilted density

    p_eff^h(y)  proportional to  E[h | y] * p_eff(y)

and the optimum is the weighted Lloyd-Max quantizer of p_eff^h. (The nearest-level boundary
stays at the midpoint, because at a boundary point the weight is common to both sides; only
the centroid condition becomes h-weighted.)

So the question is quantitative, not qualitative: HOW MUCH correlation does it take to move
the codebook enough to matter? This sweeps a one-parameter coupling family

    h(y) = |y|^gamma

with gamma < 0 putting importance on small weights, gamma > 0 on large ones, gamma = 0 the
independent case. Real p_eff is taken from actual trained weights, not assumed.

Falsification criterion, fixed in advance: if for plausible gamma the re-derived codebook loses
its advantage over E2M1 under ITS OWN weighted objective, the result does not survive the
change of metric and must be reported as objective-specific.
"""
import os

import numpy as np

from real_weights import (K, WDIR, complete, fp_levels, hist_density, linear_weights,
                          nf4_levels, residuals, st_tensor)

PATH = os.path.join(WDIR, "smollm2-135m.safetensors")
NBIN = 2000


def wlloyd(vals, dy, w, nlev=8, iters=400):
    """Lloyd-Max under a weight function w(y): centroid becomes w-weighted, boundary stays mid."""
    lv = np.array([i / (nlev - 1) for i in range(nlev)], dtype=np.float64)
    y = (np.arange(NBIN) + 0.5) * dy
    m = vals * dy * w
    for _ in range(iters):
        j = np.searchsorted((lv[:-1] + lv[1:]) / 2, y)
        num = np.bincount(j, weights=m * y, minlength=nlev)
        den = np.bincount(j, weights=m, minlength=nlev)
        new = np.where(den > 0, num / np.maximum(den, 1e-300), lv)
        new[0], new[-1] = 0.0, 1.0
        new = np.sort(new)
        if np.max(np.abs(new - lv)) < 1e-13:
            return new
        lv = new
    return lv


def wdist(vals, dy, w, lv):
    """Weighted distortion of a level set under p_eff and weight w, in the normalised domain."""
    y = (np.arange(NBIN) + 0.5) * dy
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, y)
    return float((vals * dy * w * (lv[idx] - y) ** 2).sum())


ok, _ = complete(PATH)
if not ok:
    raise SystemExit("checkpoint incomplete")
f, hdr, base, names = linear_weights(PATH)
fit = names[: len(names) // 2]

acc = []
for nm in fit:
    t = st_tensor(f, hdr, base, nm)
    if t is None or t.shape[1] < K:
        continue
    y, _ = residuals(t)
    if y is not None:
        acc.append(y[:: max(1, len(y) // 200000)])
vals, dy = hist_density(np.concatenate(acc))
yg = (np.arange(NBIN) + 0.5) * dy

E2M1 = fp_levels(2, 1)
NF4 = nf4_levels()
INT4 = np.array([i / 7 for i in range(8)])

print("Attacking the codebook with a changed objective: importance-weighted distortion")
print("p_eff taken from real SmolLM2 weights. h(y) = |y|^gamma.\n")
print("  gamma < 0 : importance on SMALL weights   gamma = 0 : independent (the theorem)")
print("  gamma > 0 : importance on LARGE weights\n")
print(f"  {'gamma':>7} {'re-derived codebook (levels 1..6)':<44} {'vs E2M1':>9} {'vs NF4':>8}"
      f" {'shift':>7}")

base_lv = wlloyd(vals, dy, np.ones(NBIN))
for g in (-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0, 2.0):
    w = np.maximum(yg, 1e-6) ** g
    lv = wlloyd(vals, dy, w)
    d_new = wdist(vals, dy, w, lv)
    d_e2 = wdist(vals, dy, w, E2M1)
    d_nf = wdist(vals, dy, w, NF4)
    shift = float(np.max(np.abs(lv - base_lv)))
    lvs = " ".join(f"{v:.3f}" for v in lv[1:7])
    print(f"  {g:>7.2f} {lvs:<44} {d_new/d_e2:>9.3f} {d_new/d_nf:>8.3f} {shift:>7.4f}")

print("\n  Also: does the gamma=0 codebook (the one we derived) survive being SCORED under a")
print("  weighted objective it was not tuned for?\n")
print(f"  {'gamma':>7} {'plain codebook vs E2M1':>24} {'vs its own optimum':>20}")
for g in (-1.0, -0.5, 0.0, 0.5, 1.0, 2.0):
    w = np.maximum(yg, 1e-6) ** g
    lv_opt = wlloyd(vals, dy, w)
    d_plain = wdist(vals, dy, w, base_lv)
    d_e2 = wdist(vals, dy, w, E2M1)
    d_opt = wdist(vals, dy, w, lv_opt)
    print(f"  {g:>7.2f} {d_plain/d_e2:>24.3f} {d_plain/d_opt:>20.3f}")
