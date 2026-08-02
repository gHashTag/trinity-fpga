#!/usr/bin/env python3
# binary128_decode_conformance_ax7203.py — IEEE 754 binary128 (quad) decode on AX7203.
# FP128 -> FP32 narrowing with RNE. NEW 128-bit decode frame (16 code bytes).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_BINARY128 = 0x24
MASK128 = (1 << 128) - 1
MASK112 = (1 << 112) - 1

# Hand-derived (code -> FP32) via canonical binary128 layout, INDEPENDENT of golden():
#   exp_field = unbiased_exp + 16383 ; mant[111:89] -> FP32 frac[22:0].
#   Expected FP32 taken from the VALUE (IEEE struct), so a wrong bias/slice is caught.
T27 = {
    0x00000000000000000000000000000000: 0x00000000,  # 0.0
    0x3FFF0000000000000000000000000000: 0x3F800000,  # +1.0   (exp=16383, mant=0)
    0xBFFF0000000000000000000000000000: 0xBF800000,  # -1.0
    0x40000000000000000000000000000000: 0x40000000,  # +2.0   (exp=16384)
    0x40008000000000000000000000000000: 0x40400000,  # +3.0   (mant bit111 -> FP32 frac .5)
    0x3FFE0000000000000000000000000000: 0x3F000000,  # +0.5   (exp=16382)
}

def golden_binary128(code):
    code &= MASK128
    if code == 0: return 0
    sign = (code >> 127) & 1
    exp128 = (code >> 112) & 0x7FFF
    mant = code & MASK112
    if exp128 == 0: return sign << 31                       # zero / subnormal -> zero
    if exp128 == 0x7FFF:
        if mant == 0: return (sign << 31) | 0x7F800000      # Inf
        return (sign << 31) | 0x7FC00000                    # NaN
    exp32_raw = exp128 - 16256                               # excess-16383 -> excess-127
    mant_pre = (mant >> 89) & 0x7FFFFF
    guard = (mant >> 88) & 1
    rnd   = (mant >> 87) & 1
    sticky = 1 if (mant & ((1 << 87) - 1)) else 0
    round_up = guard & (rnd | sticky | (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0)
    carry = 1 if mant_rnd >= 0x800000 else 0
    exp_final = exp32_raw + (1 if carry else 0)
    if exp_final > 254: return (sign << 31) | 0x7F800000    # overflow -> inf
    if exp_final < 1:   return (sign << 31)                  # underflow -> 0
    return (sign << 31) | (exp_final << 23) | (mant_rnd & 0x7FFFFF)

def hw_exchange(ser, code):
    import serial
    b = code.to_bytes(16, 'little')
    pkt = FRAME + bytes([FMT_BINARY128 & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]

def self_test():
    bad = sum(1 for c, e in T27.items() if golden_binary128(c) != e)
    print(f"self-test: golden vs {len(T27)} hand-derived vectors, {bad} failures")
    return bad == 0

def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27.keys()) + [0x40014000000000000000000000000000, 0xC0008000000000000000000000000000]
    sample = corners + [rnd.randint(0, MASK128) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_binary128(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10: print(f"MISMATCH code=0x{code:032x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})"); return fails == 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120"); ap.add_argument("--baud", type=int, default=160000); ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test: sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)

if __name__ == "__main__": main()
