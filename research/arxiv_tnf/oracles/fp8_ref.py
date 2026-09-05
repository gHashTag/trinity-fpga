#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fp8_ref.py — ЭТАЛОННЫЙ (golden) оракул для OCP FP8/FP4/FP6 минифлоат-семейства.
  fp8_e4m3 (E=4,M=3,bias=7)  — нет Inf; NaN только при exp=max & mant=max
  fp8_e5m2 (E=5,M=2,bias=15) — IEEE Inf/NaN
  fp4_e2m1 (E=2,M=1,bias=1)  — нет specials
  fp6_e2m3 (E=2,M=3,bias=1)  — нет specials
  fp6_e3m2 (E=3,M=2,bias=3)  — нет specials
Round-ties-even, точная Fraction-арифметика. По образцу conformance/gf_ref.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class FPxFormat:
    name: str
    exp_bits: int
    mant_bits: int
    bias: int
    has_inf: bool = False          # exp_max: mant==0 -> Inf, mant!=0 -> NaN
    nan_at_max_only: bool = False  # exp_max & mant==mant_max -> NaN, rest finite

    @property
    def width(self): return 1 + self.exp_bits + self.mant_bits
    @property
    def exp_max(self): return (1 << self.exp_bits) - 1
    @property
    def mant_max(self): return (1 << self.mant_bits) - 1
    @property
    def sign_shift(self): return self.exp_bits + self.mant_bits
    @property
    def mask(self): return (1 << self.width) - 1
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self): return 1 << self.sign_shift
    @property
    def quiet_nan(self):
        if self.has_inf:
            return (self.exp_max << self.mant_bits) | 1
        if self.nan_at_max_only:
            return (self.exp_max << self.mant_bits) | self.mant_max
        return (self.exp_max << self.mant_bits) | 1
    @property
    def pos_inf(self): return self.exp_max << self.mant_bits
    @property
    def neg_inf(self): return (1 << self.sign_shift) | (self.exp_max << self.mant_bits)

    def max_finite_raw(self):
        if self.has_inf:
            e = self.exp_max - 1
            m = self.mant_max
        elif self.nan_at_max_only:
            e = self.exp_max
            m = self.mant_max - 1
        else:
            e = self.exp_max
            m = self.mant_max
        return (e << self.mant_bits) | m


FORMATS = {
    "fp8_e4m3": FPxFormat("fp8_e4m3", exp_bits=4, mant_bits=3, bias=7,  nan_at_max_only=True),
    "fp8_e5m2": FPxFormat("fp8_e5m2", exp_bits=5, mant_bits=2, bias=15, has_inf=True),
    "fp4_e2m1": FPxFormat("fp4_e2m1", exp_bits=2, mant_bits=1, bias=1),
    "fp6_e2m3": FPxFormat("fp6_e2m3", exp_bits=2, mant_bits=3, bias=1),
    "fp6_e3m2": FPxFormat("fp6_e3m2", exp_bits=3, mant_bits=2, bias=3),
}


