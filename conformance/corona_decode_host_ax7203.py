#!/usr/bin/env python3
# corona_decode_host_ax7203.py — decode-HW conformance for corona_decode_top_ax7203.
#
# Protocol (corona_decode_top_ax7203, CFGMCLK): TX = AA 55 fmt code_lo code_hi <trig>
# (6 bytes); RX = A5 r0 r1 r2 r3 (5 bytes, 32-bit decoded value LE).
# Formats: 0=bf16, 1=fp8_e4m3_fnuz, 2=int8, 3=nf4, 4=posit8.
#
# Golden decoders (independent Python, matching the Corona RTL semantics):
#   int8: signed 8-bit -> int32 (sign-extend).
#   bf16: bf16 is the top 16 bits of fp32 -> fp32 = code << 16 (all cases:
#         zero/denormal/normal/Inf/NaN map directly).
#   nf4:  16-value NF4 lookup table (standard NF4 codebook).
#   fp8_e4m3_fnuz / posit8: TODO golden (need exact fnuz bias / posit8 tapered
#         decode from the RTL — add before flashing those two formats).
#
#   self-test:  python3 corona_decode_host_ax7203.py --self-test
#   on HW:      python3 corona_decode_host_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
import argparse, sys, struct

FMT_BF16, FMT_FP8, FMT_INT8, FMT_NF4, FMT_POSIT8 = 0, 1, 2, 3, 4
FMT_FP8_E5M2, FMT_FP4, FMT_INT4, FMT_FP6_E2M3, FMT_FP6_E3M2 = 5, 6, 7, 8, 9
FMT_LNS8 = 10
FMT_TF32 = 11   # NOTE: tf32 uses a 7-byte frame (3 code bytes) — see hw_exchange_tf32
FMT_BINARY16 = 12

# LNS8 antilog fractional LUT: 2^(i/16) scaled to Q0.8 (256 = 1.0). Mirrors lns8_decode.v.
LNS8_FRAC_LUT = [256, 267, 279, 292, 304, 318, 332, 347, 362, 378, 395, 412, 431, 450, 470, 490]

# FP4 E2M1 (OCP MX) codebook -> fp32 bits (16-entry LUT, mirrors fp4_decode.v).
FP4_TABLE = {
    0x0: 0x00000000, 0x1: 0x3F000000, 0x2: 0x3F800000, 0x3: 0x3FC00000,
    0x4: 0x40000000, 0x5: 0x40400000, 0x6: 0x40800000, 0x7: 0x40C00000,
    0x8: 0x80000000, 0x9: 0xBF000000, 0xA: 0xBF800000, 0xB: 0xBFC00000,
    0xC: 0xC0000000, 0xD: 0xC0400000, 0xE: 0xC0800000, 0xF: 0xC0C00000,
}

# NF4 codebook (standard NormalFloat-4, 16 values) -> fp32 bits.
NF4_TABLE = [
    0xBF800000, 0xBF3239B1, 0xBF066B30, 0xBECA32A0,  # Corona nf4 codebook (sim-verified)
    0xBE91A24D, 0xBE3D353F, 0xBDBA7871, 0x00000000,
    0x3DA2FAFF, 0x3E24CAE3, 0x3E7C04DD, 0x3EAD033A,
    0x3EE1A4B8, 0x3F1007AB, 0x3F3913B3, 0x3F800000,
]


def _fp8_e4m3_fnuz(code):
    """FP8 E4M3 FNUZ (AMD MI300) -> FP32. bias=8, 0x00=+0, 0x80=NaN, no Inf."""
    if code == 0x80:
        return 0x7FC00000                # NaN
    if code == 0x00:
        return 0x00000000                # +0
    sign = (code >> 7) & 1
    exp = (code >> 3) & 0xF
    mant = code & 0x7
    if exp == 0:                         # subnormal: value = M * 2^-10
        if mant & 0x4:
            fe, fm = 119, (mant & 0x3) << 21
        elif mant & 0x2:
            fe, fm = 118, (mant & 0x1) << 22
        else:                            # mant == 0b001
            fe, fm = 117, 0
    else:                                # normal: value = (1+M/8) * 2^(E-8)
        fe, fm = exp + 119, mant << 20
    return (sign << 31) | (fe << 23) | fm


