#!/usr/bin/env python3
"""top decode conformance — multi-format integration test.
Tests all 5 decoders (bf16, fp8_e4m3_fnuz, int8, nf4, posit8) through the
top wrapper's fmt mux. Frame: AA 55 fmt code_lo code_hi trigger -> A5 + 4 bytes LE.
"""
import serial, struct, sys, os, argparse

# Import golden decoders from existing conformance scripts
sys.path.insert(0, os.path.dirname(__file__))

def golden_bf16(raw):
    raw &= 0xFFFF
    return (raw << 16)  # bf16 = upper 16 bits of FP32

def golden_fp8_e4m3_fnuz(raw):
    raw &= 0xFF
    s = (raw >> 7) & 1
    e = (raw >> 3) & 0xF
    m = raw & 7
    if e == 0 and m == 0: return (s << 31)
    if e == 0:
        v = (m / 8.0) * (2.0 ** -6)
    else:
        v = (1 + m / 8.0) * (2.0 ** (e - 7))
    if s: v = -v
    if abs(v) > 3.4e38: return 0xFF800000 if s else 0x7F800000
    if abs(v) < 1.2e-38: return (s << 31)
    return struct.unpack(">I", struct.pack(">f", v))[0]

def golden_int8(raw):
    raw &= 0xFF
    val = raw if raw < 128 else raw - 256
    return val & 0xFFFFFFFF

def golden_nf4(raw):
    raw &= 0xF
    # NF4 (NormalFloat4) LUT per the Qwen / Dettmers spec
    nf4_lut = [0.0, 0.2920847535133362, 0.5773502691896257, 0.8726779962499655,
               1.1832159566199232, 1.5192524327104326, 1.8938714503112775, 2.339816143369586]
    v = nf4_lut[raw & 7]
    if (raw >> 3) & 1: v = -v
    return struct.unpack(">I", struct.pack(">f", v))[0]

def golden_posit8(raw):
    raw &= 0xFF
    if raw == 0: return 0
    if raw == 0x80: return 0x7FC00000  # NaR
    # Simplified posit8 golden: use float conversion via struct
    # posit8: 1 sign + 1 regime + 2 exp + 4 frac (es=2)
    s = (raw >> 7) & 1
    if s: raw = (~raw + 1) & 0xFF
    # decode regime
    bits = raw & 0x7F
    k = 0
    i = 6
    if bits & (1 << 6):
        while i >= 0 and (bits >> i) & 1: k += 1; i -= 1
        i -= 1  # skip terminator 0
    else:
        while i >= 0 and not ((bits >> i) & 1): k -= 1; i -= 1
        i -= 1  # skip terminator 1
    # exp (es=2): 2 bits
    e = 0
    for j in range(2):
        e = (e << 1) | ((bits >> i) if i >= 0 else 0)
        i -= 1
    # frac: remaining bits
    frac = 0
    nfrac = 0
    while i >= 0:
        frac = (frac << 1) | ((bits >> i) & 1)
        nfrac += 1
        i -= 1
    val = (1 + frac / (2.0 ** nfrac)) * (2.0 ** (4 * k + e)) if nfrac > 0 else (2.0 ** (4 * k + e))
    if s: val = -val
    if abs(val) > 3.4e38: return 0xFF800000 if s else 0x7F800000
    try:
        return struct.unpack(">I", struct.pack(">f", val))[0]
    except (struct.error, OverflowError):
        return 0xFF800000 if s else 0x7F800000

GOLDENS = {0: ("bf16", golden_bf16, 0xFFFF), 1: ("fp8_e4m3_fnuz", golden_fp8_e4m3_fnuz, 0xFF),
           2: ("int8", golden_int8, 0xFF), 3: ("nf4", golden_nf4, 0xF), 4: ("posit8", golden_posit8, 0xFF)}

def run_hw(port, baud):
    ser = serial.Serial(port, baud, timeout=2)
    total_ok = 0; total = 0; fmt_results = {}
    for fmt in range(5):
        name, golden, mask = GOLDENS[fmt]
        # Test representative codes for each format
        codes = [0, 1, mask, mask >> 1, mask ^ (mask >> 1), 0x55 & mask, 0xAA & mask, 0x80 & mask]
        ok = 0; fails = []
        for code in codes:
            ser.write(bytes([0xAA, 0x55, fmt, code & 0xFF, (code >> 8) & 0xFF, 0x00]))
            import time; time.sleep(0.005)
            r = ser.read(5)
            if len(r) >= 5 and r[0] == 0xA5:
                hw = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
                g = golden(code)
                # NaN-equivalence
                gn = (g >> 23 & 0xFF) == 0xFF and g & 0x7FFFFF
                hn = (hw >> 23 & 0xFF) == 0xFF and hw & 0x7FFFFF
                if (gn and hn) or hw == g: ok += 1
                else:
                    if len(fails) < 3: fails.append(f"code={code:#x} g={g:#010x} hw={hw:#010x}")
            else:
                if len(fails) < 3: fails.append(f"code={code:#x} noresp")
        print(f"  {name:20s}: {ok}/{len(codes)}{' FAIL' if fails else ' OK'}")
        for f in fails: print(f"    {f}")
        fmt_results[name] = ok == len(codes)
        total_ok += ok; total += len(codes)
    ser.close()
    verdict = "PASS" if total_ok == total else "FAIL"
    print(f"HW RESULT: {total_ok}/{total} bit-exact [{verdict}]")
    return total_ok == total

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    a = ap.parse_args()
    sys.exit(0 if run_hw(a.port, a.baud) else 1)

if __name__ == "__main__": main()
