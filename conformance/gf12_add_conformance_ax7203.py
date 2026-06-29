#!/usr/bin/env python3
"""GF12 ADD compute-conformance on AX7203 (1S+4E+7M, bias=7)."""
import sys, argparse, random

E, M, BIAS = 4, 7, 7
TOTAL = 1 + E + M  # 12
FRAME = bytes([0xAA, 0x55])

def gf12_add(a, b):
    sa = (a >> (TOTAL-1)) & 1
    ea = (a >> M) & ((1 << E) - 1)
    ma = a & ((1 << M) - 1)
    sb = (b >> (TOTAL-1)) & 1
    eb = (b >> M) & ((1 << E) - 1)
    mb = b & ((1 << M) - 1)
    az = (ea == 0) and (ma == 0)
    bz = (eb == 0) and (mb == 0)
    adn = (BIAS > 0) and (ea == 0) and (ma != 0)
    bdn = (BIAS > 0) and (eb == 0) and (mb != 0)
    if az and bz: return (1 << (TOTAL-1)) if (sa and sb) else 0
    if az: return b
    if bz: return a
    eaef = 1 if adn else ea
    ebef = 1 if bdn else eb
    sig_a = (0 if adn else (1 << M)) + ma
    sig_b = (0 if bdn else (1 << M)) + mb
    sa_mag = sig_a << (eaef - 1)
    sb_mag = sig_b << (ebef - 1)
    ssum = (-sa_mag if sa else sa_mag) + (-sb_mag if sb else sb_mag)
    if ssum == 0: return 0
    sg = 1 if ssum < 0 else 0
    mag = -ssum if ssum < 0 else ssum
    lead = mag.bit_length() - 1
    exp_field = lead - M + 1
    frac = 0
    if exp_field >= 1:
        k = lead - M
        frac = (mag >> k) & ((1 << M) - 1)
        gb = ((mag >> (k-1)) & 1) if k >= 1 else 0
        tailnz = 1 if (k >= 2 and (mag & ((1 << (k-1)) - 1))) else 0
        if gb and (tailnz or (frac & 1)):
            frac += 1
            if frac == (1 << M): frac = 0; exp_field += 1
    if exp_field >= (1 << E):
        return (sg << (TOTAL-1)) | (((1 << E) - 1) << M) | ((1 << M) - 1)
    if exp_field <= 0:
        D = mag & ((1 << M) - 1)
        if D == 0: return sg << (TOTAL-1)
        return (sg << (TOTAL-1)) | D
    return (sg << (TOTAL-1)) | (exp_field << M) | frac

def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5: return None
    return resp[1] | (resp[2] << 8)

def self_test():
    rnd = random.Random(42)
    corners = [0x000, 0x001, 0x7FF, 0x400, 0x3C0, 0x3FF, 0x010, 0x100]
    sample = corners + [rnd.randint(0, (1 << TOTAL) - 1) for _ in range(56)]
    bad = checked = 0
    for a in sample:
        for b in sample[:8]:
            g = gf12_add(a, b)
            checked += 1
            if not (0 <= g < (1 << TOTAL)):
                bad += 1
            if gf12_add(a, b) != gf12_add(b, a):
                bad += 1
    print(f"self-test: {checked}-pair GF12 golden, in-width+commutative, bad={bad}")
    return bad == 0

def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    rnd = random.Random(42)
    corners = [0x000, 0x001, 0x7FF, 0x400, 0x3C0, 0x3FF, 0x010, 0x100]
    sample = corners + [rnd.randint(0, (1 << TOTAL) - 1) for _ in range(56)]
    fails = checked = 0
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            g = gf12_add(a, b)
            checked += 1
            if hw is None or hw != g:
                fails += 1
                if fails <= 10: print(f"MISMATCH a={a} b={b} hw={hw} gold={g}")
    ser.close()
    print(f"HW RESULT: {checked-fails}/{checked} bit-exact (fails={fails})")
    return fails == 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud) else 1)
