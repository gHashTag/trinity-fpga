#!/usr/bin/env python3
"""Is the derived codebook merely a local optimum, or THE optimum?

This matters more than another point of improvement. Lloyd-Max is a fixed-point iteration and
in general converges only to a LOCAL optimum. If the solution we derived is global, then a much
stronger statement follows:

  THEOREM (ceiling on codebook design). If the Lloyd-Max solution for p_eff is the global
  optimum over all N-level codebooks, then its distortion is a HARD LOWER BOUND for every
  4-bit block-max-scaled format. No codebook -- E2M1, NF4, int4, or any yet uninvented --
  can do better. The 41 % MSE / 61 % perplexity figures are then not a result to be improved
  on but a CEILING, and further gains must come from a different axis entirely (block size,
  scale format, rotation, escape, bit-width).

A theorem that says "stop looking here" is worth more than one that says "look harder", because
it redirects effort that would otherwise be wasted.

THREE INDEPENDENT LINES OF EVIDENCE, since any one alone is weak:

  (1) ANALYTIC. Fleischer's condition (1964): if the density is LOG-CONCAVE, the Lloyd-Max
      quantizer is unique and globally optimal. So test log-concavity of p_eff directly. This
      is the only line that could actually PROVE it.

  (2) MULTI-START. Run Lloyd from many random initialisations. If a second basin of attraction
      exists, random starts should find it.

  (3) ADVERSARIAL SEARCH. Try to BEAT the Lloyd solution by direct stochastic search with
      restarts. This is the honest attack: not "does Lloyd converge" but "can anything win".

If (1) holds, (2) and (3) are corroboration. If (1) fails, (2) and (3) are all we have, and the
claim must be stated as empirical rather than proved.
"""
import numpy as np

rng = np.random.default_rng(20260809)

# p_eff of real SmolLM2 weights, reconstructed from the analytic Gaussian model that matched
# it to within 0.005 per level; the shape is what matters for the optimality question.
from design_space import DISTS, p_eff as p_eff_analytic

vals_list, DY = p_eff_analytic(DISTS["gaussian"], 32)
P = np.array(vals_list)
NBIN = len(P)                      # design_space uses its own bin count; adopt it
Y = (np.arange(NBIN) + 0.5) * DY
P = P / (P.sum() * DY)


def distortion(lv):
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, Y)
    return float((P * DY * (lv[idx] - Y) ** 2).sum())


def lloyd(init, iters=500):
    lv = np.sort(np.clip(np.asarray(init, dtype=float), 0.0, 1.0))
    lv[0], lv[-1] = 0.0, 1.0
    for _ in range(iters):
        j = np.searchsorted((lv[:-1] + lv[1:]) / 2, Y)
        w = P * DY
        num = np.bincount(j, weights=w * Y, minlength=len(lv))
        den = np.bincount(j, weights=w, minlength=len(lv))
        new = np.where(den > 0, num / np.maximum(den, 1e-300), lv)
        new[0], new[-1] = 0.0, 1.0
        new = np.sort(new)
        if np.max(np.abs(new - lv)) < 1e-14:
            return new
        lv = new
    return lv


print("Is the derived codebook the GLOBAL optimum? Three independent lines.\n")

# ---------------------------------------------------------------- (1) analytic
print("(1) ANALYTIC -- Fleischer (1964): log-concave density => Lloyd-Max is globally unique\n")
mask = P > P.max() * 1e-6
lp = np.log(np.maximum(P, 1e-300))
d2 = lp[2:] - 2 * lp[1:-1] + lp[:-2]
inner = mask[1:-1]
viol = int((d2[inner] > 1e-9).sum())
frac = viol / max(inner.sum(), 1)
worst = float(d2[inner].max()) if inner.sum() else 0.0
print(f"    support bins: {int(mask.sum())}")
print(f"    bins where (log p)'' > 0: {viol}  ({frac*100:.2f}% of support)")
print(f"    worst positive second difference: {worst:+.3e}")
logconcave = frac < 0.01
print(f"    => p_eff is {'LOG-CONCAVE (within numerical noise)' if logconcave else 'NOT log-concave'}")
if logconcave:
    print("    => Fleischer's condition holds: the Lloyd-Max solution is the UNIQUE global")
    print("       optimum, and its distortion is a hard lower bound for all 4-bit codebooks.")
else:
    print("    => the analytic guarantee does NOT apply; global optimality can only be")
    print("       supported empirically below, and must be stated as such.")

# ---------------------------------------------------------------- (2) multistart
print("\n(2) MULTI-START -- 2000 random initialisations\n")
ref = lloyd(np.linspace(0, 1, 8))
d_ref = distortion(ref)
best, bestd = ref, d_ref
distinct = 0
for _ in range(2000):
    init = np.sort(rng.random(8))
    lv = lloyd(init)
    d = distortion(lv)
    if d < bestd - 1e-15:
        best, bestd = lv, d
        distinct += 1
    if np.max(np.abs(lv - ref)) > 1e-6:
        distinct += 1
print(f"    uniform-start solution distortion: {d_ref:.8e}")
print(f"    best over 2000 random starts:      {bestd:.8e}")
print(f"    starts converging elsewhere:       {distinct}")
print(f"    => {'single basin found' if distinct == 0 else 'MULTIPLE basins exist'}")

# ---------------------------------------------------------------- (3) adversarial
print("\n(3) ADVERSARIAL SEARCH -- try to beat it, 40k perturbations with restarts\n")
cur = ref.copy()
cur_d = d_ref
overall, overall_d = cur.copy(), cur_d
T = 0.02
for it in range(40000):
    if it % 8000 == 7999:
        cur = np.sort(rng.random(8))
        cur[0], cur[-1] = 0.0, 1.0
        cur_d = distortion(cur)
        T = 0.02
    cand = cur.copy()
    k = rng.integers(1, 7)
    cand[k] += rng.normal(0, T)
    cand = np.sort(np.clip(cand, 0.0, 1.0))
    cand[0], cand[-1] = 0.0, 1.0
    d = distortion(cand)
    if d < cur_d:
        cur, cur_d = cand, d
        if d < overall_d:
            overall, overall_d = cand.copy(), d
    T *= 0.99985
    T = max(T, 1e-4)
gap = (overall_d - d_ref) / d_ref * 100
print(f"    Lloyd solution:      {d_ref:.8e}")
print(f"    best found by search:{overall_d:.8e}")
print(f"    difference: {gap:+.4f}%")
print(f"    => {'search FAILED to beat Lloyd' if overall_d >= d_ref - 1e-14 else 'SEARCH BEAT LLOYD -- not optimal'}")

print("\n  Levels: " + " ".join(f"{v:.4f}" for v in ref))
print("\n  Consequence if all three hold: the codebook axis at 4 bits is CLOSED. Improvements")
print("  must come from block size, scale format, rotation, escape, or bit-width instead.")
