#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
posit_ref.py — ЭТАЛОННЫЙ (golden) оракул для posit-семейства (Unum/posit).
  posit8  (n=8,  es=0)    useed = 2^(2^0) = 2
  posit16 (n=16, es=2)    useed = 2^(2^2) = 16   (стандартный posit16)
  posit32 (n=32, es=2)    useed = 16             (стандартный posit32)
  posit64 (n=64, es=3)    useed = 2^(2^3) = 256  (стандартный posit64)

Кодировка: sign | regime (variable-length run) | exponent (es) | fraction.
  regime = run of m одинаковых бит, terminated противоположным:
    run of 1s длины m -> k = m-1
    run of 0s длины m -> k = -m
  value = (-1)^S * useed^k * 2^e * (1 + frac)
  specials: raw==0 -> +0 ; raw==sign-bit-only (2^(n-1)) -> NaR

Round-ties-even, точная Fraction-арифметика. По образцу conformance/gf_ref.py.
Согласован с conformance/posit32_decode_conformance_ax7203.py (golden_posit32).

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class PositFormat:
    name: str
    n: int
    es: int

    @property
    def width(self): return self.n
    @property
    def mask(self): return (1 << self.n) - 1
    @property
    def useed(self): return 1 << (1 << self.es)        # 2^(2^es)
    @property
    def sign_shift(self): return self.n - 1
    @property
    def pos_zero(self): return 0
    @property
    def nar(self): return 1 << (self.n - 1)            # sign-bit-only = NaR


FORMATS = {
    "posit8":  PositFormat("posit8",  n=8,  es=0),
    "posit16": PositFormat("posit16", n=16, es=2),
    "posit32": PositFormat("posit32", n=32, es=2),
    "posit64": PositFormat("posit64", n=64, es=3),
}


class Special:
    def __init__(self, kind="nar", sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        return "NaR"


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


# -------------------- DECODE --------------------

def decode(fmt: PositFormat, raw: int):
    raw &= fmt.mask
    if raw == 0:
        return Fraction(0)
    if raw == fmt.nar:
        return Special("nar")

    sign = (raw >> (fmt.n - 1)) & 1
    # двух-дополнение всего слова для отрицательных -> magnitude field
    mag = raw if sign == 0 else ((1 << fmt.n) - raw)

    # regime: parse run starting at bit (n-2) downward
    pos = fmt.n - 2
    first = (mag >> pos) & 1 if pos >= 0 else 0
    run = 0
    while pos >= 0 and ((mag >> pos) & 1) == first:
        run += 1
        pos -= 1
    # pos now at terminator (or -1 if regime consumed all bits)
    if pos >= 0:
        pos -= 1  # skip terminator
    k = (run - 1) if first == 1 else (-run)

    # exponent: es bits after regime (fewer if not enough bits).
    # Bits are MSB-first; if regime/terminator consumed everything, e_val stays 0.
    e_val = 0
    e_bits_read = 0
    for _ in range(fmt.es):
        if pos < 0:
            break
        e_val = (e_val << 1) | ((mag >> pos) & 1)
        e_bits_read += 1
        pos -= 1
    # left-align if fewer than es bits were available (trailing zeros implicit)
    if e_bits_read < fmt.es:
        e_val <<= (fmt.es - e_bits_read)

    # fraction: remaining bits
    frac_bits = pos + 1
    frac_val = mag & ((1 << (pos + 1)) - 1) if pos >= 0 else 0

    useed = fmt.useed
    val = (Fraction(useed) ** k) * pow2(e_val) * (1 + (Fraction(frac_val, 1 << frac_bits) if frac_bits > 0 else 0))
    return -val if sign else val


# -------------------- ENCODE --------------------
# Posit magnitude field (unsigned m in [1, 2^(n-1)-1]) is MONOTONIC increasing in
# decoded value. So encode = binary-search the nearest representable m (RNE), which
# is provably correct and avoids error-prone regime-carry bookkeeping.

def _decode_mag(fmt: PositFormat, m: int) -> Fraction:
    """decode treating m as a positive (sign=0) magnitude field."""
    return decode(fmt, m)


def encode(fmt: PositFormat, value):
    if isinstance(value, Special):
        return fmt.nar

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v

    lo = 1
    hi = (1 << (fmt.n - 1)) - 1        # largest positive magnitude field

    # a below smallest representable -> round to 0 or smallest (RNE)
    smallest = _decode_mag(fmt, lo)
    largest = _decode_mag(fmt, hi)
    if a >= largest:
        m = hi
    elif a <= smallest:
        # Posit Standard 2022: a NONZERO value never rounds to zero. It saturates to
        # minpos, and symmetrically never rounds to NaR at the top. This branch applied
        # round-to-nearest-even between 0 and minpos, so anything below minpos/2 became
        # +0 -- and lost its sign on the way, since it returned pos_zero for negatives
        # too.
        #
        # Found in pass 225 against SoftPosit's pX2_div: posit8_div agreed on 135 of 251
        # pairs, and 0x01/0x61 came back as 0x00 here where the reference gives 0x01.
        # Rounding a nonzero quotient to zero is the one thing a posit is defined not to
        # do, which is why the disagreement was systematic rather than scattered.
        m = lo
    else:
        # binary search largest m with decode(m) <= a
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if _decode_mag(fmt, mid) <= a:
                lo = mid
            else:
                hi = mid - 1
        m = lo
        # candidate is m (<= a) and m+1 (> a); pick nearest, ties-to-even LSB
        dm = _decode_mag(fmt, m)
        dmp1 = _decode_mag(fmt, m + 1)
        err_lo = a - dm
        err_hi = dmp1 - a
        if err_hi < err_lo:
            m = m + 1
        elif err_hi == err_lo:
            # tie: round to even (magnitude-field LSB even)
            if (m + 1) % 2 == 0:
                m = m + 1

    raw = m if sign == 0 else ((1 << fmt.n) - m) & fmt.mask
    return raw & fmt.mask


# -------------------- ADD / MUL --------------------

def format_add(fmt: PositFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.nar
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    if a == 0 and b == 0:
        return fmt.pos_zero
    return encode(fmt, a + b)


def format_mul(fmt: PositFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.nar
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb
    if a == 0 or b == 0:
        return fmt.pos_zero
    prod = a * b
    raw = encode(fmt, prod)
    # sign already handled by value sign in encode; ensure consistency with rsign
    return raw


def _selftest():
    import random
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: +0")
        check(isinstance(decode(fmt, fmt.nar), Special), f"{fname}: NaR")
        one = encode(fmt, Fraction(1))
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")

        # exhaustive for posit8, sampled otherwise
        if fmt.n <= 16:
            codes = range(0, 1 << fmt.n)
        else:
            rng = random.Random(12345 + fmt.n)
            codes = [rng.randrange(1 << fmt.n) for _ in range(20000)]
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special):
                continue
            # x + 0 == x bit-exact
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")
            if v != 0:
                check(format_mul(fmt, raw, 0) == 0, f"{fname}: x*0!=0 0x{raw:x}")
            # value round-trip
            back = decode(fmt, encode(fmt, v))
            check(back == v, f"{fname}: round-trip 0x{raw:x} v={v} back={back}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (posit: zero/nar/unity/1+1/x+0/x*0/round-trip)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
