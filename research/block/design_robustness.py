#!/usr/bin/env python3
"""Attacking the derived codebook: model mismatch, quantised scales, and a bit-fair account.

design_space.py derived a codebook from p_eff and it beat MXFP4's E2M1 by 41-65% MSE. Three
reasons to distrust that number, each tested here.

  (1) MODEL MISMATCH. The codebook was derived from the very density that generated the test
      data. Real tensors are not exactly Gaussian, Laplace, or t3. So: derive under ONE
      assumption, measure under ALL of them. If the win survives the wrong model, it is a
      property of the CONDITIONING (*), not of knowing the density.

  (2) QUANTISED SCALE. design_space.py used an exact scale. Real MX quantises the block scale
      to UE4M3, which perturbs every level. A codebook tuned to an exact scale may lose its
      advantage once the scale is snapped.

  (3) BIT FAIRNESS. A free 8-magnitude codebook is a 16-entry lookup table. E2M1 decodes
      directly from the bit pattern. The table is the cost of the win and must be stated,
      not buried -- the same discipline applied to the composition results earlier.
"""
import math
import random

from design_space import (DISTS, fp_levels, lloyd, nf4_style, p_eff, q, sample)

random.seed(20260810)          # a different seed from the derivation script
E4M3_MAX = 448.0


def q_ue4m3(s):
    if s <= 0:
        return 0.0
    e = math.floor(math.log2(s))
    e = max(-6, min(e, 8))
    m = round((s / 2.0 ** e - 1.0) * 8)
    if m == 8:
        e, m = e + 1, 0
    return (1 + m / 8) * 2.0 ** e


def measured(lv, data, K, quant_scale=False):
    tot, nb = 0.0, 0
    top = max(lv)
    s32 = (max(abs(v) for v in data) / E4M3_MAX) if quant_scale else 1.0
    for i in range(0, len(data) - K, K):
        blk = data[i:i + K]
        amax = max(abs(v) for v in blk)
        if amax == 0:
            continue
        if quant_scale:
            s = s32 * q_ue4m3((amax / s32) / top)
        else:
            s = amax / top
        if s <= 0:
            tot += sum(v * v for v in blk) / K
            nb += 1
            continue
        tot += sum((s * q(v / s, lv) - v) ** 2 for v in blk) / K
        nb += 1
    return tot / nb


K = 32
DATA = {d: sample(d, 300000) for d in DISTS}
DERIVED = {d: lloyd(*p_eff(DISTS[d], K), nlev=8) for d in DISTS}

print("(1) MODEL MISMATCH -- derived under one density, measured under another\n")
print("    MSE relative to E2M1 on the SAME data. Lower is better; >1 means worse than MXFP4.\n")
head = "".join(f"{d:>14}" for d in DISTS)
print(f"    {'derived from':<16}{head}      (measured on)")
for src in DISTS:
    lv = DERIVED[src]
    row = ""
    for tgt in DISTS:
        ref = measured(fp_levels(2, 1), DATA[tgt], K)
        row += f"{measured(lv, DATA[tgt], K)/ref:>14.3f}"
    print(f"    {src:<16}{row}")
ref_row = ""
for tgt in DISTS:
    ref = measured(fp_levels(2, 1), DATA[tgt], K)
    ref_row += f"{measured([i/7 for i in range(8)], DATA[tgt], K)/ref:>14.3f}"
print(f"    {'int4 (baseline)':<16}{ref_row}")
nf_row = ""
for tgt in DISTS:
    ref = measured(fp_levels(2, 1), DATA[tgt], K)
    nf_row += f"{measured(nf4_style(DISTS['gaussian']), DATA[tgt], K)/ref:>14.3f}"
print(f"    {'nf4 (gaussian)':<16}{nf_row}")

print("\n(2) QUANTISED SCALE (UE4M3) -- does the advantage survive a snapped scale?\n")
for tgt in DISTS:
    ref_e = measured(fp_levels(2, 1), DATA[tgt], K, quant_scale=True)
    d_e = measured(DERIVED["gaussian"], DATA[tgt], K, quant_scale=True)
    i_e = measured([i / 7 for i in range(8)], DATA[tgt], K, quant_scale=True)
    ref_x = measured(fp_levels(2, 1), DATA[tgt], K)
    d_x = measured(DERIVED["gaussian"], DATA[tgt], K)
    print(f"    {tgt:<12} exact scale: derived {d_x/ref_x:.3f}   "
          f"UE4M3 scale: derived {d_e/ref_e:.3f}, int4 {i_e/ref_e:.3f}   (vs E2M1 = 1.000)")

print("\n(3) BIT FAIRNESS -- what the win costs\n")
print("    E2M1        4 bits/element, decoded combinationally from the bit pattern, no table")
print("    int4        4 bits/element, no table")
print("    derived     4 bits/element + a 16-entry constant lookup table per format")
print("    The element bit-width is identical; the cost is a table, and NF4 already ships one")
print("    in production (bitsandbytes), so the cost is known to be payable.")
print("\n    NOT tested here: real trained weights. Every density above is synthetic. That is")
print("    the load-bearing gap in this result and no amount of further synthetic work closes it.")
