#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extended_ref.py — REFERENCE (golden) oracle for multi-component extended formats.

  double_double  — 2 × IEEE-754 binary64 (hi + lo), representing hi+lo EXACTLY
                   as an error-free expansion (Bailey/Hida/Briggs/Dekker).
                   Width = 128 bits (2 × 64).
  quad_double    — 4 × IEEE-754 binary64 (hi + lo1 + lo2 + lo3), error-free.
                   Width = 256 bits (4 × 64).

Decode: each binary64 limb is decoded exactly (Fraction), value = sum of limbs.
Encode: exact value → sequence of error-free binary64 limbs via the
        Dekker–Hida algorithm (two-word split with round-ties-even).
Add/Mul: decode → exact Fraction arithmetic → encode.

Consistent with:
  - conformance/double_double_decode_conformance_ax7203.py
  - conformance/quad_double_decode_conformance_ax7203.py

These HW scripts send FP32 over UART (the hardware bottleneck); our oracle works
at its own width (128/256 bits) and loses no precision. The domain is
the mathematical ℤ[2^k] (exact dyadic rationals).

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


# -------------------- format --------------------

@dataclass(frozen=True)
class ExtendedFormat:
    name: str
    n_limbs: int           # 2 for double_double, 4 for quad_double
    limb_width: int = 64   # each limb is IEEE-754 binary64

    @property
    def width(self):
        return self.n_limbs * self.limb_width
    @property
    def mask(self):
        return (1 << self.width) - 1
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self):
        # sign of hi-limb = 1, all others 0 → "negative zero"
        return 1 << (self.width - 1)
    @property
    def pos_inf(self):
        # binary64 +Inf in the hi-limb (low bits), zeros elsewhere — matches HW
        # byte order where limb-0 (low address) is the most-significant.
        return _B64_INF
    @property
    def neg_inf(self):
        return _B64_INF | _B64_SIGN
    @property
    def quiet_nan(self):
        return _B64_QNAN
    @property
    def has_inf(self): return True


FORMATS = {
    "double_double": ExtendedFormat("double_double", n_limbs=2),
    "quad_double":   ExtendedFormat("quad_double",   n_limbs=4),
}


# -------------------- binary64 helpers (limb codec) --------------------

_B64_SIGN = 1 << 63
_B64_EXP_MASK = 0x7FF
_B64_MANT_BITS = 52
_B64_MANT_MAX = (1 << _B64_MANT_BITS) - 1
_B64_INF = 0x7FF0000000000000
_B64_QNAN = 0x7FF8000000000000
_B64_BIAS = 1023


