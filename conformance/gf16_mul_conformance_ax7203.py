#!/usr/bin/env python3
"""GF16 MUL compute-conformance on AX7203 (1S+6E+9M, bias=31, HAS_INF=True).

Golden = gf_ref.gf_mul (exact Fraction oracle, family-split overflow: GF16 is
the ONLY GF width with Inf/NaN, so max_exp+max_exp -> Inf, not max-finite).
Coverage = §3.5 corners + seeded random (~512 pairs), NOT exhaustive (2^32).
Result is 16 bits -> res_lo | (res_hi<<8).

  self-test:  python3 gf16_mul_conformance_ax7203.py --self-test
  on HW:      python3 gf16_mul_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
"""
import sys, os, argparse, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_mul

FMT = FORMATS["gf16"]             # exp_bits=6, mant_bits=9, bias=31, width=16, has_inf=True
WIDTH = FMT.width                 # 16
FRAME = bytes([0xAA, 0x55])

# §3.5-style corner codes (raw): zero, denormal, normal, 1.0/-1.0, max-normal, Inf, NaN.
CORNERS = [
    0x0000, 0x8000, 0x0001, 0x01FF,   # +0, -0, smallest/largest denormal
    0x3C00, 0x3E00, 0xBE00, 0x4000,   # 0.5, 1.0, -1.0, 2.0
    0x7DFF, 0x7E00, 0xFE00, 0x7E01,   # max-normal, +Inf, -Inf, NaN
]


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)   # 16-bit GF16 result


def _cov():
    rnd = random.Random(42)
    return CORNERS + [rnd.randint(0, (1 << WIDTH) - 1) for _ in range(52)]


def self_test():
    """Offline golden gate: in-width + commutativity over coverage + known specials."""
    cov = _cov()
    bad = checked = 0
    for a in cov:
        for b in cov[:8]:
            g = gf_mul(FMT, a, b)
            checked += 1
            if not (0 <= g < (1 << WIDTH)):
                bad += 1
                if bad <= 8:
                    print(f"OOB a={a:04x} b={b:04x} g={g:04x}")
            if gf_mul(FMT, a, b) != gf_mul(FMT, b, a):
                bad += 1
                if bad <= 8:
                    print(f"NONCOMM a={a:04x} b={b:04x}")
    # HAS_INF specials (GF16-specific, MUL semantics): overflow->Inf, Inf*x, Inf*0->NaN, Inf*-Inf->-Inf, NaN*x
    specials = [
        (0x0000, 0x0000, 0x0000),      # 0*0=+0
        (0x7DFF, 0x7DFF, 0x7E00),      # max*max -> +Inf (overflow, has_inf)
        (0x7E00, 0x3E00, 0x7E00),      # +Inf * 1.0 -> +Inf
        (0x7E00, 0x0000, 0x7E01),      # +Inf * 0 -> NaN
        (0x7E00, 0xFE00, 0xFE00),      # +Inf * -Inf -> -Inf
        (0x7E01, 0x3E00, 0x7E01),      # NaN * 1.0 -> NaN
    ]
    for a, b, exp in specials:
        g = gf_mul(FMT, a, b)
        if g != exp:
            bad += 1
            print(f"SPECIAL a={a:04x}+b={b:04x}: got {g:04x} exp {exp:04x}")
    print(f"self-test: {checked}-pair GF16 golden, in-width+commutative+HAS_INF specials, bad={bad}")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    cov = _cov()
    fails = checked = 0
    for a in cov:
        for b in cov[:8]:
            hw = hw_exchange(ser, a, b)
            g = gf_mul(FMT, a, b)
            checked += 1
            if hw is None or hw != g:
                fails += 1
                if fails <= 12:
                    print(f"MISMATCH a={a:04x} b={b:04x} hw={hw and '0x%04x'%hw} gold=0x{g:04x}")
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
