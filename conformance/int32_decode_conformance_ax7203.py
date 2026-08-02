#!/usr/bin/env python3
# int32_decode_conformance_ax7203.py — INT32 decode on AX7203 (identity, 32-bit frame).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_INT32 = 0x1B

def golden_int32(code):
    return code & 0xFFFFFFFF  # identity

def hw_exchange(ser, code):
    import serial
    pkt = FRAME + bytes([FMT_INT32 & 0xFF, code & 0xFF, (code >> 8) & 0xFF,
                          (code >> 16) & 0xFF, (code >> 24) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]

def self_test():
    cases = {0x00000000: 0x00000000, 0x00000001: 0x00000001, 0x7FFFFFFF: 0x7FFFFFFF,
             0x80000000: 0x80000000, 0xFFFFFFFF: 0xFFFFFFFF, 0x12345678: 0x12345678}
    bad = sum(1 for c, e in cases.items() if golden_int32(c) != e)
    print(f"self-test: identity spot-check {len(cases)} values, {bad} failures")
    return bad == 0

def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0; rnd = random.Random(42)
    corners = [0x00000000, 0x00000001, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x12345678]
    sample = corners + [rnd.randint(0, 0xFFFFFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_int32(code); checked += 1
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
