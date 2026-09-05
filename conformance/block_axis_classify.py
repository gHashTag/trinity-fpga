#!/usr/bin/env python3
"""Put the block formats on the taper map, which they fell off.

`taper_classify.py` classified every format in the catalogue snapshot of the
time (the count is a catalogue invariant that grows -- 109 at v3, Sep 2026 --
and is not hard-coded here) and put five of the six MX entries in a bin
called "range < 6, not classifiable". That was read as a limit of the
instrument. It is not: it is the instrument measuring the wrong half of the
format.

The classifier encodes one element with the block scale left at its default
(2^0). An MXFP4 element is E2M1 -- about four binades -- so the sweep runs out of
range before it has six and gives up. But in a block format the range does not
live in the element. It lives in the shared scale, and the element only has to
cover the spread *within* a block. Measuring the element alone and concluding
"no range" is like measuring a mantissa and concluding a float cannot represent
large numbers.

So this measures the composite, the way a quantiser actually uses it: choose the
scale from the data, then encode elements relative to it.

Two regimes, because they answer different questions and only one of them is
what a deployment sees:

  ideal  one value per block, scale chosen for that value. This is the element's
         precision given a perfect scale -- an upper bound nobody achieves.
  k=32   a real block: 32 values share one scale, chosen from the block maximum
         as the OCP MX specification prescribes. This is what ships.

The gap between the two is the cost of sharing, and it is the number the block
axis is actually about.

    python3 block_axis_classify.py
"""
import math
import random
import sys
from fractions import Fraction as F

sys.path.insert(0, ".")

import mxfp_ref as MX

SEED = 11
N_PROBE = 40
BLOCK = 32


def ilog2_floor(x: F) -> int:
    """Largest e with 2^e <= |x|, exactly."""
    a = abs(x)
    if a == 0:
        raise ValueError("zero has no binade")
    e = 0
    while a >= 2:
        a /= 2
        e += 1
    while a < 1:
        a *= 2
        e -= 1
    return e


def scale_for(values, fmt) -> int:
    """The shared exponent a real encoder picks: from the block maximum.

    OCP MX takes the largest magnitude in the block and lines its exponent up
    with the top of the element's range, so the biggest element lands just inside
    the element format rather than saturating it.
    """
    top = max(abs(v) for v in values)
    if top == 0:
        return 0
    elem_max_exp = (1 << fmt.exp_bits) - 1 - fmt.bias if fmt.exp_bits else 0
    return ilog2_floor(top) - elem_max_exp


def rel_err_block(fmt, values):
    """Mean relative round-trip error over one block sharing one scale."""
    se = scale_for(values, fmt)
    tot, k = F(0), 0
    for v in values:
        try:
            raw = MX.encode_scaled(fmt, v, se)
            d = MX.decode_scaled(fmt, raw, se)
        except Exception:
            continue
        if not isinstance(d, F) or v == 0:
            continue
        tot += abs(d - v) / abs(v)
        k += 1
    return (float(tot / k), k) if k else (None, 0)


def probe(fmt, e, block, rng, spread=0):
    """Mean relative error on binade |e|, blocks of `block` values.

    `spread` is the point of the whole exercise. With spread=0 every value in a
    block comes from the same binade, so they sit within a factor of two of each
    other and one scale fits them all -- which measures the best case and makes
    sharing look free. It is not free. Real blocks straddle several binades, and
    the elements far below the block maximum are the ones that lose bits, because
    the scale was set by the maximum. spread is how many binades the block covers.
    """
    tot, n = 0.0, 0
    for _ in range(max(1, N_PROBE // block)):
        vals = []
        for _ in range(block):
            s = F(rng.getrandbits(40), 1 << 40)
            off = rng.randrange(0, spread + 1) if spread else 0
            v = (1 + s) * (F(2) ** (e - off)) * (1 if rng.random() < 0.5 else -1)
            vals.append(v)
        r, k = rel_err_block(fmt, vals)
        if r is not None:
            tot += r
            n += 1
    return (tot / n) if n else None


def usable_range(fmt, block, rng, cap=140, spread=0):
    """Largest |e| where the composite is still not saturated (error < 25%)."""
    hi = 0
    for e in range(1, cap):
        a = probe(fmt, e, block, rng, spread)
        b = probe(fmt, -e, block, rng, spread)
        if a is None or b is None or a > 0.25 or b > 0.25:
            break
        hi = e
    return hi


def meff(r):
    """Effective mantissa bits from mean relative error, the catalogue's own law."""
    if r is None or r <= 0 or r >= 1:
        return None
    return -math.log2(2 * r / 0.7213) - 1


def classify(fmt, block, rng, spread=0):
    R = usable_range(fmt, block, rng, spread=spread)
    if R < 6:
        return R, None, "range<6", None
    top = int(R * 0.9)
    es = [max(1, round(top * (i + 1) / 6)) for i in range(6)]
    ms = []
    for e in es:
        r = probe(fmt, e, block, rng, spread)
        m = meff(r)
        if m is not None:
            ms.append((e, m))
    if len(ms) < 4:
        return R, None, "too few points", None
    lo = sum(m for _, m in ms[:2]) / 2
    hi = sum(m for _, m in ms[-2:]) / 2
    slope = (hi - lo) / max(1, (ms[-1][0] - ms[0][0]))
    shape = "constant" if abs(slope) < 0.005 else ("tapered" if slope < 0 else "widening")
    return R, sum(m for _, m in ms) / len(ms), shape, slope


def main() -> int:
    print("  Block formats on the taper map.")
    print("  ideal = one value per block (perfect scale, an upper bound)")
    print(f"  k={BLOCK}  = a real block sharing one scale, as OCP MX prescribes")
    print()
    print(f"  {'format':<12} {'regime':<12} {'binades':>8} {'M_eff':>7} {'shape':>10} {'slope':>9}")
    for name, fmt in MX.FORMATS.items():
        for label, block, spread in (("ideal", 1, 0), (f"k={BLOCK} flat", BLOCK, 0),
                                     (f"k={BLOCK} sp4", BLOCK, 4), (f"k={BLOCK} sp8", BLOCK, 8)):
            rng = random.Random(SEED)
            R, m, shape, slope = classify(fmt, block, rng, spread)
            ms = f"{m:7.2f}" if m is not None else "      -"
            sl = f"{slope:9.4f}" if slope is not None else "        -"
            print(f"  {name:<12} {label:<12} {R:>8} {ms} {shape:>10} {sl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
