#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gfternary_ref.py — REFERENCE (golden) oracle for GFTERNARY (2-bit ternary).

GFTERNARY = a 2-bit format with three values {-φ, 0, +φ} where φ = (1+√5)/2.
Encoding (matches corona_compute_gfternary_*_ax7203.v):

    00 = 0
    01 = +φ
    10 = -φ
    11 = +φ (reserved → collapses to +φ; matches RTL behavior)

Arithmetic: decode→exact op (in the ring Q[φ])→quantize to {0, +φ, -φ} by the
nearest rule (with sign saturation).

Since φ is irrational, decode returns a pair (a, b) representing a + b·φ
with a, b ∈ ℤ. The result of the operation is then quantized:

    result > 0  → +φ (code 1)
    result < 0  → -φ (code 2)
    result == 0 → 0  (code 0)

These thresholds match the RTL: any positive → +φ, any negative → -φ.
This is a natural "sign saturation" — decode(exact_sum)→sign(exact_sum).

The exact comparison of a + b·φ with zero is done in ℤ[√5]:
    a + b·φ > 0  <=>  2a + b + b·√5 > 0
    if b > 0:  b·√5 > -(2a+b)  — either trivially (if 2a+b >= 0), or
               5b² > (2a+b)²  (after squaring both positive sides)
    if b < 0:  the same with the opposite sign.
    if b == 0:  sign(a), obviously.

Consistent with conformance/gfternary_compute_conformance_ax7203.py (self-test
of add/mul). Patterned on gf_ref.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass
import math


# φ as a high-precision float (used only as a fallback in comparisons).
_PHI_FLOAT = (1 + math.sqrt(5)) / 2


@dataclass(frozen=True)
class GFTernaryFormat:
    name: str = "gfternary"

    @property
    def width(self): return 2
    @property
    def mask(self): return 0x3
    @property
    def pos_zero(self): return 0x0
    @property
    def neg_zero(self): return 0x0           # ternary has single zero code
    @property
    def quiet_nan(self): return 0x3          # reserved code 3 (treated as +φ)
    @property
    def has_inf(self): return False


FORMATS = {
    "gfternary": GFTernaryFormat(),
}


