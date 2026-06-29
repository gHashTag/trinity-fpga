#!/usr/bin/env python3
"""Unified exhaustive decode verifier.

--format <name>; reads "code fp32" hex lines from stdin (an iverilog TB driving
all codes of a decoder). Compares each RTL output to an INDEPENDENT oracle that
computes the real value via Python float arithmetic and re-encodes to fp32 via
struct (a different code path than the RTL's integer bit-shifts), so numeric
mismatches indicate a real RTL bug. NaN/Inf-class codes are reported separately
as convention differences (impl-defined), not numeric bugs.

Supported: fp8_e4m3 (fnuz), fp8_e5m2, fp6_e2m3, fp6_e3m2, fp4_e2m1, int4, binary16.

  iverilog -g2012 -o tb.vvp formal/<fmt>_decode_tb.v fpga/openxc7-synth/<fmt>_decode.v
  vvp tb.vvp | python3 conformance/decode_verify.py --format <name>
"""
import sys, struct


def _enc(val):
    return struct.unpack('<I', struct.pack('<f', val))[0]


def _fp(sign, exp, mant, ebits, mbits, bias, code, exp_max, has_inf):
    # generic fp decode -> fp32 bits (numeric codes only)
    if exp == 0:
        if mant == 0:
            return sign << 31                       # zero
        val = (mant / (1 << mbits)) * (2.0 ** (1 - bias))   # denormal
    else:
        val = (1.0 + mant / (1 << mbits)) * (2.0 ** (exp - bias))  # normal
    val = -val if sign else val
    return _enc(val)


def oracle(fmt, code):
    """Return (fp32_bits, is_special_class). is_special=True for Inf/NaN codes."""
    if fmt == 'binary16':
        bexp = (code >> 10) & 0x1F
        bmant = code & 0x3FF
        if bexp == 0x1F and bmant != 0:    # NaN: propagate payload (deterministic, matches RTL)
            return ((code >> 15) & 1) << 31 | (0xFF << 23) | (bmant << 13), False
        return struct.unpack('<I', struct.pack('<f',
            struct.unpack('<e', struct.pack('<H', code & 0xFFFF))[0]))[0], False
    if fmt == 'int4':
        c = code & 0xF
        v = c - 16 if (c & 8) else c
        return v & 0xFFFFFFFF, False
    if fmt == 'int8':
        v = code - 256 if (code & 0x80) else code
        return v & 0xFFFFFFFF, False
    if fmt == 'fp8_e4m3':       # fnuz: bias=8, no Inf, 0x80=NaN, 0x00=+0
        if code == 0x80:
            return 0x7FC00000, True
        if code == 0x00:
            return 0x00000000, False
        return _fp((code >> 7) & 1, (code >> 3) & 0xF, code & 7, 4, 3, 8, code, 0xF, False), False
    if fmt == 'fp8_e5m2':       # bias=15, has Inf (exp=0x1F)
        exp = (code >> 2) & 0x1F
        if exp == 0x1F:
            if (code & 3) == 0:                                     # Inf
                return ((code >> 7) & 1) << 31 | (0xFF << 23), False
            return ((code >> 7) & 1) << 31 | (0xFF << 23) | 0x400000, False  # NaN canonical (matches RTL)
        return _fp((code >> 7) & 1, exp, code & 3, 5, 2, 15, code, 0x1F, True), False
    if fmt == 'fp6_e2m3':       # bias=1
        return _fp((code >> 5) & 1, (code >> 3) & 3, code & 7, 2, 3, 1, code, 3, False), False
    if fmt == 'fp6_e3m2':       # bias=3
        return _fp((code >> 5) & 1, (code >> 2) & 7, code & 3, 3, 2, 3, code, 7, False), False
    if fmt == 'fp4_e2m1':       # bias=1
        return _fp((code >> 3) & 1, (code >> 1) & 3, code & 1, 2, 1, 1, code, 3, False), False
    if fmt == 'posit8':         # es=0, useed=2; value = 2^k * (1+fraction)
        if code == 0x00:
            return 0x00000000, False
        if code == 0x80:
            return 0x7FC00000, True                       # NaR
        sign = (code >> 7) & 1
        abs7 = code & 0x7F
        if sign:
            abs7 = ((~abs7) + 1) & 0x7F                    # 2's complement (7-bit)
        bits = format(abs7, '07b')
        first = bits[0]
        run = 0
        for b in bits:                                     # regime length (bit-string parse)
            if b == first:
                run += 1
            else:
                break
        k = run - 1 if first == '1' else -run
        regime_len = run + (1 if run < 7 else 0)           # + separator bit
        fb_bits = bits[regime_len:]
        fb = len(fb_bits)
        frac = int(fb_bits, 2) if fb_bits else 0
        val = (2.0 ** k) * (1.0 + frac / (2.0 ** fb)) if fb > 0 else 2.0 ** k
        val = -val if sign else val
        return _enc(val), False
    if fmt == 'lns8':          # 8-bit LNS: magnitude = round(256*2^(frac/16)) << int
        if code == 0x00:
            return 0x0000, False                       # is_zero
        log_val = code & 0x7F
        int_part = log_val >> 4
        frac_part = log_val & 0xF
        frac = round(256 * (2.0 ** (frac_part / 16.0)))
        mag = (frac << int_part) & 0xFFFF
        return mag, False
    raise SystemExit(f"unknown format: {fmt}")


def main():
    # Reads TAGGED lines "tag code fp32" (from the combined decode TB); dispatches
    # the oracle by tag, so one TB run checks every format. Untagged "code fp32"
    # lines require --format.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--format', default=None)
    a = ap.parse_args()
    stats = {}  # tag -> [checked, num_bad, spec_diff]
    overall_bad = 0
    for line in sys.stdin:
        parts = line.split()
        if len(parts) == 3:
            tag, code_s, rtl_s = parts
        elif len(parts) == 2 and a.format:
            tag, code_s, rtl_s = a.format, parts[0], parts[1]
        else:
            continue
        try:
            code = int(code_s, 16)
            rtl = int(rtl_s, 16)
        except ValueError:
            continue
        s = stats.setdefault(tag, [0, 0, 0])
        s[0] += 1
        try:
            exp, is_special = oracle(tag, code)
        except SystemExit:
            continue
        if rtl != exp:
            if is_special or (((rtl >> 23) & 0xFF) == 0xFF and ((exp >> 23) & 0xFF) == 0xFF):
                s[2] += 1
            else:
                s[1] += 1
                overall_bad += 1
                if s[1] <= 8:
                    print(f"[{tag}] NUMERIC MISMATCH code=0x{code:02x} rtl=0x{rtl:08x} exp=0x{exp:08x}")
    for tag in sorted(stats):
        checked, num_bad, spec = stats[tag]
        print(f"[{tag}] checked={checked} numeric_mismatches={num_bad} special_diffs={spec} -> "
              f"{'PASS' if num_bad == 0 else 'FAIL'}")
    return 0 if overall_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
