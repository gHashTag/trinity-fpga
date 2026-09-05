#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bf16_ref.py — ЭТАЛОННЫЙ (golden) оракул для bfloat-семейства (8-бит экспонента).
bfloat16 (E=8,M=7), bfloat24 (E=8,M=15), bfloat32 (E=8,M=23).
IEEE 754 стиль, round-ties-even, точная Fraction-арифметика.
По образцу conformance/gf_ref.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class BFFormat:
    name: str
    exp_bits: int
    mant_bits: int
    bias: int

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
    def pos_inf(self): return self.exp_max << self.mant_bits
    @property
    def neg_inf(self): return (1 << self.sign_shift) | (self.exp_max << self.mant_bits)
    @property
    def quiet_nan(self): return (self.exp_max << self.mant_bits) | 1


FORMATS = {
    "bfloat16": BFFormat("bfloat16", exp_bits=8, mant_bits=7,  bias=127),
    "bfloat24": BFFormat("bfloat24", exp_bits=8, mant_bits=15, bias=127),
    "bfloat32": BFFormat("bfloat32", exp_bits=8, mant_bits=23, bias=127),
    # AFP (Adaptive Floating Point, Tambe 2020): [S:1][E:8][M:7] = 16 bits,
    # identical layout to bfloat16. The per-tensor "shift" adjusts the shared
    # exponent bias (effective_bias = bias - shift). At shift=0 AFP is
    # bit-identical to bfloat16 — which is exactly what the AX7203 decode
    # cell implements (pure bf16 bit-pad, see corona_decode_afp_ax7203.v).
    # Conformance vectors are therefore generated at shift=0; shift-aware
    # decode/encode/add/mul are provided below as afp_* helpers.
    "afp":      BFFormat("afp",     exp_bits=8, mant_bits=7,  bias=127),
}


# -------------------- AFP shift-aware helpers --------------------
# AFP shares the 16-bit bfloat16 layout but applies a per-tensor integer
# "shift" that rescales the exponent bias: value = significand * 2^(exp - (bias - shift)).
# shift=0 -> AFP == bfloat16 (the conformance baseline). These helpers carry
# the shift explicitly for callers that model a non-zero tensor shift.

AFP = FORMATS["afp"]


def afp_decode(raw: int, shift: int = 0):
    """Decode AFP raw at the given tensor shift. shift=0 == bf16 decode."""
    if shift == 0:
        return decode(AFP, raw)
    raw &= AFP.mask
    sign = (raw >> AFP.sign_shift) & 1
    exp = (raw >> AFP.mant_bits) & AFP.exp_max
    mant = raw & AFP.mant_max
    eff_bias = AFP.bias - shift
    if exp == AFP.exp_max:
        if mant == 0:
            return Special("inf", sign)
        return Special("nan")
    if exp == 0:
        if mant == 0:
            return Fraction(0)
        val = Fraction(mant, 1 << AFP.mant_bits) * pow2(1 - eff_bias)
    else:
        val = (1 + Fraction(mant, 1 << AFP.mant_bits)) * pow2(exp - eff_bias)
    return -val if sign else val


def afp_encode(value, shift: int = 0) -> int:
    """Encode a value to AFP raw at the given tensor shift. shift=0 == bf16 encode."""
    if shift == 0:
        return encode(AFP, value)
    # Rescale into the bf16 domain: a value v at bias' = bias - shift encodes
    # the same bit-pattern as v * 2^(-shift) at the original bias. Encode the
    # rescaled value with the unmodified bf16 encoder.
    if isinstance(value, Special):
        return encode(AFP, value)
    v = Fraction(value)
    if shift > 0:
        v = v / pow2(shift)
    else:
        v = v * pow2(-shift)
    return encode(AFP, v)


def afp_add(a_raw: int, b_raw: int, shift: int = 0) -> int:
    a = afp_decode(a_raw, shift)
    b = afp_decode(b_raw, shift)
    if isinstance(a, Special) and a.kind == "nan": return AFP.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return AFP.quiet_nan
    if isinstance(a, Special) and a.kind == "inf":
        if isinstance(b, Special) and b.kind == "inf" and b.sign != a.sign:
            return AFP.quiet_nan
        return AFP.neg_inf if a.sign else AFP.pos_inf
    if isinstance(b, Special) and b.kind == "inf":
        return AFP.neg_inf if b.sign else AFP.pos_inf
    sa = (a_raw >> AFP.sign_shift) & 1
    sb = (b_raw >> AFP.sign_shift) & 1
    if a == 0 and b == 0:
        return AFP.neg_zero if (sa == 1 and sb == 1) else AFP.pos_zero
    return afp_encode(a + b, shift)


def afp_mul(a_raw: int, b_raw: int, shift: int = 0) -> int:
    a = afp_decode(a_raw, shift)
    b = afp_decode(b_raw, shift)
    sa = (a_raw >> AFP.sign_shift) & 1
    sb = (b_raw >> AFP.sign_shift) & 1
    rsign = sa ^ sb
    if isinstance(a, Special) and a.kind == "nan": return AFP.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return AFP.quiet_nan
    a_inf = isinstance(a, Special) and a.kind == "inf"
    b_inf = isinstance(b, Special) and b.kind == "inf"
    if a_inf or b_inf:
        if a == 0 or b == 0:
            return AFP.quiet_nan
        return AFP.neg_inf if rsign else AFP.pos_inf
    if a == 0 or b == 0:
        return AFP.neg_zero if rsign else AFP.pos_zero
    return afp_encode(a * b, shift)


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


