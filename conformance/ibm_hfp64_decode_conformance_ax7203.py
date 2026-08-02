#!/usr/bin/env python3
# ibm_hfp64_decode_conformance_ax7203.py — IBM hex floating-point (64-bit, HFP double) decode on AX7203.
# 1S + 7E(excess-64, base-16) + 56M(hex 0.MMMM...). -> FP32 via leading-1 normalize (truncate).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_IBM_HFP64 = 0x23

# Hand-derived (code -> FP32) for the HFP-double canonical layout, INDEPENDENT of golden():
#   exp excess-64 base-16, 56-bit fraction; value = 16^(E-64) * frac/2^56.
#   Expected FP32 taken from the VALUE (IEEE struct), so a wrong bias/normalize is caught.
T27 = {
    0x0000000000000000: 0x00000000,  # 0.0
    0x4110000000000000: 0x3F800000,  # +1.0  (E=65, frac=0x10000000000000 -> 0.1 hex * 16)
    0xC110000000000000: 0xBF800000,  # -1.0
    0x4120000000000000: 0x40000000,  # +2.0  (E=65, frac=0x20000000000000 -> 0.2 hex * 16)
    0x4130000000000000: 0x40400000,  # +3.0  (E=65, frac=0x30000000000000 -> 0.3 hex * 16)
    0x4080000000000000: 0x3F000000,  # +0.5  (E=64, frac=0x80000000000000 -> 0.8 hex * 1)
}

MASK56 = (1 << 56) - 1

def golden_ibm_hfp64(code):
    code &= 0xFFFFFFFFFFFFFFFF
    sign = (code >> 63) & 1
    exp_field = (code >> 56) & 0x7F
    fraction = code & MASK56
    if exp_field == 0 and fraction == 0:
        return sign << 31
    if fraction == 0:
        return sign << 31
    exp_base2 = 4 * (exp_field - 64) - 56
    lead = fraction.bit_length() - 1           # 0..55
    exp_final = exp_base2 + lead + 127
    frac = fraction ^ (1 << lead)              # clear leading 1
    mant = ((frac << (55 - lead)) >> 32) & 0x7FFFFF
    if exp_final > 254: return (sign << 31) | 0x7F800000
    if exp_final < 1:   return (sign << 31)
    return (sign << 31) | (exp_final << 23) | mant

def hw_exchange(ser, code):
    import serial
    b = code.to_bytes(8, 'little')
    pkt = FRAME + bytes([FMT_IBM_HFP64 & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]

def self_test():
    bad = sum(1 for c, e in T27.items() if golden_ibm_hfp64(c) != e)
    print(f"self-test: golden vs {len(T27)} hand-derived vectors, {bad} failures")
    return bad == 0

def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27.keys()) + [0x4210000000000000, 0xC130000000000000, 0x4010000000000000, 0x7FFFFFFFFFFFFFFF]
    sample = corners + [rnd.randint(0, 0xFFFFFFFFFFFFFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_ibm_hfp64(code); checked += 1
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

if __name__ == "__main__": main()
