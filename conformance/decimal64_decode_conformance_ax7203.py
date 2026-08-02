#!/usr/bin/env python3
# decimal64_decode_conformance_ax7203.py — IEEE 754 decimal64 (BID) -> FP32 decode on AX7203.
# BID combination-field decode per IEEE 754-2008 (Wikipedia decimal64). value = (-1)^s * C * 10^(E-398).
# Oracle = Python decimal.Decimal (authoritative); exact RNE rounding to binary32 (no double-rounding).
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import argparse, sys, struct, random
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

FRAME = bytes([0xAA, 0x55])
FMT_DECIMAL64 = 0x25
MASK64 = (1 << 64) - 1


def _bid_decode(code):
    """Return ('finite', sign, C, E) | ('inf', sign) | ('nan', sign)."""
    code &= MASK64
    sign = (code >> 63) & 1
    cf = (code >> 50) & 0x1FFF          # combination field, bits 62:50
    top2 = (cf >> 11) & 0x3             # bits 62:61
    if top2 != 0b11:                    # case A: small coefficient (leading digit 0..7)
        exp_biased = (code >> 53) & 0x3FF
        C = code & ((1 << 53) - 1)      # bits 52:0, 53-bit binary integer
        return ('finite', sign, C, exp_biased)
    top4 = (cf >> 9) & 0xF              # bits 62:59
    if top4 == 0b1111:                  # special: inf / nan
        return ('nan', sign) if (cf >> 8) & 1 else ('inf', sign)
    # case B: big coefficient (leading digit 8..9), implicit "100" MSBs
    exp_biased = (code >> 51) & 0x3FF   # bits 60:51
    C = (0b100 << 51) | (code & ((1 << 51) - 1))   # 54-bit: implicit 100 + bits 50:0
    return ('finite', sign, C, exp_biased)


def _dec_to_fp32(sign, d):
    """Exact RNE rounding of non-negative finite Decimal d to binary32 bits (sign applied)."""
    if d == 0:
        return sign << 31
    with localcontext() as ctx:
        ctx.prec = 60
        a = d
        # binary exponent e with 2^e <= a < 2^(e+1)
        e = int((a.ln() / Decimal(2).ln()).to_integral_value(rounding=ROUND_HALF_EVEN))
        two_e = Decimal(2) ** e
        while a < two_e:
            e -= 1; two_e = Decimal(2) ** e
        while a >= two_e * 2:
            e += 1; two_e = Decimal(2) ** e
        if e > 127:
            return (sign << 31) | 0x7F800000           # overflow -> Inf
        if e >= -126:                                    # normal
            m = (a / two_e) * (1 << 23)                  # [2^23, 2^24)
            m_int = int(m.to_integral_value(rounding=ROUND_HALF_EVEN))
            if m_int >= (1 << 24):                       # rounded up to 2.0
                m_int >>= 1; e += 1
                if e > 127:
                    return (sign << 31) | 0x7F800000
            return (sign << 31) | ((e + 127) << 23) | (m_int & 0x7FFFFF)
        # subnormal / underflow: represent as k * 2^-149
        k = a * (Decimal(2) ** 149)
        k_int = int(k.to_integral_value(rounding=ROUND_HALF_EVEN))
        if k_int == 0:
            return sign << 31
        if k_int >= (1 << 23):                           # rounded up to smallest normal
            return (sign << 31) | (1 << 23)
        return (sign << 31) | k_int                      # exp field 0, mantissa k_int


def golden_decimal64(code):
    kind = _bid_decode(code)
    if kind[0] == 'inf':
        return (kind[1] << 31) | 0x7F800000
    if kind[0] == 'nan':
        return (kind[1] << 31) | 0x7FC00000
    _, sign, C, E = kind
    if C == 0:
        return sign << 31
    de = E - 398
    with localcontext() as ctx:
        ctx.prec = 60
        d = Decimal(C) * (Decimal(10) ** de)
    return _dec_to_fp32(sign, d)


def _enc(sign, C, E):
    """Encode finite decimal64 BID (case A if C < 2^53, else case B). For test-vector building."""
    if C < (1 << 53):
        return (sign << 63) | (E << 53) | C
    assert C < (1 << 54) and (C >> 51) == 0b100
    return (sign << 63) | (0b11 << 61) | (E << 51) | (C & ((1 << 51) - 1))


# Hand-derived: encode (sign, C, E) -> decimal64 code; expected FP32 from the VALUE (independent).
T27 = {
    _enc(0, 1, 398): 0x3F800000,       # +1.0
    _enc(1, 1, 398): 0xBF800000,       # -1.0
    _enc(0, 2, 398): 0x40000000,       # +2.0
    _enc(0, 3, 398): 0x40400000,       # +3.0
    _enc(0, 5, 397): 0x3F000000,       # +0.5   (5e-1)
    _enc(0, 1, 399): 0x41200000,       # +10.0  (1e1)
    _enc(0, 1, 397): 0x3DCCCCCD,       # +0.1   (1e-1) -> nearest binary32
    _enc(0, 1 << 53, 398): 0x5A000000, # +2^53  (case B, leading "100"); FP32 exp 53 -> 0x5A000000
    0x7800000000000000: 0x7F800000,    # +Inf  (sign0, bits62:58 = 11110)
    0x7C00000000000000: 0x7FC00000,    # quiet NaN (bits62:57 = 111110)
}


def hw_exchange(ser, code):
    import serial
    b = code.to_bytes(8, 'little')
    pkt = FRAME + bytes([FMT_DECIMAL64 & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    bad = 0
    for code, exp in T27.items():
        g = golden_decimal64(code)
        if g != exp:
            bad += 1
            print(f"  0x{code:016x}: golden=0x{g:08x} exp=0x{exp:08x}")
    print(f"self-test: golden vs {len(T27)} hand-derived vectors (BID case A/B + inf/nan), {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    import serial
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(42)
    corners = list(T27.keys()) + [_enc(0, 9999999999999999, 398), _enc(1, 1234567890123456, 384)]
    sample = corners + [rnd.randint(0, MASK64) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_decimal64(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:016x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})"); return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
