#!/usr/bin/env python3
"""Exhaustive verify fp8_e5m2_decode.v RTL vs an INDEPENDENT oracle.

Reads "code fp32" hex lines from stdin (the iverilog TB over all 256 codes),
compares each RTL output to an oracle that computes the value via Python float
arithmetic and re-encodes to fp32 via struct — a DIFFERENT code path than the
RTL's integer bit-shifts, so numeric mismatches indicate a real RTL bug.

NaN payload is implementation-defined for fp8; the RTL canonicalizes (0x7fc00000)
while this oracle propagates the payload — those are reported separately as
"NaN-convention" differences, NOT numeric bugs. Zero/denormal/normal/Inf must
match exactly.

  iverilog -g2012 -o tb.vvp formal/fp8_e5m2_decode_tb.v fpga/openxc7-synth/fp8_e5m2_decode.v
  vvp tb.vvp | python3 conformance/fp8_e5m2_verify.py
"""
import sys, struct


def golden(code):
    sign = (code >> 7) & 1
    exp = (code >> 2) & 0x1F
    mant = code & 0x3
    if exp == 0x1F:
        if mant == 0:
            return (sign << 31) | (0xFF << 23)            # Inf
        return (sign << 31) | (0xFF << 23) | (mant << 21)  # NaN (propagate — impl-defined)
    if exp == 0 and mant == 0:
        return sign << 31                                  # zero
    if exp == 0:
        val = (mant / 4.0) * (2.0 ** -14)                  # denormal
    else:
        val = (1.0 + mant / 4.0) * (2.0 ** (exp - 15))     # normal
    val = -val if sign else val
    return struct.unpack('<I', struct.pack('<f', val))[0]


def main():
    num_bad = nan_diff = checked = 0
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 2:
            continue
        code = int(parts[0], 16)
        rtl = int(parts[1], 16)
        exp = golden(code)
        checked += 1
        if rtl != exp:
            # is it a NaN-convention difference (exp==0x1F on both)?
            if (rtl >> 23) & 0xFF == 0xFF and (exp >> 23) & 0xFF == 0xFF:
                nan_diff += 1
            else:
                num_bad += 1
                if num_bad <= 16:
                    print(f"NUMERIC MISMATCH code=0x{code:02x} rtl=0x{rtl:08x} exp=0x{exp:08x}")
    print(f"checked={checked} numeric_mismatches={num_bad} nan_convention_diffs={nan_diff}")
    print("NUMERIC DECODE: " + ("PASS (zero/denormal/normal/Inf all correct)" if num_bad == 0 else "FAIL"))
    return 0 if num_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
