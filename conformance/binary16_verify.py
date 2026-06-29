#!/usr/bin/env python3
"""Exhaustive verify binary16_decode.v RTL vs the C-library binary16 oracle.

Reads "code fp32" hex lines from stdin (the iverilog TB $display of all 65536
codes), compares each RTL output to fp32 bits obtained from Python's struct 'e'
(half-precision, the platform C library) -> float32. That oracle is INDEPENDENT
of the Verilog decode formula, so a clean pass is a real correctness proof.

  iverilog -g2012 -o tb.vvp formal/binary16_decode_tb.v fpga/openxc7-synth/binary16_decode.v
  vvp tb.vvp | python3 conformance/binary16_verify.py
"""
import sys, struct


def golden(code):
    """binary16 raw bits -> fp32 bits via the C-library half (struct 'e')."""
    f16 = struct.unpack('<e', struct.pack('<H', code & 0xFFFF))[0]
    return struct.unpack('<I', struct.pack('<f', f16))[0]


def main():
    bad = checked = 0
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 2:
            continue
        code = int(parts[0], 16)
        rtl = int(parts[1], 16)
        exp = golden(code)
        checked += 1
        if rtl != exp:
            bad += 1
            if bad <= 16:
                print(f"MISMATCH code=0x{code:04x} rtl=0x{rtl:08x} exp=0x{exp:08x}")
    print(f"checked={checked} mismatches={bad} (oracle: C-library binary16 via struct 'e')")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
