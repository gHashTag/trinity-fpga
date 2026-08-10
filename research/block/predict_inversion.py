#!/usr/bin/env python3
"""Does our finite-N formula reproduce IBM's published block-size anomaly?

IBM Research (arXiv:2601.19026) report "perplexity inversion": with FP8 UE4M3 block
scales, DECREASING the block size below a threshold INCREASES quantization error --
against the obvious expectation that finer blocks track the data better. With
unquantised BF16 scales the anomaly disappears entirely, which is how they identify
SCALE QUANTISATION as the cause. The threshold is model-dependent: granite-3.3-8b
inverts at block size 16, llama-3.1-8b and mixtral-8x7b at 8, llama-2-7b not at all
down to 8. They tie this to the per-tensor sigma, with a crossover near 2e-2.

Our formula (finite_n_theory.py) has K explicit, so it can be tested against this. It
needs one extension: the scale must be quantised.

  exact scale     s = a / t_max                       -> max reproduced exactly
  quantised scale s_q = Q_scale(a / t_max)            -> max no longer exact, may clamp

  D(a) = (K-1)/K * E_{x ~ p||x|<a} [ (s_q Q(x/s_q) - x)^2 ]  +  (1/K) (s_q Q(a/s_q) - a)^2

This is an out-of-sample test: the formula was built and checked on a different question,
and IBM's result was published before we looked at it.
"""
import math

K_LIST = [8, 16, 32, 64, 128, 256]


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)


E2M1 = fp_levels(2, 1)          # the MXFP4 element
TOP = max(E2M1)


def q_elem(y):
    s = -1.0 if y < 0 else 1.0
    return s * min(E2M1, key=lambda L: abs(L - abs(y)))


def q_scale_ue4m3(s):
    """FP8 UE4M3, unsigned: 4 exponent bits, 3 mantissa bits."""
    if s <= 0:
        return 0.0
    eb, mb, bias = 4, 3, 7
    e = math.floor(math.log2(s))
    e = max(1 - bias, min(e, (1 << eb) - 2 - bias))
    m = round((s / 2.0 ** e - 1.0) * (1 << mb))
    if m == (1 << mb):
        e, m = e + 1, 0
    return (1 + m / (1 << mb)) * 2.0 ** e


def q_scale_exact(s):
    return s


def pdf(x, sigma):
    return math.exp(-x * x / (2 * sigma * sigma)) / (sigma * math.sqrt(2 * math.pi))


def cdf_abs(a, sigma):
    return math.erf(a / (sigma * math.sqrt(2)))


def distortion(K, sigma, qscale, na=600, nx=500):
    hi = 6.0 * sigma
    total = 0.0
    da = hi / na
    for ia in range(1, na + 1):
        a = ia * da
        Fa = cdf_abs(a, sigma)
        if Fa <= 1e-12:
            continue
        f_a = K * (2 * pdf(a, sigma)) * (Fa ** (K - 1))
        if f_a <= 0:
            continue
        s = qscale(a / TOP)
        if s <= 0:
            continue
        # non-maximal elements, p truncated to [-a, a]
        acc = 0.0
        dx = 2 * a / nx
        for ix in range(nx):
            x = -a + (ix + 0.5) * dx
            acc += (s * q_elem(x / s) - x) ** 2 * pdf(x, sigma) * dx
        acc /= Fa
        # the maximal element itself
        emax = (s * q_elem(a / s) - a) ** 2
        total += ((K - 1) / K * acc + emax / K) * f_a * da
    return total


print("Predicting IBM's block-size anomaly from our formula (out-of-sample test)\n")
print("normalised MSE per element, relative to the K=256 value of the same curve")
print("a MINIMUM in the middle of a row = inversion: smaller blocks get WORSE\n")

for sigma, label in ((2e-3, "narrow  (sigma=2e-3)"),
                     (8e-3, "medium  (sigma=8e-3)"),
                     (3e-2, "wide    (sigma=3e-2)")):
    for qs, qn in ((q_scale_exact, "BF16 scale (exact)"), (q_scale_ue4m3, "FP8 UE4M3 scale")):
        vals = [distortion(K, sigma, qs) / (sigma * sigma) for K in K_LIST]
        ref = vals[-1]
        row = "".join(f"{v/ref:>9.3f}" for v in vals)
        # inversion = the minimum is not at the smallest block size
        imin = min(range(len(vals)), key=lambda i: vals[i])
        flag = "" if imin == 0 else f"  <-- inversion below K={K_LIST[imin]}"
        print(f"  {label:<22}{qn:<20}{row}{flag}")
    print()
print("  columns: K = " + "  ".join(f"{k:>6}" for k in K_LIST))
