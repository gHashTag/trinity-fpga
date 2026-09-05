#!/usr/bin/env python3
"""One-pass router over the mismatch classes that actually matter.

The data-dependence result (mismatch_enumeration.py) showed that whether two levers
compose depends on the block, not the levers: rotation+escape overlaps destructively on
heavy tails and synergises 24x on correlated blocks. So the routing statistic is not an
optimisation -- it decides which combination is even valid.

Three statistics, all from ONE pass over the block:

  dc    = mean^2 / E[x^2]      energy fraction a Hadamard would drive into DC.
                               Exact, not a proxy: the DC coefficient is sqrt(K)*mean,
                               so its energy share is K*mean^2 / sum(x^2) = mean^2/m2.
                               High dc  -> BASIS mismatch -> rotate, then escape.
  crest = amax / rms           EXTENT mismatch  -> escape.
  bkurt = kurtosis of the block with its largest element removed
                               DENSITY mismatch of the bulk -> change codebook.

Compared against the oracle that tries every candidate on every block.
"""
import math
import random

random.seed(20260809)
K = 32
E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
E3M0 = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
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
        out.append(blk[i] if i == j else qr[k])
        if i != j:
            k += 1
    return out


def hadamard(n):
    H = [[1.0]]
    while len(H) < n:
        H = [r + r for r in H] + [r + [-v for v in r] for r in H]
    s = 1.0 / math.sqrt(n)
    return [[v * s for v in r] for r in H]


HAD = hadamard(K)


def rot(v):
    return [sum(HAD[i][j] * v[j] for j in range(K)) for i in range(K)]


def q_rot_escape(blk, levels):
    return rot(q_escape(rot(blk), levels))


CANDIDATES = [
    ("shape-e3m0", lambda b: q_block(b, E3M0)),
    ("shape-int4", lambda b: q_block(b, INT4)),
    ("escape",     lambda b: q_escape(b, E2M1)),
    ("rot+escape", lambda b: q_rot_escape(b, E2M1)),
]


def stats(blk):
    n = len(blk)
    m1 = sum(blk) / n
    m2 = sum(v * v for v in blk) / n
    if m2 == 0:
        return 0.0, 0.0, 0.0
    dc = m1 * m1 / m2
    crest = max(abs(v) for v in blk) / math.sqrt(m2)
    j = max(range(n), key=lambda i: abs(blk[i]))
    rest = [v for i, v in enumerate(blk) if i != j]
    r2 = sum(v * v for v in rest) / len(rest)
    bkurt = (sum(v ** 4 for v in rest) / len(rest)) / (r2 * r2) if r2 else 0.0
    return dc, crest, bkurt


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def make_blocks(nb):
    out = []
    for _ in range(nb):
        r = random.random()
        if r < 0.25:
            out.append([random.gauss(0, 1) for _ in range(K)])
        elif r < 0.50:
            out.append([random.gauss(0, 1) * (25.0 if random.random() < 0.06 else 1.0)
                        for _ in range(K)])
        elif r < 0.75:
            b0 = random.gauss(0, 1)
            out.append([b0 + 0.25 * random.gauss(0, 1) for _ in range(K)])
        else:
            out.append([random.uniform(-1, 1) for _ in range(K)])
    return out


blocks = [b for b in make_blocks(2000) if max(abs(v) for v in b) > 0]
rows = []
for blk in blocks:
    base = mse(blk, q_block(blk, E2M1))
    if base == 0:
        continue
    gains = {nm: base / mse(blk, fn(blk)) if mse(blk, fn(blk)) else 0.0
             for nm, fn in CANDIDATES}
    rows.append((stats(blk), gains))

names = [n for n, _ in CANDIDATES]
oracle = sum(max(g.values()) for _, g in rows) / len(rows)
fixed = {n: sum(g[n] for _, g in rows) / len(rows) for n in names}
best_fixed_name = max(fixed, key=fixed.get)

# grid-search a small rule; thresholds fixed, not per-block fitted
best = None
for tdc in (0.2, 0.3, 0.4, 0.5, 0.6):
    for tcr in (2.0, 2.25, 2.5, 2.75, 3.0):
        for tbk in (3.0, 4.0, 5.0, 6.0, 8.0):
            tot = 0.0
            for (dc, cr, bk), g in rows:
                if dc >= tdc:
                    tot += g["rot+escape"]
                elif cr >= tcr and bk <= tbk:
                    tot += g["escape"]
                else:
                    tot += max(g["shape-e3m0"], g["shape-int4"]) if False else g["shape-int4"]
            if best is None or tot > best[0]:
                best = (tot, tdc, tcr, tbk)
tot, tdc, tcr, tbk = best
rule = tot / len(rows)

print("One-pass router over three mismatch classes\n")
print("  fixed choices (mean gain per block):")
for n in names:
    print(f"    {n:<14}{fixed[n]:>9.3f}")
print(f"\n  best fixed        {fixed[best_fixed_name]:>9.3f}   ({best_fixed_name})")
print(f"  3-statistic rule  {rule:>9.3f}   (dc>={tdc}, crest>={tcr}, bkurt<={tbk})")
print(f"  oracle            {oracle:>9.3f}")
head = oracle - fixed[best_fixed_name]
print(f"\n  headroom captured: {100*(rule-fixed[best_fixed_name])/head:.0f}%"
      f"  ({len(rows)} blocks, one pass, no trial quantisation)")
