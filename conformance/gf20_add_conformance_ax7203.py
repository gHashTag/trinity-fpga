#!/usr/bin/env python3
"""GF20 ADD compute-conformance on AX7203 (1S+7E+12M, bias=63, no Inf).

Golden = gf_ref.gf_add (exact Fraction oracle, family-split overflow). Coverage =
corners + seeded random (~512 pairs), NOT exhaustive (2^40). GF20 operands are
20-bit -> WIDER protocol than gf8/gf12/gf16: 9-byte request (3 bytes/operand),
4-byte response (3 result bytes).

  self-test:  python3 gf20_add_conformance_ax7203.py --self-test
  on HW:      python3 gf20_add_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
"""
import sys, os, argparse, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

FMT = FORMATS["gf20"]             # exp_bits=7, mant_bits=12, bias=63, width=20, no Inf
WIDTH = FMT.width                 # 20
FRAME = bytes([0xAA, 0x55])

# §3.5-style corner codes (raw, 20-bit): zero, denormal, normals, max-finite.
CORNERS = [
    0x00000, 0x80000, 0x00001, 0x00FFF,   # +0, -0, smallest/largest denormal
    1 << 12, (1 << 12) | 1, 0xFFFFF, 0x7FFFF,   # 1.0-ish, max-finite, large normals
]


def hw_exchange(ser, a, b):
    # 9-byte frame: AA 55 a_lo a_mid a_hi b_lo b_mid b_hi trig
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xF,
                         b & 0xFF, (b >> 8) & 0xFF, (b >> 16) & 0xF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8) | (resp[3] << 16)   # 20-bit result


def _cov():
    rnd = random.Random(42)
    return CORNERS + [rnd.randint(0, (1 << WIDTH) - 1) for _ in range(52)]


def self_test():
    cov = _cov()
    bad = checked = 0
    for a in cov:
        for b in cov[:8]:
            g = gf_add(FMT, a, b)
            checked += 1
            if not (0 <= g < (1 << WIDTH)):
                bad += 1
                if bad <= 8:
                    print(f"OOB a={a:05x} b={b:05x} g={g:05x}")
            if gf_add(FMT, a, b) != gf_add(FMT, b, a):
                bad += 1
                if bad <= 8:
                    print(f"NONCOMM a={a:05x} b={b:05x}")
    print(f"self-test: {checked}-pair GF20 golden, in-width+commutative, bad={bad}")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    cov = _cov()
    fails = checked = 0
    for a in cov:
        for b in cov[:8]:
            hw = hw_exchange(ser, a, b)
            g = gf_add(FMT, a, b)
            checked += 1
            if hw is None or hw != g:
                fails += 1
                if fails <= 12:
                    print(f"MISMATCH a={a:05x} b={b:05x} hw={hw and '0x%05x'%hw} gold=0x{g:05x}")
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
