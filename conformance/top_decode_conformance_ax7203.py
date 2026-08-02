#!/usr/bin/env python3
"""top decode conformance — multi-format integration test.
Tests all 5 decoders (bf16, fp8_e4m3_fnuz, int8, nf4, posit8) through the
top wrapper's fmt mux. Frame: AA 55 fmt code_lo code_hi trigger -> A5 + 4 bytes LE.
"""
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import struct, sys, os, argparse

# Import golden decoders from existing conformance scripts
sys.path.insert(0, os.path.dirname(__file__))

def golden_bf16(raw):
    raw &= 0xFFFF
    return (raw << 16)  # bf16 = upper 16 bits of FP32

def golden_fp8_e4m3_fnuz(raw):
    raw &= 0xFF
    # FP8 E4M3 FN-UZ: 1s+4e+3m, bias=8, 0x00=+0, 0x80=NaN, no inf
    s = (raw >> 7) & 1
    e = (raw >> 3) & 0xF
    m = raw & 7
    if raw == 0x80: return 0x7FC00000  # NaN
    if e == 0 and m == 0: return (s << 31)
    if e == 0:
        v = (m / 8.0) * (2.0 ** (1 - 8))  # bias=8
    else:
        v = (1 + m / 8.0) * (2.0 ** (e - 8))  # bias=8
    if s: v = -v
    if abs(v) > 3.4e38: return 0xFF800000 if s else 0x7F800000
    return struct.unpack(">I", struct.pack(">f", v))[0]

def golden_int8(raw):
    raw &= 0xFF
    val = raw if raw < 128 else raw - 256
    return val & 0xFFFFFFFF

def golden_nf4(raw):
    raw &= 0xF
    # NF4 RTL uses two's-complement style encoding (NOT Dettmers unsigned+sign):
    # 0x0=-1.0, ..., 0x7=0.0, ..., 0xF=+1.0 (values from nf4_decode.v LUT)
    nf4_lut = [0xBF800000, 0xBF3239B1, 0xBF066B30, 0xBECA32A0,
               0xBE91A24D, 0xBE3D353F, 0xBDBA7871, 0x00000000,
               0x3DA2FAFF, 0x3E24CAE3, 0x3E7C04DD, 0x3EAD033A,
               0x3EE1A4B8, 0x3F1007AB, 0x3F3913B3, 0x3F800000]
    return nf4_lut[raw]

