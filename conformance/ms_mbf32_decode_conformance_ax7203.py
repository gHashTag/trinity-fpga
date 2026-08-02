#!/usr/bin/env python3
# ms_mbf32_decode_conformance_ax7203.py — Microsoft Binary Format (32-bit) decode on AX7203.
# MBF32 = IEEE FP32 with excess-129 bias. Decode = exp_field - 2.
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_MBF = 0x1F

T27_VECTORS = {
    0x00000000: 0x00000000, 0x40800000: 0x3F800000, 0xC0800000: 0xBF800000,
    0x41000000: 0x40000000, 0x41400000: 0x40400000,
}

def golden_mbf32(code):
    code &= 0xFFFFFFFF
    if code == 0: return 0
    sign = (code >> 31) & 1
    exp_field = (code >> 23) & 0xFF
    mantissa = code & 0x7FFFFF
    if exp_field <= 2: return sign << 31
    return (sign << 31) | ((exp_field - 2) << 23) | mantissa

def hw_exchange(ser, code):
    import serial
    pkt = FRAME + bytes([FMT_MBF & 0xFF, code & 0xFF, (code >> 8) & 0xFF,
                          (code >> 16) & 0xFF, (code >> 24) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]

def self_test():
    bad = sum(1 for c, e in T27_VECTORS.items() if golden_mbf32(c) != e)
    print(f"self-test: golden vs {len(T27_VECTORS)} t27 vectors, {bad} failures")
    return bad == 0

def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27_VECTORS.keys()) + [0x41800000, 0xC1400000, 0x42000000]
    sample = corners + [rnd.randint(0, 0xFFFFFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_mbf32(code); checked += 1
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
