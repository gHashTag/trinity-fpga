#!/usr/bin/env python3
"""MX's two-level scale hierarchy -- and what it implies about IBM's sigma-dependence.

predict_inversion.py modelled only ONE scale level, so at narrow sigma the block scale
fell below UE4M3's minimum normal and clamped. Real MX has two levels (MixFP4 Alg. 1):

    s32 = max|X| / (6 * 448)          per-tensor, FP32          (448 = E4M3 max)
    X_fp8 = X / s32
    s8  = FP8_E4M3( block-max|X_fp8| / 6 )     per block

The per-tensor level exists precisely to keep block scales inside E4M3's range.

Working the algebra through gives a prediction worth testing. Since s32 is proportional
to the tensor maximum, and the tensor maximum is proportional to sigma for a fixed shape,
the entire pipeline is SCALE-INVARIANT in sigma: D/sigma^2 cannot depend on sigma.

But IBM report a clear sigma dependence, with a crossover near 2e-2. Both cannot be true,
so the real driver must be a quantity that merely CORRELATES with sigma across tensors.
The candidate is the tensor-level crest factor

    c = max|X| / sigma

which is not fixed: heavier-tailed tensors have larger c at the same sigma. This script
sweeps c and asks whether the inversion tracks it.
"""
import math

K_LIST = [8, 16, 32, 64, 128, 256]
E4M3_MAX = 448.0


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)


E2M1 = fp_levels(2, 1)
TOP = max(E2M1)


def q_elem(y):
    s = -1.0 if y < 0 else 1.0
    return s * min(E2M1, key=lambda L: abs(L - abs(y)))


def q_e4m3(s):
    if s <= 0:
        return 0.0
    eb, mb, bias = 4, 3, 7
    e = math.floor(math.log2(s))
    e = max(1 - bias, min(e, (1 << eb) - 2 - bias))
    m = round((s / 2.0 ** e - 1.0) * (1 << mb))
    if m == (1 << mb):
        e, m = e + 1, 0
    return (1 + m / (1 << mb)) * 2.0 ** e


def pdf(x, sg):
    return math.exp(-x * x / (2 * sg * sg)) / (sg * math.sqrt(2 * math.pi))


def cdf_abs(a, sg):
    return math.erf(a / (sg * math.sqrt(2)))


def distortion(K, sigma, crest, two_level=True, na=500, nx=400):
    """crest = tensor_max / sigma, which sets the per-tensor scale."""
    tensor_max = crest * sigma
    s32 = tensor_max / (TOP * E4M3_MAX) if two_level else 1.0
    hi = min(6.0 * sigma, tensor_max)
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
        s8 = q_e4m3((a / s32) / TOP)          # block scale in the normalised domain
        s = s32 * s8                          # effective scale
        if s <= 0:
            continue
        acc = 0.0
        dx = 2 * a / nx
        for ix in range(nx):
            x = -a + (ix + 0.5) * dx
            acc += (s * q_elem(x / s) - x) ** 2 * pdf(x, sigma) * dx
        acc /= Fa
        emax = (s * q_elem(a / s) - a) ** 2
        total += ((K - 1) / K * acc + emax / K) * f_a * da
    return total


print("Two-level MX scaling: is the driver sigma, or the tensor crest factor?\n")
print("normalised MSE per element, each row divided by its own K=256 value")
print("minimum away from K=8 means inversion: finer blocks are WORSE\n")

print("  (a) sigma varied, crest held fixed at 5.0")
for sigma in (2e-3, 8e-3, 3e-2, 1e-1):
    vals = [distortion(K, sigma, 5.0) / (sigma * sigma) for K in K_LIST]
    ref = vals[-1]
    imin = min(range(len(vals)), key=lambda i: vals[i])
    flag = "" if imin == 0 else f"  inversion below K={K_LIST[imin]}"
    print(f"    sigma={sigma:<8.0e}" + "".join(f"{v/ref:>9.3f}" for v in vals) + flag)

print("\n  (b) crest varied, sigma held fixed at 8e-3")
for crest in (3.0, 4.0, 5.0, 7.0, 10.0, 20.0):
    vals = [distortion(K, 8e-3, crest) / (8e-3 ** 2) for K in K_LIST]
    ref = vals[-1]
    imin = min(range(len(vals)), key=lambda i: vals[i])
    flag = "" if imin == 0 else f"  inversion below K={K_LIST[imin]}"
    print(f"    crest={crest:<8.1f}" + "".join(f"{v/ref:>9.3f}" for v in vals) + flag)

print("\n  columns: K = " + "  ".join(f"{k:>6}" for k in K_LIST))
