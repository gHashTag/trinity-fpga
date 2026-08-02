#!/usr/bin/env python3
# mxint8_decode_conformance_ax7203.py — OCP MX INT8 decode on AX7203.
# int8 x 2^-6 -> FP32 (range +/-127/64). -128 reserved -> NaN. Core:
# fpga/openxc7-synth/mxint8_decode.v (ported from gHashTag/tt-trinity-corona).
# Self-contained golden mirrors the RTL (leading-one normalize).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct

FRAME = bytes([0xAA, 0x55])
FMT_MXINT8 = 0x13  # ignored by the single-decoder build; sent for protocol parity


def golden_mxint8(code):
    if code == 0x00:
        return 0x00000000                       # +0
    if code == 0x80:
        return 0x7FC00000                       # -128 reserved -> NaN
    sign = (code >> 7) & 0x1
    mag = code & 0x7F
    abs_val = (0x80 - mag) if sign else mag     # |int8|
    lop = abs_val.bit_length() - 1              # leading-one pos 0..6
    fp32_exp = 121 + lop                        # 127 + (lop - 6)
    frac = abs_val ^ (1 << lop)                 # strip leading 1
    fp32_mant = (frac << (23 - lop)) & 0x7FFFFF
    return (sign << 31) | (fp32_exp << 23) | fp32_mant


def hw_exchange(ser, code):
    import serial
    # Frame: AA 55 fmt code_lo code_hi trig  ->  A5 r0 r1 r2 r3 (uint32 LE)
    pkt = FRAME + bytes([FMT_MXINT8 & 0xFF, code & 0xFF, 0x00, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    # 0x40=1.0, 0x01=2^-6, 0x7F=127/64, 0xFF=-2^-6, -128=NaN, 0=+0
    cases = {0x00: 0x00000000, 0x80: 0x7FC00000, 0x40: 0x3F800000,
             0x01: 0x3C800000, 0x7F: 0x3FFE0000, 0xFF: 0xBC800000}
    bad = 0
    for code, exp in cases.items():
        if golden_mxint8(code) != exp:
            bad += 1
    print(f"self-test: golden spot-check {len(cases)} MXINT8 values, {bad} failures")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    for code in range(256):           # exhaustive over the 8-bit MXINT8 space
        hw = hw_exchange(ser, code)
        gold = golden_mxint8(code)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:02x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud) else 1)


if __name__ == "__main__":
    main()
