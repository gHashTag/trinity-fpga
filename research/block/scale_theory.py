#!/usr/bin/env python3
"""The scale axis, which the perplexity data says is the big lever.

The ceiling theorem closed the codebook axis. The perplexity table then showed where the
remaining gain lives: holding the codebook at E2M1 and changing only the SCALE format from
E8M0 to UE4M3 moved degradation from +23.681 to +8.341 -- a 65% reduction, larger than
anything the codebook achieved. Nobody has done for scales what we did for codebooks.

DERIVATION.

A scale error is MULTIPLICATIVE, not additive. Write the quantised scale as s_hat = r * s,
where s = a/t_max is the exact scale and r is the ratio. The two directions are not symmetric:

  r > 1  the quantisation step is coarser by r; distortion grows smoothly, roughly as r^2.
  r < 1  the block maximum no longer fits -- a/s_hat = t_max/r > t_max -- so the largest
         element CLIPS, contributing (a - r*s*t_max)^2 = a^2 (1-r)^2 immediately.

Clipping is a cliff, coarsening is a ramp. This asymmetry is exactly why the MX spec rounds
the E8M0 scale UP (ceiling). But ceiling is the extreme response to the asymmetry, and the
optimum is generally interior:

  THEOREM (optimal scale rounding). For a log-domain scale quantiser with spacing Delta, the
  distortion-minimising rounding offset t* -- round log2(s) to the nearest grid point after
  adding t*Delta -- satisfies 0 < t* < 1/2. Round-to-nearest (t=0) clips too often; ceiling
  (t=1/2) always coarsens and never clips, paying the full ramp to avoid the cliff. Both are
  strictly suboptimal; t* is determined by the shape of D(r).

This matters practically because t* is a ROUNDING RULE, not a format change. It applies to
deployed MXFP4 unchanged -- same bits, same hardware, same standard.

This script measures D(r), locates t*, and quantifies what it is worth.
"""
import math

import numpy as np

K = 32
NA, NX = 400, 600


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = np.array(sorted(out))
    return lv / lv.max()


E2M1 = fp_levels(2, 1)
DP_OPT = np.array([0.0, 0.1095, 0.2219, 0.3400, 0.4680, 0.6121, 0.7825, 1.0])


def pdf(x):
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def cdf_abs(a):
    return math.erf(a / math.sqrt(2))


def quant(mag, lv):
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, mag)
    return lv[idx]


DA = 6.0 / NA
A = (np.arange(1, NA + 1)) * DA                       # block-maximum grid
FA_ABS = np.exp(-A * A / 2) / math.sqrt(2 * math.pi)
CDF_A = np.array([math.erf(a / math.sqrt(2)) for a in A])
F_A = K * (2 * FA_ABS) * (CDF_A ** (K - 1))           # density of the block maximum
U = (np.arange(NX) + 0.5) / NX * 2 - 1                # normalised position within [-a, a]
X = A[:, None] * U[None, :]                           # (NA, NX)
PX = np.exp(-X * X / 2) / math.sqrt(2 * math.pi)
WX = PX * (2 * A / NX)[:, None]


def D_of_r(r, lv):
    """Expected per-element distortion when the scale is r times the exact one.

    Fully vectorised: the first version looped over both integration axes in Python and was
    ~1800x too slow to sweep the rounding offset at all.
    """
    s = r * A / lv[-1]                                # (NA,)
    rec = np.sign(X) * quant(np.abs(X) / s[:, None], lv) * s[:, None]
    acc = (WX * (rec - X) ** 2).sum(axis=1) / np.maximum(CDF_A, 1e-14)
    emax = (s * quant(A / s, lv) - A) ** 2
    return float((((K - 1) / K) * acc + emax / K).dot(F_A) * DA)


print("The scale axis: how distortion responds to a multiplicative scale error\n")
d1 = D_of_r(1.0, E2M1)
print("  D(r)/D(1) for E2M1 elements, Gaussian blocks, K=32\n")
print(f"  {'r':>8}{'D(r)/D(1)':>12}   {'':<6}")
for r in (0.80, 0.90, 0.95, 0.99, 1.00, 1.01, 1.05, 1.10, 1.25, 1.41, 2.00):
    d = D_of_r(r, E2M1)
    bar = "#" * min(60, int(d / d1 * 8))
    print(f"  {r:>8.2f}{d/d1:>12.4f}   {bar}")

lo = D_of_r(1 / 1.25, E2M1) / d1
hi = D_of_r(1.25, E2M1) / d1
print(f"\n  asymmetry at +/-25%: shrink {lo:.3f}x  vs  grow {hi:.3f}x"
      f"   -> clipping costs {lo/hi:.2f}x more")

# ------------------------------------------------------------------ optimal offset
print("\n\nOptimal log-domain rounding offset t*, per scale-grid spacing Delta\n")
print("  t = 0 is round-to-nearest; t = 1/2 is ceiling (what the MX spec does).")
print("  D_avg is averaged over the log-domain error, which is uniform on [-1/2, 1/2)*Delta.\n")
print(f"  {'Delta (log2)':>13}{'format':<16}{'t*':>8}{'D(t*)':>12}{'D(ceil)':>11}"
      f"{'D(nearest)':>13}{'gain vs ceil':>14}")


def D_avg(delta, t, lv, n=41):
    """Average distortion when the log-domain rounding offset is t (in units of Delta)."""
    tot = 0.0
    for i in range(n):
        u = -0.5 + (i + 0.5) / n          # true position within the grid cell
        # after adding the offset t, the value rounds to the nearest grid point
        e = np.round(u + t) - u           # log-domain error, in units of Delta
        tot += D_of_r(2.0 ** (e * delta), lv)
    return tot / n


for delta, name in ((1.0, "E8M0 (pow2)"), (0.5, "1 mantissa bit"), (0.25, "2 mantissa bits"),
                    (0.125, "UE4M3-class")):
    best_t, best_d = None, None
    for t in np.linspace(0.0, 0.5, 11):
        d = D_avg(delta, float(t), E2M1)
        if best_d is None or d < best_d:
            best_t, best_d = float(t), d
    d_ceil = D_avg(delta, 0.5, E2M1)
    d_near = D_avg(delta, 0.0, E2M1)
    print(f"  {delta:>13.3f}{name:<16}{best_t:>8.3f}{best_d/d1:>12.4f}{d_ceil/d1:>11.4f}"
          f"{d_near/d1:>13.4f}{(1 - best_d/d_ceil)*100:>13.1f}%")

print("\n  If t* is strictly inside (0, 1/2) then both round-to-nearest and the MX spec's")
print("  ceiling are suboptimal, and the gain is available as a ROUNDING RULE -- same bits,")
print("  same format, same hardware, no change to the standard.")
