#!/usr/bin/env python3
# bitnet_decode_conformance_ax7203.py — BitNet 1.58b ternary decode on AX7203.
# 2-bit input (low bits of the code byte): 00=0, 01=+1.0, 10=-1.0, 11=NaN(reserved).
# Core: fpga/openxc7-synth/bitnet_decode.v (ported from gHashTag/tt-trinity-corona).
# Self-contained golden (no gf_ref / no vector files). Exhaustive over the full byte
# to confirm the decoder only consumes code[1:0] (upper 6 bits are don't-care).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct

FRAME = bytes([0xAA, 0x55])
FMT_BITNET = 0x11  # ignored by the single-decoder build; sent for protocol parity

# ternary_in[1:0] -> FP32
LUT = {0b00: 0x00000000,   # 0
       0b01: 0x3F800000,   # +1.0
       0b10: 0xBF800000,   # -1.0
       0b11: 0x7FC00000}   # NaN (reserved)


def golden_bitnet(code):
    return LUT[code & 0x3]


def hw_exchange(ser, code):
    import serial
    # Frame: AA 55 fmt code_lo code_hi trig  ->  A5 r0 r1 r2 r3 (uint32 LE)
    pkt = FRAME + bytes([FMT_BITNET & 0xFF, code & 0xFF, 0x00, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    bad = 0
    for tb, exp in LUT.items():
        if golden_bitnet(tb) != exp:
            bad += 1
    # upper bits must not affect the result
    for code in (0x04, 0x40, 0x80, 0xFF):
        if golden_bitnet(code) != LUT[code & 0x3]:
            bad += 1
    print(f"self-test: golden LUT {len(LUT)} entries + 4 don't-care, {bad} failures")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    for code in range(256):           # exhaustive over the byte (low 2 bits drive the LUT)
        hw = hw_exchange(ser, code)
        gold = golden_bitnet(code)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:02x} hw={hw} gold=0x{gold:08x}")
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
