#!/usr/bin/env python3
# ms_mbf64_decode_conformance_ax7203.py — Microsoft Binary Format (64-bit) decode on AX7203.
# MBF64 = excess-129 bias + 55-bit mantissa → FP32 23-bit with RNE.
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55]); FMT = 0x22

T27 = {0x0:0x0, 0x4080000000000000:0x3F800000, 0xC080000000000000:0xBF800000,
       0x4100000000000000:0x40000000, 0x4140000000000000:0x40400000}

def golden_mbf64(code):
    code &= 0xFFFFFFFFFFFFFFFF
    if code == 0: return 0
    sign = (code >> 63) & 1; exp_field = (code >> 55) & 0xFF
    mant = code & 0x7FFFFFFFFFFFFF
    if exp_field <= 2: return sign << 31
    mant_pre = (mant >> 32) & 0x7FFFFF; guard = (mant >> 31) & 1; rnd = (mant >> 30) & 1
    sticky = 1 if (mant & 0x3FFFFFF) else 0
    round_up = guard & (rnd | sticky | (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0); carry = 1 if mant_rnd >= 0x800000 else 0
    exp_final = exp_field - 2 + (1 if carry else 0)
    if exp_final > 254: return (sign << 31) | 0x7F800000
    return (sign << 31) | (exp_final << 23) | (mant_rnd & 0x7FFFFF)

def hw_exchange(ser, code):
    import serial
    b = code.to_bytes(8, 'little'); pkt = FRAME + bytes([FMT & 0xFF]) + b + bytes([0x00])
    ser.write(pkt); resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]

def self_test():
    bad = sum(1 for c,e in T27.items() if golden_mbf64(c) != e)
    print(f"self-test: golden vs {len(T27)} t27 vectors, {bad} failures"); return bad == 0

def run_hw(port, baud, n):
    import serial
    import serial; ser = serial.Serial(port, baud, timeout=2); fails=0; checked=0; rnd=random.Random(42)
    corners = list(T27.keys()) + [0x4180000000000000, 0xC140000000000000]
    sample = corners + [rnd.randint(0, 0xFFFFFFFFFFFFFFFF) for _ in range(max(0, n-len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_mbf64(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10: print(f"MISMATCH code=0x{code:016x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked-fails}/{checked} bit-exact (fails={fails})"); return fails == 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120"); ap.add_argument("--baud", type=int, default=160000); ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test: sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)

if __name__ == "__main__": main()