def golden_posit8(raw):
    raw &= 0xFF
    # Posit8(es=0) LUT from iverilog witness of posit8_decode.v
    # value = (-1)^S * 2^k * (1 + fraction), useed=2
    POSIT8_LUT = [
        0x00000000,0x3C800000,0x3D000000,0x3D400000,0x3D800000,0x3DA00000,0x3DC00000,0x3DE00000,
        0x3E000000,0x3E100000,0x3E200000,0x3E300000,0x3E400000,0x3E500000,0x3E600000,0x3E700000,
        0x3E800000,0x3E880000,0x3E900000,0x3E980000,0x3EA00000,0x3EA80000,0x3EB00000,0x3EB80000,
        0x3EC00000,0x3EC80000,0x3ED00000,0x3ED80000,0x3EE00000,0x3EE80000,0x3EF00000,0x3EF80000,
        0x3F000000,0x3F040000,0x3F080000,0x3F0C0000,0x3F100000,0x3F140000,0x3F180000,0x3F1C0000,
        0x3F200000,0x3F240000,0x3F280000,0x3F2C0000,0x3F300000,0x3F340000,0x3F380000,0x3F3C0000,
        0x3F400000,0x3F440000,0x3F480000,0x3F4C0000,0x3F500000,0x3F540000,0x3F580000,0x3F5C0000,
        0x3F600000,0x3F640000,0x3F680000,0x3F6C0000,0x3F700000,0x3F740000,0x3F780000,0x3F7C0000,
        0x3F800000,0x3F840000,0x3F880000,0x3F8C0000,0x3F900000,0x3F940000,0x3F980000,0x3F9C0000,
        0x3FA00000,0x3FA40000,0x3FA80000,0x3FAC0000,0x3FB00000,0x3FB40000,0x3FB80000,0x3FBC0000,
        0x3FC00000,0x3FC40000,0x3FC80000,0x3FCC0000,0x3FD00000,0x3FD40000,0x3FD80000,0x3FDC0000,
        0x3FE00000,0x3FE40000,0x3FE80000,0x3FEC0000,0x3FF00000,0x3FF40000,0x3FF80000,0x3FFC0000,
        0x40000000,0x40080000,0x40100000,0x40180000,0x40200000,0x40280000,0x40300000,0x40380000,
        0x40400000,0x40480000,0x40500000,0x40580000,0x40600000,0x40680000,0x40700000,0x40780000,
        0x40800000,0x40900000,0x40A00000,0x40B00000,0x40C00000,0x40D00000,0x40E00000,0x40F00000,
        0x41000000,0x41200000,0x41400000,0x41600000,0x41800000,0x41C00000,0x42000000,0x42800000,
        0x7FC00000,0xC2800000,0xC2000000,0xC1C00000,0xC1800000,0xC1600000,0xC1400000,0xC1200000,
        0xC1000000,0xC0F00000,0xC0E00000,0xC0D00000,0xC0C00000,0xC0B00000,0xC0A00000,0xC0900000,
        0xC0800000,0xC0780000,0xC0700000,0xC0680000,0xC0600000,0xC0580000,0xC0500000,0xC0480000,
        0xC0400000,0xC0380000,0xC0300000,0xC0280000,0xC0200000,0xC0180000,0xC0100000,0xC0080000,
        0xC0000000,0xBFFC0000,0xBFF80000,0xBFF40000,0xBFF00000,0xBFEC0000,0xBFE80000,0xBFE40000,
        0xBFE00000,0xBFDC0000,0xBFD80000,0xBFD40000,0xBFD00000,0xBFCC0000,0xBFC80000,0xBFC40000,
        0xBFC00000,0xBFBC0000,0xBFB80000,0xBFB40000,0xBFB00000,0xBFAC0000,0xBFA80000,0xBFA40000,
        0xBFA00000,0xBF9C0000,0xBF980000,0xBF940000,0xBF900000,0xBF8C0000,0xBF880000,0xBF840000,
        0xBF800000,0xBF7C0000,0xBF780000,0xBF740000,0xBF700000,0xBF6C0000,0xBF680000,0xBF640000,
        0xBF600000,0xBF5C0000,0xBF580000,0xBF540000,0xBF500000,0xBF4C0000,0xBF480000,0xBF440000,
        0xBF400000,0xBF3C0000,0xBF380000,0xBF340000,0xBF300000,0xBF2C0000,0xBF280000,0xBF240000,
        0xBF200000,0xBF1C0000,0xBF180000,0xBF140000,0xBF100000,0xBF0C0000,0xBF080000,0xBF040000,
        0xBF000000,0xBEF80000,0xBEF00000,0xBEE80000,0xBEE00000,0xBED80000,0xBED00000,0xBEC80000,
        0xBEC00000,0xBEB80000,0xBEB00000,0xBEA80000,0xBEA00000,0xBE980000,0xBE900000,0xBE880000,
        0xBE800000,0xBE700000,0xBE600000,0xBE500000,0xBE400000,0xBE300000,0xBE200000,0xBE100000,
        0xBE000000,0xBDE00000,0xBDC00000,0xBDA00000,0xBD800000,0xBD400000,0xBD000000,0xBC800000,
    ]
    return POSIT8_LUT[raw]

GOLDENS = {0: ("bf16", golden_bf16, 0xFFFF), 1: ("fp8_e4m3_fnuz", golden_fp8_e4m3_fnuz, 0xFF),
           2: ("int8", golden_int8, 0xFF), 3: ("nf4", golden_nf4, 0xF), 4: ("posit8", golden_posit8, 0xFF)}

def run_hw(port, baud):
    import serial
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
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    a = ap.parse_args()
    sys.exit(0 if run_hw(a.port, a.baud) else 1)

if __name__ == "__main__": main()
