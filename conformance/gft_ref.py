#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gft_ref.py — parameterized bit-exact oracle for the WHOLE GF-T ladder.

One oracle for every rung (GF-T4 .. GF-T1024): a GoldenFloat whose exponent is a
balanced-ternary number of `exp_trits` trits (offset in [0, 3^Et - 1], balanced
exponent e = offset - (3^Et-1)/2) and a `mant_bits` binary mantissa. No regime
decode; add/mul are decode -> exact Fraction -> re-encode (round-to-nearest-even).

Off-path conformance oracle (like gf_ref.py / tekum_ref.py). Supersedes the
single-width gft16_ref.py (GF-T16 == GFTFormat(4, 9)).
"""

from fractions import Fraction
from dataclasses import dataclass
import math


def _floor_log2(fr: Fraction) -> int:
    # pure-integer floor(log2) for a positive Fraction (no float -> no overflow
    # even for the >1000-decade wide rungs).
    e = fr.numerator.bit_length() - fr.denominator.bit_length()
    if (Fraction(1) * (1 << e) if e >= 0 else Fraction(1, 1 << -e)) > fr:
        e -= 1
    while (Fraction(1) * (1 << (e + 1)) if e + 1 >= 0 else Fraction(1, 1 << -(e + 1))) <= fr:
        e += 1
    return e


def _pow2(e: int) -> Fraction:
    return Fraction(1) * (1 << e) if e >= 0 else Fraction(1, 1 << -e)


@dataclass(frozen=True)
class GFTFormat:
    exp_trits: int
    mant_bits: int

    @property
    def offset_max(self): return 3 ** self.exp_trits - 1          # reserved special row
    @property
    def exp_offset(self): return (3 ** self.exp_trits - 1) // 2   # balanced zero point
    @property
    def mant(self): return 1 << self.mant_bits
    @property
    def sign_shift(self): return 24                               # room for wide exp/mant
    @property
    def exp_shift(self): return self.mant_bits
    @property
    def inf(self): return self.offset_max << self.exp_shift
    def range_decades(self): return 2 * self.exp_offset * math.log10(2)


def encode(fmt: GFTFormat, value) -> int:
    if value == 0:
        return 0
    sign = 1 if value < 0 else 0
    av = abs(Fraction(value))
    e = _floor_log2(av)
    offset = e + fmt.exp_offset
    if offset >= fmt.offset_max:
        return (sign << fmt.sign_shift) | fmt.inf
    if offset < 1:
        offset = 1
        e = offset - fmt.exp_offset
    frac = av / _pow2(e) - 1
    scaled = frac * fmt.mant
    fl = int(scaled)
    rem = scaled - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and (fl & 1)):
        fl += 1
    if fl == fmt.mant:
        fl = 0
        offset += 1
        if offset >= fmt.offset_max:
            return (sign << fmt.sign_shift) | fmt.inf
    return (sign << fmt.sign_shift) | (offset << fmt.exp_shift) | fl


def is_special(fmt: GFTFormat, raw: int) -> bool:
    return ((raw >> fmt.exp_shift) & ((1 << (fmt.exp_trits * 2)) - 1)) == fmt.offset_max


def decode(fmt: GFTFormat, raw: int):
    sign = (raw >> fmt.sign_shift) & 1
    offset = (raw >> fmt.exp_shift) & ((1 << (fmt.exp_trits * 2)) - 1)
    m = raw & (fmt.mant - 1)
    if offset == fmt.offset_max:
        return math.nan if m else (-math.inf if sign else math.inf)
    if offset == 0:
        return Fraction(0)
    val = (Fraction(1) + Fraction(m, fmt.mant)) * _pow2(offset - fmt.exp_offset)
    return -val if sign else val


def gft_add(fmt: GFTFormat, a: int, b: int) -> int:
    if is_special(fmt, a) or is_special(fmt, b):
        return (fmt.offset_max << fmt.exp_shift) | 1
    return encode(fmt, decode(fmt, a) + decode(fmt, b))


def gft_mul(fmt: GFTFormat, a: int, b: int) -> int:
    if is_special(fmt, a) or is_special(fmt, b):
        return (fmt.offset_max << fmt.exp_shift) | 1
    return encode(fmt, decode(fmt, a) * decode(fmt, b))


# Canonical ladder rungs (exp_trits, mant_bits) per nominal width.
LADDER = {
    4:   GFTFormat(2, 1),
    8:   GFTFormat(3, 4),
    16:  GFTFormat(4, 9),
    32:  GFTFormat(5, 21),
    64:  GFTFormat(7, 52),
    128: GFTFormat(8, 115),
    256: GFTFormat(9, 242),
    512: GFTFormat(10, 497),
    1024: GFTFormat(11, 1006),
}


if __name__ == "__main__":
    import random
    rnd = random.Random(1)
    print(f"{'rung':>6} {'Et':>3} {'M':>5} {'range(dec)':>11} {'add/mul commute (5k pairs)':>28}")
    for w, f in LADDER.items():
        bad = 0
        klim = max(1, int(f.exp_offset * 0.29))
        def rv():
            k = rnd.randint(-klim, klim)
            m = Fraction(rnd.randint(0, f.mant if f.mant_bits < 30 else (1 << 30)), (f.mant if f.mant_bits < 30 else (1 << 30)))
            s = 1 if rnd.random() < .5 else -1
            return s * (Fraction(1) + m) * (Fraction(2) ** k)
        for _ in range(3000):
            x, y = rv(), rv()
            if gft_add(f, encode(f, x), encode(f, y)) != gft_add(f, encode(f, y), encode(f, x)):
                bad += 1
            if gft_mul(f, encode(f, x), encode(f, y)) != gft_mul(f, encode(f, y), encode(f, x)):
                bad += 1
        print(f"GF-T{w:<4} {f.exp_trits:>3} {f.mant_bits:>5} {f.range_decades():11.0f} {('%d violations' % bad):>28}")
    F16 = LADDER[16]
    assert abs(float(decode(F16, gft_mul(F16, encode(F16, 1.5), encode(F16, 2.0)))) - 3.0) < 1e-2
    print("GF-T16 1.5*2.0 =", float(decode(F16, gft_mul(F16, encode(F16, 1.5), encode(F16, 2.0)))))
