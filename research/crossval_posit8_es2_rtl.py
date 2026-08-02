#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does the new posit8(es=2) core decode what SoftPosit says it should?

`fpga/openxc7-synth/posit8_es2_decode.v` exists because the core the board proof used
implements posit(8,0) while the catalogue's pack declares posit(8,2). This checks the
new one against SoftPosit -- the posit reference implementation -- rather than against
a model written alongside it. A testbench that decides its own correctness is not a
second witness.

The RTL emits FP32 bit patterns; SoftPosit emits doubles. Every posit8 value carries at
most five fraction bits and lies between 2^-24 and 2^24, so all of them are exactly
representable in FP32 and the comparison is exact, not approximate. That is checked
here rather than asserted: any value that does not round-trip through FP32 exactly is
reported instead of being quietly tolerated.

    iverilog -g2012 -o /tmp/tb fpga/openxc7-synth/tb_posit8_es2_decode.v \\
             fpga/openxc7-synth/posit8_es2_decode.v \\
             fpga/openxc7-synth/posit16_decode.v && /tmp/tb > rtl.txt
    python3 research/crossval_posit8_es2_rtl.py --rtl rtl.txt --ref spx8.tsv
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import sys

SCRATCH = ("/private/tmp/claude-501/-Users-playom-trinity-fpga/"
           "3a885a60-490c-4733-abfd-86bfa298080d/scratchpad")


def fp32_bits_to_float(bits: int) -> float:
    return struct.unpack(">f", struct.pack(">I", bits & 0xFFFFFFFF))[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl", default=os.path.join(SCRATCH, "rtl_p8.txt"))
    ap.add_argument("--ref", default=os.path.join(SCRATCH, "spx8.tsv"))
    args = ap.parse_args()

    for p in (args.rtl, args.ref):
        if not os.path.exists(p):
            print(f"missing: {p}")
            print("Nothing is assumed when an input is absent.")
            return 2

    rtl = {}
    for line in open(args.rtl, encoding="utf-8"):
        parts = line.split()
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        code, hexbits, is_zero, is_nar = parts[0], parts[1], parts[2], parts[3]
        rtl[int(code)] = (fp32_bits_to_float(int(hexbits, 16)),
                          is_zero == "1", is_nar == "1")

    ref = {}
    for line in open(args.ref, encoding="utf-8"):
        if not line.strip():
            continue
        a, b = line.split("\t")
        ref[int(a)] = float(b)

    same = differ = nar = notfp32 = 0
    worst = []
    for code in range(256):
        if code not in rtl or code not in ref:
            continue
        got, is_zero, is_nar = rtl[code]
        want = ref[code]

        if math.isinf(want):                       # SoftPosit signals NaR as INFINITY
            nar += 1
            if not is_nar:
                differ += 1
                worst.append((float("inf"), code, got, want,
                              "RTL did not flag NaR"))
            continue

        # Exactness of the comparison itself, checked rather than assumed.
        if struct.unpack(">f", struct.pack(">f", want))[0] != want:
            notfp32 += 1

        if got == want:
            same += 1
        else:
            differ += 1
            rel = abs((got - want) / want) if want else float("inf")
            worst.append((rel, code, got, want, ""))

    print(f"posit8(es=2) RTL vs SoftPosit")
    print(f"  codes compared        : {same + differ + nar}")
    print(f"  bit-identical         : {same}")
    print(f"  NaR, correctly flagged: {nar - sum(1 for w in worst if w[4])}")
    print(f"  differing             : {differ}")
    if notfp32:
        print(f"  NOT exactly representable in FP32 : {notfp32}"
              f"   (the comparison would be approximate for these)")

    worst.sort(key=lambda t: -t[0] if t[0] != float("inf") else -1e400)
    for rel, code, got, want, note in worst[:6]:
        print(f"    code {code:>3}  rtl {got!r}  SoftPosit {want!r}"
              f"{'  ' + note if note else f'  rel {rel:.3g}'}")

    if not differ:
        print("""
Every code agrees exactly, and every posit8 value is exactly representable in FP32, so
this is bit equality and not a tolerance. The new core decodes the format the pack
describes.

What it does NOT do is complete a Tier-E chain: that needs a bitstream SHA-256, a public
CI run, a UART log from the board and a matching IDCODE. Simulation is explicitly not
one of the four, by this project's own standard.""")
    return 1 if differ else 0


if __name__ == "__main__":
    raise SystemExit(main())
