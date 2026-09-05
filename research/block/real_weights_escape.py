#!/usr/bin/env python3
"""The escape break-even rule, applied to real trained weights.

escape_theory.py derived, on synthetic densities, that escape beats spending the same bits on
precision only above a block-size threshold that falls as the tail gets heavier:

    K >= 128 (gaussian)   K >= 64 (laplace)   K >= 32 (student-t3)

Real LLM weights sit somewhere on that tail-weight scale (SmolLM2's linear layers have median
excess kurtosis +1.07 -- heavier than Gaussian, lighter than t3). So the rule makes a concrete,
falsifiable prediction about where real weights land, and this checks it on held-out layers.

MX's standard block size is K = 32. If the rule says "spend on precision" there, then escape
-- which several competing proposals rely on for outlier handling -- is the wrong lever at the
block size the industry actually ships, and that is worth knowing.
"""
import numpy as np

from real_weights import (K as _K, WDIR, complete, fp_levels, hist_density, linear_weights,
                          lloyd, mse_rel, residuals, st_tensor)
import os

PATH = os.path.join(WDIR, "smollm2-135m.safetensors")


def blocks(mat, k):
    v = mat.astype(np.float32)
    n = (v.shape[1] // k) * k
    if n == 0:
        return None
    b = v[:, :n].reshape(-1, k).astype(np.float64)
    return b[np.abs(b).max(axis=1) > 0]


def mse_plain(b, lv):
    a = np.abs(b).max(axis=1)
    s = a / lv.max()
    mag = np.abs(b / s[:, None])
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, mag)
    rec = np.sign(b) * lv[idx] * s[:, None]
    return float(((rec - b) ** 2).mean())


def mse_escape(b, lv):
    """Top element removed and stored exactly; the rest scaled by the 2nd order statistic."""
    k = b.shape[1]
    order = np.argsort(-np.abs(b), axis=1)
    rows = np.arange(b.shape[0])[:, None]
    srt = b[rows, order]
    rest = srt[:, 1:]                       # the escaped element contributes zero error
    a2 = np.abs(rest).max(axis=1)
    ok = a2 > 0
    rest, a2 = rest[ok], a2[ok]
    s = a2 / lv.max()
    mag = np.abs(rest / s[:, None])
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, mag)
    rec = np.sign(rest) * lv[idx] * s[:, None]
    return float(((rec - rest) ** 2).sum() / (rest.shape[0] * k))


ok, _ = complete(PATH)
if not ok:
    raise SystemExit("checkpoint incomplete")
f, hdr, base, names = linear_weights(PATH)
fit_names, test_names = names[: len(names) // 2], names[len(names) // 2:]

print("Escape break-even on REAL weights (SmolLM2-135M, held-out layers)\n")
print("  D4      derived 4-bit codebook, plain")
print("  D4+esc  same codebook, top element escaped, scale from the 2nd order statistic")
print("  D5      derived 5-bit codebook -- the 'just spend the bits on precision' alternative\n")

for k in (16, 32, 64, 128):
    # codebook fitted on the FIT half at this block size, then applied to held-out layers
    acc = []
    for nm in fit_names:
        t = st_tensor(f, hdr, base, nm)
        if t is None or t.shape[1] < k:
            continue
        v = t.astype(np.float32)
        n = (v.shape[1] // k) * k
        bb = v[:, :n].reshape(-1, k)
        a = np.abs(bb).max(axis=1)
        m = a > 0
        y = np.abs(bb[m] / a[m][:, None])
        idx = y.argmax(axis=1)
        keep = np.ones_like(y, dtype=bool)
        keep[np.arange(y.shape[0]), idx] = False
        yy = y[keep]
        acc.append(yy[:: max(1, len(yy) // 200000)])
    y_all = np.concatenate(acc)
    lv4 = lloyd(*hist_density(y_all), nlev=8)
    lv5 = lloyd(*hist_density(y_all), nlev=16)

    d4 = de = d5 = 0.0
    for nm in test_names:
        t = st_tensor(f, hdr, base, nm)
        if t is None or t.shape[1] < k:
            continue
        b = blocks(t, k)
        if b is None or len(b) == 0:
            continue
        d4 += mse_plain(b, lv4)
        de += mse_escape(b, lv4)
        d5 += mse_plain(b, lv5)
    ovh = (np.log2(k) + 16) / k
    g_esc = (1 - de / d4) / ovh
    g_bit = (1 - d5 / d4) / 1.0
    verdict = "ESCAPE WINS" if g_esc > g_bit else "spend on precision"
    print(f"  K={k:<4} overhead {ovh:.4f} b/elem   esc {de/d4:.3f}, 5-bit {d5/d4:.3f}   "
          f"| per bit: esc {g_esc:.3f} vs prec {g_bit:.3f}  -> {verdict}")

print("\n  Synthetic rule predicted the threshold falls with tail weight; real weights sit")
print("  between gaussian and t3 (excess kurtosis +1.07), so the crossover should land")
print("  between K=32 and K=128.")
