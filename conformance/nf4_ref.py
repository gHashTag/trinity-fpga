#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nf4_ref.py — REFERENCE (golden) oracle for NF4 (NormalFloat 4-bit, QLoRA / Dettmers 2023).

NF4 is a 16-entry table of N(0,1) quantiles — NOT an S:E:M format. Each 4-bit
value (0..15) indexes one of 16 fixed constants:

    index:  0      1       2       3       4       5       6       7    8       9      ...
    value: -1.0  -0.696  -0.525  -0.395  -0.284  -0.185  -0.091   0.0  +0.080  +0.161 ...

Asymmetric representation: 8 negative (including -1.0), 0, 7 positive
(including +1.0). There is NO sign bit — this is a LUT encoding.

Decoder: raw → table[raw] (exact Fraction of the fp32 constant).
Encoder: Fraction → nearest table entry (round-ties-even), saturating to [-1.0, +1.0].
Add/Mul: decode→exact op→encode. Matches the LUT in nf4_decode.v (Corona RTL).

Compatible with conformance/generate_vectors.py (FORMATS dict shape, decode/encode/
format_add/format_mul). Patterned on gf_ref.py.

Honesty: Trinity conformance team. Confirmed against
conformance/top_decode_conformance_ax7203.py:nf4_lut (bit-identical).
"""

import struct
from fractions import Fraction
from dataclasses import dataclass


# NF4 LUT — 16 values as fp32 bit-patterns (from nf4_decode.v).
# Duplicates conformance/top_decode_conformance_ax7203.py:golden_nf4.
_NF4_FP32_HEX = [
    0xBF800000, 0xBF3239B1, 0xBF066B30, 0xBECA32A0,
    0xBE91A24D, 0xBE3D353F, 0xBDBA7871, 0x00000000,
    0x3DA2FAFF, 0x3E24CAE3, 0x3E7C04DD, 0x3EAD033A,
    0x3EE1A4B8, 0x3F1007AB, 0x3F3913B3, 0x3F800000,
]


def _fp32_to_exact_fraction(fp32_bits: int) -> Fraction:
    """fp32 bit-pattern → exact Fraction (no loss of precision)."""
    f = struct.unpack('>f', struct.pack('>I', fp32_bits & 0xFFFFFFFF))[0]
    return Fraction(f)


# Pre-computed exact Fractions (one per LUT slot).
_VALUES = [_fp32_to_exact_fraction(h) for h in _NF4_FP32_HEX]


@dataclass(frozen=True)
class NF4Format:
    name: str = "nf4"

    @property
    def width(self): return 4
    @property
    def mask(self): return 0xF
    @property
    def pos_zero(self): return 0x7        # index 7 = +0.0
    @property
    def neg_zero(self): return 0x7        # NF4 has single 0.0 code (index 7)
    @property
    def quiet_nan(self): return 0x0       # no NaN; treat invalid as -1.0 (index 0)


FORMATS = {
    "nf4": NF4Format(),
}


class Special:
    """NF4 has no specials; placeholder for API symmetry with other oracles."""
    def __init__(self, kind="nan", sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        return "NaN" if self.kind == "nan" else ("-" if self.sign else "+") + "Inf"


def decode(fmt: NF4Format, raw: int) -> Fraction:
    """4-bit index → exact Fraction value of the LUT constant."""
    raw &= fmt.mask
    return _VALUES[raw]


def encode(fmt: NF4Format, value) -> int:
    """Exact Fraction → 4-bit index of the nearest LUT value (round-ties-even).

    Saturation: an input outside [-1.0, +1.0] is clipped to the end indices (0 or 15).
    Ties (exactly between two LUT constants) go to the even index.
    """
    if isinstance(value, Special):
        return fmt.quiet_nan
    v = Fraction(value)
    # Saturate to [-1, +1] (NF4 represents only this range).
    if v <= _VALUES[0]:
        return 0
    if v >= _VALUES[15]:
        return 15
    # Linear scan: find nearest (ties-even).
    best_i = 0
    best_d = abs(v - _VALUES[0])
    for i in range(1, 16):
        d = abs(v - _VALUES[i])
        if d < best_d or (d == best_d and i % 2 == 0):
            best_d = d
            best_i = i
    return best_i


def format_add(fmt: NF4Format, a_raw: int, b_raw: int) -> int:
    """Decode→exact add→encode (with saturation)."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a + b)


def format_mul(fmt: NF4Format, a_raw: int, b_raw: int) -> int:
    """Decode→exact mul→encode (with saturation; NF4(-1)*NF4(-1)=+1 → index 15)."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a * b)


def _selftest():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    fmt = FORMATS["nf4"]

    # LUT matches known NF4 quantile values (spot checks against Dettmers 2023).
    check(decode(fmt, 0x0) == Fraction(-1), "nf4: index 0 == -1.0")
    check(decode(fmt, 0x7) == Fraction(0), "nf4: index 7 == 0.0")
    check(decode(fmt, 0xF) == Fraction(1), "nf4: index 15 == +1.0")

    # Round-trip of every LUT value: encode(decode(raw)) == raw.
    for raw in range(16):
        v = decode(fmt, raw)
        check(encode(fmt, v) == raw, f"nf4: round-trip raw={raw:x} (got {encode(fmt, v):x})")

    # Zero identity: 0 + 0 = 0 (both are index 7).
    check(format_add(fmt, 0x7, 0x7) == 0x7, "nf4: 0+0 = 0 (index 7)")

    # x + 0 == x (round-trip identity): decode(x+0) == decode(x).
    for raw in range(16):
        v = decode(fmt, raw)
        r = format_add(fmt, raw, 0x7)
        check(decode(fmt, r) == v, f"nf4: x+0 value raw={raw:x}")

    # -1 * -1 = +1 (saturation): index 0 * index 0 → index 15.
    check(format_mul(fmt, 0x0, 0x0) == 0xF, "nf4: (-1)*(-1) = +1 (index 15)")
    # x * 0 == 0 (index 7) for any x.
    for raw in range(16):
        check(format_mul(fmt, raw, 0x7) == 0x7, f"nf4: x*0 = 0 raw={raw:x}")

    # Exhaustive ADD over 16x16 = 256 pairs: encode(decode(a)+decode(b)) == format_add(a,b).
    for a in range(16):
        for b in range(16):
            exp = encode(fmt, decode(fmt, a) + decode(fmt, b))
            check(format_add(fmt, a, b) == exp, f"nf4: add mismatch {a:x}+{b:x}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (nf4: LUT/round-trip/zero-identity/exhaustive 16x16 add)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
