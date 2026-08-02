#!/usr/bin/env python3
# vax_g_decode_conformance_ax7203.py — DEC VAX G_floating (64-bit) decode on AX7203.
# VAX G = sign + 11-bit exp (excess-1024) + 52-bit mantissa -> FP32 (RNE narrowing).
# VAX has NO inf/nan sentinel exponent (unlike IEEE): exp 0..2047 all normal/reserved;
# exp==0 -> signed zero, overflow -> FP32 inf. Decode exp = exp64 - 897.
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_VAX_G = 0x22

# Hand-derived (code -> FP32) via the canonical VAX-G layout, INDEPENDENT of golden():
#   exp_field = unbiased_exp + 1024 ; mant[51:29] -> FP32 frac[22:0].
# Expected FP32 taken from the VALUE (IEEE struct), so a wrong bias/slice is caught.
T27 = {
    0x0000000000000000: 0x00000000,  # 0.0
    0x4000000000000000: 0x3F800000,  # +1.0   (exp_field=1024, mant=0)
    0xC000000000000000: 0xBF800000,  # -1.0
    0x4010000000000000: 0x40000000,  # +2.0   (exp_field=1025)
    0x4018000000000000: 0x40400000,  # +3.0   (mant bit51 -> FP32 frac .5)
    0x3FF0000000000000: 0x3F000000,  # +0.5   (exp_field=1023)
}

def golden_vax_g(code):
    code &= 0xFFFFFFFFFFFFFFFF
    if code == 0: return 0
    sign = (code >> 63) & 1
    exp64 = (code >> 52) & 0x7FF
    mant64 = code & 0xFFFFFFFFFFFFF
    if exp64 == 0: return sign << 31                       # zero / reserved operand
    exp32_raw = exp64 - 897                                  # excess-1024 -> excess-127
    mant_pre = (mant64 >> 29) & 0x7FFFFF
    guard = (mant64 >> 28) & 1
    rnd   = (mant64 >> 27) & 1
    sticky = 1 if (mant64 & 0x7FFFFFF) else 0
    round_up = guard & (rnd | sticky | (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0)
    carry = 1 if mant_rnd >= 0x800000 else 0
    exp_final = exp32_raw + (1 if carry else 0)
    if exp_final > 254: return (sign << 31) | 0x7F800000    # overflow -> FP32 inf
    if exp_final < 1:   return (sign << 31)                  # underflow -> 0
    return (sign << 31) | (exp_final << 23) | (mant_rnd & 0x7FFFFF)

def hw_exchange(ser, code):
    import serial
    b = code.to_bytes(8, 'little')
    pkt = FRAME + bytes([FMT_VAX_G & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]

def self_test():
    bad = sum(1 for c, e in T27.items() if golden_vax_g(c) != e)
    print(f"self-test: golden vs {len(T27)} hand-derived vectors, {bad} failures")
    return bad == 0

def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27.keys()) + [0x4024000000000000, 0xC018000000000000]
    sample = corners + [rnd.randint(0, 0xFFFFFFFFFFFFFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_vax_g(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10: print(f"MISMATCH code=0x{code:016x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})"); return fails == 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120"); ap.add_argument("--baud", type=int, default=160000); ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test: sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)

if __name__ == "__main__": main()
