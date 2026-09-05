#!/usr/bin/env python3
"""Does cross-mismatch composition survive being charged for its own bits?

falsify_boundary.py showed composition beats both parents when the levers address
DIFFERENT mismatches. But the escape lever spends unbudgeted bits: one value stored
out-of-band plus an index naming it. A reviewer's first objection is that the win is
bought, not earned.

So here every configuration is priced in bits per element, and the question becomes
Pareto: at equal or lower cost, does composition beat simply spending those bits on a
wider element format?

Pricing, block of K=32:
  elements      b bits each
  block scale   8 bits, amortised = 0.25 bits/element
  escape        value stored at v bits + 5-bit index = (v+5)/32 bits/element

That last line is the honest cost of the trick, and it is charged in full.
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


def int_levels(nbits):
    n = (1 << (nbits - 1)) - 1
    return [i / n for i in range(n + 1)]


def q_block(blk, levels):
    amax = max((abs(v) for v in blk), default=0.0)
    if amax == 0:
        return [0.0] * len(blk)
    s = amax / max(levels)
    return [(-1.0 if v < 0 else 1.0) * min(levels, key=lambda L: abs(L - abs(v) / s)) * s
            for v in blk]


def q_escape(blk, levels, esc_bits):
    """Escape the largest element; it is stored at esc_bits precision, not exactly."""
    j = max(range(len(blk)), key=lambda i: abs(blk[i]))
    esc = blk[j]
    if esc and esc_bits < 32:
        # Quantise the escaped value ARITHMETICALLY. Enumerating a 16-bit level set is
        # 32768 entries scanned per block -- that mistake hung the first run.
        mb = esc_bits - 5 if esc_bits >= 8 else esc_bits - 4   # sign + exponent field
        e = math.floor(math.log2(abs(esc)))
        frac = abs(esc) / 2.0 ** e - 1.0
        m = round(frac * (1 << mb))
        if m == (1 << mb):
            e, m = e + 1, 0
        esc = (-1.0 if esc < 0 else 1.0) * (1 + m / (1 << mb)) * 2.0 ** e
    rest = [v for i, v in enumerate(blk) if i != j]
    qr = q_block(rest, levels)
    out, k = [], 0
    for i in range(len(blk)):
        if i == j:
            out.append(esc)
        else:
            out.append(qr[k]); k += 1
    return out


def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def workload(kind, n):
    if kind == "heavy-tail":
        return [random.gauss(0, 1) * (30.0 if random.random() < 0.02 else 1.0)
                for _ in range(n)]
    if kind == "weights":
        return [random.gauss(0, 1) for _ in range(n)]
    return [random.gauss(0, 1) * (10 ** random.uniform(-1, 0)) for _ in range(n)]


SCALE_BITS = 8.0


def configs():
    """(name, bits/element, quantiser)"""
    out = []
    for nm, eb, mb, b in (("e2m1 4b", 2, 1, 4), ("e3m0 4b", 3, 0, 4),
                          ("e2m2 5b", 2, 2, 5), ("e3m1 5b", 3, 1, 5),
                          ("e3m2 6b", 3, 2, 6)):
        lv = fp_levels(eb, mb)
        out.append((nm, b + SCALE_BITS / K, lambda blk, lv=lv: q_block(blk, lv)))
    out.append(("int4 4b", 4 + SCALE_BITS / K, lambda blk: q_block(blk, int_levels(4))))
    # composition: escape + best shape, escaped value priced at 8 and 16 bits
    for vb in (8, 16):
        for nm, lv in (("e2m1", fp_levels(2, 1)), ("e3m0", fp_levels(3, 0)),
                       ("int4", int_levels(4))):
            cost = 4 + SCALE_BITS / K + (vb + 5) / K
            out.append((f"escape{vb}+{nm}", cost,
                        lambda blk, lv=lv, vb=vb: q_escape(blk, lv, vb)))
    return out


for kind in ("heavy-tail", "weights", "mixed"):
    data = workload(kind, 32768)
    rows = []
    for nm, bits, fn in configs():
        tot = 0.0
        for i in range(0, len(data), K):
            blk = data[i:i + K]
            tot += mse(blk, fn(blk))
        rows.append((bits, tot, nm))
    ref = min(t for b, t, n in rows if n == "e2m1 4b")
    rows.sort(key=lambda r: (r[0], r[1]))
    print(f"\n===== {kind} =====")
    print(f"  {'bits/elem':>10}{'gain vs e2m1 4b':>18}   config            Pareto?")
    best_so_far = float("inf")
    for bits, tot, nm in rows:
        on_front = tot < best_so_far - 1e-18
        if on_front:
            best_so_far = tot
        print(f"  {bits:>10.3f}{ref/tot:>18.3f}   {nm:<18}{'  <-- frontier' if on_front else ''}")
print("\n  A composition entry on the frontier means it beats every cheaper-or-equal")
print("  alternative, i.e. the win is earned rather than bought.")
