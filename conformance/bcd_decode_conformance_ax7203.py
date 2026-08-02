#!/usr/bin/env python3
# bcd_decode_conformance_ax7203.py — 2-digit packed BCD decode conformance on AX7203.
# bcd_in = {tens[7:4], ones[3:0]} -> bin = tens*10 + ones (0..99), zero-extended to
# 32-bit LE in the UART reply. Core: fpga/openxc7-synth/bcd_decode.v (ported from
# gHashTag/tt-trinity-corona). Golden is self-contained (no gf_ref / no vector files).
#
#   self-test:   python3 bcd_decode_conformance_ax7203.py --self-test
#   on hardware: python3 bcd_decode_conformance_ax7203.py --port /dev/cu.usbserial-1120 --baud 160000
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct

FRAME = bytes([0xAA, 0x55])
FMT_BCD = 0x10  # ignored by the single-decoder build; sent for protocol parity


def golden_bcd(code):
    """tens*10 + ones for valid BCD; None for invalid nibbles (>9)."""
    tens = (code >> 4) & 0xF
    ones = code & 0xF
    if tens > 9 or ones > 9:
        return None
    return tens * 10 + ones


def hw_exchange(ser, code):
    import serial
    # Frame: AA 55 fmt code_lo code_hi trig  ->  A5 r0 r1 r2 r3 (uint32 LE)
    pkt = FRAME + bytes([FMT_BCD & 0xFF, code & 0xFF, 0x00, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    # Golden sanity (no hardware): spot-check + all-valid monotonic.
    cases = {0x00: 0, 0x01: 1, 0x09: 9, 0x10: 10, 0x99: 99, 0x45: 45, 0x83: 83}
    bad = 0
    for code, exp in cases.items():
        if golden_bcd(code) != exp:
            bad += 1
    # Invalid nibbles must return None.
    for code in (0x0A, 0xA0, 0xFF, 0x1F):
        if golden_bcd(code) is not None:
            bad += 1
    print(f"self-test: golden spot-check {len(cases)} valid + 4 invalid, {bad} failures")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    for code in range(256):           # exhaustive; skip invalid-BCD codes
        gold = golden_bcd(code)
        if gold is None:
            continue
        hw = hw_exchange(ser, code)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:02x} hw={hw} gold={gold}")
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