def _posit8(code):
    """Posit8(es=0) -> FP32. useed=2, value=(-1)^S * 2^k * (1+fraction). 0x00=0, 0x80=NaR."""
    if code == 0x00:
        return 0x00000000
    if code == 0x80:
        return 0x7FC00000                # NaR -> NaN
    sign = (code >> 7) & 1
    abs7 = code & 0x7F
    if sign:
        abs7 = ((~abs7) + 1) & 0x7F      # 2's complement (7-bit)
    regime_sign = (abs7 >> 6) & 1
    regime_bits = ((~abs7) & 0x7F) if regime_sign else abs7
    lzc = 7 - regime_bits.bit_length()    # leading-zero count on 7 bits
    k = (lzc - 1) if regime_sign else (-lzc)
    regime_total = lzc + (1 if lzc < 7 else 0)
    shifted = (abs7 << regime_total) & 0x7F
    fraction = (shifted >> 1) & 0x3F      # shifted[6:1], 6 bits
    fp32_exp = (127 + k) & 0xFF
    return (sign << 31) | (fp32_exp << 23) | (fraction << 17)


def _fp8_e5m2(code):
    """FP8 E5M2 (OCP MX / IEEE-like) -> FP32. bias=15, sign=bit7, exp=bits6:2, mant=bits1:0.
    Has Inf (exp=0x1F,mant=0) and NaN (exp=0x1F,mant!=0). Mirrors fp8_e5m2_decode.v."""
    sign = (code >> 7) & 1
    exp = (code >> 2) & 0x1F
    mant = code & 0x3
    if exp == 0x1F:
        if mant == 0:                       # Inf
            return (sign << 31) | (0xFF << 23)
        return (sign << 31) | (0xFF << 23) | 0x400000   # quiet NaN
    if exp == 0 and mant == 0:              # zero
        return sign << 31
    if exp == 0:                            # subnormal: value = 2^-14 * (0.mant)
        if mant & 0x2:                      # 1x -> normalized 2^-15
            fe, fm = 112, (mant & 0x1) << 22
        else:                               # 01 -> normalized 2^-16
            fe, fm = 111, 0
        return (sign << 31) | (fe << 23) | fm
    # normal: value = (1+M/4) * 2^(E-15); fp32 exp = E-15+127 = E+112
    return (sign << 31) | ((exp + 112) << 23) | (mant << 21)


def _fp4(code):
    """FP4 E2M1 (OCP MX) -> FP32. 16-entry LUT (mirrors fp4_decode.v)."""
    return FP4_TABLE[code & 0xF]


def _int4(code):
    """INT4 signed (two's complement) -> INT32 sign-extension (mirrors int4_decode.v)."""
    c = code & 0xF
    v = c - 16 if (c & 0x8) else c          # [-8, +7]
    return v & 0xFFFFFFFF


def _fp6_e2m3(code):
    """FP6 E2M3 (Blackwell) -> FP32. bias=1, sign=bit5, exp=bits4:3, mant=bits2:0.
    No Inf/NaN. Mirrors fp6_e2m3_decode.v."""
    sign = (code >> 5) & 1
    exp = (code >> 3) & 0x3
    mant = code & 0x7
    if exp == 0 and mant == 0:              # zero
        return sign << 31
    if exp == 0:                            # subnormal: value = 0.mmm
        if mant & 0x4:                      # 1xx -> normalized 1.xx * 2^-1
            fe, fm = 126, (mant & 0x3) << 21
        elif mant & 0x2:                    # 01x -> normalized 1.x * 2^-2
            fe, fm = 125, (mant & 0x1) << 22
        else:                               # 001 -> 1.0 * 2^-3
            fe, fm = 124, 0
        return (sign << 31) | (fe << 23) | fm
    # normal: value = (1+M/8) * 2^(E-1); fp32 exp = E-1+127 = E+126
    return (sign << 31) | ((exp + 126) << 23) | (mant << 20)


