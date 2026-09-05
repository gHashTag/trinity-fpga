#!/usr/bin/env python3
"""Does classical high-resolution quantization theory predict our measurements?

Everything measured in this programme has been empirical. But there is a closed-form
theory for exactly the quantity we have been calling "mismatch", and it is 75 years old.

BENNETT (1948). For a scalar quantizer with N levels described by a point density
lambda(x) (levels per unit x, normalised so integral lambda = 1), the high-resolution
mean-square error is

        D(lambda) = 1/(12 N^2) * integral p(x) / lambda(x)^2 dx.

PANTER-DITE (1951). Minimising D over lambda subject to integral lambda = 1 gives

        lambda*(x) proportional to p(x)^(1/3).

DERIVATION OF THE BOUND (Holder, exponents 3 and 3/2):

        integral p^(1/3) = integral (p/lambda^2)^(1/3) * lambda^(2/3)
                        <= (integral p/lambda^2)^(1/3) * (integral lambda)^(2/3)
                         = (integral p/lambda^2)^(1/3)

  so   integral p/lambda^2 >= (integral p^(1/3))^3,  equality iff p/lambda^2 prop. lambda,
  i.e. iff lambda^3 prop. p, i.e. lambda prop. p^(1/3).   []

So define the MISMATCH FACTOR

        M(lambda, p) = [integral p/lambda^2] / [(integral p^(1/3))^3]  >= 1,

with M = 1 exactly when the level placement matches the distribution optimally. This is a
closed form for the thing we have been measuring by trial all along.

This script checks whether M predicts the MSE ordering of our candidate formats. If it
does, the empirical results have a theory; if it does not, the high-resolution assumption
is broken at 4 bits and we should say so.
"""
import math
import random

random.seed(20260809)


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)


CANDS = {
    "e2m1": fp_levels(2, 1),
    "e1m2": fp_levels(1, 2),
    "e3m0": fp_levels(3, 0),
    "int4": [i / 7 for i in range(8)],
}

NBIN = 400


def hist(data, lo, hi):
    h = [0.0] * NBIN
    w = (hi - lo) / NBIN
    for v in data:
        if lo <= v < hi:
            h[min(NBIN - 1, int((v - lo) / w))] += 1
    s = sum(h) * w
    return [c / s if s else 0.0 for c in h], w


def lambda_from_levels(levels, lo, hi):
    """Point density from LEVEL SPACING, not from histogramming the points.

    For sorted reconstruction points t_1..t_M the local density is
    lambda(x) = 1 / (M * (t_{i+1} - t_i)) on the interval containing x.
    Histogramming 15 points into 400 bins leaves most bins empty and makes p/lambda^2
    explode -- that produced M ~ 1e21 in the first version of this script.
    """
    pts = sorted(set([-v for v in levels if v > 0] + list(levels)))
    M = len(pts)
    lam = [0.0] * NBIN
    w = (hi - lo) / NBIN
    for i in range(NBIN):
        x = lo + (i + 0.5) * w
        if x <= pts[0] or x >= pts[-1]:
            d = pts[1] - pts[0] if x <= pts[0] else pts[-1] - pts[-2]
        else:
            k = 0
            while k + 1 < M and pts[k + 1] < x:
                k += 1
            d = pts[k + 1] - pts[k]
        lam[i] = 1.0 / (M * d) if d > 0 else 0.0
    s = sum(lam) * w
    return [v / s if s else 0.0 for v in lam], w


def mismatch(levels, data):
    amax = max(abs(v) for v in data) or 1.0
    top = max(levels)
    scaled = [v / amax * top for v in data]
    lo, hi = -top * 1.05, top * 1.05
    pdf, w = hist(scaled, lo, hi)
    lam, _ = lambda_from_levels(levels, lo, hi)
    num = den = 0.0
    for i in range(NBIN):
        if pdf[i] <= 0 or lam[i] <= 0:
            continue
        num += pdf[i] / (lam[i] * lam[i]) * w
        den += pdf[i] ** (1.0 / 3.0) * w
    return num / (den ** 3) if den > 0 else float("inf")


def q(blk, levels):
    amax = max((abs(v) for v in blk), default=0.0)
    if amax == 0:
        return [0.0] * len(blk)
    s = amax / max(levels)
    return [(-1.0 if v < 0 else 1.0) * min(levels, key=lambda L: abs(L - abs(v) / s)) * s
            for v in blk]


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def workload(kind, n):
    if kind == "gaussian":
        return [random.gauss(0, 1) for _ in range(n)]
    if kind == "uniform":
        return [random.uniform(-1, 1) for _ in range(n)]
    if kind == "laplace":
        return [random.expovariate(1.0) * (1 if random.random() < .5 else -1)
                for _ in range(n)]
    return [random.gauss(0, 1) * (20.0 if random.random() < 0.05 else 1.0) for _ in range(n)]


print("Does Bennett/Panter-Dite mismatch M predict the measured MSE ordering?\n")
K = 32
for kind in ("gaussian", "uniform", "laplace", "heavy-tail"):
    data = workload(kind, 20000)
    meas, theo = {}, {}
    for nm, lv in CANDS.items():
        theo[nm] = mismatch(lv, data)
        t = 0.0
        for i in range(0, len(data) - K, K):
            blk = data[i:i + K]
            t += mse(blk, q(blk, lv))
        meas[nm] = t
    order_m = sorted(CANDS, key=lambda n: meas[n])
    order_t = sorted(CANDS, key=lambda n: theo[n])
    ok = "MATCH" if order_m == order_t else ("first ok" if order_m[0] == order_t[0] else "MISMATCH")
    print(f"  {kind:<12} measured best->worst {' < '.join(order_m)}")
    print(f"  {'':<12} theory   best->worst {' < '.join(order_t)}    [{ok}]")
    print(f"  {'':<12} M = " + ", ".join(f"{n}:{theo[n]:.2f}" for n in CANDS))
    print()
