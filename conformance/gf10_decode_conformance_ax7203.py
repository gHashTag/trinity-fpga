#!/usr/bin/env python3
# gf10_decode_conformance_ax7203.py — GoldenFloat10 (1S+3E+6M, bias 3, has_inf=0) decode on AX7203.
# Core: fpga/openxc7-synth/gf10_decode.v. Standard IEEE-like unpack; exp=all-ones is
# finite max (no Inf/NaN). Decode to FP32 exact. Golden mirrors the RTL.
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])  # magic only — the fmt byte is appended with the payload below
FMT_GF10 = 0x17


def golden_gf10(code):
    code &= 0x3FF  # 10-bit
    sign = (code >> 9) & 1
    exp = (code >> 6) & 0x7
    mant = code & 0x3F
    if exp == 0 and mant == 0:
        return sign << 31                              # +/-0
    if exp == 0:                                       # subnormal: 2^(1-3) * (mant/64) = 2^-2 * mant/64
        lead = 0
        for i in range(5, -1, -1):
            if (mant >> i) & 1:
                lead = i; break
        fp32_exp = lead + 119                          # 2^(lead-8): exp = lead-8+127
        frac = mant ^ (1 << lead)
        fp32_mant = (frac << (23 - lead)) & 0x7FFFFF if lead > 0 else 0
        return (sign << 31) | (fp32_exp << 23) | fp32_mant
    # normal (exp 1..7): 2^(exp-3)*(1.mant); FP32 exp = exp+124, mant << 17
    return (sign << 31) | ((exp + 124) << 23) | (mant << 17)


def hw_exchange(ser, code):
    import serial
    pkt = FRAME + bytes([FMT_GF10 & 0xFF, code & 0xFF, (code >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    # 0->0, 0x0C0->1.0, 0x120->3.0 (exp4/mant32), 0x1C0->16.0, 0x001->2^-8
    cases = {0x000: 0x00000000, 0x0C0: 0x3F800000, 0x120: 0x40400000,
             0x1C0: 0x41800000, 0x001: 0x3B800000}
    bad = 0
    for code, exp in cases.items():
        if golden_gf10(code) != exp:
            bad += 1; print(f"  0x{code:03x}: golden=0x{golden_gf10(code):08x} expected=0x{exp:08x}")
    print(f"self-test: golden spot-check {len(cases)} values, {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0x000, 0x001, 0x0C0, 0x120, 0x1C0, 0x0FF, 0x1FF, 0x200]
    sample = corners + [rnd.randint(0, 0x3FF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code)
        gold = golden_gf10(code)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:03x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
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
