#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# mxfp4_block_host_ax7203.py -- UART host for corona_decode_mxfp4_block_ax7203.
#
# Wide frame (host -> FPGA), 20 bytes:
#   0xAA 0x55 | 16 element bytes | scale byte | lane-index byte
#   element byte k packs lane 2k (low nibble) and lane 2k+1 (high nibble).
# Reply (FPGA -> host), 5 bytes: 0xA5 + FP32 (little-endian) of the requested lane.
#
# Usage on the flashed AX7203 (CP2102N):
#   python3 mxfp4_block_host_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
#   python3 mxfp4_block_host_ax7203.py --self-test   # golden-only, no serial
#
# STATUS: horizon B -- bitstream not yet synth/flashed. A green run here == real
# decode-HW ONLY when paired with CI run-id + bitstream SHA256 + IDCODE
# 0x13636093 on issue #199.
import argparse, struct, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mxfp4_block_golden import decode_block, fp32_bits_to_float  # noqa: E402


def pack_frame(codes, scale_e, lane):
    assert len(codes) == 32
    b = bytearray([0xAA, 0x55])
    for k in range(16):
        lo = codes[2 * k] & 0xF
        hi = codes[2 * k + 1] & 0xF
        b.append((hi << 4) | lo)
    b.append(scale_e & 0xFF)
    b.append(lane & 0x1F)
    return bytes(b)


# Representative block test set: 5-class element grid + scale sweep + random.
def build_cases():
    cases = []
    grid = list(range(16))
    # every element code paired with a scale sweep
    for scale_e in (0x00, 0x7D, 0x7E, 0x7F, 0x80, 0x81, 0x85, 0x8F, 0xFE, 0xFF):
        codes = [grid[i % 16] for i in range(32)]
        cases.append((codes, scale_e))
    # a few structured blocks
    cases.append(([0x2] * 32, 0x7F))   # all +1.0, X=1
    cases.append(([0x7] * 32, 0x80))   # all +6.0, X=2 -> +12.0
    cases.append(([0x0] * 32, 0x85))   # all zero
    import random
    random.seed(20260707)
    for _ in range(20):
        cases.append(([random.randint(0, 15) for _ in range(32)],
                      random.randint(0, 254)))
    return cases


def self_test():
    cases = build_cases()
    total = 0
    for codes, scale_e in cases:
        g = decode_block(codes, scale_e)
        for lane in range(32):
            total += 1
            _ = g[lane]  # golden defined for every lane
    print(f"self-test: {len(cases)} blocks x 32 lanes = {total} golden points OK")


def run_hw(port, baud):
    import serial  # pyserial, only needed for real HW
    ser = serial.Serial(port, baud, timeout=2)
    cases = build_cases()
    passes = 0
    total = 0
    for ci, (codes, scale_e) in enumerate(cases):
        g = decode_block(codes, scale_e)
        for lane in range(32):
            ser.reset_input_buffer()
            ser.write(pack_frame(codes, scale_e, lane))
            resp = ser.read(5)
            total += 1
            if len(resp) != 5 or resp[0] != 0xA5:
                print(f"[block {ci} lane {lane}] bad reply {resp!r}")
                continue
            got = struct.unpack('<I', resp[1:5])[0]
            exp = g[lane]
            if got == exp:
                passes += 1
            else:
                print(f"[block {ci} lane {lane}] scale={scale_e:#x} code={codes[lane]:#x} "
                      f"exp={exp:#010x} got={got:#010x} "
                      f"(exp={fp32_bits_to_float(exp)} got={fp32_bits_to_float(got)})")
    ser.close()
    print(f"HW RESULT: {passes}/{total} bit-exact (fails={total - passes})")
    return 0 if passes == total else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/cu.usbserial-120')
    ap.add_argument('--baud', type=int, default=160000)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    return run_hw(args.port, args.baud)


if __name__ == '__main__':
    sys.exit(main())
