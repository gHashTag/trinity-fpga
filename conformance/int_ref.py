#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
int_ref.py — REFERENCE (golden) oracle for integer formats.
  int4, int8, int16, int32, int64, int128    — two's complement signed
  uint4, uint8, uint16, uint32               — unsigned

Integers are exactly representable as Fraction. Arithmetic is modular (wraparound)
by default (standard fixed-width int behaviour); saturating variants exist too.
Patterned on gf_ref.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class IntFormat:
    name: str
    bits: int
    signed: bool
    bcd: bool = False          # Binary-coded decimal: 4 bits per decimal digit

    @property
    def mask(self): return (1 << self.bits) - 1
    @property
    def width(self): return self.bits
    @property
    def sign_shift(self): return self.bits - 1
    @property
    def n_digits(self):
        return self.bits // 4
    @property
    def max_val(self):
        if self.bcd:
            return 10 ** self.n_digits - 1
        return (1 << (self.bits - 1)) - 1 if self.signed else self.mask
    @property
    def min_val(self):
        if self.bcd:
            return 0     # BCD represents non-negative decimals (unsigned)
        return -(1 << (self.bits - 1)) if self.signed else 0
    @property
    def pos_zero(self): return 0
    @property
    def quiet_nan(self): return 0   # ints have no NaN


FORMATS = {
    "int4":   IntFormat("int4",   bits=4,   signed=True),
    "int8":   IntFormat("int8",   bits=8,   signed=True),
    "int16":  IntFormat("int16",  bits=16,  signed=True),
    "int32":  IntFormat("int32",  bits=32,  signed=True),
    "int64":  IntFormat("int64",  bits=64,  signed=True),
    "int128": IntFormat("int128", bits=128, signed=True),
    "uint4":  IntFormat("uint4",  bits=4,   signed=False),
    "uint8":  IntFormat("uint8",  bits=8,   signed=False),
    "uint16": IntFormat("uint16", bits=16,  signed=False),
    "uint32": IntFormat("uint32", bits=32,  signed=False),
    # Binary-coded decimal — 2-digit packed BCD (8 bits, value 0..99).
    # Matches conformance/bcd_decode_conformance_ax7203.py (golden_bcd) and
    # fpga/openxc7-synth/bcd_decode.v (Corona RTL).
    "bcd":    IntFormat("bcd",    bits=8,   signed=False, bcd=True),
}


def pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def decode(fmt: IntFormat, raw: int) -> Fraction:
    """raw -> exact integer value as Fraction.

    For BCD: each nibble is one decimal digit (0..9); value = sum digit_i * 10^i.
    Invalid nibbles (>9) decode as if the nibble were its raw value (best-effort
    wraparound); callers wanting strict BCD should validate separately.
    """
    raw &= fmt.mask
    if fmt.bcd:
        val = 0
        for i in range(fmt.n_digits):
            nib = (raw >> (4 * i)) & 0xF
            val += nib * (10 ** i)
        return Fraction(val)
    if fmt.signed and (raw >> fmt.sign_shift):
        return Fraction(raw - (1 << fmt.bits))
    return Fraction(raw)


