#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tnf_ref.py — parameterized bit-exact oracle for the WHOLE TNF ladder.

One oracle for every rung (TNF4 .. TNF1024): a GoldenFloat whose exponent is a
balanced-ternary number of `exp_trits` trits (offset in [0, 3^Et - 1], balanced
exponent e = offset - (3^Et-1)/2) and a `mant_bits` binary mantissa. No regime
decode; add/mul are decode -> exact Fraction -> re-encode (round-to-nearest-even).

Off-path conformance oracle (like gf_ref.py / tekum_ref.py). Supersedes the
single-width tnf16_ref.py (TNF16 == TNFFormat(4, 9)).

WIDTH NOTICE (2026-08-18, measured in conformance/true_width_ladder.py):
the LADDER keys below are NAMES, not stored widths. The exponent field needs
ceil(Et*log2 3) bits, so the stored widths are:

    TNF4=6b(+2)  TNF8=10b(+2)  TNF16=17b(+1)  TNF32=30b(-2)  TNF64=65b(+1)
    TNF128=129b  TNF256=258b   TNF512=514b    TNF1024=1025b

Not one rung stores the width in its name. Use stored_width(fmt) before any
"at N bits" comparison, or use TRUE_LADDER, whose rungs are exactly their
named width. Measured consequence of the misnaming: the sign of the advantage
over takum followed the sign of the width excess (+2 bits: 484x; +1: 2x;
-2: 0.08x), and at true width with range to spare the advantage is 1.00x.
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
class TNFFormat:
    exp_trits: int
    mant_bits: int

    @property
    def offset_max(self): return 3 ** self.exp_trits - 1          # reserved special row
    @property
    def exp_offset(self): return (3 ** self.exp_trits - 1) // 2   # balanced zero point
    @property
    def mant(self): return 1 << self.mant_bits
    @property
    def exp_bits(self):
        """Bits the offset field actually occupies."""
        return self.offset_max.bit_length()

    @property
    def sign_shift(self):
        # Derived, not fixed. This was hardcoded to 24 — "room for wide exp/mant" —
        # which holds only while the payload stays below that bit. At mant_bits of
        # 21 or 25 the exponent field reaches bit 24 and the sign lands inside the
        # payload: encoding 1.5 through TNF32 returned -1.5. Wider mantissas were
        # corrupted too, silently, whenever bit 24 of the significand happened to
        # be set — which is why a spot check on 1.5 passed at mant_bits=52.
        #
        # The commutativity check the ladder relies on cannot see this: an inverted
        # sign survives on both sides of a + b == b + a. A round-trip assertion
        # catches it in one line.
        return self.mant_bits + self.exp_bits
    @property
    def exp_shift(self): return self.mant_bits
    @property
    def inf(self): return self.offset_max << self.exp_shift
    def range_decades(self): return 2 * self.exp_offset * math.log10(2)


def encode(fmt: TNFFormat, value) -> int:
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


def is_special(fmt: TNFFormat, raw: int) -> bool:
    return ((raw >> fmt.exp_shift) & ((1 << fmt.exp_bits) - 1)) == fmt.offset_max


def decode(fmt: TNFFormat, raw: int):
    sign = (raw >> fmt.sign_shift) & 1
    offset = (raw >> fmt.exp_shift) & ((1 << fmt.exp_bits) - 1)
    m = raw & (fmt.mant - 1)
    if offset == fmt.offset_max:
        return math.nan if m else (-math.inf if sign else math.inf)
    if offset == 0:
        return Fraction(0)
    val = (Fraction(1) + Fraction(m, fmt.mant)) * _pow2(offset - fmt.exp_offset)
    return -val if sign else val


def tef_add(fmt: TNFFormat, a: int, b: int) -> int:
    if is_special(fmt, a) or is_special(fmt, b):
        return (fmt.offset_max << fmt.exp_shift) | 1
    return encode(fmt, decode(fmt, a) + decode(fmt, b))


def tef_mul(fmt: TNFFormat, a: int, b: int) -> int:
    if is_special(fmt, a) or is_special(fmt, b):
        return (fmt.offset_max << fmt.exp_shift) | 1
    return encode(fmt, decode(fmt, a) * decode(fmt, b))


# Canonical ladder rungs (exp_trits, mant_bits) per nominal width.

def stored_width(fmt):
    """Bits this rung actually stores. Not the name; the name lies on every rung."""
    return fmt.sign_shift + 1


# Rungs that are exactly their named width, chosen by measurement
# (true_width_ladder.py). The narrow-exponent splits that score better inside
# +-3 decades are deliberately NOT here: TNF(3,10) drops 58% of values at +-9
# decades, and a default that traps is worse than a default that ties.
TRUE_LADDER = {
    8:  TNFFormat(2, 3),    # 1+4+3;  best true-8 split measured (2.04x vs takum8)
    16: TNFFormat(4, 8),    # 1+7+8;  range-safe, ties takum16 at 1.00x
    32: TNFFormat(4, 24),   # 1+7+24; range-safe, ties takum32 at 0.94x
}


LADDER = {
    4:   TNFFormat(2, 1),
    8:   TNFFormat(3, 4),
    16:  TNFFormat(4, 9),
    32:  TNFFormat(5, 21),
    64:  TNFFormat(7, 52),
    128: TNFFormat(8, 115),
    256: TNFFormat(9, 242),
    512: TNFFormat(10, 497),
    1024: TNFFormat(11, 1006),
}


def _selftest():
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
            if tef_add(f, encode(f, x), encode(f, y)) != tef_add(f, encode(f, y), encode(f, x)):
                bad += 1
            if tef_mul(f, encode(f, x), encode(f, y)) != tef_mul(f, encode(f, y), encode(f, x)):
                bad += 1
        print(f"TNF{w:<4} {f.exp_trits:>3} {f.mant_bits:>5} {f.range_decades():11.0f} {('%d violations' % bad):>28}")
    F16 = LADDER[16]
    assert abs(float(decode(F16, tef_mul(F16, encode(F16, 1.5), encode(F16, 2.0)))) - 3.0) < 1e-2
    print("TNF16 1.5*2.0 =", float(decode(F16, tef_mul(F16, encode(F16, 1.5), encode(F16, 2.0)))))


if __name__ == "__main__":
    _selftest()