def _fp6_e3m2(code):
    """FP6 E3M2 (OCP MX) -> FP32. bias=3, sign=bit5, exp=bits4:2, mant=bits1:0.
    No Inf/NaN. Mirrors fp6_e3m2_decode.v."""
    sign = (code >> 5) & 1
    exp = (code >> 2) & 0x7
    mant = code & 0x3
    if exp == 0 and mant == 0:              # zero
        return sign << 31
    if exp == 0:                            # subnormal: value = 2^-2 * (0.mant)
        if mant & 0x2:                      # 1x
            fe, fm = 124, (mant & 0x1) << 22
        else:                               # 01
            fe, fm = 123, 0
        return (sign << 31) | (fe << 23) | fm
    # normal: value = (1+M/4) * 2^(E-3); fp32 exp = E-3+127 = E+124
    return (sign << 31) | ((exp + 124) << 23) | (mant << 21)


def _lns8(code):
    """8-bit LNS (base-2) decode. PACKING: bit31=sign, bits[15:0]=16-bit Q8.8 magnitude,
    bits[30:16]=0 (NOT fp32). Mirrors lns8_decode.v exactly."""
    sign = (code >> 7) & 1
    log_val = code & 0x7F                       # 7-bit Q3.4
    if code == 0x00:                            # is_zero
        magnitude = 0
    else:
        int_part = (log_val >> 4) & 0x7         # log_val[6:4]
        frac_part = log_val & 0xF               # log_val[3:0]
        magnitude = (LNS8_FRAC_LUT[frac_part] << int_part) & 0xFFFF
    return (sign << 31) | magnitude


def _tf32(code):
    """TF32 (1+8+10 = 19-bit) -> FP32. Pure wiring: zero-extend mantissa 10->23.
    sign=bit18, exp=bits17:10, mant=bits9:0. Mirrors tf32_decode.v."""
    code &= 0x7FFFF
    sign = (code >> 18) & 1
    exp = (code >> 10) & 0xFF
    mant = code & 0x3FF
    return (sign << 31) | (exp << 23) | (mant << 13)


def _binary16(code):
    """IEEE 754 binary16 (half) -> FP32. NaN payload propagated EXPLICITLY
    ({sign,0xFF,mant<<13}, matching binary16_decode.v) — do NOT rely on struct 'e'
    for NaN, whose float16->float32 payload handling is platform-dependent.
    Zero/Inf/normal/denormal use struct 'e' (deterministic, exact in fp32)."""
    code &= 0xFFFF
    exp = (code >> 10) & 0x1F
    mant = code & 0x3FF
    if exp == 0x1F and mant != 0:                       # NaN: propagate payload
        return ((code >> 15) & 1) << 31 | (0xFF << 23) | (mant << 13)
    f16 = struct.unpack('<e', struct.pack('<H', code))[0]
    return struct.unpack('<I', struct.pack('<f', f16))[0]


def golden(fmt, code):
    """Independent decode golden (32-bit result), matching Corona RTL — 5/5 formats."""
    if fmt == FMT_INT8:
        v = code - 256 if (code & 0x80) else code
        return v & 0xFFFFFFFF
    if fmt == FMT_BF16:
        return (code & 0xFFFF) << 16       # bf16 = top 16 bits of fp32
    if fmt == FMT_NF4:
        return NF4_TABLE[code & 0xF]
    if fmt == FMT_FP8:
        return _fp8_e4m3_fnuz(code & 0xFF)
    if fmt == FMT_POSIT8:
        return _posit8(code & 0xFF)
    if fmt == FMT_FP8_E5M2:
        return _fp8_e5m2(code & 0xFF)
    if fmt == FMT_FP4:
        return _fp4(code & 0xF)
    if fmt == FMT_INT4:
        return _int4(code & 0xF)
    if fmt == FMT_FP6_E2M3:
        return _fp6_e2m3(code & 0x3F)
    if fmt == FMT_FP6_E3M2:
        return _fp6_e3m2(code & 0x3F)
    if fmt == FMT_LNS8:
        return _lns8(code & 0xFF)
    if fmt == FMT_TF32:
        return _tf32(code & 0x7FFFF)
    if fmt == FMT_BINARY16:
        return _binary16(code & 0xFFFF)
    return None