def encode(fmt: IntFormat, value) -> int:
    """Exact integer -> raw (two's complement for signed; packed BCD for bcd).

    Out-of-range wraps (modular): for BCD, value mod 10^n_digits, each decimal
    digit packed into 4 bits.
    """
    v = Fraction(value)
    assert v.denominator == 1, "int encode requires integer value"
    n = v.numerator
    if fmt.bcd:
        mod = 10 ** fmt.n_digits
        n %= mod
        raw = 0
        for i in range(fmt.n_digits):
            digit = (n // (10 ** i)) % 10
            raw |= digit << (4 * i)
        return raw & fmt.mask
    return n & fmt.mask


def encode_saturating(fmt: IntFormat, value) -> int:
    """Saturating variant: clamp to [min_val, max_val]."""
    v = Fraction(value)
    assert v.denominator == 1
    n = v.numerator
    if n < fmt.min_val:
        n = fmt.min_val
    elif n > fmt.max_val:
        n = fmt.max_val
    return n & fmt.mask


def format_add(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Modular (wraparound) addition."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a + b)


def format_mul(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Modular (wraparound) multiplication."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a * b)


def format_add_sat(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Saturating addition."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode_saturating(fmt, a + b)


def format_mul_sat(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Saturating multiplication."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode_saturating(fmt, a * b)


def _selftest():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: 0")
        check(encode(fmt, 0) == 0, f"{fname}: encode 0")
        one = encode(fmt, 1)
        check(decode(fmt, one) == 1, f"{fname}: 1")
        # 1 + 1 = 2
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        # 0 + 0 = 0
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")
        # x + 0 == x (bit-exact for all x): exhaustive for tiny, sampled otherwise.
        # BCD skips this — invalid nibbles (>9) don't round-trip bit-exactly
        # (BCD-specific x+0 covered by dedicated checks below).
        if fmt.bcd:
            continue
        if fmt.bits <= 16:
            check_range = range(0, 1 << fmt.bits)
        else:
            rng = __import__("random").Random(0x1337 + fmt.bits)
            check_range = [rng.randrange(1 << fmt.bits) for _ in range(8000)]
        for raw in check_range:
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")
        # identity: x * 1 == x
        check(format_mul(fmt, one, one) == one, f"{fname}: 1*1=1")
        # wraparound at boundary
        check(decode(fmt, encode(fmt, fmt.max_val)) == fmt.max_val, f"{fname}: max round-trip")
        if fmt.signed:
            check(decode(fmt, encode(fmt, fmt.min_val)) == fmt.min_val, f"{fname}: min round-trip")
            # max + 1 wraps to min
            mx = encode(fmt, fmt.max_val)
            check(decode(fmt, format_add(fmt, mx, one)) == fmt.min_val,
                  f"{fname}: max+1 wraps to min")
        else:
            # unsigned: max + 1 wraps to 0
            mx = encode(fmt, fmt.max_val)
            check(format_add(fmt, mx, one) == 0, f"{fname}: max+1 wraps to 0")

    # specific signed/int8 checks
    i8 = FORMATS["int8"]
    check(decode(i8, 0xFF) == -1, "int8: 0xFF -> -1")
    check(decode(i8, 0x80) == -128, "int8: 0x80 -> -128")
    check(decode(i8, 0x7F) == 127, "int8: 0x7F -> 127")
    check(decode(i8, format_add(i8, encode(i8, -1), encode(i8, 1))) == 0, "int8: -1+1=0")
    u4 = FORMATS["uint4"]
    check(decode(u4, 0xF) == 15, "uint4: 0xF -> 15")

    # BCD: matches conformance/bcd_decode_conformance_ax7203.py (golden_bcd).
    bcd = FORMATS["bcd"]
    check(decode(bcd, 0x00) == 0, "bcd: 0x00 -> 0")
    check(decode(bcd, 0x01) == 1, "bcd: 0x01 -> 1")
    check(decode(bcd, 0x09) == 9, "bcd: 0x09 -> 9")
    check(decode(bcd, 0x10) == 10, "bcd: 0x10 -> 10")
    check(decode(bcd, 0x99) == 99, "bcd: 0x99 -> 99")
    check(decode(bcd, 0x45) == 45, "bcd: 0x45 -> 45")
    check(encode(bcd, 0) == 0x00, "bcd: encode 0")
    check(encode(bcd, 9) == 0x09, "bcd: encode 9")
    check(encode(bcd, 10) == 0x10, "bcd: encode 10")
    check(encode(bcd, 99) == 0x99, "bcd: encode 99")
    # wraparound: 100 mod 100 = 0
    check(encode(bcd, 100) == 0x00, "bcd: encode 100 wraps to 0")
    # 1 + 1 = 2
    check(decode(bcd, format_add(bcd, encode(bcd, 1), encode(bcd, 1))) == 2,
          "bcd: 1+1=2")
    # 99 + 1 wraps to 0 (mod 100)
    check(decode(bcd, format_add(bcd, encode(bcd, 99), encode(bcd, 1))) == 0,
          "bcd: 99+1 wraps to 0")
    # 50 + 50 = 100 -> wraps to 0
    check(decode(bcd, format_add(bcd, encode(bcd, 50), encode(bcd, 50))) == 0,
          "bcd: 50+50 wraps to 0")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (int: zero/unity/1+1/x+0/x*1/wraparound/boundaries)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
