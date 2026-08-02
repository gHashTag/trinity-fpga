#!/usr/bin/env python3
# ibm_hfp32_decode_conformance_ax7203.py — IBM hex floating-point (32-bit) decode on AX7203.
# 1S + 7E(excess-64, base-16) + 24M(hex 0.MMMMMM). -> FP32 via normalize.
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_IBM = 0x1D

T27_VECTORS = {
    0x00000000: 0x00000000, 0x41100000: 0x3F800000, 0xC1100000: 0xBF800000,
    0x41200000: 0x40000000, 0x41300000: 0x40400000,
}


def golden_ibm_hfp32(code):
    code &= 0xFFFFFFFF
    sign = (code >> 31) & 1
    exp_field = (code >> 24) & 0x7F
    fraction = code & 0xFFFFFF
    if exp_field == 0 and fraction == 0:
        return sign << 31
    if fraction == 0:
        return sign << 31
    exp_base2 = 4 * (exp_field - 64) - 24
    lead = fraction.bit_length() - 1  # 0..23
    exp_final = exp_base2 + lead + 127
    frac = fraction ^ (1 << lead)
    mant = (frac << (23 - lead)) & 0x7FFFFF
    if exp_final > 254: return (sign << 31) | 0x7F800000
    if exp_final < 1: return (sign << 31)
    return (sign << 31) | (exp_final << 23) | mant


def hw_exchange(ser, code):
    import serial
    pkt = FRAME + bytes([FMT_IBM & 0xFF, code & 0xFF, (code >> 8) & 0xFF,
                          (code >> 16) & 0xFF, (code >> 24) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    bad = 0
    for code, exp in T27_VECTORS.items():
        if golden_ibm_hfp32(code) != exp:
            bad += 1; print(f"  0x{code:08x}: golden=0x{golden_ibm_hfp32(code):08x} exp=0x{exp:08x}")
    print(f"self-test: golden vs {len(T27_VECTORS)} t27 vectors, {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27_VECTORS.keys()) + [0x42100000, 0xC1300000, 0x40100000, 0x7FFFFFFF]
    sample = corners + [rnd.randint(0, 0xFFFFFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_ibm_hfp32(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10: print(f"MISMATCH code=0x{code:08x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
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
