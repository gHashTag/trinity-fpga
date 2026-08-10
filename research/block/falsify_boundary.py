#!/usr/bin/env python3
"""The test that can falsify our own boundary claim.

THEOREM_2026-08-09 says composition fails when both levers address the SAME mismatch
(level-set vs data support), and that the boundary is drawn at "same mismatch" -- dMX
composes successfully across layers because those are DIFFERENT mismatches.

Every lever measured so far was picked because it addresses the one mismatch. So
confirming the theorem on them is close to circular. The honest test is to build two
levers that address DIFFERENT mismatches inside a single block, where the theory
PREDICTS composition should work, and see whether it does.

  mismatch 1  RANGE: a few outliers force the block scale up, so the dense bulk gets
              only a fraction of the available levels.
              lever O -- escape the single largest element, store it separately, and
              rescale the remaining elements to their own maximum.

  mismatch 2  SHAPE: the spacing of the level set does not match the shape of the bulk.
              lever S -- flatter, INT-like spacing (E1M2) instead of exponent-heavy E2M1.

These are different defects of the same quantiser. If the boundary is drawn correctly,
composition here should beat both parents. If it does not, the theory is wrong or the
boundary is in the wrong place.

CAVEAT, stated up front: lever O spends extra bits (one escaped value plus an index).
This measures whether the MISMATCHES compose, not a bit-fair format comparison. The
composition question is about error structure; the bit cost is noted, not hidden.
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


E2M1 = fp_levels(2, 1)
E1M2 = fp_levels(1, 2)


def q_block(blk, levels):
    amax = max((abs(v) for v in blk), default=0.0)
    if amax == 0:
        return [0.0] * len(blk)
    s = amax / max(levels)
    out = []
    for v in blk:
        sg = -1.0 if v < 0 else 1.0
        out.append(sg * min(levels, key=lambda L: abs(L - abs(v) / s)) * s)
    return out


def q_escape(blk, levels):
    """Lever O: store the largest element exactly, quantise the rest to their own max."""
    j = max(range(len(blk)), key=lambda i: abs(blk[i]))
    rest = [v for i, v in enumerate(blk) if i != j]
    qrest = q_block(rest, levels)
    out, k = [], 0
    for i in range(len(blk)):
        if i == j:
            out.append(blk[i])          # escaped: exact
        else:
            out.append(qrest[k]); k += 1
    return out


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def workload(kind, n):
    if kind == "heavy-tail":            # a few big outliers over a dense bulk
        return [random.gauss(0, 1) * (30.0 if random.random() < 0.02 else 1.0)
                for _ in range(n)]
    if kind == "weights":
        return [random.gauss(0, 1) for _ in range(n)]
    return [random.gauss(0, 1) * (10 ** random.uniform(-1, 0)) for _ in range(n)]


print("Levers addressing DIFFERENT mismatches — theory predicts composition WORKS here")
print("gain = MSE(baseline E2M1) / MSE(method); >1 better than baseline\n")
print(f"  {'workload':<12}{'O: escape':>11}{'S: shape':>11}{'best':>8}"
      f"{'SELECTION':>11}{'COMPOSITION':>13}{'verdict':>22}")

for kind in ("heavy-tail", "weights", "mixed"):
    data = workload(kind, 32768)
    t = {k: 0.0 for k in ("base", "O", "S", "sel", "comp")}
    for i in range(0, len(data), K):
        blk = data[i:i + K]
        if max((abs(v) for v in blk), default=0) == 0:
            continue
        eb = mse(blk, q_block(blk, E2M1))
        eo = mse(blk, q_escape(blk, E2M1))          # range mismatch addressed
        es = mse(blk, q_block(blk, E1M2))           # shape mismatch addressed
        ec = mse(blk, q_escape(blk, E1M2))          # BOTH
        t["base"] += eb; t["O"] += eo; t["S"] += es
        t["sel"] += min(eo, es); t["comp"] += ec
    g = lambda k: t["base"] / t[k] if t[k] else float("inf")
    best = max(g("O"), g("S"))
    comp = g("comp")
    verdict = "COMPOSES (> best)" if comp > best * 1.02 else (
              "ties best" if comp > best * 0.98 else "FAILS to compose")
    print(f"  {kind:<12}{g('O'):>11.3f}{g('S'):>11.3f}{best:>8.3f}"
          f"{g('sel'):>11.3f}{comp:>13.3f}{verdict:>22}")

print("\n  Theory predicts COMPOSITION > best for different mismatches.")
print("  If it does not exceed the best single lever, the boundary claim is wrong.")
