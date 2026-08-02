#!/usr/bin/env python3
# gf14_decode_conformance_ax7203.py — GoldenFloat14 (1S+5E+8M, bias 15, has_inf=0) decode on AX7203.
# Core: fpga/openxc7-synth/gf14_decode.v. Standard IEEE-like unpack; exp=all-ones is
# finite max (no Inf/NaN). Decode to FP32 is exact. Golden mirrors the RTL.
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])  # magic only — the fmt byte is appended with the payload below
FMT_GF14 = 0x16


def golden_gf14(code):
    code &= 0x3FFF  # 14-bit
    sign = (code >> 13) & 1
    exp = (code >> 8) & 0x1F
    mant = code & 0xFF
    if exp == 0 and mant == 0:
        return sign << 31                              # +/-0
    if exp == 0:                                       # subnormal: 2^-14 * (mant/256)
        lead = 0
        for i in range(7, -1, -1):
            if (mant >> i) & 1:
                lead = i; break
        fp32_exp = lead + 105                          # 2^(lead-22): exp = lead-22+127
        frac = mant ^ (1 << lead)                      # strip leading 1
        fp32_mant = (frac << (23 - lead)) & 0x7FFFFF if lead > 0 else 0
        return (sign << 31) | (fp32_exp << 23) | fp32_mant
    # normal (exp 1..31): 2^(exp-15)*(1.mant); FP32 exp = exp+112, mant << 15
    return (sign << 31) | ((exp + 112) << 23) | (mant << 15)


def hw_exchange(ser, code):
    import serial
    pkt = FRAME + bytes([FMT_GF14 & 0xFF, code & 0xFF, (code >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    # Hand-verified: 0->0, 4096->2.0, 7936->65536, 16128->-65536, 1->2^-22
    cases = {0x0000: 0x00000000, 0x1000: 0x40000000, 0x1F00: 0x47800000,
             0x3F00: 0xC7800000, 0x0001: 0x34800000, 0x0FFF: None}  # 0x0001=2^-22=0x34800000; 0x0FFF no-crash
    bad = 0
    for code, exp in cases.items():
        if exp is None:
            _ = golden_gf14(code); continue
        if golden_gf14(code) != exp:
            bad += 1; print(f"  0x{code:04x}: golden=0x{golden_gf14(code):08x} expected=0x{exp:08x}")
    print(f"self-test: golden spot-check {sum(1 for v in cases.values() if v is not None)} values, {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0x0000, 0x0001, 0x1000, 0x1F00, 0x3F00, 0x0FFF, 0x2001, 0x7FFF]
    sample = corners + [rnd.randint(0, 0x3FFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code)
        gold = golden_gf14(code)
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
