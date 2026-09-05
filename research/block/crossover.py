#!/usr/bin/env python3
"""Where does one-pass routing overtake trial-quantisation? Measured, not asserted.

Testing the router against MixFP4's Algorithm 1 showed it loses: 83% agreement, 15.4%
worse MSE, on a TWO-candidate choice. The surviving claim was that a cheap router pays
off when the candidate set is large, because trial cost grows linearly in candidates
while the router stays at one pass.

That claim is directional until someone measures the crossover. This does.

Method:
  - candidate sets of growing size, drawn from real MX-family options
  - oracle: trial-quantise every candidate, keep the best   -> cost N quantisations
  - router: three statistics in one pass, nearest-centroid   -> cost 1 quantisation
  - centroids are FITTED ON A TRAINING SPLIT and scored on a held-out split, so the
    router is never evaluated on the blocks that defined it

Reported: quality gap vs candidate count, alongside the cost ratio.
"""
import math
import random

random.seed(20260809)
K = 16


def fp(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)


def ints(n):
    return [i / n for i in range(n + 1)]


def q(blk, lv):
    amax = max((abs(v) for v in blk), default=0.0)
    if amax == 0:
        return [0.0] * len(blk)
    s = amax / max(lv)
    return [(-1.0 if v < 0 else 1.0) * min(lv, key=lambda L: abs(L - abs(v) / s)) * s
            for v in blk]


def q_escape(blk, lv):
    j = max(range(len(blk)), key=lambda i: abs(blk[i]))
    rest = [v for i, v in enumerate(blk) if i != j]
    qr = q(rest, lv)
    out, k = [], 0
    for i in range(len(blk)):
        out.append(blk[i] if i == j else qr[k])
        if i != j:
            k += 1
    return out


def had(n):
    H = [[1.0]]
    while len(H) < n:
        H = [r + r for r in H] + [r + [-v for v in r] for r in H]
    s = 1.0 / math.sqrt(n)
    return [[v * s for v in r] for r in H]


HAD = had(K)


def rot(v):
    return [sum(HAD[i][j] * v[j] for j in range(K)) for i in range(K)]


E2M1, E1M2, E3M0 = fp(2, 1), fp(1, 2), fp(3, 0)
# ordered so that prefixes give sensible candidate sets of each size
POOL = [
    ("e2m1",        lambda b: q(b, E2M1)),
    ("e1m2",        lambda b: q(b, E1M2)),
    ("e3m0",        lambda b: q(b, E3M0)),
    ("escape-e2m1", lambda b: q_escape(b, E2M1)),
    ("int4",        lambda b: q(b, ints(7))),
    ("rot+esc",     lambda b: rot(q_escape(rot(b), E2M1))),
    ("escape-e3m0", lambda b: q_escape(b, E3M0)),
    ("rot+e2m1",    lambda b: rot(q(rot(b), E2M1))),
]


def stats(blk):
    n = len(blk)
    m1 = sum(blk) / n
    m2 = sum(v * v for v in blk) / n
    if m2 == 0:
        return (0.0, 0.0, 0.0)
    j = max(range(n), key=lambda i: abs(blk[i]))
    rest = [v for i, v in enumerate(blk) if i != j]
    r2 = sum(v * v for v in rest) / len(rest)
    bk = (sum(v ** 4 for v in rest) / len(rest)) / (r2 * r2) if r2 else 0.0
    return (m1 * m1 / m2, max(abs(v) for v in blk) / math.sqrt(m2), bk)


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def blocks(n):
    out = []
    for _ in range(n):
        r = random.random()
        if r < 0.25:
            out.append([random.gauss(0, 1) for _ in range(K)])
        elif r < 0.50:
            out.append([random.gauss(0, 1) * (20.0 if random.random() < 0.08 else 1.0)
                        for _ in range(K)])
        elif r < 0.75:
            b0 = random.gauss(0, 1)
            out.append([b0 + 0.3 * random.gauss(0, 1) for _ in range(K)])
        else:
            out.append([random.uniform(-1, 1) for _ in range(K)])
    return [b for b in out if max(abs(v) for v in b) > 0]


TRAIN, TEST = blocks(1200), blocks(1200)
S_TR = [stats(b) for b in TRAIN]
S_TE = [stats(b) for b in TEST]
# normalise statistics by training spread so the three axes are comparable
mu = [sum(s[i] for s in S_TR) / len(S_TR) for i in range(3)]
sd = [math.sqrt(sum((s[i] - mu[i]) ** 2 for s in S_TR) / len(S_TR)) or 1.0 for i in range(3)]
nz = lambda s: tuple((s[i] - mu[i]) / sd[i] for i in range(3))

print("Crossover: does a one-pass router catch up as the candidate set grows?\n")
print(f"  {'candidates':>11}{'oracle MSE':>13}{'router MSE':>13}{'penalty':>10}"
      f"{'trial cost':>12}")
for n in (2, 3, 4, 5, 6, 7, 8):
    cands = POOL[:n]
    # oracle on both splits
    e_tr = [[mse(b, f(b)) for _, f in cands] for b in TRAIN]
    e_te = [[mse(b, f(b)) for _, f in cands] for b in TEST]
    # centroids from the training split only
    cent = []
    for c in range(n):
        pts = [nz(S_TR[i]) for i in range(len(TRAIN)) if min(range(n), key=lambda k: e_tr[i][k]) == c]
        cent.append(tuple(sum(p[d] for p in pts) / len(pts) for d in range(3)) if pts else None)
    tot_r = tot_o = 0.0
    for i, s in enumerate(S_TE):
        z = nz(s)
        best_c, best_d = 0, None
        for c in range(n):
            if cent[c] is None:
                continue
            d = sum((z[d0] - cent[c][d0]) ** 2 for d0 in range(3))
            if best_d is None or d < best_d:
                best_c, best_d = c, d
        tot_r += e_te[i][best_c]
        tot_o += min(e_te[i])
    pen = 100 * (tot_r / tot_o - 1)
    print(f"  {n:>11}{tot_o/len(TEST):>13.5f}{tot_r/len(TEST):>13.5f}"
          f"{pen:>9.1f}%{f'{n}x':>12}")

print("\n  penalty = how much worse the one-pass router is than trialling everything")
print("  trial cost = quantisations per block; the router always costs 1")
