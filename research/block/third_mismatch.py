#!/usr/bin/env python3
"""A third mismatch we did not invent: wasted code. Does it compose?

NxFP (arXiv:2412.19821) identifies three challenges of low-bit MxFP. Two match our
taxonomy (range, shape). The third we never considered:

  WASTED CODE -- sign-magnitude FP4 spends two codes on +0 and -0. One is redundant.
  NxFP's "Code Recycling" remaps it to half the smallest quantisation level.

This is a better test of the boundary than our own levers, because we did not design it
and cannot have tuned it to fit the theory.

Our theory predicts composition works when mismatches DIFFER. So:
  - recycling + shape      should compose (redundancy vs spacing)
  - recycling + escape     ??? recycling adds resolution near ZERO, and escape frees
                           resolution for the bulk by removing the peak. Both end up
                           helping small values. If they overlap, the theory predicts
                           they should NOT compose well -- and that is a real risk to
                           the theory, not a safe bet.

E2M1 magnitudes are {0, 0.5, 1, 1.5, 2, 3, 4, 6}. Recycling gives the negative side one
extra magnitude at 0.25, since the -0 code is otherwise dead.
"""
import math
import random

random.seed(20260809)
K = 32

E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
E2M1_RECYCLED_NEG = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]   # -0 code reused
E3M0 = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]


def q_block(blk, pos_levels, neg_levels=None):
    neg_levels = neg_levels or pos_levels
    amax = max((abs(v) for v in blk), default=0.0)
    if amax == 0:
        return [0.0] * len(blk)
    s = amax / max(pos_levels)
    out = []
    for v in blk:
        lv = pos_levels if v >= 0 else neg_levels
        sg = 1.0 if v >= 0 else -1.0
        out.append(sg * min(lv, key=lambda L: abs(L - abs(v) / s)) * s)
    return out


def q_escape(blk, pos_levels, neg_levels=None):
    j = max(range(len(blk)), key=lambda i: abs(blk[i]))
    rest = [v for i, v in enumerate(blk) if i != j]
    qr = q_block(rest, pos_levels, neg_levels)
    out, k = [], 0
    for i in range(len(blk)):
        if i == j:
            out.append(blk[i])
        else:
            out.append(qr[k]); k += 1
    return out


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def workload(kind, n):
    if kind == "heavy-tail":
        return [random.gauss(0, 1) * (25.0 if random.random() < 0.05 else 1.0)
                for _ in range(n)]
    if kind == "weights":                       # the published shape of real weights
        return [random.gauss(0, 1) for _ in range(n)]
    return [random.uniform(-1, 1) for _ in range(n)]


METHODS = [
    ("baseline",            lambda b: q_block(b, E2M1)),
    ("C: recycle",          lambda b: q_block(b, E2M1, E2M1_RECYCLED_NEG)),
    ("S: shape",            lambda b: q_block(b, E3M0)),
    ("O: escape",           lambda b: q_escape(b, E2M1)),
    ("C+S",                 lambda b: q_block(b, E3M0, [0.125] + E3M0[1:])),
    ("C+O",                 lambda b: q_escape(b, E2M1, E2M1_RECYCLED_NEG)),
    ("O+S",                 lambda b: q_escape(b, E3M0)),
    ("C+O+S",               lambda b: q_escape(b, E3M0, [0.125] + E3M0[1:])),
]

print("Does the THIRD mismatch (wasted code) compose with the other two?\n")
print(f"  {'workload':<12}" + "".join(f"{n:>12}" for n, _ in METHODS[1:]))
for kind in ("weights", "heavy-tail", "uniform"):
    data = workload(kind, 32768)
    tot = {}
    for nm, fn in METHODS:
        t = 0.0
        for i in range(0, len(data), K):
            blk = data[i:i + K]
            if max((abs(v) for v in blk), default=0) == 0:
                continue
            t += mse(blk, fn(blk))
        tot[nm] = t
    base = tot["baseline"]
    print(f"  {kind:<12}" + "".join(f"{base/tot[n]:>12.3f}" for n, _ in METHODS[1:]))

print("\n  gains vs baseline E2M1; >1 is better")
print("  Theory: C+S and O+S compose (different mismatches).")
print("  C+O is the risky one -- both add resolution near zero, so if they overlap")
print("  they should NOT compose, and the theory would be exposed if they did.")
