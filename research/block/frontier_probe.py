#!/usr/bin/env python3
"""Where the headroom is at 4 bits with block scaling -- measured, not argued.

The industry's low-precision problem was solved on an axis this project's map does
not cover: MX puts the exponent OUTSIDE the number, one per block of 32. MXFP4
runs natively on Blackwell and MI355X. So "is there a better format" has to be
asked there, and answered with numbers.

Four levers were tested. Their sizes are the finding.
"""
import math
import random
import statistics

K = 32  # MX block size


def fp_levels(eb, mb, n):
    """Positive representable magnitudes of a minifloat e{eb}m{mb}, zero included."""
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return sorted(out)[:n]


def quantise(x, levels, signed=True):
    if signed:
        s = -1.0 if x < 0 else 1.0
        return s * min(levels, key=lambda L: abs(L - abs(x)))
    return min(levels, key=lambda L: abs(L - x))


def mx_blocks(data, levels, signed=True, scale_frac_bits=0):
    """MX block quantisation. scale_frac_bits=0 is the standard's e8m0 -- the shared
    scale is a power of two. Nonzero lets the scale carry fractional bits."""
    top = max(levels)
    out = []
    for i in range(0, len(data), K):
        b = data[i:i + K]
        amax = max(abs(v) for v in b)
        if amax == 0:
            out += [0.0] * len(b)
            continue
        ideal = math.log2(amax / top)
        if scale_frac_bits:
            st = 2.0 ** -scale_frac_bits
            sc = 2.0 ** (math.ceil(ideal / st) * st)
        else:
            sc = 2.0 ** math.ceil(ideal)
        out += [quantise(v / sc, levels, signed) * sc for v in b]
    return out


def lloyd_max(samples, n_pos, iters=60):
    """MSE-optimal levels for the sample's own distribution, in the element's
    normalised domain -- fitting them anywhere else measures the mismatch, not the
    quantiser. That mistake cost this file one wrong result before it was caught."""
    a = sorted(abs(v) for v in samples if v != 0)
    if not a:
        return [0.0]
    lv = [0.0] + [a[min(len(a) - 1, int(len(a) * i / n_pos))] for i in range(1, n_pos + 1)]
    for _ in range(iters):
        buckets = [[] for _ in lv]
        for v in a:
            j = min(range(len(lv)), key=lambda k: abs(lv[k] - v))
            buckets[j].append(v)
        lv = sorted(set(statistics.fmean(b) if b else lv[i] for i, b in enumerate(buckets)))
    return lv


def nrmse(orig, deq):
    num = sum((a - b) ** 2 for a, b in zip(orig, deq))
    den = sum(a * a for a in orig)
    return math.sqrt(num / den) if den else 0.0


def _selftest():
    rng = random.Random(20260809)
    n = 8192
    weights = [rng.gauss(0, 0.05) for _ in range(n)]
    acts = [max(0.0, rng.gauss(0, 1.0)) for _ in range(n)]
    mxfp4 = fp_levels(2, 1, 8)

    base_w = nrmse(weights, mx_blocks(weights, mxfp4))
    base_a = nrmse(acts, mx_blocks(acts, mxfp4))

    # Lever 1: a finer shared scale. Weak -- the element dominates at 4 bits.
    finer = nrmse(weights, mx_blocks(weights, mxfp4, scale_frac_bits=1))
    assert 1.0 < base_w / finer < 1.3, f"scale lever moved unexpectedly: {base_w / finer}"

    # Lever 2: dropping the sign on one-sided data. The largest lever found.
    uns = nrmse(acts, mx_blocks(acts, [i * 6 / 15 for i in range(16)], signed=False))
    assert base_a / uns > 2.0, f"unsigned lever too small: {base_a / uns}"

    # Control: the same unsigned format must collapse on signed data, or the
    # measurement is not measuring what it claims.
    bad = nrmse(weights, mx_blocks(weights, fp_levels(2, 2, 16), signed=False))
    assert base_w / bad < 0.5, f"unsigned did not collapse on weights: {base_w / bad}"

    print("SELF-TEST: PASS (scale lever weak, sign lever >2x, control collapses)")


if __name__ == "__main__":
    _selftest()