def decode(fmt: BFFormat, raw: int):
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


def encode(fmt: BFFormat, value):
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
        m, _ = _round_half_even(m_real)
        if m == 0:
            return (sign << fmt.sign_shift) | 0
        if m > fmt.mant_max:
            return (sign << fmt.sign_shift) | (1 << fmt.mant_bits)
        return (sign << fmt.sign_shift) | (m & fmt.mant_max)


def format_add(fmt: BFFormat, a_raw: int, b_raw: int) -> int:
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
    if a == 0 and b == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero

    return encode(fmt, a + b)


def format_mul(fmt: BFFormat, a_raw: int, b_raw: int) -> int:
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
        one = encode(fmt, Fraction(1))
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2")

        # Multiplication was checked nowhere. Pass 221's mutation gate corrupted format_mul and
        # this self-test did not notice, while bfloat*_mul.json is generated from it. Six of sixteen
        # oracles had the same hole and every one of them was multiplication -- addition is
        # checked everywhere, mul nowhere.
        #
        # Properties of the OPERATION, not of the implementation: unity is neutral and zero
        # absorbs. Both hold in every format here regardless of width or rounding.
        check(format_mul(fmt, one, one) == one, f"{fname}: 1*1=1")
        check(decode(fmt, format_mul(fmt, one, fmt.pos_zero)) == 0, f"{fname}: 1*0=0")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")
        check(isinstance(decode(fmt, fmt.pos_inf), Special), f"{fname}: +Inf")
        check(isinstance(decode(fmt, fmt.quiet_nan), Special), f"{fname}: NaN")

        rng = random.Random(0xBEEF + fmt.width)
        for _ in range(3000):
            raw = rng.randrange(1 << fmt.width)
            v = decode(fmt, raw)
            if isinstance(v, Special) or v == 0:
                continue
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    # AFP shift sanity: shift=0 must match bf16 bit-for-bit; non-zero shift
    # rescales the shared exponent bias (eff_bias = bias - shift, i.e. a raw
    # held under shift k represents value * 2^k vs the same bits at shift 0).
    afp_fmt = FORMATS["afp"]
    bf16_fmt = FORMATS["bfloat16"]

    # afp_mul was checked nowhere. This module has TWO multiplication functions and the
    # first patch of pass 221 covered only format_mul; the mutation gate still reported
    # afp_mul surviving. Properties of the operation, at the default shift.
    _afp_one = afp_encode(Fraction(1))
    check(afp_mul(_afp_one, _afp_one) == _afp_one, "afp: 1*1=1")
    check(afp_decode(afp_mul(_afp_one, afp_encode(Fraction(0)))) == 0, "afp: 1*0=0")
    check(afp_decode(afp_mul(_afp_one, afp_encode(Fraction(2)))) == 2, "afp: 1*2=2")

    def _same(a, b):
        if isinstance(a, Special) or isinstance(b, Special):
            return isinstance(a, Special) and isinstance(b, Special) \
                and a.kind == b.kind and a.sign == b.sign
        return a == b

    # shift=0: AFP decode/encode == bf16 decode/encode for every raw.
    for raw in (0, bf16_fmt.pos_zero, bf16_fmt.pos_inf,
                bf16_fmt.neg_inf, bf16_fmt.quiet_nan,
                encode(bf16_fmt, Fraction(1)), encode(bf16_fmt, Fraction(2)),
                encode(bf16_fmt, Fraction(1, 2)), encode(bf16_fmt, Fraction(-3))):
        check(_same(afp_decode(raw, 0), decode(bf16_fmt, raw)),
              f"afp: shift0 decode raw=0x{raw:x}")
        # encode(0) always yields +0, so skip neg_zero for the round-trip.
        if raw != bf16_fmt.neg_zero:
            check(afp_encode(decode(bf16_fmt, raw), 0) == raw,
                  f"afp: shift0 round-trip raw=0x{raw:x}")
    # neg_zero still decodes to zero at shift 0.
    check(afp_decode(bf16_fmt.neg_zero, 0) == 0, "afp: neg_zero decodes to 0")

    # Round-trip at non-zero shifts: decode(encode(v, k), k) == v.
    for k in (-3, -1, 1, 4):
        for v in (Fraction(1), Fraction(2), Fraction(1, 2), Fraction(-3),
                  Fraction(7, 4), Fraction(0)):
            raw = afp_encode(v, k)
            check(afp_decode(raw, k) == v, f"afp: round-trip v={v} k={k}")

    # Cross-check: a raw encoded at shift k decodes under plain bf16 to v/2^k.
    for k in (1, 2, -1):
        raw = afp_encode(Fraction(1), k)
        check(decode(bf16_fmt, raw) == Fraction(1, 1 << k) if k > 0
              else decode(bf16_fmt, raw) == Fraction(1 << (-k)),
              f"afp: encode 1.0 at shift={k} maps to bf16 2^(-{k})")

    check(afp_add(0, 0, 0) == 0, "afp: 0+0=0 shift0")
    if failures:
        print("SELF-TEST: FAIL (afp: %d)" % len(failures))
        for f in failures[-10:]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (bfloat+afp: zero/unity/inf/nan/1+1/x+0/shift)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
