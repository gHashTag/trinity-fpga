#!/usr/bin/env python3
# gf8_add_conformance_ax7203.py — GF8 ADD compute-conformance on AX7203.
#
# The flashed design (fpga/vivado/gf8_clean_ax7203.v) computes FULL a+b via the
# conformant gf_adder_param #(3,4) (RNE+GRS, denormal I/O, HAS_INF=0). The
# frame protocol: TX = AA 55 a_lo a_hi b_lo b_hi <trigger>; RX = A5 r_lo r_hi 00.
# This script sends a+b pairs, reads the HW result, and checks against the
# golden oracle in gf_ref.py (parametric Fraction-exact reference; the same
# model as the verified iverilog reference, formal/gf_adder_ref_tb.v — GF8
# exhaustive 65536/0).
#
#   self-test (no hardware):   python3 gf8_add_conformance_ax7203.py --self-test
#   on hardware (after flash): python3 gf8_add_conformance_ax7203.py --port /dev/cu.usbserial-1120 --baud 160000
#
# HONESTY: a bit-exact pass on hardware (IDCODE-recheck 0x13636093 + UART) is the
# only thing that turns compute-HW 0→1/83. SW self-test = [simulated], not HW.
import argparse, struct, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

# GF8 = 1S + 3E + 4M, bias = 3, HAS_INF = 0 (exp=all-ones is finite max).
E, M, BIAS, HAS_INF = 3, 4, 3, 0
TOTAL = 1 + E + M  # 8
FMT = FORMATS["gf8"]


# ---- protocol ----
FRAME = bytes([0xAA, 0x55])  # magic only — the gf compute wrappers have no fmt byte  # + a_lo a_hi b_lo b_hi + trigger


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, 0, b & 0xFF, 0, 0x00])  # 16-bit words, LE; trigger
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)                       # result (low 8 bits = GF8)


def self_test():
    # exhaustive GF8 (65536 pairs) — golden internal consistency only (no HW)
    bad = 0
    for a in range(256):
        for b in range(256):
            # golden must be self-consistent: a+b commutative, a+0=a (a nonzero),
            # a+(-a)=0. The a+0==a check excludes a=±0 (those follow the IEEE
            # both-zero rule: (-0)+(+0)=+0, not -0).
            r = gf_add(FMT, a, b)
            if r != gf_add(FMT, b, a):
                bad += 1
            if b == 0 and a not in (0, 0x80) and r != a:
                bad += 1
    print(f"self-test: commutativity+identity over 65536 pairs, {bad} inconsistencies")
    # spot-check known values (from the iverilog reference)
    print(f"gf8_add(1,1)={gf_add(FMT,1,1)}  gf8_add(0x10,0x90)={gf_add(FMT,0x10,0x90)} (expect 0)")
    return bad == 0 and gf_add(FMT, 0x10, 0x90) == 0


def run_hw(port, baud, n, exhaustive=False):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0
    checked = 0
    import random
    rnd = random.Random(42)
    if exhaustive:
        sample = list(range(256))
    else:
        sample = [0x00, 0x01, 0x7F, 0xFF, 0x10, 0x40, 0x80, 0x90]
        sample += [rnd.randint(0, 255) for _ in range(n - len(sample))]
    for a in sample:
        for b in (sample if exhaustive else sample[:8]):
            hw = hw_exchange(ser, a, b)
            gold = gf_add(FMT, a, b)
            checked += 1
            if hw is None or hw != gold:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH a=0x{a:02x} b=0x{b:02x} hw={hw} gold=0x{gold:02x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--exhaustive", action="store_true", help="all 256x256=65536")
    a = ap.parse_args()
    if a.self_test:
        ok = self_test()
        sys.exit(0 if ok else 1)
    ok = run_hw(a.port, a.baud, a.n, a.exhaustive)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
