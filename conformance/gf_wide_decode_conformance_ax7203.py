#!/usr/bin/env python3
"""Generic GF wide decode conformance — for GF48/64/96/128.
Python golden mirrors gf_wide_decode.v exactly."""
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import time, random, sys, argparse

GF_WIDE_PARAMS = {
    "gf48":  {"N": 48,  "E": 18, "M": 29, "BIAS": 131071},
    "gf64":  {"N": 64,  "E": 24, "M": 39, "BIAS": 8388607},
    "gf96":  {"N": 96,  "E": 36, "M": 59, "BIAS": 34359738367},
    "gf128": {"N": 128, "E": 49, "M": 78, "BIAS": 281474976710655},
}

def golden_fp32(raw, p):
    N, E, M, BIAS = p["N"], p["E"], p["M"], p["BIAS"]
    mask = (1 << N) - 1
    raw &= mask
    sign = raw >> (N - 1)
    exp = (raw >> M) & ((1 << E) - 1)
    mant = raw & ((1 << M) - 1)
    
    EMAX = (1 << E) - 1
    OVFL = BIAS + 128
    UDFL = BIAS - 127 if BIAS >= 127 else 0
    
    if exp == EMAX:
        if mant == 0: return 0xFF800000 if sign else 0x7F800000
        return 0x7FC00001
    if exp == 0: return sign << 31
    if exp >= OVFL: return 0xFF800000 if sign else 0x7F800000
    if exp <= UDFL: return sign << 31
    
    fp32_exp = exp - BIAS + 127
    mant23 = mant >> (M - 23) if M >= 23 else mant << (23 - M)
    return (sign << 31) | (fp32_exp << 23) | mant23

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmt", required=True, choices=list(GF_WIDE_PARAMS.keys()))
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()

    p = GF_WIDE_PARAMS[args.fmt]
    N, M = p["N"], p["M"]
    BIAS = p["BIAS"]
    EMAX = (1 << p["E"]) - 1
    nbytes = (N + 7) // 8
    mask = (1 << N) - 1

    codes = set()
    codes.add(0)
    codes.add(1 << (N-1))
    # Special values
    for e in [0, 1, BIAS-200, BIAS-128, BIAS-127, BIAS-126, BIAS-1, BIAS, BIAS+1, 
              BIAS+126, BIAS+127, BIAS+128, BIAS+200, EMAX-1, EMAX]:
        for m in [0, 1, (1 << M) - 1, (1 << (M-1)), (1 << 23) - 1]:
            for s in [0, 1]:
                codes.add(((s << (N-1)) | (e << M) | m) & mask)
    # Random
    rng = random.Random(42)
    for _ in range(args.n):
        codes.add(rng.randrange(1 << N) & mask)
    codes = sorted(codes)

    port = serial.Serial(args.port, args.baud, timeout=5)
    ok = 0; fails = []

    for raw in codes:
        gold = golden_fp32(raw, p)
        b = [(raw >> (i * 8)) & 0xFF for i in range(nbytes)]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.012)
        r = port.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            gn = (gold >> 23 & 0xFF) == 0xFF and (gold & 0x7FFFFF)
            dn = (d >> 23 & 0xFF) == 0xFF and (d & 0x7FFFFF)
            if (gn and dn) or d == gold:
                ok += 1
            else:
                if len(fails) < 5:
                    fails.append(f"raw=0x{raw:0{(N+3)//4}x} gold={gold:#010x} hw={d:#010x}")
        else:
            if len(fails) < 5:
                fails.append(f"raw=0x{raw:0{(N+3)//4}x} noresp")

    total = len(codes)
    print(f"HW RESULT: {ok}/{total} bit-exact (fails={total-ok})")
    for fmsg in fails:
        print(f"  {fmsg}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
