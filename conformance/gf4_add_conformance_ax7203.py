#!/usr/bin/env python3
"""GF4 ADD compute-conformance on AX7203 (1S+1E+2M, bias=0, no Inf).

Exhaustive: all 16x16 = 256 input pairs. Golden = gf_ref.gf_add (exact
Fraction oracle, 2-oracle cross-checked, same as gf6/gf8/gf12 HW runs).
Result is 4 bits, packed in the low nibble of res_lo by gf4_clean_ax7203.

  self-test:  python3 gf4_add_conformance_ax7203.py --self-test
  on HW:      python3 gf4_add_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

FMT = FORMATS["gf4"]              # exp_bits=1, mant_bits=2, bias=0, width=4, no Inf
WIDTH = FMT.width
FRAME = bytes([0xAA, 0x55])


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] & 0x0F          # GF4 result is the low nibble of res_lo


def self_test():
    """Offline golden gate (no HW): every result in-width + ADD commutativity + corners."""
    bad = 0
    for a in range(1 << WIDTH):
        for b in range(1 << WIDTH):
            g = gf_add(FMT, a, b)
            if not (0 <= g < (1 << WIDTH)):
                bad += 1
                if bad <= 8:
                    print(f"OOB a={a:x} b={b:x} g={g:x}")
            if gf_add(FMT, a, b) != gf_add(FMT, b, a):   # commutativity
                bad += 1
                if bad <= 8:
                    print(f"NONCOMM a={a:x} b={b:x}")
    # known corners
    corners = {0x0: ("0+0", 0x0)}
    for a, (label, exp) in list(corners.items()):
        g = gf_add(FMT, a, a)
        if g != exp:
            bad += 1
            print(f"CORNER {label}: got {g:x} exp {exp:x}")
    n = (1 << WIDTH) * (1 << WIDTH)
    print(f"self-test: {n}-pair GF4 golden, in-width + commutative, bad={bad}")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = checked = 0
    for a in range(1 << WIDTH):
        for b in range(1 << WIDTH):
            hw = hw_exchange(ser, a, b)
            g = gf_add(FMT, a, b)
            checked += 1
            if hw is None or hw != g:
                fails += 1
                if fails <= 12:
                    print(f"MISMATCH a={a:x} b={b:x} hw={hw} gold={g:x}")
    ser.close()
    print(f"HW RESULT: {checked-fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


ap = argparse.ArgumentParser()
ap.add_argument("--self-test", action="store_true")
ap.add_argument("--port", default="/dev/cu.usbserial-120")
ap.add_argument("--baud", type=int, default=160000)
a = ap.parse_args()
if a.self_test:
    sys.exit(0 if self_test() else 1)
sys.exit(0 if run_hw(a.port, a.baud) else 1)