class Special:
    def __init__(self, kind="nan", sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        return "NaN" if self.kind == "nan" else ("-" if self.sign else "+") + "Inf"


def _pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def _decode_binary64(bits: int):
    """binary64 raw → Fraction | Special('inf'|'nan')."""
    bits &= (1 << 64) - 1
    sign = (bits >> 63) & 1
    exp = (bits >> 52) & _B64_EXP_MASK
    mant = bits & _B64_MANT_MAX

    if exp == _B64_EXP_MASK:
        if mant == 0:
            return Special("inf", sign)
        return Special("nan", sign)

    if exp == 0:
        if mant == 0:
            return Fraction(0)
        val = Fraction(mant, 1 << 1074)           # subnormal: mant * 2^-1074
    else:
        val = (1 + Fraction(mant, 1 << _B64_MANT_BITS)) * _pow2(exp - _B64_BIAS)

    return -val if sign else val


def _round_half_even(x: Fraction):
    """Round exact Fraction x to nearest integer, ties-to-even. Returns int."""
    floor_i = x.numerator // x.denominator
    rem = x - floor_i
    half = Fraction(1, 2)
    if rem < half:
        return floor_i
    if rem > half:
        return floor_i + 1
    return floor_i if (floor_i % 2 == 0) else floor_i + 1


def _ilog2_floor(a: Fraction) -> int:
    """floor(log2(a)) for an exact positive Fraction a."""
    assert a > 0
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < _pow2(e):
        e -= 1
    while Fraction(n, d) >= _pow2(e + 1):
        e += 1
    return e


def _encode_binary64(value) -> int:
    """Exact Fraction (or Special) → binary64 raw, round-ties-even, gradual underflow."""
    if isinstance(value, Special):
        if value.kind == "nan":
            return _B64_QNAN
        return (_B64_INF | _B64_SIGN) if value.sign else _B64_INF

    v = Fraction(value)
    if v == 0:
        return 0

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v
    E = _ilog2_floor(a)
    exp_field = E + _B64_BIAS

    if exp_field >= 1:
        frac = a / _pow2(E) - 1                  # [0, 1)
        scaled = frac * (1 << _B64_MANT_BITS)
        mant = _round_half_even(scaled)
        if mant >= (1 << _B64_MANT_BITS):
            # rounded up to 1.0 → bump exponent
            mant = 0
            exp_field += 1
        if exp_field >= _B64_EXP_MASK:
            return (_B64_INF | _B64_SIGN) if sign else _B64_INF
        return (sign << 63) | (exp_field << _B64_MANT_BITS) | (mant & _B64_MANT_MAX)
    else:
        # subnormal
        scale = _pow2(1 - _B64_BIAS)
        m_real = a / scale * (1 << _B64_MANT_BITS)
        m = _round_half_even(m_real)
        if m == 0:
            return (sign << 63) | 0
        if m > _B64_MANT_MAX:
            return (sign << 63) | (1 << _B64_MANT_BITS)   # smallest normal
        return (sign << 63) | (m & _B64_MANT_MAX)


# -------------------- Error-free expansion (Dekker / Hida) --------------------
#
# Given an exact Fraction x, produce a sequence of binary64 limbs (l0=hi, l1, ...)
# such that the EXACT sum of their decoded values equals x when x is representable
# as the sum of N binary64 values, and otherwise equals the rounded sum of N
# binary64 encodings of successively smaller residuals.
#
# Algorithm (Hida–Li–Bailey 2001, "Algorithms for quad-double arithmetic"):
#   1. Encode the leading limb l0 = round(x).
#   2. Residual r1 = x - decode(l0)  (exact, since both are dyadic rationals).
#   3. Repeat on r_i to obtain l_i, until N limbs or residual == 0.


def _encode_expansion(value, n_limbs: int) -> int:
    """Exact value → packed N-limb raw (hi-limb at low bits — matches HW)."""
    if isinstance(value, Special):
        # specials live in the hi-limb (low bits) per HW convention.
        return _encode_binary64(value)

    v = Fraction(value)
    limbs = []
    residual = v
    for _ in range(n_limbs):
        if residual == 0:
            limbs.append(0)
            continue
        l = _encode_binary64(residual)
        limbs.append(l)
        residual = residual - _decode_binary64(l)
        if isinstance(residual, Special):
            # shouldn't happen for finite residual; safety net.
            residual = Fraction(0)

    # Pack: hi-limb in the most-significant position (matches HW byte order
    # little-endian within limb, but limb-0 is the low address → low bits).
    raw = 0
    for i, l in enumerate(limbs):
        raw |= (l & ((1 << 64) - 1)) << (64 * i)
    return raw


def _decode_expansion(fmt: ExtendedFormat, raw: int):
    """Packed N-limb raw → Fraction (exact finite sum) | Special.

    Limb order: limb 0 (least-significant bit position) is the LO limb;
    limb (n-1) is the HI limb (matches Hida convention l1 most-sig first
    when laid out little-endian as the HW protocol does).
    """
    raw &= fmt.mask
    limbs = [(raw >> (64 * i)) & ((1 << 64) - 1) for i in range(fmt.n_limbs)]

    # Scan for specials in any limb.
    has_nan = False
    infs = []  # list of (sign)
    for i, l in enumerate(limbs):
        exp = (l >> 52) & _B64_EXP_MASK
        mant = l & _B64_MANT_MAX
        if exp == _B64_EXP_MASK:
            if mant != 0:
                has_nan = True
            else:
                infs.append((l >> 63) & 1)
    if has_nan:
        return Special("nan")
    if infs:
        # inf + (-inf) → NaN
        if any(s == 0 for s in infs) and any(s == 1 for s in infs):
            return Special("nan")
        return Special("inf", sign=max(infs))

    total = Fraction(0)
    for l in limbs:
        d = _decode_binary64(l)
        if not isinstance(d, Special):
            total += d
    return total


def is_canonical(fmt: ExtendedFormat, raw: int):
    """Is this packed word a valid expansion, rather than merely a correct value?

    These two formats are the only ones in the corpus where membership is a relation
    between limbs instead of a pattern of bits. A double_double is a pair of binary64
    values summing to the number, and it is a double_double only if the pair is
    *nonoverlapping*: each limb must be the correctly-rounded binary64 of the exact sum of
    itself and everything below it. Shewchuk calls that a nonoverlapping expansion; the QD
    library of Hida, Li and Bailey calls it renormalized and requires it of every input.

    So 0.5 + 0.5 holds the value 1 exactly and is not a double_double, because
    fl(0.5 + 0.5) is 1.0 and not 0.5 -- the leading limb does not absorb its own tail.
    Comparing decoded values can never see the difference; that is the whole point.

    Returns None when a limb is Inf or NaN. A special is judged by the rules in
    research/audit_special_coverage.py, and answering under both would count it twice.

    Limb order note: limb 0 sits at bit position 0 and is the MOST significant, which
    _decode_expansion's docstring words the other way round. encode(1.0) settles it --
    [0x3ff0000000000000, 0x0]. An audit written from the docstring reported 80% of the
    corpus as non-canonical before validating itself against encode().
    """
    limbs = [(raw >> (64 * i)) & ((1 << 64) - 1) for i in range(fmt.n_limbs)]
    vals = []
    for l in limbs:
        d = _decode_binary64(l)
        if isinstance(d, Special):
            return None
        vals.append(d)
    for i in range(len(limbs) - 1):
        tail = sum(vals[i + 1:], Fraction(0))
        if _encode_binary64(vals[i] + tail) != limbs[i]:
            return False
    return True


# -------------------- public API --------------------

def decode(fmt: ExtendedFormat, raw: int):
    return _decode_expansion(fmt, raw)


def encode(fmt: ExtendedFormat, value) -> int:
    return _encode_expansion(value, fmt.n_limbs)


def format_add(fmt: ExtendedFormat, a_raw: int, b_raw: int) -> int:
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

    sa = (a_raw >> (fmt.width - 1)) & 1
    sb = (b_raw >> (fmt.width - 1)) & 1
    if a == 0 and b == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero

    return encode(fmt, a + b)


def format_mul(fmt: ExtendedFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    sa = (a_raw >> (fmt.width - 1)) & 1
    sb = (b_raw >> (fmt.width - 1)) & 1
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


# -------------------- SELF-TEST --------------------

def _selftest():
    import random
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        # Zero.
        check(decode(fmt, 0) == 0, f"{fname}: decode +0")
        check(encode(fmt, 0) == 0, f"{fname}: encode +0")
        # Unity: hi-limb (bits 0..63) = binary64 1.0, others = 0.
        # Limb order matches HW: l0=hi at the LOW bit position (little-endian).
        one_raw = _encode_binary64(Fraction(1))
        check(encode(fmt, Fraction(1)) == one_raw, f"{fname}: encode 1.0")
        check(decode(fmt, one_raw) == 1, f"{fname}: decode 1.0")
        # 1 + 1 = 2.
        r = format_add(fmt, one_raw, one_raw)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        # 1 * 1 = 1.
        check(decode(fmt, format_mul(fmt, one_raw, one_raw)) == 1,
              f"{fname}: 1*1=1")
        # 0 + 0 = 0.
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")
        # x + 0 == x bit-exact for DYADIC (binary64-representable) values —
        # only dyadics can round-trip exactly through any number of binary64 limbs.
        for v in [Fraction(1), Fraction(-1), Fraction(2), Fraction(1, 2),
                  Fraction(0x3CB0000000000000, 1 << 52),  # tiny (binary64 eps)
                  Fraction(10) ** 30,                     # ~2^99.7, dyadic
                  Fraction(1, 1 << 200)]:                 # ultra-tiny dyadic
            x_raw = encode(fmt, v)
            check(format_add(fmt, x_raw, 0) == x_raw,
                  f"{fname}: x+0!=x for dyadic v={v}")
            check(decode(fmt, x_raw) == v,
                  f"{fname}: dyadic round-trip v={v}")

        # Inf / NaN: specials live in the hi-limb (low bits) per HW convention.
        pos_inf_raw = _B64_INF
        neg_inf_raw = _B64_INF | _B64_SIGN
        qnan_raw = _B64_QNAN
        check(isinstance(decode(fmt, pos_inf_raw), Special) and
              decode(fmt, pos_inf_raw).kind == "inf",
              f"{fname}: decode +Inf")
        check(isinstance(decode(fmt, qnan_raw), Special) and
              decode(fmt, qnan_raw).kind == "nan",
              f"{fname}: decode NaN")
        check(format_add(fmt, pos_inf_raw, neg_inf_raw) == fmt.quiet_nan,
              f"{fname}: +Inf + -Inf = NaN")
        check(format_mul(fmt, pos_inf_raw, 0) == fmt.quiet_nan,
              f"{fname}: Inf * 0 = NaN")

    # double_double: known value 1.0 + eps where eps = 2^-53 (next binary64 below 1).
    # encode(1 + 2^-53) should produce hi = round(1+2^-53) = 1.0 (round-ties-even
    # picks the even mantissa), lo = 2^-53.
    dd = FORMATS["double_double"]
    target = Fraction(1) + Fraction(1, 1 << 53)
    raw = encode(dd, target)
    hi = raw & ((1 << 64) - 1)
    lo = (raw >> 64) & ((1 << 64) - 1)
    check(decode(dd, raw) == target, "double_double: 1+2^-53 round-trip exact")
    check(hi == _encode_binary64(Fraction(1)),
          "double_double: hi-limb of 1+2^-53 is binary64 1.0")
    check(lo == _encode_binary64(Fraction(1, 1 << 53)),
          "double_double: lo-limb captures the 2^-53 residual")

    # Non-dyadic precision monotonicity: 1/3 represented in 1, 2, 4 binary64 limbs
    # should be progressively closer to the exact value.
    third = Fraction(1, 3)
    dd_err = abs(decode(dd, encode(dd, third)) - third)
    qd_err = abs(decode(FORMATS["quad_double"], encode(FORMATS["quad_double"], third)) - third)
    one_limb_err = abs(_decode_binary64(_encode_binary64(third)) - third)
    check(qd_err < dd_err < one_limb_err,
          f"extended: 1/3 approximation improves 1→2→4 limbs "
          f"(errs={float(one_limb_err):.3e},{float(dd_err):.3e},{float(qd_err):.3e})")

    # quad_double: 1 + 2^-105 + 2^-158 + 2^-211 fits in 4 limbs (just barely).
    qd = FORMATS["quad_double"]
    big = (Fraction(1) + Fraction(1, 1 << 105) + Fraction(1, 1 << 158)
           + Fraction(1, 1 << 211))
    qraw = encode(qd, big)
    check(decode(qd, qraw) == big, "quad_double: 4-limb expansion exact")

    # pass 187: membership is not the same question as value.
    dd = FORMATS["double_double"]
    half = _encode_binary64(Fraction(1, 2))
    overlapping = half | (half << 64)
    check(decode(dd, overlapping) == 1,
          "187: 0.5+0.5 holds the value 1 exactly")
    check(is_canonical(dd, overlapping) is False,
          "187: ...and is still not a valid expansion")
    check(is_canonical(dd, encode(dd, Fraction(1, 3))) is True,
          "187: encode() emits renormalized expansions")
    check(is_canonical(dd, encode(dd, Fraction(1))) is True,
          "187: a zero tail limb is canonical")
    qd = FORMATS["quad_double"]
    check(is_canonical(qd, encode(qd, Fraction(10) ** 40 / 3)) is True,
          "187: quad_double encode() is renormalized too")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (extended: zero/unity/1+1/x+0/round-trip/Inf/NaN"
          " + pass-187 expansion canonicality)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