def hw_exchange(ser, fmt, code):
    pkt = bytes([0xAA, 0x55, fmt, code & 0xFF, (code >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8) | (resp[3] << 16) | (resp[4] << 24)


def hw_exchange_tf32(ser, code):
    # tf32 uses a 7-byte frame: AA 55 fmt lo mid hi trig (19-bit code in 3 bytes).
    pkt = bytes([0xAA, 0x55, FMT_TF32, code & 0xFF, (code >> 8) & 0xFF, (code >> 16) & 0x7, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8) | (resp[3] << 16) | (resp[4] << 24)


def self_test():
    # golden internal consistency (no HW)
    checks = [
        (FMT_INT8, 0x05, 0x00000005),
        (FMT_INT8, 0xFF, 0xFFFFFFFF),   # -1
        (FMT_INT8, 0x80, 0xFFFFFF80),   # -128
        (FMT_BF16, 0x3F80, 0x3F800000), # 1.0
        (FMT_BF16, 0xBF80, 0xBF800000), # -1.0
        (FMT_BF16, 0x0000, 0x00000000), # +0
        (FMT_NF4,  0x0F, 0x3F800000),   # nf4 code 15 -> +1.0 (last entry of codebook)
        (FMT_FP8,  0x40, 0x3F800000),   # fp8 e4m3 0x40 (exp=8) -> 1.0
        (FMT_FP8,  0x44, 0x3FC00000),   # fp8 0x44 -> 1.5
        (FMT_FP8,  0x80, 0x7FC00000),   # fp8 NaN
        (FMT_POSIT8, 0x40, 0x3F800000), # posit8 0x40 -> 1.0
        (FMT_POSIT8, 0x80, 0x7FC00000), # posit8 NaR -> NaN
        (FMT_FP8_E5M2, 0x3C, 0x3F800000), # 1.0
        (FMT_FP8_E5M2, 0x40, 0x40000000), # 2.0
        (FMT_FP8_E5M2, 0x7C, 0x7F800000), # +Inf
        (FMT_FP8_E5M2, 0xFC, 0xFF800000), # -Inf
        (FMT_FP8_E5M2, 0x7F, 0x7FC00000), # NaN
        (FMT_FP8_E5M2, 0x01, 0x37800000), # subnormal 2^-16
        (FMT_FP8_E5M2, 0x03, 0x38400000), # subnormal 1.5*2^-15
        (FMT_FP8_E5M2, 0x80, 0x80000000), # -0
        (FMT_FP4, 0x2, 0x3F800000),       # 1.0
        (FMT_FP4, 0xA, 0xBF800000),       # -1.0
        (FMT_FP4, 0x7, 0x40C00000),       # 6.0
        (FMT_FP4, 0x0, 0x00000000),       # +0
        (FMT_INT4, 0x5, 0x00000005),      # +5
        (FMT_INT4, 0xF, 0xFFFFFFFF),      # -1
        (FMT_INT4, 0x8, 0xFFFFFFF8),      # -8
        (FMT_FP6_E2M3, 0x10, 0x40000000), # 2.0
        (FMT_FP6_E2M3, 0x18, 0x40800000), # 4.0
        (FMT_FP6_E2M3, 0x20, 0x80000000), # -0
        (FMT_FP6_E2M3, 0x01, 0x3E000000), # subnormal 1.0*2^-3
        (FMT_FP6_E3M2, 0x14, 0x40800000), # 4.0
        (FMT_FP6_E3M2, 0x1C, 0x41800000), # 16.0
        (FMT_FP6_E3M2, 0x20, 0x80000000), # -0
        (FMT_LNS8, 0x00, 0x00000000),     # zero (sign0, mag0)
        (FMT_LNS8, 0x10, 0x00000200),     # 256<<1
        (FMT_LNS8, 0x01, 0x0000010B),     # 267 (2^(1/16))
        (FMT_LNS8, 0x7F, 0x0000F500),     # 490<<7 (max log)
        (FMT_LNS8, 0x80, 0x80000100),     # sign1, log0 -> -1.0 mag
        (FMT_LNS8, 0xFF, 0x8000F500),     # sign1, max log
        (FMT_TF32, 0x00000, 0x00000000),  # +0
        (FMT_TF32, 0x40000, 0x80000000),  # -0
        (FMT_TF32, 0x1FC00, 0x3F800000),  # 1.0
        (FMT_TF32, 0x5FC00, 0xBF800000),  # -1.0
        (FMT_TF32, 0x3FC00, 0x7F800000),  # +Inf
        (FMT_TF32, 0x3FC01, 0x7F802000),  # NaN
        (FMT_TF32, 0x0FC01, 0x1F802000),  # normal exp=63, mant=1
        (FMT_BINARY16, 0x0000, 0x00000000),  # +0
        (FMT_BINARY16, 0x3C00, 0x3F800000),  # 1.0
        (FMT_BINARY16, 0x7C00, 0x7F800000),  # +Inf
        (FMT_BINARY16, 0xFC00, 0xFF800000),  # -Inf
        (FMT_BINARY16, 0x7C01, 0x7F802000),  # NaN (payload 1)
        (FMT_BINARY16, 0x0001, 0x33800000),  # smallest denormal 2^-24
    ]
    bad = 0
    for fmt, code, exp in checks:
        g = golden(fmt, code)
        ok = (g == exp)
        if not ok:
            bad += 1
        print(f"{'ok' if ok else 'FAIL'}  fmt={fmt} code=0x{code:x} golden=0x{g:08x}" + ("" if ok else f" exp=0x{exp:08x}"))
    print(f"self-test: {len(checks)-bad}/{len(checks)} golden checks pass")
    return bad == 0


def run_hw(port, baud, fmt_filter=None):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = checked = 0
    # int8 exhaustive (256), bf16 sample (corners + a spread), nf4 exhaustive (16)
    cases = [(FMT_INT8, c) for c in range(256)]
    cases += [(FMT_BF16, c) for c in [0x0000, 0x3F80, 0xBF80, 0x4000, 0xC000, 0x7F80, 0x0001, 0x4248]]
    cases += [(FMT_NF4, c) for c in range(16)]
    cases += [(FMT_FP8, c) for c in range(256)]            # fp8 e4m3 fnuz exhaustive
    cases += [(FMT_POSIT8, c) for c in range(256)]         # posit8 exhaustive
    cases += [(FMT_FP8_E5M2, c) for c in range(256)]       # fp8 e5m2 exhaustive
    cases += [(FMT_FP4, c) for c in range(16)]             # fp4 e2m1 exhaustive
    cases += [(FMT_INT4, c) for c in range(16)]            # int4 exhaustive
    cases += [(FMT_FP6_E2M3, c) for c in range(64)]        # fp6 e2m3 exhaustive
    cases += [(FMT_FP6_E3M2, c) for c in range(64)]        # fp6 e3m2 exhaustive
    cases += [(FMT_LNS8, c) for c in range(256)]           # lns8 exhaustive
    cases += [(FMT_TF32, c) for c in                      # tf32 corners (19-bit, not exhaustive)
              [0x00000, 0x40000, 0x1FC00, 0x5FC00, 0x3FC00, 0x3FC01, 0x0FC01, 0x3FBFF]]
    cases += [(FMT_BINARY16, c) for c in range(65536)]    # binary16 exhaustive
    for fmt, code in cases:
        if fmt_filter is not None and fmt != fmt_filter:
            continue
        g = golden(fmt, code)
        if g is None:
            continue
        hw = hw_exchange_tf32(ser, code) if fmt == FMT_TF32 else hw_exchange(ser, fmt, code)
        checked += 1
        if hw is None or hw != g:
            fails += 1
            if fails <= 12:
                print(f"MISMATCH fmt={fmt} code=0x{code:x} hw={hw and ('0x%08x' % hw)} golden=0x{g:08x}")
    ser.close()
    print(f"HW RESULT: {checked-fails}/{checked} bit-exact (decode-HW); fails={fails}")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--fmt", type=int, default=None, help="only test this format (0-9), None=all")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.fmt) else 1)


if __name__ == "__main__":
    main()