class Special:
    def __init__(self, kind, sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        if self.kind == "nan":
            return "NaN"
        return ("-" if self.sign else "+") + "Inf"


def pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def ilog2_floor(a: Fraction) -> int:
    assert a > 0
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < pow2(e):
        e -= 1
    while Fraction(n, d) >= pow2(e + 1):
        e += 1
    return e


def _round_half_even(x: Fraction, cap=None):
    floor_i = x.numerator // x.denominator
    rem = x - floor_i
    half = Fraction(1, 2)
    if rem < half:
        r = floor_i
    elif rem > half:
        r = floor_i + 1
    else:
        r = floor_i if (floor_i % 2 == 0) else floor_i + 1
    if cap is not None and r >= cap:
        return cap, True
    return r, False


def decode(fmt: FPxFormat, raw: int):
    raw &= fmt.mask
    sign = (raw >> fmt.sign_shift) & 1
    exp = (raw >> fmt.mant_bits) & fmt.exp_max
    mant = raw & fmt.mant_max

    if exp == fmt.exp_max:
        if fmt.has_inf:
            if mant == 0:
                return Special("inf", sign)
            return Special("nan")
        if fmt.nan_at_max_only and mant == fmt.mant_max:
            return Special("nan")
        # otherwise: finite normal at exp_max (no special)

    if exp == 0:
        if mant == 0:
            return Fraction(0)
        val = Fraction(mant, 1 << fmt.mant_bits) * pow2(1 - fmt.bias)
    else:
        val = (1 + Fraction(mant, 1 << fmt.mant_bits)) * pow2(exp - fmt.bias)

    return -val if sign else val


def _overflow_raw(fmt: FPxFormat, sign: int) -> int:
    """Saturate on overflow per format policy."""
    if fmt.has_inf:
        return fmt.neg_inf if sign else fmt.pos_inf
    sat = fmt.max_finite_raw()
    return ((1 << fmt.sign_shift) | sat) if sign else sat


def encode(fmt: FPxFormat, value):
    if isinstance(value, Special):
        if value.kind == "nan":
            return fmt.quiet_nan
        if fmt.has_inf:
            return fmt.neg_inf if value.sign else fmt.pos_inf
        return _overflow_raw(fmt, value.sign)

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v
    E = ilog2_floor(a)
    exp_field = E + fmt.bias

    if exp_field >= 1:
        frac = a / pow2(E) - 1
        mant, carry = _round_half_even(frac * (1 << fmt.mant_bits), cap=(1 << fmt.mant_bits))
        if carry:
            mant = 0
            exp_field += 1
        # overflow check
        if fmt.has_inf:
            if exp_field >= fmt.exp_max:
                return _overflow_raw(fmt, sign)
        elif fmt.nan_at_max_only:
            if exp_field > fmt.exp_max:
                return _overflow_raw(fmt, sign)
            if exp_field == fmt.exp_max and mant >= fmt.mant_max:
                return _overflow_raw(fmt, sign)
        else:
            if exp_field > fmt.exp_max:
                return _overflow_raw(fmt, sign)
        return (sign << fmt.sign_shift) | (exp_field << fmt.mant_bits) | (mant & fmt.mant_max)
    else:
        scale = pow2(1 - fmt.bias)
        m_real = a / scale * (1 << fmt.mant_bits)
        m, _ = _round_half_even(m_real)
        if m == 0:
            return (sign << fmt.sign_shift) | 0
        if m > fmt.mant_max:
            return (sign << fmt.sign_shift) | (1 << fmt.mant_bits)
        return (sign << fmt.sign_shift) | (m & fmt.mant_max)


def format_add(fmt: FPxFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)

    if isinstance(a, Special) and a.kind == "nan": return fmt.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return fmt.quiet_nan
    a_inf = isinstance(a, Special) and a.kind == "inf"
    b_inf = isinstance(b, Special) and b.kind == "inf"
    if a_inf or b_inf:
        if a_inf and b_inf and a.sign != b.sign:
            return fmt.quiet_nan
        s = a.sign if a_inf else b.sign
        return fmt.neg_inf if s else fmt.pos_inf

    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    if a == 0 and b == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero

    return encode(fmt, a + b)


def format_mul(fmt: FPxFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb

    if isinstance(a, Special) and a.kind == "nan": return fmt.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return fmt.quiet_nan
    a_inf = isinstance(a, Special) and a.kind == "inf"
    b_inf = isinstance(b, Special) and b.kind == "inf"
    if a_inf or b_inf:
        if a == 0 or b == 0:
            return fmt.quiet_nan
        return fmt.neg_inf if rsign else fmt.pos_inf

    if a == 0 or b == 0:
        return fmt.neg_zero if rsign else fmt.pos_zero

    return encode(fmt, a * b)


def _selftest():
    import random
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: +0")
        check(encode(fmt, 0) == 0, f"{fname}: encode 0")
        one = encode(fmt, Fraction(1))
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")

        # Multiplication was checked nowhere. Pass 220's mutation gate corrupted
        # format_mul and this self-test did not notice -- while fp8_*_mul.json is
        # generated from it. Three properties of the operation, not of the
        # implementation: unity is neutral, zero absorbs, and 2*2 is 4 wherever 4 is
        # representable, which it is at every fp8 width here.
        check(format_mul(fmt, one, one) == one, f"{fname}: 1*1=1")
        check(decode(fmt, format_mul(fmt, one, 0)) == 0, f"{fname}: 1*0=0")
        two = format_add(fmt, one, one)
        check(decode(fmt, format_mul(fmt, two, two)) == 4,
              f"{fname}: 2*2=4 (got {decode(fmt, format_mul(fmt, two, two))})")
        if fmt.has_inf or fmt.nan_at_max_only:
            check(isinstance(decode(fmt, fmt.quiet_nan), Special), f"{fname}: NaN")

        # exhaustive for tiny formats, sampled for fp8
        if fmt.width <= 6:
            codes = range(0, 1 << fmt.width)
        else:
            codes = range(0, 1 << fmt.width)  # fp8: 256 — exhaustive is cheap
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special) or v == 0:
                continue
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (fp8/fp4/fp6: zero/unity/nan/1+1/x+0, exhaustive)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
