#!/usr/bin/env python3
"""Is the observed universality a contraction property, or just two similar models?

The previous section claimed max-normalisation "strips most tail-shape information", offered
as an explanation for why SmolLM2's and Qwen's codebooks agree to ~0.003 per level. That was
asserted, not tested, and there is an obvious deflationary alternative: the two models are
simply similar, and no contraction is involved.

The two hypotheses make different quantitative predictions:

  CONTRACTION   a given change in the input density produces a SMALLER change in p_eff, so the
                codebook distance per unit of distributional difference is small in general.

  SIMILARITY    no contraction; the codebooks agree because the inputs agree. Synthetic
                densities that differ a lot should then produce codebooks that differ a lot,
                in proportion.

So: measure codebook distance against a common measure of distributional difference (excess
kurtosis gap) for synthetic pairs whose gap is known, and compare the slope to the real-model
pair. If real models fall on the same line, the effect is SIMILARITY and the doc's claim is an
overstatement that must be narrowed.

This is deliberately set up to disconfirm a claim already written down.
"""
import math

import numpy as np

from design_space import DISTS, lloyd, p_eff

K = 32

# excess kurtosis of each analytic density (exact, standard values)
KURT = {"gaussian": 0.0, "laplace": 3.0, "student-t3": float("inf")}
# t3 has undefined 4th moment; use a large finite stand-in for the SAMPLE kurtosis regime
KURT_EFF = {"gaussian": 0.0, "laplace": 3.0, "student-t3": 12.0}

cb = {n: np.array(lloyd(*p_eff(DISTS[n], K), nlev=8)) for n in DISTS}

print("Testing the contraction claim against the deflationary alternative\n")
print("  codebook distance = mean |level difference| over the 6 interior levels\n")


def dist(a, b):
    return float(np.mean(np.abs(np.asarray(a)[1:7] - np.asarray(b)[1:7])))


print("  synthetic pairs (kurtosis gap known exactly):")
pairs = [("gaussian", "laplace"), ("gaussian", "student-t3"), ("laplace", "student-t3")]
slopes = []
for a, b in pairs:
    dk = abs(KURT_EFF[a] - KURT_EFF[b])
    d = dist(cb[a], cb[b])
    slopes.append(d / dk)
    print(f"    {a:<11} vs {b:<11}  kurt gap {dk:>5.1f}   codebook dist {d:.5f}"
          f"   per unit kurt {d/dk:.6f}")

# real models, from real_weights.py (empirical p_eff, K=32, fit halves)
SMOL = [0.0000, 0.1071, 0.2184, 0.3361, 0.4644, 0.6091, 0.7808, 1.0000]
QWEN = [0.0000, 0.1058, 0.2158, 0.3328, 0.4608, 0.6060, 0.7789, 1.0000]
K_SMOL, K_QWEN = 1.07, 1.71
dk_real = abs(K_SMOL - K_QWEN)
d_real = dist(SMOL, QWEN)
print(f"\n  real models:")
print(f"    SmolLM2     vs Qwen2.5      kurt gap {dk_real:>5.2f}   codebook dist {d_real:.5f}"
      f"   per unit kurt {d_real/dk_real:.6f}")

med = float(np.median(slopes))
pred = med * dk_real
print(f"\n  synthetic slope (median): {med:.6f} per unit kurtosis")
print(f"  predicted real-model distance under SIMILARITY: {pred:.5f}")
print(f"  observed:                                       {d_real:.5f}")
ratio = d_real / pred if pred > 0 else float("inf")
print(f"  observed / predicted = {ratio:.2f}")
print()
if 0.5 <= ratio <= 2.0:
    print("  VERDICT: consistent with SIMILARITY. The real-model agreement is explained by the")
    print("  models being close in tail weight, NOT by an extra contraction. The doc's claim")
    print("  that max-normalisation 'strips most tail-shape information' is an OVERSTATEMENT")
    print("  and must be narrowed to: p_eff varies smoothly and slowly with tail weight, and")
    print("  real LLM weight tensors happen to occupy a narrow band of it.")
else:
    print("  VERDICT: NOT explained by similarity alone; a contraction effect is present.")

print("\n  Independent check -- how far is each real codebook from the analytic Gaussian one,")
print("  given that real weights are NOT Gaussian (kurtosis +1.07 / +1.71 vs 0)?")
g = cb["gaussian"]
print(f"    gaussian vs SmolLM2 {dist(g, SMOL):.5f}    gaussian vs Qwen {dist(g, QWEN):.5f}")
print(f"    gaussian vs laplace {dist(g, cb['laplace']):.5f}  (kurt gap 3.0, for scale)")
