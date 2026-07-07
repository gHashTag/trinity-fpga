#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# mxfp4_block_rtl_bitmodel.py -- cycle-free bit model of mxfp4_block_scale.v,
# cross-checked against mxfp4_block_golden.py. This is the "no hardware" proof
# path: golden oracle (independent decode law) == RTL bit model (mirrors the
# Verilog combinational logic gate-for-gate). Exhaustive over all 16 element
# codes x all 256 E8M0 scale values = 4096 (element, scale) points.
#
# NOTE: passing here is SW-equivalence only. It is NOT decode-HW. Tier-E still
# requires a real CI synth + AX7203 flash + UART (IDCODE 0x13636093) on #199.
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mxfp4_block_golden import FP4_E2M1_BITS, decode_block  # noqa: E402


def rtl_lane(code4, scale_e):
    """Mirror mxfp4_block_scale.v for a single lane."""
    elem = FP4_E2M1_BITS[code4 & 0xF]        # fp4_decode
    scale_nan = (scale_e == 0xFF)
    shift = scale_e - 127                    # signed 9-bit in RTL
    sgn = elem & 0x80000000
    eexp = (elem >> 23) & 0xFF
    frac = elem & 0x7FFFFF
    is_zero = (eexp == 0x00) and (frac == 0)
    new_exp = eexp + shift                   # signed 11-bit in RTL
    if scale_nan:
        return 0x7FC00000
    elif is_zero:
        return elem
    elif new_exp <= 0:
        return sgn                           # {sgn, 31'b0}
    elif new_exp >= 255:
        return sgn | 0x7F800000              # {sgn, 8'hFF, 23'b0}
    else:
        return sgn | ((new_exp & 0xFF) << 23) | frac


def main():
    total = 0
    fails = 0
    for scale_e in range(256):
        # golden: build a block where lane i has code (i & 0xF); check all lanes.
        codes = [(i & 0xF) for i in range(32)]
        g = decode_block(codes, scale_e)
        for i in range(32):
            r = rtl_lane(codes[i], scale_e)
            total += 1
            if r != g[i]:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH scale_e={scale_e} lane={i} code={codes[i]:#x} "
                          f"golden={g[i]:#010x} rtl={r:#010x}")
    print(f"exhaustive (16 codes x 256 scales x 32 lanes) = {total} points, fails={fails}")
    if fails == 0:
        print("RESULT: golden == rtl-bitmodel, 0 diffs (SW-equivalence)")
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
