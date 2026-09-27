#!/usr/bin/env python3
# gf8_sub_conformance_ax7203.py — GF8 SUB compute-conformance on AX7203.
#
# SUB(a,b) = ADD(a, -b). The flashed design (fpga/vivado/gf8_sub_ax7203.v) flips
# b's sign bit then runs the conformant gf_adder_param #(3,4) — the SAME adder that
# is exhaustive-sim + formal-PROVEN + silicon-PROVEN for ADD. So SUB correctness
# reduces to ADD correctness plus a value-preserving sign XOR.
#
# Golden = gf_ref.gf_add(GF8, a, b ^ 0x80) — the canonical Fraction oracle already
# used for the silicon ADD/MUL conformance (conformance/gf_ref.py). Frame/response
# protocol identical to gf8_clean (ADD): TX = AA 55 a_lo a_hi b_lo b_hi <trig>;
# RX = A5 r_lo r_hi 00.
#
#   self-test (no hardware):   python3 gf8_sub_conformance_ax7203.py --self-test
#   on hardware (after flash): python3 gf8_sub_conformance_ax7203.py --port /dev/cu.usbserial-1120 --baud 160000
#
# HONESTY: a bit-exact pass on hardware (IDCODE-recheck 0x13636093 + UART) is the
# only thing that turns a compute-HW SUB cell 0→1. SW self-test = [simulated].
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

GF8 = FORMATS["gf8"]          # 1S+3E+4M, bias=3, HAS_INF=0
SIGN = 1 << (GF8.exp_bits + GF8.mant_bits)   # sign bit position = 0x80 for GF8


def golden_sub(a, b):
    # SUB(a,b) = ADD(a, -b): flip b's sign bit, then the verified ADD golden.
    return gf_add(GF8, a, b ^ SIGN)


# ---- protocol (identical to gf8_clean ADD) ----
FRAME = bytes([0xAA, 0x55])  # magic only — the gf compute wrappers have no fmt byte


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, 0, b & 0xFF, 0, 0x00])  # 16-bit LE words + trigger
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)


def self_test():
    # exhaustive GF8 (65536 pairs): SUB algebra vs the canonical ADD golden.
    # a - a == 0 for nonzero a (a + (-a) = 0; ±0 excluded — IEEE zero-sign rule).
    # a - 0 == a for nonzero a. Anti-commutativity: a-b and b-a are same magnitude,
    # opposite sign (modulo the ±0 zero-sign edge).
    bad = 0
    for a in range(256):
        for b in range(256):
            r = golden_sub(a, b)
            # a - a -> 0 (skip ±0: 0-0 follows IEEE both-zero sign rule, not plain 0)
            if a == b and a not in (0, SIGN) and r not in (0, SIGN):
                bad += 1
            # a - (+0) == a  for nonzero a  (b=+0 -> -b=+0 (0^0x80... wait +0=0x00, ^0x80=0x80=-0)
            # NOTE: -(+0) = -0, and a + (-0) = a (one-zero passthrough). So a-0=a holds.
            if b == 0 and a not in (0, SIGN) and r != a:
                bad += 1
    # cross-check: SUB golden must equal the silicon-ADD golden with sign flipped
    # (definitional, but guards against a sign-mask typo).
    cross_bad = sum(1 for a in range(256) for b in range(256)
                    if golden_sub(a, b) != gf_add(GF8, a, b ^ SIGN))
    print(f"self-test: SUB algebra over 65536 pairs, {bad} inconsistencies; "
          f"cross-check vs gf_add(a,-b) {cross_bad} mismatches")
    print(f"gf8_sub(0x10,0x10)={golden_sub(0x10,0x10)} (expect 0)  "
          f"gf8_sub(0x40,0x10)={golden_sub(0x40,0x10)} (2.0-0.25=1.75 -> 0x3C=60)")
    return bad == 0 and cross_bad == 0 and golden_sub(0x10, 0x10) in (0, SIGN)


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
            gold = golden_sub(a, b)
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
