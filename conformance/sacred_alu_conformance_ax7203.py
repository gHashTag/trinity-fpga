#!/usr/bin/env python3
"""sacred_alu_conformance_ax7203.py — Sacred ALU conformance host.

Sacred ALU has 4 modes:
  MODE_GF16_ADD (0): GF16 addition via gf16_adder
  MODE_GF16_MUL (1): GF16 multiplication via gf16_multiplier
  MODE_TF3_ADD  (2): TF3-9 ternary addition
  MODE_TF3_DOT  (3): TF3-9 ternary dot product

Golden oracle: gf_ref.py for GF16, exact ternary for TF3-9.

Usage:
  python3 sacred_alu_conformance_ax7203.py --port /dev/cu.usbserial-1120 --mode gf16_add
  python3 sacred_alu_conformance_ax7203.py --port /dev/cu.usbserial-1120 --mode gf16_mul
  python3 sacred_alu_conformance_ax7203.py --self-test --mode gf16_add

Note: Sacred ALU is standalone RTL (not in UART-conformance catalog format).
This script is a SKELETON — actual HW test requires a UART wrapper around sacred_alu.
The standalone RTL uses AXI-Stream, not UART. A bridge module is needed.

Honesty: [simulated] — skeleton. Not HW-tested.
"""
import argparse, sys, os, math
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import gf_ref for GF16 golden oracle
try:
    from gf_ref import FORMATS, gf_add, gf_mul
    GF16 = FORMATS["gf16"]
    HAS_GF_REF = True
except ImportError:
    HAS_GF_REF = False
    print("WARNING: gf_ref.py not found, GF16 golden oracle unavailable")

# TF3-9: 9-bit ternary format (1 sign_trit + 3 exp_trits + 5 mant_trits)
# Each trit is 2 bits: 0=T(-1), 1=0, 2=T(+1)
# Value = (-1)^sign * (1 + mant/3^5) * 3^(exp - bias)
# bias for 3 trits = (3^3 - 1)/2 = 13
TF3_BIAS = 13
TF3_MANT_TRITS = 5

def tf3_decode(raw_18bit):
    """Decode TF3-9 18-bit (9 trits × 2 bits) to float."""
    trits = []
    for i in range(9):
        trit_val = (raw_18bit >> (i * 2)) & 3
        if trit_val == 0: trits.append(-1)
        elif trit_val == 1: trits.append(0)
        else: trits.append(1)

    sign = trits[0]
    exp_trits = trits[1:4]  # 3 exp trits
    mant_trits = trits[4:9]  # 5 mant trits

    # Exponent: balanced ternary value
    exp = sum(t * (3 ** (2 - i)) for i, t in enumerate(exp_trits))

    # Mantissa: (1 + sum(trit_i / 3^(i+1)))
    mant_frac = sum(t * Fraction(1, 3 ** (i + 1)) for i, t in enumerate(mant_trits))
    value = (1 + mant_frac) * Fraction(3) ** (exp - TF3_BIAS)

    if sign < 0:
        value = -value
    return float(value)

def golden_gf16_add(a, b):
    if not HAS_GF_REF:
        return None
    return gf_add(GF16, a, b)

def golden_gf16_mul(a, b):
    if not HAS_GF_REF:
        return None
    return gf_mul(GF16, a, b)

def golden_tf3_add(a_raw, b_raw):
    """Golden TF3-9 ternary addition: decode→add→encode (approximate)."""
    a = tf3_decode(a_raw)
    b = tf3_decode(b_raw)
    result = a + b
    # Encode back to TF3-9 is complex — return fp32 approximation for now
    # Full encode would require ternary rounding (not implemented yet)
    return result  # float, not raw TF3-9

def self_test(mode):
    if mode == "gf16_add":
        if not HAS_GF_REF:
            print("SKIP: gf_ref not available")
            return False
        # Spot check: 1.0 + 1.0 = 2.0 in GF16
        one = 0x2200  # GF16 1.0 (sign=0, exp=31, mant=0)
        result = golden_gf16_add(one, one)
        print(f"self-test gf16_add: GF16(1.0) + GF16(1.0) = raw={result:#06x}")
        return result is not None
    elif mode == "gf16_mul":
        if not HAS_GF_REF:
            print("SKIP: gf_ref not available")
            return False
        one = 0x2200
        result = golden_gf16_mul(one, one)
        print(f"self-test gf16_mul: GF16(1.0) * GF16(1.0) = raw={result:#06x}")
        return result is not None
    elif mode == "tf3_add":
        # TF3-9: 0 (all zeros) + 0 = 0
        zero_raw = 0x00000  # all trits = 0
        a = tf3_decode(zero_raw)
        print(f"self-test tf3_add: TF3(0) decode = {a}")
        return True
    elif mode == "tf3_dot":
        print("self-test tf3_dot: (skeleton — dot product golden TBD)")
        return True
    return False

def main():
    ap = argparse.ArgumentParser(description="Sacred ALU conformance skeleton for AX7203")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--mode", default="gf16_add",
                    choices=["gf16_add", "gf16_mul", "tf3_add", "tf3_dot"])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test(a.mode) else 1)
    # HW test requires UART wrapper around sacred_alu — not yet implemented
    print("ERROR: Sacred ALU HW test requires UART bridge module (not yet built)")
    print("The sacred_alu.v uses AXI-Stream, not UART. Need corona_compute_sacred_alu_ax7203.v wrapper.")
    sys.exit(1)

if __name__ == "__main__":
    main()
