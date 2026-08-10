#!/usr/bin/env python3
"""Attack our own prediction: does two-level scaling really remove the inversion?

We predicted (two_level_scale.py) that IBM's block-size inversion is a SINGLE-LEVEL
scaling phenomenon and that NVFP4's two-level hierarchy should remove it. That prediction
came out of the same integral that produced the theorem, so testing it with that integral
again would be circular.

So this is a direct Monte-Carlo simulation of whole tensors -- no integration, no
conditional densities, just quantise and measure. If simulation and formula disagree, the
formula is wrong; if they agree, the prediction has independent support.

Tensor profiles follow NxFP Figure 3 and IBM Figure 3a: real LLM weight blocks scaled by
their shared exponent are well modelled by a Normal. We vary the tensor-level crest factor
because the theorem says sigma itself cannot matter.
"""
import math
import random

random.seed(20260809)
E4M3_MAX = 448.0


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)


E2M1 = fp_levels(2, 1)
TOP = max(E2M1)
LOOK = sorted(E2M1)


def q_elem(y):
    s = -1.0 if y < 0 else 1.0
    a = abs(y)
    best = min(LOOK, key=lambda L: abs(L - a))
    return s * best


def q_e4m3(s):
    if s <= 0:
        return 0.0
    e = math.floor(math.log2(s))
    e = max(-6, min(e, 8))
    m = round((s / 2.0 ** e - 1.0) * 8)
    if m == 8:
        e, m = e + 1, 0
    return (1 + m / 8) * 2.0 ** e


def quantise_tensor(x, K, two_level):
    """Returns MSE per element."""
    if two_level:
        s32 = max(abs(v) for v in x) / (TOP * E4M3_MAX)
    else:
        s32 = 1.0
    err = 0.0
    for i in range(0, len(x), K):
        blk = x[i:i + K]
        amax = max(abs(v) for v in blk)
        if amax == 0:
            continue
        s8 = q_e4m3((amax / s32) / TOP)
        s = s32 * s8
        if s <= 0:
            err += sum(v * v for v in blk)
            continue
        for v in blk:
            err += (s * q_elem(v / s) - v) ** 2
    return err / len(x)


def tensor(n, sigma, crest):
    """Normal tensor whose maximum is forced to crest*sigma, matching the published shape."""
    x = [random.gauss(0, sigma) for _ in range(n)]
    m = max(abs(v) for v in x)
    target = crest * sigma
    j = max(range(n), key=lambda i: abs(x[i]))
    x[j] = target if x[j] > 0 else -target
    # clip anything else above target so the tensor max is exactly as specified
    return [max(-target, min(target, v)) for v in x]


N = 65536
KS = [8, 16, 32, 64, 128, 256]
print("Monte-Carlo test of our own prediction (no integrals used)\n")
print("MSE per element, each row divided by its own K=256 value")
print("minimum away from K=8 = inversion (finer blocks worse)\n")

for two_level, label in ((False, "SINGLE-level (IBM's setup)"), (True, "TWO-level (NVFP4)")):
    print(f"  {label}")
    for sigma in (2e-3, 8e-3, 3e-2):
        for crest in (4.5,):
            x = tensor(N, sigma, crest)
            vals = [quantise_tensor(x, K, two_level) for K in KS]
            ref = vals[-1]
            imin = min(range(len(vals)), key=lambda i: vals[i])
            flag = "" if imin == 0 else f"   INVERSION below K={KS[imin]}"
            print(f"    sigma={sigma:<8.0e}" + "".join(f"{v/ref:>9.3f}" for v in vals) + flag)
    print()

print("  columns: K = " + "  ".join(f"{k:>6}" for k in KS))
print("\n  Prediction under test: inversion present with one level, absent with two.")
