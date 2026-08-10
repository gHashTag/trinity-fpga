#!/usr/bin/env python3
"""Enumerate mismatch classes from first principles, then test the untested ones.

Three mismatch classes are verified independent so far, but all three were found by
INSPECTION -- two by us, one imported from NxFP. Finding things by inspection is how
taxonomies end up incomplete. So enumerate the degrees of freedom instead.

A block quantiser is fully described by: a set of levels, a code assignment, the unit
that shares a scale, and the basis the data sits in. Each can mismatch the data:

  1 EXTENT        level range vs data range          -> escape / NanoMantissa   [verified]
  2 DENSITY       level spacing vs data density      -> codebook choice / AM    [verified]
  3 CODE USE      redundant or dead codes            -> code recycling          [verified]
  4 SYMMETRY      symmetric levels vs skewed data    -> unsigned / asymmetric   [tested before,
                                                        but never as a composition partner]
  5 GRANULARITY   how many values share one scale    -> block size              [measured: a trade]
  6 BASIS         axis-aligned levels vs correlated  -> rotation (Hadamard)     [NEVER TESTED]

Class 6 is the interesting gap: MixFP4 notes Hadamard transforms "reshape local
distributions and may change which low-bit format is preferable", and QuaRot-style
rotation is standard practice -- but we never placed it in the taxonomy.

Risky prediction, recorded before measuring: rotation reduces crest factor, so it may
OVERLAP with extent (class 1). If it overlaps, theory says rotation and escape should
NOT compose. That is a genuine risk, since rotation is widely believed to be complementary
to everything.
"""
import math
import random

random.seed(20260809)
K = 32
E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]


def q_block(blk, levels):
    amax = max((abs(v) for v in blk), default=0.0)
    if amax == 0:
        return [0.0] * len(blk)
    s = amax / max(levels)
    return [(-1.0 if v < 0 else 1.0) * min(levels, key=lambda L: abs(L - abs(v) / s)) * s
            for v in blk]


def q_escape(blk, levels):
    j = max(range(len(blk)), key=lambda i: abs(blk[i]))
    rest = [v for i, v in enumerate(blk) if i != j]
    qr = q_block(rest, levels)
    out, k = [], 0
    for i in range(len(blk)):
        out.append(blk[i] if i == j else qr[k])
        if i != j:
            k += 1
    return out


def hadamard(n):
    """Sylvester Hadamard matrix, n a power of two, normalised to be orthonormal."""
    H = [[1.0]]
    while len(H) < n:
        H = [row + row for row in H] + [row + [-v for v in row] for row in H]
    s = 1.0 / math.sqrt(n)
    return [[v * s for v in row] for row in H]


HAD = hadamard(K)


def rot(v, H):
    return [sum(H[i][j] * v[j] for j in range(len(v))) for i in range(len(H))]


def q_rotated(blk, levels, inner=q_block):
    """Class 6: quantise in the rotated basis, then rotate back."""
    y = rot(blk, HAD)
    qy = inner(y, levels)
    return rot(qy, HAD)            # Hadamard is its own inverse when orthonormal


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def workload(kind, n):
    if kind == "heavy-tail":
        return [random.gauss(0, 1) * (25.0 if random.random() < 0.05 else 1.0)
                for _ in range(n)]
    if kind == "weights":
        return [random.gauss(0, 1) for _ in range(n)]
    if kind == "correlated":       # structure a rotation should be able to exploit
        out = []
        for _ in range(n // K):
            base = random.gauss(0, 1)
            out += [base + 0.25 * random.gauss(0, 1) for _ in range(K)]
        return out
    return [random.uniform(-1, 1) for _ in range(n)]


METHODS = [
    ("baseline",  lambda b: q_block(b, E2M1)),
    ("O: escape", lambda b: q_escape(b, E2M1)),
    ("R: rotate", lambda b: q_rotated(b, E2M1)),
    ("R+O",       lambda b: q_rotated(b, E2M1, inner=q_escape)),
]

print("Class 6 (BASIS) — rotation. Does it compose with class 1 (EXTENT)?\n")
print(f"  {'workload':<12}" + "".join(f"{n:>12}" for n, _ in METHODS[1:]) + f"{'verdict':>22}")
for kind in ("weights", "heavy-tail", "correlated"):
    data = workload(kind, 8192)
    tot = {}
    for nm, fn in METHODS:
        t = 0.0
        for i in range(0, len(data), K):
            blk = data[i:i + K]
            if len(blk) < K or max((abs(v) for v in blk), default=0) == 0:
                continue
            t += mse(blk, fn(blk))
        tot[nm] = t
    base = tot["baseline"]
    g = {n: base / tot[n] for n, _ in METHODS[1:]}
    best = max(g["O: escape"], g["R: rotate"])
    v = "COMPOSES" if g["R+O"] > best * 1.02 else (
        "ties" if g["R+O"] > best * 0.98 else "OVERLAPS (no gain)")
    print(f"  {kind:<12}" + "".join(f"{g[n]:>12.3f}" for n, _ in METHODS[1:]) + f"{v:>22}")

print("\n  gains vs baseline E2M1; >1 better")
print("  Rotation lowers crest factor, so overlap with EXTENT is the live risk.")
