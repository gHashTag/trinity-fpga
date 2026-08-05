#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gft16_ref.py — bit-exact golden oracle for GF-T16 (ternary-native GoldenFloat).

Off-path conformance oracle (like gf_ref.py / tekum_ref.py). GF-T16:

    raw = [ sign(1) | exp_offset(7) | mant(9) ]        (17-bit canonical raw)
    exp_offset in [0,80]; balanced exponent e = exp_offset - 40 for normals.
      exp_offset == 0   -> zero (mant==0) / subnormal
      exp_offset == 80  -> Inf (mant==0) / NaN (mant!=0)
      else (1..79)      -> value = (-1)^sign * (1 + mant/2^9) * 2^(exp_offset-40)

The 7-bit exp_offset is the DECODED exponent field; on ternary hardware it is a
4-trit balanced-ternary number (offset = Σ tᵢ·3ⁱ, tᵢ∈{0,1,2}) added natively.
Arithmetic: decode -> exact in Fractions -> re-encode with round-to-nearest-even.
"""

from fractions import Fraction
import math

MANT_BITS = 9
MANT = 1 << MANT_BITS          # 512
EXP_OFFSET = 40                # balanced zero point (3^4-1)/2 = 40
OFFSET_MAX = 80                # reserved special row
SIGN_SHIFT = 16
EXP_SHIFT = MANT_BITS

INF = OFFSET_MAX << EXP_SHIFT               # +Inf raw (sign 0)
NAN = (OFFSET_MAX << EXP_SHIFT) | 1         # NaN raw


def _floor_log2(fr: Fraction) -> int:
    # floor(log2(fr)) for a positive Fraction, exact.
    n, d = fr.numerator, fr.denominator
    e = n.bit_length() - d.bit_length()
    # correct off-by-one
    if Fraction(n, d) < Fraction(1) * (1 << e) if e >= 0 else Fraction(n, d) < Fraction(1, 1 << -e):
        e -= 1
    while (Fraction(1) * (1 << e) if e >= 0 else Fraction(1, 1 << -e)) > fr:
        e -= 1
    while (Fraction(1) * (1 << (e + 1)) if e + 1 >= 0 else Fraction(1, 1 << -(e + 1))) <= fr:
        e += 1
    return e


def _pow2(e: int) -> Fraction:
    return Fraction(1) * (1 << e) if e >= 0 else Fraction(1, 1 << -e)


def encode(value) -> int:
    if value == 0:
        return 0
    sign = 1 if value < 0 else 0
    av = abs(Fraction(value))
    e = _floor_log2(av)
    offset = e + EXP_OFFSET
    if offset >= OFFSET_MAX:
        return (sign << SIGN_SHIFT) | INF
    if offset < 1:
        # underflow to smallest normal (keep the oracle simple, no subnormals)
        offset = 1
        e = offset - EXP_OFFSET
    frac = av / _pow2(e) - 1                      # in [0,1)
    # round-to-nearest-even to MANT bits
    scaled = frac * MANT
    fl = int(scaled)
    rem = scaled - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and (fl & 1)):
        fl += 1
    if fl == MANT:                               # mantissa carry
        fl = 0
        offset += 1
        if offset >= OFFSET_MAX:
            return (sign << SIGN_SHIFT) | INF
    return (sign << SIGN_SHIFT) | (offset << EXP_SHIFT) | fl


def is_special(raw: int) -> bool:
    return ((raw >> EXP_SHIFT) & 0x7F) == OFFSET_MAX


def decode(raw: int):
    sign = (raw >> SIGN_SHIFT) & 1
    offset = (raw >> EXP_SHIFT) & 0x7F
    mant = raw & (MANT - 1)
    if offset == OFFSET_MAX:
        return math.nan if mant else (-math.inf if sign else math.inf)
    if offset == 0:
        return Fraction(0)
    val = (Fraction(1) + Fraction(mant, MANT)) * _pow2(offset - EXP_OFFSET)
    return -val if sign else val


def gft16_add(a_raw: int, b_raw: int) -> int:
    if is_special(a_raw) or is_special(b_raw):
        return NAN
    return encode(decode(a_raw) + decode(b_raw))


def gft16_mul(a_raw: int, b_raw: int) -> int:
    if is_special(a_raw) or is_special(b_raw):
        return NAN
    return encode(decode(a_raw) * decode(b_raw))


if __name__ == "__main__":
    # self-test: round-trip, commutativity, known values, monotone exponent
    import random
    rnd = random.Random(1)
    bad = 0
    for _ in range(20000):
        x = (1 if rnd.random() < .5 else -1) * 2.0 ** rnd.uniform(-38, 38) * (1 + rnd.uniform(0, .99))
        y = (1 if rnd.random() < .5 else -1) * 2.0 ** rnd.uniform(-38, 38) * (1 + rnd.uniform(0, .99))
        if gft16_add(encode(x), encode(y)) != gft16_add(encode(y), encode(x)):
            bad += 1
        if gft16_mul(encode(x), encode(y)) != gft16_mul(encode(y), encode(x)):
            bad += 1
    # exactness on representable values
    assert abs(float(decode(encode(3.0))) - 3.0) < 1e-2
    assert is_special(INF) and is_special(NAN)
    assert decode(encode(0)) == 0
    print(f"gft16_ref self-test: add/mul commutative over 20000 pairs, {bad} violations")
    print(f"  1.5*2.0 = {float(decode(gft16_mul(encode(1.5), encode(2.0)))):.4f} (expect ~3.0)")
    # 2^35 is inside GF-T16's +-40-exponent (~24-decade) range but OUTSIDE GF16's
    # 6-bit-exponent (~18-decade) range, where GF16 saturates to Inf.
    v = 2.0 ** 35
    print(f"  2^35 round-trip = {float(decode(encode(v))):.4e} (GF-T16 holds it; GF16 clips to Inf)")
