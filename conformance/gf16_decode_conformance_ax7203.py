#!/usr/bin/env python3
# gf16_decode_conformance_ax7203.py — GoldenFloat16 (1S + 6E + 9M, bias 31, HAS_INF=1)
# decode on AX7203. Core RTL: fpga/openxc7-synth/corona_decode_gf16_ax7203.v, which
# instantiates gf_decode_param #(.N(16),.E(6),.M(9),.BIAS(31)). The decode is exact
# (every gf16 value lands inside FP32 normal range — BIAS=31 never reaches the FP32
# subnormal/overflow paths), so the golden below mirrors the RTL bit-for-bit.
#
# Frame (matched-substrate wrapper, identical to binary16/gf14 decode wrappers):
#   TX 6 bytes:  AA 55 fmt code_lo code_hi trig     (fmt/trig ignored by single-format wrapper)
#   RX 5 bytes:  A5 r0 r1 r2 r3                      (r0..r3 = FP32 result, little-endian)
# Baud 160000. Board AX7203 = XC7A200T-2FBG484I, IDCODE 0x13636093.
#
# NaN handling: IEEE-754 does not mandate a NaN bit pattern. The RTL canonicalises to
# quiet NaN 0x7FC00001; the golden emits the same canonical value. For robustness the
# HW compare is NaN-payload-agnostic (class check exp=0xFF & mant!=0), matching the
# iverilog witness (tb_gf_decode.v, 65536/65536 PASS, fpga/witness/gf_decode/).
import argparse, sys, struct, random

FRAME = bytes([0xAA, 0x55])
FMT_GF16 = 0x0D  # informational; single-format wrapper ignores the fmt byte

# gf16 parameters
N, E, M, BIAS = 16, 6, 9, 31
EXP_MAX = (1 << E) - 1          # 0x3F
MANT_MASK = (1 << M) - 1        # 0x1FF
FP32_QNAN    = 0x7FC00001       # matches gf_decode_param.v localparam FP32_QNAN
FP32_POS_INF = 0x7F800000
FP32_NEG_INF = 0xFF800000


def golden_gf16(code):
    """Independent GF16 -> FP32 bit-pattern golden. Mirrors gf_decode_param #(16,6,9,31).
    5 classes: zero / subnormal / normal / Inf / NaN. BIAS=31 keeps every finite value
    inside the FP32 normal exponent range, so no FP32-subnormal path is ever taken."""
    code &= 0xFFFF
    sign = (code >> 15) & 1
    exp = (code >> M) & EXP_MAX
    mant = code & MANT_MASK
    if exp == EXP_MAX:
        if mant != 0:
            return FP32_QNAN                                   # quiet NaN
        return FP32_NEG_INF if sign else FP32_POS_INF          # +/-Inf
    if exp == 0 and mant == 0:
        return sign << 31                                      # +/-0
    if exp == 0:
        # subnormal: (-1)^s * (mant/2^M) * 2^(1-BIAS) = mant/512 * 2^-30
        # renormalise: find leading 1 in the 9-bit mantissa
        lead = 0
        for i in range(M - 1, -1, -1):
            if (mant >> i) & 1:
                lead = i
                break
        # value = 2^(lead - M) * 2^(1-BIAS) * (1.frac) = 2^(lead - 9 - 30) * (1.frac)
        # true FP32 exp = (lead - 9 + 1 - BIAS) - ... build directly:
        #   normalized: leading bit at position `lead`, so exponent = (1-BIAS) + (lead - M)
        true_exp = (1 - BIAS) + (lead - M)                     # unbiased power of two
        fp32_exp = true_exp + 127
        frac = mant ^ (1 << lead)                              # strip the leading 1
        # remaining `lead` bits become the top of the FP32 23-bit mantissa
        fp32_mant = (frac << (23 - lead)) & 0x7FFFFF if lead > 0 else 0
        return (sign << 31) | (fp32_exp << 23) | fp32_mant
    # normal: (-1)^s * (1 + mant/2^M) * 2^(exp-BIAS)
    #   FP32 exp field = (exp - BIAS) + 127 = exp - 31 + 127 = exp + 96
    #   FP32 mantissa   = mant << (23 - M) = mant << 14
    return (sign << 31) | ((exp + (127 - BIAS)) << 23) | (mant << (23 - M))


def is_nan_bits(w):
    return ((w >> 23) & 0xFF) == 0xFF and (w & 0x7FFFFF) != 0


def hw_exchange(ser, code):
    pkt = FRAME + bytes([FMT_GF16 & 0xFF, code & 0xFF, (code >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    # Hand-verified spot checks:
    #   0x0000 -> +0
    #   0x3E00 -> 1.0    (exp=31, mant=0)  => 0x3F800000
    #   0x4000 -> 2.0    (exp=32, mant=0)  => 0x40000000
    #   0x7E00 -> +Inf   (exp=63, mant=0)  => 0x7F800000
    #   0xFE00 -> -Inf                     => 0xFF800000
    #   0x7E01 -> NaN                      => 0x7FC00001
    #   0x0001 -> smallest subnormal (mant=1) => 2^-39 = 0x2C000000
    cases = {
        0x0000: 0x00000000,
        0x3E00: 0x3F800000,
        0x4000: 0x40000000,
        0x7E00: 0x7F800000,
        0xFE00: 0xFF800000,
        0x7E01: 0x7FC00001,
        0x0001: 0x2C000000,
    }
    bad = 0
    for code, exp in cases.items():
        got = golden_gf16(code)
        if is_nan_bits(exp):
            if not is_nan_bits(got):
                bad += 1
                print(f"  0x{code:04x}: golden=0x{got:08x} expected NaN-class")
        elif got != exp:
            bad += 1
            print(f"  0x{code:04x}: golden=0x{got:08x} expected=0x{exp:08x}")
    print(f"self-test: golden spot-check {len(cases)} values, {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0
    checked = 0
    rnd = random.Random(42)
    corners = [0x0000, 0x8000, 0x0001, 0x3E00, 0x4000, 0x7DFF, 0x7E00,
               0xFE00, 0x7E01, 0x01FF, 0x7FFF, 0xBE00]
    if n >= 65536:
        sample = list(range(65536))          # exhaustive
    else:
        sample = corners + [rnd.randint(0, 0xFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code)
        gold = golden_gf16(code)
        checked += 1
        if hw is None:
            fails += 1
        elif is_nan_bits(gold):
            if not is_nan_bits(hw):
                fails += 1
        elif hw != gold:
            fails += 1
        if fails and fails <= 10 and (hw is None or (not is_nan_bits(gold) and hw != gold)):
            print(f"MISMATCH code=0x{code:04x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser(description="GF16 decode conformance on AX7203")
    ap.add_argument("--self-test", action="store_true", help="run golden spot-check only")
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=256,
                    help="samples (>=65536 = exhaustive all codes)")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
