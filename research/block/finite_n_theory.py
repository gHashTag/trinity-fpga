#!/usr/bin/env python3
"""An exact finite-N distortion formula for BLOCK-SCALED quantization.

bennett_theory.py showed the classical high-resolution integral gets the 4-bit format
ordering wrong in half the workloads. The reason is structural, not numerical: Bennett
assumes N -> infinity and negligible overload, whereas block scaling sets the scale from
the block MAXIMUM, so the largest element sits exactly on the top level by construction
and the distribution seen by the quantizer is CONDITIONED on that maximum.

Derivation.

Let x_1..x_K be iid with density p and let a = max_i |x_i|. The block scale is chosen so
that a maps to the top level t_max, i.e. s = a / t_max. Then:

  * the maximal element is reproduced EXACTLY (its scaled value is t_max, a level), so it
    contributes zero error;
  * each remaining element is, conditional on a, distributed as p truncated to [-a, a]:

        p(x | a) = p(x) / (2F(a) - 1),   |x| <= a

  * its reconstruction is  x_hat = s * Q(x / s),  Q = nearest level.

So the per-block distortion conditional on a is

    D(a) = (K-1)/K * integral_{-a}^{a} ( s*Q(x/s) - x )^2 * p(x)/(2F(a)-1) dx

and the total distortion integrates over the density of the block maximum, which for K
iid samples of |x| is

    f_a(a) = K * f_|x|(a) * F_|x|(a)^(K-1).

    D = integral_0^inf D(a) f_a(a) da.

No high-resolution assumption, no overload term, valid at N = 15 levels. This mirrors the
structure IBM used for the Normal + E2M1 case (arXiv:2601.19026 eqs 1-5); what is written
here is the general version for an arbitrary level set and an arbitrary density, so it can
RANK formats rather than describe one.

The test: does it reproduce the measured ordering that Bennett got wrong?
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


CANDS = {
    "e2m1": fp_levels(2, 1),
    "e1m2": fp_levels(1, 2),
    "e3m0": fp_levels(3, 0),
    "int4": [i / 7 for i in range(8)],
}


# ---------- densities, each with pdf and cdf of |x| ----------
def gaussian():
    pdf = lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
    cdf_abs = lambda a: math.erf(a / math.sqrt(2))
    return pdf, cdf_abs, 6.0


def laplace():
    pdf = lambda x: 0.5 * math.exp(-abs(x))
    cdf_abs = lambda a: 1 - math.exp(-a)
    return pdf, cdf_abs, 12.0


def uniform():
    pdf = lambda x: 0.5 if abs(x) <= 1 else 0.0
    cdf_abs = lambda a: min(1.0, a)
    return pdf, cdf_abs, 1.0


DISTS = {"gaussian": gaussian(), "laplace": laplace(), "uniform": uniform()}


def quantise(y, levels):
    s = -1.0 if y < 0 else 1.0
    return s * min(levels, key=lambda L: abs(L - abs(y)))


def distortion(levels, dist, na=90, nx=400):
    """Exact finite-N block-scaled distortion by numerical integration."""
    pdf, cdf_abs, amax_hi = dist
    top = max(levels)
    total = 0.0
    da = amax_hi / na
    for ia in range(1, na + 1):
        a = ia * da
        Fa = cdf_abs(a)
        if Fa <= 0:
            continue
        # density of the block maximum of |x|
        f_abs = 2 * pdf(a)
        f_a = K * f_abs * (Fa ** (K - 1))
        if f_a <= 0:
            continue
        s = a / top
        # conditional distortion of a non-maximal element
        acc = 0.0
        dx = 2 * a / nx
        for ix in range(nx):
            x = -a + (ix + 0.5) * dx
            xh = s * quantise(x / s, levels)
            acc += (xh - x) ** 2 * pdf(x) * dx
        acc /= Fa                      # normalise the truncated density
        total += (K - 1) / K * acc * f_a * da
    return total


def sample(dist_name, n):
    if dist_name == "gaussian":
        return [random.gauss(0, 1) for _ in range(n)]
    if dist_name == "laplace":
        return [random.expovariate(1.0) * (1 if random.random() < .5 else -1)
                for _ in range(n)]
    return [random.uniform(-1, 1) for _ in range(n)]


def measured(levels, data):
    tot = 0.0
    nb = 0
    for i in range(0, len(data) - K, K):
        blk = data[i:i + K]
        amax = max(abs(v) for v in blk)
        if amax == 0:
            continue
        s = amax / max(levels)
        tot += sum((s * quantise(v / s, levels) - v) ** 2 for v in blk) / K
        nb += 1
    return tot / nb


print("Exact finite-N block-scaled theory vs measurement (Bennett failed at this)\n")
for dname in ("gaussian", "laplace", "uniform"):
    data = sample(dname, 60000)
    theo = {n: distortion(lv, DISTS[dname]) for n, lv in CANDS.items()}
    meas = {n: measured(lv, data) for n, lv in CANDS.items()}
    om = sorted(CANDS, key=lambda n: meas[n])
    ot = sorted(CANDS, key=lambda n: theo[n])
    verdict = "MATCH" if om == ot else ("winner ok" if om[0] == ot[0] else "MISMATCH")
    print(f"  {dname}")
    print(f"    measured  {' < '.join(om)}")
    print(f"    predicted {' < '.join(ot)}    [{verdict}]")
    err = max(abs(theo[n] / meas[n] - 1) for n in CANDS) * 100
    print(f"    values    " + ", ".join(f"{n}: theory {theo[n]:.4f} / measured {meas[n]:.4f}"
                                        for n in CANDS))
    print(f"    worst magnitude error {err:.1f}%\n")
