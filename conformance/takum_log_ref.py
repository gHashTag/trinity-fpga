#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""takum_log_ref.py — an exact takum oracle in the log domain, after lns_ref.py.

Why this exists
---------------
`conformance/takum_ref.py` states in its own header that real takum is logarithmic,
`value = (-1)^S * exp(ell/2)`, so values are generally irrational and admit no exact
`fractions.Fraction`. Its answer was to implement a *linear* structural model instead.
Pass 132 measured what that costs: over takum8 and takum16, the linear model and the
logarithmic definition agree on **3 codes out of 65,536**, with worst-case
disagreements of 437 and 439 binades. They are different functions sharing a field
layout.

`conformance/lns_ref.py` met the identical problem — `value = (-1)^sign * 2^L`, also
irrational — and solved it honestly: it works in the log domain exactly, returns the
exact logarithm as a Fraction, and returns `Special('irrational')` rather than a
fabricated rational where the value cannot be represented. That pattern is the right
one and it already lives in this directory.

This module applies it to takum. Nothing here is novel; it is `lns_ref.py`'s method
with takum's field decode.

What is exact and what is not
-----------------------------
    ell = (1 - 2S) * (c + m)        exact: c is an integer, m is dyadic
    ln|value| = ell / 2             exact, a Fraction
    value     = (-1)^S * e^(ell/2)  irrational unless ell == 0

So `decode_ln` is exact for every finite code, and `decode` returns an exact value only
for `ell == 0`, where the value is exactly ±1. Everywhere else it returns
`Special('exp')` carrying the exact `ln|value|`, exactly as `lns_ref.decode` returns
`Special('irrational')` carrying the exact `log2|value|`.

The field decode is transcribed from `conformance/takum16_decode_conformance_ax7203.py`,
which describes itself as replicating the t27 verified second-witness, rather than from
the linear oracle.

    python3 conformance/takum_log_ref.py        # self-test
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

# From fpga/openxc7-synth/takum64_decode.v:22-27, index = (D << 3) | R.
CBIAS = (-255, -127, -63, -31, -15, -7, -3, -1,
         0, 1, 3, 7, 15, 31, 63, 127)

OVERHEAD = 5          # sign + direction + 3 regime bits
REGIME_BITS = 3


@dataclass(frozen=True)
class TakumLogFormat:
    name: str
    width: int

    @property
    def mask(self) -> int:
        return (1 << self.width) - 1

    @property
    def nar(self) -> int:
        return 1 << (self.width - 1)

    @property
    def sign_shift(self) -> int:
        return self.width - 1


FORMATS = {
    "takum8": TakumLogFormat("takum8", 8),
    "takum16": TakumLogFormat("takum16", 16),
    "takum32": TakumLogFormat("takum32", 32),
    "takum64": TakumLogFormat("takum64", 64),
}


class Special:
    """Mirrors lns_ref.Special: a value the format holds but a Fraction cannot."""

    __slots__ = ("kind", "sign", "ln")

    def __init__(self, kind: str, sign: int = 0, ln: Fraction | None = None):
        self.kind = kind
        self.sign = sign
        self.ln = ln

    def __repr__(self) -> str:
        if self.kind == "exp":
            s = "-" if self.sign else "+"
            return f"{s}e^({self.ln})"
        return self.kind

    def __eq__(self, other) -> bool:
        return (isinstance(other, Special) and other.kind == self.kind
                and other.sign == self.sign and other.ln == self.ln)


def sign_of(fmt: TakumLogFormat, raw: int) -> int:
    return (raw >> fmt.sign_shift) & 1


def decode_ln(fmt: TakumLogFormat, raw: int):
    """Exact natural logarithm of |value|, as a Fraction. Special for 0 and NaR."""
    raw &= fmt.mask
    if raw == 0:
        return Special("zero")
    if raw == fmt.nar:
        return Special("nar")

    n = fmt.width
    S = (raw >> (n - 1)) & 1
    D = (raw >> (n - 2)) & 1
    R = (raw >> (n - OVERHEAD)) & ((1 << REGIME_BITS) - 1)

    c_bias = CBIAS[(D << REGIME_BITS) | R]
    r_eff = R if D else ((1 << REGIME_BITS) - 1 - R)
    p = n - r_eff - OVERHEAD
    if p < 0:
        p = 0

    lower = raw & ((1 << (r_eff + p)) - 1)
    m_uint = (lower & ((1 << p) - 1)) if p > 0 else 0
    c_uint = ((lower >> p) & ((1 << r_eff) - 1)) if r_eff > 0 else 0

    c = c_bias + c_uint
    m = Fraction(m_uint, 1 << p) if p > 0 else Fraction(0)
    ell = (1 - 2 * S) * (Fraction(c) + m)
    return ell / 2                                     # ln|value|


def decode(fmt: TakumLogFormat, raw: int):
    """Exact value where one exists, else Special carrying the exact logarithm.

    e^(ell/2) is rational only at ell == 0, where the value is exactly +-1. This is the
    same discipline as lns_ref.decode, which returns an exact Fraction only when the
    stored log is an integer.
    """
    raw &= fmt.mask
    ln = decode_ln(fmt, raw)
    if isinstance(ln, Special):
        return Fraction(0) if ln.kind == "zero" else ln
    sign = sign_of(fmt, raw)
    if ln == 0:
        return Fraction(-1) if sign else Fraction(1)
    return Special("exp", sign, ln)


def _selftest() -> int:
    """Landmarks the conformance script names, plus the discipline itself."""
    bad = 0
    f16 = FORMATS["takum16"]
    for raw, want in ((0x4000, Fraction(1)), (0xC000, Fraction(-1))):
        got = decode(f16, raw)
        ok = got == want
        bad += not ok
        print(f"  takum16 0x{raw:04X} -> {got!r:<12} expected {want}  "
              f"{'ok' if ok else 'MISMATCH'}")

    f8 = FORMATS["takum8"]
    exact = irrational = 0
    for c in range(256):
        v = decode(f8, c)
        if isinstance(v, Special) and v.kind == "exp":
            irrational += 1
        elif isinstance(v, Fraction):
            exact += 1
    print(f"  takum8: {exact} codes with an exact value, {irrational} carrying an "
          f"exact logarithm instead")
    print(f"  (lns8 for comparison: 31 exact, the rest Special -- the same shape)")

    print("\nself-test:", "PASS" if bad == 0 else f"FAIL ({bad})")
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if _selftest() else 0)
