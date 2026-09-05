#!/usr/bin/env python3
"""The scale format is where the leader is weak — measure TEF against it there.

IBM Research (arXiv:2601.19026) showed that MXFP4's block-size anomaly is caused by
quantisation of the SHARED SCALE, not of the elements: with unquantised BF16 scales
the anomaly disappears, and they propose FP8 UE5M3 (one more exponent bit, one less
mantissa bit) as the fix.

Every lever measured here previously was element-side. This asks the on-axis question
instead: at a fixed 8-bit scale budget, which scale ENCODING minimises error?

TEF's whole claim is that a balanced-ternary exponent field encodes exponents more
efficiently than a binary one. A shared block scale is nothing but an exponent. So
this is TEF's natural home, and it is on the leader's own axis.

Formats compared, all 8 bits of scale:
  e8m0    original MX: power-of-two only, huge range, no mantissa
  ue4m3   NVFP4 / current default
  ue5m3   IBM's proposal: +1 exponent bit, -1 mantissa bit
  tef8    balanced-ternary exponent field + binary mantissa (our ladder's rung)

Reported as NRMSE relative to unquantised (BF16-like) scales, so 1.00 is the ceiling
set by element quantisation alone and lower is better.
"""
import math
import random
import statistics

random.seed(20260809)


# ---------- element format: FP4 E2M1, the MXFP4 element ----------

def e2m1_levels():
    out = {0.0}
    for e in range(-1, 3):              # exponent range of E2M1 with bias 1
        for m in range(2):
            out.add((1 + m / 2) * 2.0 ** e)
    return sorted(out)


ELEM = e2m1_levels()
ELEM_MAX = max(ELEM)


def q_elem(x, scale):
    if scale == 0:
        return 0.0
    y = x / scale
    s = -1.0 if y < 0 else 1.0
    y = min(abs(y), ELEM_MAX)
    return s * min(ELEM, key=lambda L: abs(L - y)) * scale


# ---------- scale formats, all 8 bits ----------

def q_scale_e8m0(s):
    """Power of two only — the original MX scale."""
    if s <= 0:
        return 0.0
    return 2.0 ** round(math.log2(s))


def _q_scale_fp(s, eb, mb):
    """Unsigned minifloat scale with eb exponent bits and mb mantissa bits."""
    if s <= 0:
        return 0.0
    bias = (1 << (eb - 1)) - 1
    e = math.floor(math.log2(s))
    e = max(1 - bias, min(e, (1 << eb) - 2 - bias))
    frac = s / 2.0 ** e - 1.0
    m = round(frac * (1 << mb))
    if m == (1 << mb):
        e, m = e + 1, 0
    return (1 + m / (1 << mb)) * 2.0 ** e


def q_scale_ue4m3(s):
    return _q_scale_fp(s, 4, 3)


def q_scale_ue5m3(s):
    return _q_scale_fp(s, 5, 3)          # IBM's proposal (8 bits total, unsigned)


def q_scale_tef8(s):
    """TEF-style scale: balanced-ternary exponent field, binary mantissa.

    5 trits would be 3^5 = 243 exponent codes; at 8 bits we spend Et trits on the
    exponent and the remainder on a binary mantissa. Encoding an exponent in balanced
    ternary covers a wider exponent range per symbol than binary, which is exactly the
    trade IBM made by hand when going UE4M3 -> UE5M3.
    """
    if s <= 0:
        return 0.0
    ET = 4                                # 4 trits = 81 exponent codes, ~6.34 bits
    MB = 1                                # remaining budget as binary mantissa bits
    half = (3 ** ET - 1) // 2
    e = math.floor(math.log2(s))
    e = max(-half, min(e, half))
    frac = s / 2.0 ** e - 1.0
    m = round(frac * (1 << MB))
    if m == (1 << MB):
        e, m = e + 1, 0
    return (1 + m / (1 << MB)) * 2.0 ** e


SCALES = [("e8m0 (MX)", q_scale_e8m0), ("ue4m3 (NVFP4)", q_scale_ue4m3),
          ("ue5m3 (IBM)", q_scale_ue5m3), ("tef8 (ours)", q_scale_tef8)]


# ---------- block quantisation ----------

def nrmse(data, K, q_scale):
    err2 = 0.0
    ref2 = 0.0
    for i in range(0, len(data), K):
        blk = data[i:i + K]
        amax = max(abs(v) for v in blk)
        if amax == 0:
            continue
        s = q_scale(amax / ELEM_MAX)
        for v in blk:
            d = q_elem(v, s) - v
            err2 += d * d
            ref2 += v * v
    return math.sqrt(err2 / ref2) if ref2 else 0.0


def draw(n, sigma):
    return [random.gauss(0.0, sigma) for _ in range(n)]


if __name__ == "__main__":
    N = 32768
    print("NRMSE by scale format and block size (lower is better)")
    print("weights ~ Normal(0, sigma); FP4 E2M1 elements throughout\n")
    for sigma in (2e-3, 1e-2, 4e-2):
        data = draw(N, sigma)
        base = {K: nrmse(data, K, lambda s: s) for K in (8, 16, 32, 64)}
        print(f"sigma = {sigma:g}   (unquantised-scale NRMSE at K=32: {base[32]:.5f})")
        print(f"  {'scale format':<16} " + "".join(f"{'K='+str(K):>10}" for K in (8, 16, 32, 64)))
        for name, fn in SCALES:
            row = "".join(f"{nrmse(data, K, fn)/base[K]:>10.3f}" for K in (8, 16, 32, 64))
            print(f"  {name:<16} {row}")
        print("  (values are relative to unquantised scales at the same block size;"
              " 1.000 = scale quantisation costs nothing)")
        print()
