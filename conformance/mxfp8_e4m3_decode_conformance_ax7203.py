#!/usr/bin/env python3
# mxfp8_e4m3_decode_conformance_ax7203.py — OCP MX FP8 E4M3 decode on AX7203.
# E4M3: 1 sign + 4 exp (bias 7) + 3 mant. No Inf. NaN = S.1111.111. -> FP32.
# Core: fpga/openxc7-synth/mxfp8_e4m3_decode.v (ported from tt-trinity-corona).
# Self-contained golden mirrors the RTL exactly (NaN/zero/subnormal-3-case/normal).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct

FRAME = bytes([0xAA, 0x55])
FMT_MXFP8 = 0x12  # ignored by the single-decoder build; sent for protocol parity


def golden_mxfp8(code):
    sign = (code >> 7) & 0x1
    exp  = (code >> 3) & 0xF
    mant = code & 0x7
    if exp == 0xF and mant == 0x7:                 # NaN = {sign, FF, 400000}
        return (sign << 31) | 0x7FC00000
    if exp == 0 and mant == 0:                     # +/-0
        return sign << 31
    if exp == 0:                                   # subnormal: 2^-6 * (0.mant)
        if mant & 0x4:
            fe, fm = 120, (mant & 0x3) << 21
        elif mant & 0x2:
            fe, fm = 119, (mant & 0x1) << 22
        else:                                      # mant == 1
            fe, fm = 118, 0
    else:                                          # normal: (1.mant) * 2^(exp-7)
        fe, fm = exp + 120, mant << 20
    return (sign << 31) | (fe << 23) | fm


def hw_exchange(ser, code):
    import serial
    # Frame: AA 55 fmt code_lo code_hi trig  ->  A5 r0 r1 r2 r3 (uint32 LE)
    pkt = FRAME + bytes([FMT_MXFP8 & 0xFF, code & 0xFF, 0x00, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    # Spot-checks: 0x3C=1.5, 0x7F=+NaN, 0xFF=-NaN, 0x04=2^-7, 0x00=+0, 0x80=-0.
    cases = {0x00: 0x00000000, 0x80: 0x80000000, 0x3C: 0x3FC00000,
             0x7F: 0x7FC00000, 0xFF: 0xFFC00000, 0x04: 0x3C000000}
    bad = 0
    for code, exp in cases.items():
        if golden_mxfp8(code) != exp:
            bad += 1
    print(f"self-test: golden spot-check {len(cases)} E4M3 values, {bad} failures")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    for code in range(256):           # exhaustive over the 8-bit E4M3 space
        hw = hw_exchange(ser, code)
        gold = golden_mxfp8(code)
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
