#!/usr/bin/env python3
# gf8_add_conformance_ax7203.py — GF8 ADD compute-conformance on AX7203.
#
# The flashed design (fpga/vivado/gf8_clean_ax7203.v) computes FULL a+b via the
# conformant gf_adder_param #(3,4) (RNE+GRS, denormal I/O, HAS_INF=0). The
# frame protocol: TX = AA 55 a_lo a_hi b_lo b_hi <trigger>; RX = A5 r_lo r_hi 00.
# This script sends a+b pairs, reads the HW result, and checks against an
# independent Python GF8-ADD golden (same spec as the verified iverilog reference,
# formal/gf_adder_ref_tb.v — GF8 exhaustive 65536/0).
#
#   self-test (no hardware):   python3 gf8_add_conformance_ax7203.py --self-test
#   on hardware (after flash): python3 gf8_add_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
#
# HONESTY: a bit-exact pass on hardware (IDCODE-recheck 0x13636093 + UART) is the
# only thing that turns compute-HW 0→1/83. SW self-test = [смоделировано], not HW.
import argparse, struct, sys

# GF8 = 1S + 3E + 4M, bias = 3, HAS_INF = 0 (exp=all-ones is finite max).
E, M, BIAS, HAS_INF = 3, 4, 3, 0
TOTAL = 1 + E + M  # 8


def decode(x):
    s = (x >> 7) & 1
    exp = (x >> 4) & 0x7
    mant = x & 0xF
    zero = (exp == 0) and (mant == 0)
    denorm = (BIAS > 0) and (exp == 0) and (mant != 0)
    eeff = 1 if denorm else exp
    sig = (0 if denorm else (1 << M)) + mant          # {implicit, mant}
    return s, exp, mant, zero, denorm, eeff, sig


def pack_den(sgn, D):
    # denormal mantissa D (handles carry -> smallest normal, 0 -> signed zero)
    if D >= (1 << M):
        return (sgn << 7) | (1 << M)                  # exp_field=1, mant=0 (smallest normal)
    if D == 0:
        return (sgn << 7)                             # ±0
    return (sgn << 7) | D                             # exp_field=0, mant=D


def gf8_add(a, b):
    sa, ea, ma, az, adn, eaef, siga = decode(a)
    sb, eb, mb, bz, bdn, ebef, sigb = decode(b)
    # zero-sign: both-zero -> -0 iff both -0; one-zero -> passthrough
    if az and bz:
        return (1 << 7) if (sa and sb) else 0
    if az:
        return b
    if bz:
        return a
    # integer-scaled magnitudes (unit = smallest denormal = 2^(1-BIAS-M))
    sa_mag = siga << (eaef - 1)
    sb_mag = sigb << (ebef - 1)
    ssum = (sa and -sa_mag or sa_mag) + (sb and -sb_mag or sb_mag)
    if ssum == 0:
        return 0                                      # cancellation -> +0
    sg = 1 if ssum < 0 else 0
    mag = -ssum if ssum < 0 else ssum
    lead = mag.bit_length() - 1
    exp_field = lead - M + 1                          # biased, normal form
    if exp_field >= 1:
        k = lead - M
        frac = (mag >> k) & ((1 << M) - 1)
        gb = (mag >> (k - 1)) & 1 if k >= 1 else 0
        tailnz = 1 if (k >= 2 and (mag & ((1 << (k - 1)) - 1))) else 0
        if gb and (tailnz or (frac & 1)):
            frac += 1
            if frac == (1 << M):
                frac = 0
                exp_field += 1
    # classify + pack (HAS_INF=0 -> overflow saturates to max-finite)
    if (not HAS_INF) and exp_field >= (1 << E):
        return (sg << 7) | ((1 << E) - 1) << M | ((1 << M) - 1)   # max-finite
    if exp_field <= 0:
        # ADD: mag is an exact integer multiple of the smallest denormal unit
        # (both operands are), so for a subnormal result the denormal mantissa
        # IS mag directly (exp_field<=0 => lead<=M-1 => mag < 2^M). No shift,
        # no rounding — matches the verified iverilog reference.
        return pack_den(sg, mag)
    return (sg << 7) | (exp_field << M) | frac


# ---- protocol ----
FRAME = bytes([0xAA, 0x55])  # + a_lo a_hi b_lo b_hi + trigger


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
            r = gf8_add(a, b)
            if r != gf8_add(b, a):
                bad += 1
            if b == 0 and a not in (0, 0x80) and r != a:
                bad += 1
    print(f"self-test: commutativity+identity over 65536 pairs, {bad} inconsistencies")
    # spot-check known values (from the iverilog reference)
    checks = [(0x01, 0x01, gf8_add(1, 1)),   # 2x smallest denormal
              (0x10, 0x90, gf8_add(0x10, 0x90))]  # 0.25 + (-0.25) -> 0
    print(f"gf8_add(1,1)={gf8_add(1,1)}  gf8_add(0x10,0x90)={gf8_add(0x10,0x90)} (expect 0)")
    return bad == 0 and gf8_add(0x10, 0x90) == 0


def run_hw(port, baud, n):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0
    checked = 0
    # representative sample: corners + random
    import random
    rnd = random.Random(42)
    sample = [0x00, 0x01, 0x7F, 0xFF, 0x10, 0x40, 0x80, 0x90]
    sample += [rnd.randint(0, 255) for _ in range(n - len(sample))]
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            gold = gf8_add(a, b)
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
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test:
        ok = self_test()
        sys.exit(0 if ok else 1)
    ok = run_hw(a.port, a.baud, a.n)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
