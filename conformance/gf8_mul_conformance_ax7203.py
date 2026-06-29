#!/usr/bin/env python3
"""GF8 MUL compute-conformance on AX7203 (GoldenFloat8: 1S+3E+4M, HAS_INF=0).

Golden = gf_ref.gf_mul (exact Fraction oracle, family-split overflow). HW exchange
mirrors the ADD family but the FPGA runs gf_mul_param #(3,4). Standard 6-byte
request (AA 55 a_lo a_hi b_lo b_hi), 4-byte response (A5 r_lo r_hi 0x00); the GF8
operand is the low byte (high byte ignored by the DUT). Result is 8-bit (r_lo).

  self-test: python3 gf8_mul_conformance_ax7203.py --self-test
  on HW:     python3 gf8_mul_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
"""
import sys, os, argparse, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_mul

FMT = FORMATS["gf8"]            # exp_bits=3, mant_bits=4, width=8, no Inf
WIDTH = FMT.width              # 8
FRAME = bytes([0xAA, 0x55])

# §3.5-style corner codes (raw, 8-bit): +0, -0, smallest/largest denormal, 1.0, max-finite, large normals.
CORNERS = [0x00, 0x80, 0x01, 0x0F, 0x70, 0x71, 0x7F, 0x38]


def hw_exchange(ser, a, b):
    # 6-byte frame: AA 55 a_lo a_hi b_lo b_hi (operand = low byte; high byte ignored).
    pkt = FRAME + bytes([a & 0xFF, 0x00, b & 0xFF, 0x00, 0x00])  # +trigger byte
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1]            # 8-bit result (r_lo)


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
                if bad <= 8: print(f"OOB a={a:02x} b={b:02x} g={g:02x}")
            if gf_mul(FMT, a, b) != gf_mul(FMT, b, a):
                bad += 1
                if bad <= 8: print(f"NONCOMM a={a:02x} b={b:02x}")
    print(f"self-test: {checked}-pair GF8 MUL golden, in-width+commutative, bad={bad}")
    return bad == 0


def run_hw(port, baud, exhaustive=False):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    cov = list(range(1 << WIDTH)) if exhaustive else _cov()
    fails = checked = 0
    for a in cov:
        for b in (cov if exhaustive else cov[:8]):
            hw = hw_exchange(ser, a, b); g = gf_mul(FMT, a, b); checked += 1
            if hw is None or hw != g:
                fails += 1
                if fails <= 12: print(f"MISMATCH a={a:02x} b={b:02x} hw={hw and '0x%02x' % hw} gold=0x{g:02x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


ap = argparse.ArgumentParser()
ap.add_argument("--self-test", action="store_true")
ap.add_argument("--port", default="/dev/cu.usbserial-120")
ap.add_argument("--baud", type=int, default=160000)
ap.add_argument("--exhaustive", action="store_true", help="all 256x256=65536 pairs (gf8 fits)")
a = ap.parse_args()
if a.self_test:
    sys.exit(0 if self_test() else 1)
sys.exit(0 if run_hw(a.port, a.baud, a.exhaustive) else 1)
