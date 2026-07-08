#!/usr/bin/env python3
"""gfternary decode conformance — 2-bit {-phi,0,+phi} -> FP32. 2-byte frame."""
import serial, struct, sys, argparse, math
PHI = (1 + math.sqrt(5)) / 2
GFT_LUT = {0: 0.0, 1: PHI, 2: -PHI, 3: PHI}  # code 3 = reserved -> +phi
def golden(raw):
    return struct.unpack(">I", struct.pack(">f", GFT_LUT[raw & 3]))[0]
def run_hw(port, baud):
    ser = serial.Serial(port, baud, timeout=2)
    ok = 0; fails = []
    for code in range(4):
        g = golden(code)
        ser.write(bytes([0xAA, 0x55, 0, code & 0xFF, 0, 0]))
        import time; time.sleep(0.005)
        r = ser.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            hw = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            if hw == g: ok += 1
            else: fails.append(f"code={code} g={g:#010x} hw={hw:#010x}")
        else: fails.append(f"code={code} noresp")
    ser.close()
    print(f"HW RESULT: {ok}/4 bit-exact (fails={len(fails)})")
    for f in fails: print(f"  {f}")
    return ok == 4
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    a = ap.parse_args()
    sys.exit(0 if run_hw(a.port, a.baud) else 1)
if __name__ == "__main__": main()
