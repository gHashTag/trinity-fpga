#!/usr/bin/env python3
# posit16_decode_conformance_ax7203.py — Posit16 (n=16, es=2) decode on AX7203.
# Core: fpga/openxc7-synth/posit16_decode.v. Decode -> FP32 is exact (fraction <=13
# bits fits FP32 mantissa; exponent integral). Golden mirrors the RTL exactly and is
# validated against the 8 authoritative t27 vectors (posit16_conformance_v0.json).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_POSIT16 = 0x15

# t27 authoritative vectors (code -> FP32). All FP32-exact.
T27_VECTORS = {
    0x0000: 0x00000000,  # 0.0
    0x4000: 0x3F800000,  # 1.0
    0xC000: 0xBF800000,  # -1.0
    0x4800: 0x40000000,  # 2.0
    0x4C00: 0x40400000,  # 3.0
    0x3800: 0x3F000000,  # 0.5
    0x5000: 0x40800000,  # 4.0
    0xB400: 0xC0400000,  # -3.0
}


def golden_posit16(code):
    code &= 0xFFFF
    if code == 0x0000:
        return 0x00000000
    if code == 0x8000:
        return 0x7FC00000  # NaR -> qNaN
    sign = (code >> 15) & 1
    mag = code & 0x7FFF
    abs_val = (0x8000 - mag) if sign else mag        # 2's complement of 15-bit if negative
    regime_sign = (abs_val >> 14) & 1
    regime_bits = (abs_val ^ 0x7FFF) if regime_sign else abs_val
    # leading-zero count on 15 bits, capped at 14 (matches RTL default case)
    lzc = 0
    for i in range(14, -1, -1):
        if (regime_bits >> i) & 1:
            break
        lzc += 1
    else:
        lzc = 14
    k = (lzc - 1) if regime_sign else (-lzc)
    regime_total = (lzc + 1) if lzc < 14 else lzc
    after_regime = (abs_val << regime_total) & 0x7FFF
    e_field = (after_regime >> 13) & 0x3
    frac_field = (after_regime << 2) & 0x7FFF
    exp_raw = 4 * k + e_field + 127
    if exp_raw > 254:
        return (sign << 31) | 0x7F800000             # overflow -> Inf
    if exp_raw < 1:
        return (sign << 31)                           # underflow -> zero (flush)
    return (sign << 31) | (exp_raw << 23) | ((frac_field << 8) & 0x7FFFFF)


def hw_exchange(ser, code):
    import serial
    pkt = FRAME + bytes([FMT_POSIT16 & 0xFF, code & 0xFF, (code >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    bad = 0
    for code, exp in T27_VECTORS.items():
        g = golden_posit16(code)
        if g != exp:
            bad += 1
            print(f"  T27 vec 0x{code:04x}: golden=0x{g:08x} expected=0x{exp:08x}")
    print(f"self-test: golden vs {len(T27_VECTORS)} t27 vectors, {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    sample = list(T27_VECTORS.keys()) + [rnd.randint(0, 0xFFFF) for _ in range(max(0, n - len(T27_VECTORS)))]
    for code in sample:
        hw = hw_exchange(ser, code)
        gold = golden_posit16(code)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:04x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
