#!/usr/bin/env python3
# binary64_decode_conformance_ax7203.py — IEEE 754 binary64 (FP64/double) decode on AX7203.
# FP64 → FP32 narrowing with RNE rounding. NEW 64-bit decode frame (8 code bytes).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_BINARY64 = 0x20

T27_VECTORS = {
    0x0000000000000000: 0x00000000, 0x3FF0000000000000: 0x3F800000, 0xBFF0000000000000: 0xBF800000,
    0x4000000000000000: 0x40000000, 0x4008000000000000: 0x40400000, 0x3FE0000000000000: 0x3F000000,
    0x4010000000000000: 0x40800000, 0xC008000000000000: 0xC0400000,
}

def golden_binary64(code):
    code &= 0xFFFFFFFFFFFFFFFF
    if code == 0: return 0
    sign = (code >> 63) & 1
    exp64 = (code >> 52) & 0x7FF
    mant64 = code & 0xFFFFFFFFFFFFF
    if exp64 == 0: return sign << 31  # zero/subnormal -> zero
    if exp64 == 0x7FF:
        if mant64 == 0: return (sign << 31) | 0x7F800000  # Inf
        return (sign << 31) | 0x7FC00000  # NaN
    exp32_raw = exp64 - 896
    mant_pre = (mant64 >> 29) & 0x7FFFFF
    guard = (mant64 >> 28) & 1
    round_b = (mant64 >> 27) & 1
    sticky = 1 if (mant64 & 0x7FFFFFF) else 0
    round_up = guard & (round_b | sticky | (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0)
    mant_carry = 1 if mant_rnd >= 0x800000 else 0
    mant_final = mant_rnd & 0x7FFFFF
    exp_final = exp32_raw + (1 if mant_carry else 0)
    if exp_final > 254: return (sign << 31) | 0x7F800000
    if exp_final < 1: return (sign << 31)
    return (sign << 31) | (exp_final << 23) | mant_final

def hw_exchange(ser, code):
    import serial
    b = code.to_bytes(8, 'little')
    pkt = FRAME + bytes([FMT_BINARY64 & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]

def self_test():
    bad = sum(1 for c, e in T27_VECTORS.items() if golden_binary64(c) != e)
    print(f"self-test: golden vs {len(T27_VECTORS)} t27 vectors, {bad} failures")
    return bad == 0

def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27_VECTORS.keys()) + [0x4024000000000000, 0x3F947AE147AE147B]
    sample = corners + [rnd.randint(0, 0xFFFFFFFFFFFFFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_binary64(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10: print(f"MISMATCH code=0x{code:016x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})"); return fails == 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120"); ap.add_argument("--baud", type=int, default=160000); ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test: sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)

if __name__ == "__main__":
    main()
