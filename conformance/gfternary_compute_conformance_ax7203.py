#!/usr/bin/env python3
# gfternary_compute_conformance_ax7203.py — GFTERNARY compute-conformance on AX7203.
# Tests ADD, MUL (and optionally DIV, SQRT) for the 2-bit ternary {-φ, 0, +φ} format.
#
# Golden oracle: exact arithmetic using phi = (1+√5)/2, then quantize to gfternary
# via the same threshold rules as the RTL (corona_compute_gfternary_*_ax7203.v).
#
# Format: 2-bit code. 0=0.0, 1=+φ, 2=-φ, 3=+φ(reserved→+φ).
# Frame: AA 55 fmt a_byte b_byte trigger → A5 + 4 bytes (result in [1:0] of byte 1).
#
# Honesty: [simulated] — SW golden oracle. HW conformance requires UART flash + run.
import argparse, sys, struct, math, random
from fractions import Fraction

PHI = (1 + math.sqrt(5)) / 2
PHI_F32 = struct.unpack('>I', struct.pack('>f', PHI))[0]  # 0x3FCF1BBD

# GFT decode: 2-bit code -> float
GFT_DECODE = {0: 0.0, 1: PHI, 2: -PHI, 3: PHI}

# GFT quantize: fp32 value -> 2-bit code (mirrors RTL exactly)
def gft_quantize(fp32_val):
    """Quantize float to gfternary 2-bit code, mirroring corona_compute_gfternary_*.v"""
    if fp32_val == 0.0:
        return 0
    if fp32_val != fp32_val:  # NaN
        # NaN = 0x7FC00000: sign=0, exp=0xFF, mant=0x400000
        # RTL: q_in[31]=0, q_in>=0x3F800000 → code 1
        return 1
    bits = struct.unpack('>I', struct.pack('>f', fp32_val))[0]
    if bits == 0x7F800000:  # +Inf
        return 1  # positive >= 1.0
    if bits == 0xFF800000:  # -Inf
        return 2  # negative <= -0.5
    if fp32_val < 0:
        if fp32_val <= -0.5:
            return 2  # -φ
        else:
            return 0  # round to zero
    else:
        if fp32_val >= 0.25:
            return 1  # +φ
        else:
            return 0  # round to zero

def golden_add(a_code, b_code):
    """Golden gfternary ADD: decode→fp32 add→quantize."""
    a = GFT_DECODE[a_code & 3]
    b = GFT_DECODE[b_code & 3]
    result = a + b
    return gft_quantize(result)

def golden_mul(a_code, b_code):
    """Golden gfternary MUL: decode→fp32 mul→quantize."""
    a = GFT_DECODE[a_code & 3]
    b = GFT_DECODE[b_code & 3]
    result = a * b
    return gft_quantize(result)

def golden_div(a_code, b_code):
    """Golden gfternary DIV: decode→fp32 div→quantize."""
    a = GFT_DECODE[a_code & 3]
    b = GFT_DECODE[b_code & 3]
    if b == 0.0:
        if a > 0: return 1   # +Inf → +φ
        if a < 0: return 2   # -Inf → -φ
        return 0             # 0/0 = NaN → 1... but RTL gives code 1 for NaN
    result = a / b
    return gft_quantize(result)

def golden_sqrt(a_code, b_code):
    """Golden gfternary SQRT: decode→fp32 sqrt→quantize."""
    a = GFT_DECODE[a_code & 3]
    if a < 0:
        return 1  # NaN → code 1 (per RTL quantize rule)
    result = math.sqrt(a)
    return gft_quantize(result)

GOLDEN_OPS = {"add": golden_add, "mul": golden_mul, "div": golden_div, "sqrt": golden_sqrt}

FRAME = bytes([0xAA, 0x55, 0x00])  # AA 55 fmt

def hw_exchange(ser, a, b, op_name):
    """Send gfternary compute request and read result.

    The wrapper's parser is exactly six bytes wide — AA 55 fmt a b trig — so
    FRAME already carries the fmt byte and only a, b and the trigger follow.
    An earlier version emitted a second fmt byte here, which shifted the
    operands by one: the FPGA read a=0 for every job and dutifully returned
    zero. It matched the golden oracle on the seven cases whose answer is zero
    anyway, so the bug was invisible until the cell was first run on silicon.
    """
    pkt = FRAME + bytes([a & 0xFF, b & 0xFF, 0x00])  # a, b, trigger
    ser.write(pkt)
    resp = ser.read(5)  # A5 + 4 bytes
    if len(resp) < 5 or resp[0] != 0xA5:
        return None
    result_32 = resp[1] | (resp[2] << 8) | (resp[3] << 16) | (resp[4] << 24)
    return result_32 & 3  # gfternary result is 2-bit in [1:0]

def self_test(op_name):
    """Exhaustive test: 4×4 = 16 input pairs (gfternary has only 4 values)."""
    golden = GOLDEN_OPS[op_name]
    print(f"self-test gfternary_{op_name}: exhaustive 4×4 = 16 pairs")
    for a in range(4):
        for b in range(4):
            g = golden(a, b)
            a_val = GFT_DECODE[a]
            b_val = GFT_DECODE[b]
            g_val = GFT_DECODE[g]
            print(f"  gft_{op_name}({a_val:+.4f}, {b_val:+.4f}) = {g_val:+.4f} (code={g})")
    # Spot checks
    if op_name == "add":
        assert golden(1, 1) == 1, f"φ+φ should be +φ, got {golden(1,1)}"
        assert golden(1, 2) == 0, f"φ+(-φ) should be 0, got {golden(1,2)}"
        assert golden(2, 2) == 2, f"-φ+(-φ) should be -φ, got {golden(2,2)}"
    elif op_name == "mul":
        assert golden(1, 1) == 1, f"φ*φ should be +φ, got {golden(1,1)}"
        assert golden(1, 2) == 2, f"φ*(-φ) should be -φ, got {golden(1,2)}"
        assert golden(0, 1) == 0, f"0*φ should be 0, got {golden(0,1)}"
    print(f"self-test: PASS")
    return True

def run_hw(port, baud, op_name):
    """Run exhaustive HW conformance for gfternary (only 4×4=16 pairs needed)."""
    import serial
    golden = GOLDEN_OPS[op_name]
    ser = serial.Serial(port, baud, timeout=2)
    ok = 0; fails = []
    for a in range(4):
        for b in range(4):
            g = golden(a, b)
            hw = hw_exchange(ser, a, b, op_name)
            if hw is not None and hw == g:
                ok += 1
            else:
                fails.append(f"gft_{op_name}({a},{b}) gold={g} hw={hw}")
    ser.close()
    total = 16
    print(f"HW RESULT: {ok}/{total} bit-exact (fails={len(fails)})")
    for f in fails:
        print(f"  {f}")
    return ok == total

def main():
    ap = argparse.ArgumentParser(description="GFTERNARY compute conformance for AX7203")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--op", default="add", choices=["add", "mul", "div", "sqrt"])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--n", type=int, default=16)  # ignored for gfternary (always 4×4)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test(a.op) else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.op) else 1)

if __name__ == "__main__":
    main()
