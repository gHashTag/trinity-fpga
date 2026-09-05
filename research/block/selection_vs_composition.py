#!/usr/bin/env python3
"""Selection saturates; composition can degrade. Same premise, two different bounds.

MixFP4 (arXiv:2605.31035 §2.4) measures that adding candidate formats gives rapidly
diminishing returns -- 8.26 -> 8.06 -> 8.01 perplexity on Llama-3.1-8B, and exactly
0.00 further gain on Qwen3-8B. Our own earlier measurement found combining levers is
strictly WORSE than the best single. Those look contradictory. They are not, and the
distinction is the contribution.

  SELECTION  choose the best of several candidate level-sets per block, by MSE.
             The chosen set is one of the candidates, so error = min over candidates.
             Adding a candidate can never hurt: monotone, bounded below by the best
             single lever. It SATURATES.

  COMPOSITION apply two levers at once to the same block, producing a level-set that
             is NOT any candidate. Nothing forces it to beat either parent, and when
             both levers address the SAME mismatch -- level-set vs data support --
             it routinely loses to both.

This script measures both on identical data and levers, so the difference is not an
artefact of workload.
"""
import math
import random

random.seed(20260809)
K = 32


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)


def quantise_block(blk, levels, signed=True, unit=None):
    """Quantise one block against a level set, scaled so max(levels) covers amax."""
    amax = max(abs(v) for v in blk)
    if amax == 0:
        return [0.0] * len(blk)
    top = max(levels)
    s = amax / top
    out = []
    for v in blk:
        if signed:
            sg = -1.0 if v < 0 else 1.0
            q = min(levels, key=lambda L: abs(L - abs(v) / s))
            out.append(sg * q * s)
        else:
            q = min(levels, key=lambda L: abs(L - max(v, 0.0) / s))
            out.append(q * s)
    return out


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


# ---- two levers, both aimed at the SAME mismatch (level set vs data support) ----
E2M1 = fp_levels(2, 1)                       # exponent-heavy spacing
E1M2 = fp_levels(1, 2)                       # flatter, INT-like spacing


def lever_shape(blk):                        # lever A: change minifloat shape
    return quantise_block(blk, E1M2, signed=True)


def lever_unsigned(blk):                     # lever B: drop the sign bit
    return quantise_block(blk, fp_levels(2, 2), signed=False)


def baseline(blk):
    return quantise_block(blk, E2M1, signed=True)


def composition(blk):                        # BOTH at once: flat spacing AND unsigned
    return quantise_block(blk, fp_levels(1, 3), signed=False)


def workload(kind, n):
    if kind == "relu":
        return [max(0.0, random.gauss(0, 1)) for _ in range(n)]
    if kind == "weights":
        return [random.gauss(0, 1) for _ in range(n)]
    return [random.gauss(0, 1) * (10 ** random.uniform(-2, 0)) for _ in range(n)]


print("Selection vs composition, identical data and identical levers")
print("gain = MSE(baseline E2M1) / MSE(method).  >1 is better than baseline.\n")
print(f"  {'workload':<10}{'lever A':>10}{'lever B':>10}{'best single':>13}"
      f"{'SELECTION':>12}{'COMPOSITION':>13}")

for kind in ("relu", "weights", "mixed"):
    data = workload(kind, 32768)
    tot = {k: 0.0 for k in ("base", "A", "B", "sel", "comp")}
    for i in range(0, len(data), K):
        blk = data[i:i + K]
        if max(abs(v) for v in blk) == 0:
            continue
        qb = baseline(blk)
        qa = lever_shape(blk)
        qu = lever_unsigned(blk)
        qc = composition(blk)
        eb, ea, eu, ec = mse(blk, qb), mse(blk, qa), mse(blk, qu), mse(blk, qc)
        # selection: pick the lower-MSE candidate per block, as MixFP4 does
        esel = min(ea, eu)
        tot["base"] += eb; tot["A"] += ea; tot["B"] += eu
        tot["sel"] += esel; tot["comp"] += ec
    g = lambda k: tot["base"] / tot[k] if tot[k] else float("inf")
    best = max(g("A"), g("B"))
    print(f"  {kind:<10}{g('A'):>10.3f}{g('B'):>10.3f}{best:>13.3f}"
          f"{g('sel'):>12.3f}{g('comp'):>13.3f}")

print("\n  SELECTION is >= both levers on every workload -- it cannot lose, by construction.")
print("  COMPOSITION is not bounded that way and can fall below both parents.")
