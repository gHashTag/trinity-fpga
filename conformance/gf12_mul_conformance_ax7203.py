#!/usr/bin/env python3
"""GF12 e4m7 MUL compute-conformance on AX7203 (1S+4E+7M, bias=7, no Inf).

Golden = gf_ref.gf_mul (exact Fraction oracle). Standard 6-byte request
(AA 55 a_lo a_hi b_lo b_hi), 4-byte response (A5 r_lo r_hi 0x00); the GF12
12-bit result spans r_lo (low 8) | r_hi (high 4).
"""
import sys, os, argparse, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_mul

FMT = FORMATS["gf12"]          # exp_bits=4, mant_bits=7, bias=7, width=12
WIDTH = FMT.width             # 12
FRAME = bytes([0xAA, 0x55])
CORNERS = [0x000, 0x800, 0x001, 0x07F, 0x3F0, 0x7F0, 0x3FF, 0x4F0]


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)            # 12-bit result


def _cov():
    rnd = random.Random(42)
    return CORNERS + [rnd.randint(0, (1 << WIDTH) - 1) for _ in range(52)]


def self_test():
    cov = _cov(); bad = checked = 0
    for a in cov:
        for b in cov[:8]:
            g = gf_mul(FMT, a, b); checked += 1
            if not (0 <= g < (1 << WIDTH)):
                bad += 1
                if bad <= 8: print(f"OOB a={a:03x} b={b:03x} g={g:03x}")
            if gf_mul(FMT, a, b) != gf_mul(FMT, b, a):
                bad += 1
                if bad <= 8: print(f"NONCOMM a={a:03x} b={b:03x}")
    print(f"self-test: {checked}-pair GF12 MUL golden, in-width+commutative, bad={bad}")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    cov = _cov(); fails = checked = 0
    for a in cov:
        for b in cov[:8]:
            hw = hw_exchange(ser, a, b); g = gf_mul(FMT, a, b); checked += 1
            if hw is None or hw != g:
                fails += 1
                if fails <= 12: print(f"MISMATCH a={a:03x} b={b:03x} hw={hw and '0x%03x' % hw} gold=0x{g:03x}")
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
