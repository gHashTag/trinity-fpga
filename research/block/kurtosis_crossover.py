#!/usr/bin/env python3
"""Where does E2M1 overtake a density-matched codebook? A crossover in tail weight.

The re-audit produced a clean pair of facts:

    weights      excess kurtosis  +1.1   -> a p_eff-derived codebook wins by 6-9%
    activations  excess kurtosis +65.8   -> E2M1 wins, and int4/NF4 lose badly (+74%/+44%)

Two regimes with opposite winners implies a crossover. If it can be located, then a tensor's
KURTOSIS ALONE predicts which 4-bit format will win on it -- a usable design rule, and one that
is independent of whether our codebook ever leads overall.

Method. Generate blocks from a Gaussian scale mixture, x = z * exp(sigma_h * u), z,u ~ N(0,1)
independent per ELEMENT. This has excess kurtosis 3*(exp(4*sigma_h^2) - 1), tunable smoothly
from 0 to very large, and it is the right model for the real situation: activation outliers vary
per channel, i.e. WITHIN a block, and block-max scaling cannot normalise them away. (A mixture
that varied per BLOCK instead would be removed entirely by the block scale -- worth stating,
because it is the difference between a heavy-tailed tensor that matters and one that does not.)

The codebooks compared are the correctly-implemented ones: E2M1 with its subnormal, real NF4,
int4, and the DP optimum derived from Gaussian weights (our table).

Prediction being tested: a single crossover kurtosis, below which the density-matched table
wins and above which E2M1 does.
"""
import math

import numpy as np

rng = np.random.default_rng(20260810)
K, N = 32, 400000

MAGS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
E2M1 = np.array(sorted(set([-v / 6 for v in MAGS] + [v / 6 for v in MAGS])))
NF4 = np.array([-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
                -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
                0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
                0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
                0.7229568362236023, 1.0])
INT4 = np.array(sorted(set([-i / 7 for i in range(8)] + [i / 7 for i in range(8)])))
DP16Z = np.array([-1.0000, -0.7805, -0.6094, -0.4645, -0.3361, -0.2183, -0.1066, 0.0000,
                  0.0944, 0.1901, 0.2908, 0.3987, 0.5162, 0.6491, 0.8053, 1.0000])
CANDS = {"E2M1": E2M1, "NF4": NF4, "int4": INT4, "DP-16+zero (ours)": DP16Z}


def mse(b, lv):
    a = np.abs(b).max(1)
    ok = a > 0
    b, a = b[ok], a[ok]
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, b / a[:, None]).clip(0, len(lv) - 1)
    return float(((lv[idx] * a[:, None] - b) ** 2).mean())


print("Crossover in tail weight: which 4-bit codebook wins, as a function of kurtosis\n")
print("  Gaussian scale mixture, per-ELEMENT scale (the case block scaling cannot remove)\n")
print(f"  {'sigma_h':>8}{'excess kurt':>13}   " + "".join(f"{n:>20}" for n in CANDS)
      + "   winner")
prev = None
cross = []
for sh in (0.0, 0.15, 0.25, 0.35, 0.45, 0.55, 0.7, 0.85, 1.0, 1.2):
    z = rng.standard_normal(N)
    u = rng.standard_normal(N)
    x = (z * np.exp(sh * u)).reshape(-1, K)
    flat = x.reshape(-1)
    ek = float(((flat - flat.mean()) ** 4).mean() / flat.std() ** 4 - 3)
    vals = {n: mse(x, lv) for n, lv in CANDS.items()}
    ref = vals["E2M1"]
    win = min(vals, key=lambda n: vals[n])
    print(f"  {sh:>8.2f}{ek:>13.1f}   "
          + "".join(f"{vals[n]/ref:>20.4f}" for n in CANDS) + f"   {win}")
    if prev is not None and (prev == "E2M1") != (win == "E2M1"):
        cross.append((prev, win, ek))
    prev = win

print("\n  (all columns relative to E2M1)")
if cross:
    for a, b, ek in cross:
        print(f"\n  CROSSOVER: winner changes {a} -> {b} near excess kurtosis ~{ek:.0f}")
else:
    print("\n  No crossover found in this range.")

print("\n  Theoretical kurtosis of this mixture: 3*(exp(4*sigma_h^2) - 1)")
for sh in (0.25, 0.5, 1.0):
    print(f"    sigma_h={sh}: {3*(math.exp(4*sh*sh)-1):.1f}")

print("\n  Real anchors measured earlier: SmolLM2 weights +1.1 (our table wins by 6-9%),")
print("  SmolLM2 activations +65.8 (E2M1 wins). The crossover above should sit between them")
print("  for the rule to be consistent with both.")
