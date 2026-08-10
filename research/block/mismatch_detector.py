#!/usr/bin/env python3
"""Can a cheap per-block statistic tell you WHICH mismatch a block has?

The design rule from THEOREM_2026-08-09 is: compose levers only when the second
mismatch is actually present. That makes detecting presence the useful artefact --
otherwise you must trial-quantise with every candidate, which is what makes selection
expensive.

Two candidate statistics, both computable in one pass:
  crest  = amax / rms          -- large when a few outliers dominate  (RANGE mismatch)
  kurt   = E[x^4]/E[x^2]^2     -- peakedness of the bulk              (SHAPE mismatch)

MixFP4 already uses crest factor to choose between FP-like and INT-like codebooks
(their §2.2 gives a threshold of 2.224). The open question here is whether crest also
predicts the ESCAPE lever's payoff, which is a different mismatch from codebook shape.

Reported: correlation of each statistic with each lever's realised gain, then a
one-threshold rule scored against the oracle that trial-quantises everything.
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
E3M0 = fp_levels(3, 0)
INT4 = [i / 7 for i in range(8)]


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
        if i == j:
            out.append(blk[i])
        else:
            out.append(qr[k]); k += 1
    return out


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def stats(blk):
    n = len(blk)
    m2 = sum(v * v for v in blk) / n
    if m2 == 0:
        return 0.0, 0.0
    rms = math.sqrt(m2)
    crest = max(abs(v) for v in blk) / rms
    m4 = sum(v ** 4 for v in blk) / n
    kurt = m4 / (m2 * m2)
    return crest, kurt


def corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n * sx * sy)


# blocks drawn from a deliberately heterogeneous mix, as real tensors are
def make_blocks(nblk):
    out = []
    for _ in range(nblk):
        r = random.random()
        if r < 0.34:                       # clean gaussian
            blk = [random.gauss(0, 1) for _ in range(K)]
        elif r < 0.67:                     # a couple of strong outliers
            blk = [random.gauss(0, 1) * (25.0 if random.random() < 0.06 else 1.0)
                   for _ in range(K)]
        else:                              # flat-ish, uniform bulk
            blk = [random.uniform(-1, 1) for _ in range(K)]
        out.append(blk)
    return out


blocks = make_blocks(3000)
crests, kurts = [], []
g_esc, g_shape = [], []
for blk in blocks:
    if max(abs(v) for v in blk) == 0:
        continue
    c, k = stats(blk)
    base = mse(blk, q_block(blk, E2M1))
    if base == 0:
        continue
    e = mse(blk, q_escape(blk, E2M1))
    # shape lever: best of the two alternative codebooks for this block
    s = min(mse(blk, q_block(blk, E3M0)), mse(blk, q_block(blk, INT4)))
    crests.append(c); kurts.append(k)
    g_esc.append(base / e if e else 0.0)
    g_shape.append(base / s if s else 0.0)

print("Which statistic predicts which lever?  (Pearson r over 3000 blocks)\n")
print(f"  {'':<10}{'escape gain':>14}{'shape gain':>13}")
print(f"  {'crest':<10}{corr(crests, g_esc):>14.3f}{corr(crests, g_shape):>13.3f}")
print(f"  {'kurtosis':<10}{corr(kurts, g_esc):>14.3f}{corr(kurts, g_shape):>13.3f}")

# one-threshold rule on crest: escape when the block looks outlier-dominated
best = None
for thr in [1.5 + 0.1 * i for i in range(45)]:
    tot = 0.0
    for c, ge, gs in zip(crests, g_esc, g_shape):
        tot += ge if c >= thr else gs
    if best is None or tot > best[1]:
        best = (thr, tot)
thr = best[0]
rule = sum(ge if c >= thr else gs for c, ge, gs in zip(crests, g_esc, g_shape))
oracle = sum(max(ge, gs) for ge, gs in zip(g_esc, g_shape))
always_e = sum(g_esc)
always_s = sum(g_shape)
n = len(g_esc)
print(f"\nOne-threshold rule on crest factor (threshold {thr:.1f}), mean gain per block:")
print(f"  always escape        {always_e/n:>8.3f}")
print(f"  always shape         {always_s/n:>8.3f}")
print(f"  crest-threshold rule {rule/n:>8.3f}")
print(f"  oracle (try both)    {oracle/n:>8.3f}")
print(f"\n  rule captures {100*(rule-max(always_e,always_s))/(oracle-max(always_e,always_s)):.0f}%"
      f" of the headroom between the best fixed choice and the oracle,")
print(f"  at one pass over the block instead of trial-quantising every candidate.")
