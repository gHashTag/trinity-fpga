#!/usr/bin/env python3
# posit32_decode_conformance_ax7203.py — Posit32 (n=32, es=2) decode on AX3203.
# Regime decode + RNE rounding (fraction up to 27 bits → FP32 23-bit mantissa).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_POSIT32 = 0x1C

T27_VECTORS = {
    0x00000000: 0x00000000, 0x40000000: 0x3F800000, 0xC0000000: 0xBF800000,
    0x48000000: 0x40000000, 0x4C000000: 0x40400000, 0x38000000: 0x3F000000,
    0x50000000: 0x40800000, 0xB4000000: 0xC0400000,
}


def golden_posit32(code):
    code &= 0xFFFFFFFF
    if code == 0: return 0
    if code == 0x80000000: return 0x7FC00000
    sign = (code >> 31) & 1
    mag = code & 0x7FFFFFFF
    abs_val = (0x80000000 - mag) if sign else mag
    regime_sign = (abs_val >> 30) & 1
    regime_bits = (abs_val ^ 0x7FFFFFFF) if regime_sign else abs_val
    lzc = 0
    for i in range(30, -1, -1):
        if (regime_bits >> i) & 1: break
        lzc += 1
    else: lzc = 29
    k = (lzc - 1) if regime_sign else (-lzc)
    regime_total = (lzc + 1) if lzc < 29 else lzc
    after_regime = (abs_val << regime_total) & 0x7FFFFFFF
    e_field = (after_regime >> 29) & 0x3
    frac_field = (after_regime << 2) & 0x7FFFFFFF
    exp_raw = 4 * k + e_field + 127
    mant_pre = (frac_field >> 8) & 0x7FFFFF
    guard = (frac_field >> 7) & 1
    round_b = (frac_field >> 6) & 1
    sticky = 1 if (frac_field & 0x3F) else 0
    round_up = guard & (round_b | sticky | (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0)
    mant_carry = 1 if mant_rnd >= 0x800000 else 0
    mant_final = mant_rnd & 0x7FFFFF
    exp_final = exp_raw + (1 if mant_carry else 0)
    if exp_final > 254: return (sign << 31) | 0x7F800000
    if exp_final < 1: return (sign << 31)
    return (sign << 31) | (exp_final << 23) | mant_final


def hw_exchange(ser, code):
    import serial
    pkt = FRAME + bytes([FMT_POSIT32 & 0xFF, code & 0xFF, (code >> 8) & 0xFF,
                          (code >> 16) & 0xFF, (code >> 24) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    bad = 0
    for code, exp in T27_VECTORS.items():
        if golden_posit32(code) != exp:
            bad += 1; print(f"  0x{code:08x}: golden=0x{golden_posit32(code):08x} exp=0x{exp:08x}")
    print(f"self-test: golden vs {len(T27_VECTORS)} t27 vectors, {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27_VECTORS.keys()) + [0x44000000, 0x3C000000, 0x7C000000, 0xBC000000]
    sample = corners + [rnd.randint(0, 0xFFFFFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_posit32(code); checked += 1
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