class Special:
    """GFTERNARY has no Inf/NaN in the strict sense; placeholder for API symmetry."""
    def __init__(self, kind="nan", sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        return "NaN" if self.kind == "nan" else ("-" if self.sign else "+") + "Inf"


@dataclass(frozen=True)
class PhiVal:
    """Element of Q[φ]: represents a + b·φ exactly (a, b rational).

    For GFTERNARY arithmetic only small integer combinations arise:
    decode results in a=0, b∈{-1,0,1}; sum/product stays in ℤ[φ] (b integer).
    """
    a: Fraction
    b: Fraction

    def __add__(self, other):
        return PhiVal(self.a + other.a, self.b + other.b)

    def __mul__(self, other):
        # (a + b·φ)(c + d·φ) = ac + bd·φ² + (ad + bc)·φ
        # φ² = φ + 1, so bd·φ² = bd·φ + bd
        return PhiVal(self.a * other.a + self.b * other.b,
                      self.b * other.a + self.a * other.b + self.b * other.b)

    def __neg__(self):
        return PhiVal(-self.a, -self.b)

    def is_zero(self):
        return self.a == 0 and self.b == 0

    def sign(self) -> int:
        """Sign of (a + b·φ). Returns -1, 0, +1.

        Exact via ℤ[√5] comparison: a + b·φ = (2a + b + b·√5)/2.
        """
        if self.a == 0 and self.b == 0:
            return 0
        # Reduce to integer coefficients for the sqrt(5) comparison.
        # self = A/Ad + (B/Bd)·φ ; scale to common denominator D.
        D = self.a.denominator * self.b.denominator
        if D == 1:
            ra, rb = int(self.a), int(self.b)
        else:
            ra = int(self.a * D)
            rb = int(self.b * D)
        # value = (2·ra + rb + rb·√5) / (2·D); D > 0 so sign = sign(2·ra + rb + rb·√5).
        s = 2 * ra + rb
        if rb == 0:
            return (s > 0) - (s < 0)
        if rb > 0:
            # need s + rb·√5 > 0  ⟺  rb·√5 > -s
            if s >= 0:
                return +1                       # both terms non-negative, √5>0
            # s < 0: compare (-s/rb) vs √5 → 5·rb² vs s²
            return +1 if 5 * rb * rb > s * s else (-1 if 5 * rb * rb < s * s else 0)
        else:  # rb < 0
            # need s + rb·√5 > 0  ⟺  |rb|·√5 < s
            if s <= 0:
                return -1
            # s > 0: compare s/|rb| vs √5 → s² vs 5·rb²
            return +1 if s * s > 5 * rb * rb else (-1 if s * s < 5 * rb * rb else 0)


# Decode table: 2-bit code → PhiVal.
_DECODE = {
    0: PhiVal(Fraction(0), Fraction(0)),     # 0
    1: PhiVal(Fraction(0), Fraction(1)),     # +φ
    2: PhiVal(Fraction(0), Fraction(-1)),    # -φ
    3: PhiVal(Fraction(0), Fraction(1)),     # reserved → +φ (matches RTL)
}


def decode(fmt: GFTernaryFormat, raw: int) -> PhiVal:
    """2-bit code → exact PhiVal (element of Q[φ])."""
    return _DECODE[raw & fmt.mask]


def encode(fmt: GFTernaryFormat, value) -> int:
    """Quantize a PhiVal (or Fraction) to the nearest of {0, +φ, -φ} by sign.

    Rule (matches RTL gfternary_compute_*.v quantizer):
        result > 0  → +φ (code 1)
        result < 0  → -φ (code 2)
        result == 0 → 0  (code 0)
    """
    if isinstance(value, Special):
        return fmt.quiet_nan
    if isinstance(value, PhiVal):
        s = value.sign()
    else:
        v = Fraction(value)
        s = (v > 0) - (v < 0)
    if s > 0:
        return 0x1
    if s < 0:
        return 0x2
    return 0x0


def format_add(fmt: GFTernaryFormat, a_raw: int, b_raw: int) -> int:
    """Decode→exact add in Q[φ]→quantize to {0, ±φ} by sign."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a + b)


def format_mul(fmt: GFTernaryFormat, a_raw: int, b_raw: int) -> int:
    """Decode→exact mul in Q[φ]→quantize to {0, ±φ} by sign.

    Note φ·φ = φ + 1 > 0 → quantizes to +φ (matches RTL self-test).
    """
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a * b)


def _selftest():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    fmt = FORMATS["gfternary"]

    # Decode table.
    check(decode(fmt, 0).is_zero(), "gfternary: code 0 -> 0")
    check(decode(fmt, 1).sign() == +1, "gfternary: code 1 -> +φ")
    check(decode(fmt, 2).sign() == -1, "gfternary: code 2 -> -φ")
    check(decode(fmt, 3).sign() == +1, "gfternary: code 3 -> +φ (reserved)")

    # The four assertions above check sign and zero-ness and never the VALUE, so a
    # decoder returning the right sign with the wrong magnitude passed. Pass 219's
    # mutation gate doubled every decoded value and this self-test did not notice.
    # PhiVal is a + b*phi with exact Fractions, so the value is checkable outright.
    for code, want_a, want_b in ((0, 0, 0), (1, 0, 1), (2, 0, -1), (3, 0, 1)):
        d = decode(fmt, code)
        check(d.a == Fraction(want_a) and d.b == Fraction(want_b),
              f"gfternary: code {code} is {want_a} + {want_b}*phi, got "
              f"{d.a} + {d.b}*phi")

    # Zero identity.
    check(format_add(fmt, 0, 0) == 0, "gfternary: 0+0 = 0")
    check(format_mul(fmt, 0, 0) == 0, "gfternary: 0*0 = 0")

    # x + 0 = x (bit-exact for canonical codes 0,1,2; code 3 is a non-canonical
    # alias for +φ and round-trips to code 1 — value-based check below).
    for raw in (0, 1, 2):
        check(format_add(fmt, raw, 0) == raw, f"gfternary: x+0!=x raw={raw}")
    check(decode(fmt, format_add(fmt, 3, 0)).sign() == +1,
          "gfternary: code-3 + 0 value == +φ")

    # Spot checks against the RTL self-test in
    # conformance/gfternary_compute_conformance_ax7203.py.
    check(format_add(fmt, 1, 1) == 1, "gfternary: φ+φ = +φ")
    check(format_add(fmt, 1, 2) == 0, "gfternary: φ+(-φ) = 0")
    check(format_add(fmt, 2, 2) == 2, "gfternary: -φ+(-φ) = -φ")
    check(format_mul(fmt, 1, 1) == 1, "gfternary: φ*φ = +φ (φ²=φ+1 > 0)")
    check(format_mul(fmt, 1, 2) == 2, "gfternary: φ*(-φ) = -φ")
    check(format_mul(fmt, 0, 1) == 0, "gfternary: 0*φ = 0")
    check(format_mul(fmt, 2, 2) == 1, "gfternary: -φ*-φ = +φ (φ²>0)")

    # Exhaustive 4x4 ADD and MUL: result must be a valid code (0/1/2).
    # (Code 3 never appears as an output; only as an input collapsing to +φ.)
    for op_name, fn in (("add", format_add), ("mul", format_mul)):
        for a in range(4):
            for b in range(4):
                r = fn(fmt, a, b)
                check(r in (0, 1, 2), f"gfternary: {op_name}({a},{b})={r} invalid code")

    # PhiVal.sign() exactness: known exact cases.
    check(PhiVal(Fraction(1), Fraction(-1)).sign() == -1,
          "gfternary: 1 - φ < 0 (φ>1)")
    check(PhiVal(Fraction(2), Fraction(-1)).sign() == +1,
          "gfternary: 2 - φ > 0 (φ<2)")
    check(PhiVal(Fraction(1), Fraction(1)).sign() == +1,
          "gfternary: 1 + φ > 0")
    # 2φ - φ² = 2φ - (φ+1) = φ - 1 > 0 (since φ > 1)
    check(PhiVal(Fraction(-1), Fraction(1)).sign() == +1,
          "gfternary: φ - 1 > 0")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (gfternary: decode/add/mul/PhiVal.sign exactness)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
