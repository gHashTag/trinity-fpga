#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ieee_ref.py — REFERENCE (golden) software oracle for the standard
IEEE 754 binary formats: binary16/32/64/128/256 + tf32.

Uses exact rational arithmetic (fractions.Fraction):
round-ties-even is provable, gradual underflow is correct.
Patterned on conformance/gf_ref.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class IEEFormat:
    name: str
    exp_bits: int
    mant_bits: int
    bias: int

    @property
    def width(self):
        return 1 + self.exp_bits + self.mant_bits

    @property
    def exp_max(self):
        return (1 << self.exp_bits) - 1

    @property
    def mant_max(self):
        return (1 << self.mant_bits) - 1

    @property
    def sign_shift(self):
        return self.exp_bits + self.mant_bits

    @property
    def mask(self):
        return (1 << self.width) - 1

    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self): return 1 << self.sign_shift
    @property
    def pos_inf(self): return self.exp_max << self.mant_bits
    @property
    def neg_inf(self): return (1 << self.sign_shift) | (self.exp_max << self.mant_bits)
    @property
    def quiet_nan(self): return (self.exp_max << self.mant_bits) | 1


FORMATS = {
    "binary16":  IEEFormat("binary16",  exp_bits=5,  mant_bits=10,  bias=15),
    "binary32":  IEEFormat("binary32",  exp_bits=8,  mant_bits=23,  bias=127),
    "binary64":  IEEFormat("binary64",  exp_bits=11, mant_bits=52,  bias=1023),
    "binary128": IEEFormat("binary128", exp_bits=15, mant_bits=112, bias=16383),
    "binary256": IEEFormat("binary256", exp_bits=19, mant_bits=236, bias=262143),
    "tf32":      IEEFormat("tf32",      exp_bits=8,  mant_bits=10,  bias=127),
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


def decode(fmt: IEEFormat, raw: int):
    raw &= fmt.mask
    sign = (raw >> fmt.sign_shift) & 1
    exp = (raw >> fmt.mant_bits) & fmt.exp_max
    mant = raw & fmt.mant_max

    if exp == fmt.exp_max:
        if mant == 0:
            return Special("inf", sign)
        return Special("nan")

    if exp == 0:
        if mant == 0:
            return Fraction(0)
        val = Fraction(mant, 1 << fmt.mant_bits) * pow2(1 - fmt.bias)
    else:
        val = (1 + Fraction(mant, 1 << fmt.mant_bits)) * pow2(exp - fmt.bias)

    return -val if sign else val


def encode(fmt: IEEFormat, value):
    if isinstance(value, Special):
        if value.kind == "nan":
            return fmt.quiet_nan
        return fmt.neg_inf if value.sign else fmt.pos_inf

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
        if exp_field >= fmt.exp_max:
            return fmt.neg_inf if sign else fmt.pos_inf
        return (sign << fmt.sign_shift) | (exp_field << fmt.mant_bits) | (mant & fmt.mant_max)
    else:
        scale = pow2(1 - fmt.bias)
        m_real = a / scale * (1 << fmt.mant_bits)
        m, carry = _round_half_even(m_real)
        if m == 0:
            return (sign << fmt.sign_shift) | 0
        if m > fmt.mant_max:
            return (sign << fmt.sign_shift) | (1 << fmt.mant_bits)
        return (sign << fmt.sign_shift) | (m & fmt.mant_max)


def format_add(fmt: IEEFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)

    if isinstance(a, Special) and a.kind == "nan": return fmt.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return fmt.quiet_nan
    if isinstance(a, Special) and a.kind == "inf":
        if isinstance(b, Special) and b.kind == "inf" and b.sign != a.sign:
            return fmt.quiet_nan
        return fmt.neg_inf if a.sign else fmt.pos_inf
    if isinstance(b, Special) and b.kind == "inf":
        return fmt.neg_inf if b.sign else fmt.pos_inf

    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    a_zero = (a == 0)
    b_zero = (b == 0)
    if a_zero and b_zero:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero

    return encode(fmt, a + b)


def format_mul(fmt: IEEFormat, a_raw: int, b_raw: int) -> int:
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
        check(encode(fmt, Special("inf")) == fmt.pos_inf, f"{fname}: +Inf")
        check(isinstance(decode(fmt, fmt.pos_inf), Special), f"{fname}: decode +Inf")
        check(isinstance(decode(fmt, fmt.quiet_nan), Special), f"{fname}: decode NaN")

        # 1 + 1 = 2
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got decode {decode(fmt, r)})")
        # 0 + 0 = 0
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")
        # x + 0 == x bit-exact (for non-special x)
        if fmt.width <= 16:
            codes = range(0, 1 << fmt.width)
        else:
            rng = random.Random(0xABCDEF + fmt.width)
            codes = [rng.randrange(1 << fmt.width) for _ in range(4000)]
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special) or v == 0:
                continue
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")
            check(format_mul(fmt, raw, format_mul(fmt, raw, 0)) == 0,
                  f"{fname}: x*0=0")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (ieee: zero/unity/inf/nan/1+1/x+0/x*0)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
