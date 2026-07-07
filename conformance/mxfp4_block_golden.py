#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# mxfp4_block_golden.py -- golden oracle for the MXFP4 *block* decoder.
#
# OCP Microscaling MXFP4 block = 32 x E2M1 elements + 1 shared E8M0 scale.
#   block_value[i] = decode_E2M1(element[i]) * X,  where X = 2^(scale_e - 127)
#
# This is the true mxfp4 novelty: the single-element decoder (fp4_decode) is
# bit-identical to the already-proven fp4_e2m1 cell (Tier-E #199 c4863304724),
# so it adds NO new decode-HW cell. The block scaling below is the part that has
# no prior RTL -> horizon B candidate.
#
# Scale application is a pure power-of-two, so the reference (and the RTL) apply
# it by adding (scale_e - 127) to the FP32 exponent of the decoded element,
# with subnormal/zero handled exactly. No general multiplier is required.
#
# Element grid (E2M1, bias=1, 16 codes) -- verbatim from SSOT
#   conformance/vectors/mxfp4_e2m1_conformance_v0.json.
import struct

# 16-entry E2M1 -> FP32 LUT (bit-for-bit == fpga/openxc7-synth/fp4_decode.v)
FP4_E2M1_BITS = {
    0x0: 0x00000000, 0x1: 0x3F000000, 0x2: 0x3F800000, 0x3: 0x3FC00000,
    0x4: 0x40000000, 0x5: 0x40400000, 0x6: 0x40800000, 0x7: 0x40C00000,
    0x8: 0x80000000, 0x9: 0xBF000000, 0xA: 0xBF800000, 0xB: 0xBFC00000,
    0xC: 0xC0000000, 0xD: 0xC0400000, 0xE: 0xC0800000, 0xF: 0xC0C00000,
}


def fp32_bits_to_float(b):
    return struct.unpack('<f', struct.pack('<I', b & 0xFFFFFFFF))[0]


def float_to_fp32_bits(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def decode_element(code4):
    """E2M1 4-bit code -> FP32 bit pattern (single element, no scale)."""
    return FP4_E2M1_BITS[code4 & 0xF]


def apply_scale_bits(elem_bits, scale_e):
    """Apply E8M0 shared scale X = 2^(scale_e-127) to an FP32 element by
    exponent-add. Returns FP32 bits. Mirrors the RTL exactly.

    E8M0 rules (OCP MX): 0x00 -> 2^-127; 0xFF -> NaN (whole block poisoned).
    """
    if scale_e == 0xFF:
        return 0x7FC00000  # block scale NaN -> element result is NaN
    sign = elem_bits & 0x80000000
    exp = (elem_bits >> 23) & 0xFF
    frac = elem_bits & 0x7FFFFF
    # Zero element stays zero regardless of scale.
    if exp == 0 and frac == 0:
        return elem_bits
    shift = scale_e - 127  # signed power-of-two exponent
    new_exp = exp + shift
    # Element grid has no subnormals in the LUT above (0.5 encoded as normal
    # 0x3F000000), so element exp is always in [126,129]. Clamp to FP32 range.
    if new_exp <= 0:
        # Underflow to signed zero (flush; block grid is coarse, this is the
        # documented behaviour for the coarse MX grid under extreme scales).
        return sign
    if new_exp >= 0xFF:
        # Overflow to signed Inf.
        return sign | 0x7F800000
    return sign | (new_exp << 23) | frac


def decode_block(elements, scale_e):
    """elements: iterable of 32 4-bit codes; scale_e: 8-bit E8M0 exponent.
    Returns list of 32 FP32 bit patterns."""
    assert len(elements) == 32, "MX block is exactly 32 elements"
    out = []
    for c in elements:
        eb = decode_element(c)
        out.append(apply_scale_bits(eb, scale_e))
    return out


def _selftest():
    # scale_e = 127 -> X = 1.0 -> identity vs element decode.
    for c in range(16):
        assert decode_block([c] * 32, 127)[0] == decode_element(c), c
    # scale_e = 128 -> X = 2.0 -> +1.0 element (0x2) becomes +2.0 (0x40000000).
    assert decode_block([0x2] * 32, 128)[0] == 0x40000000
    # scale_e = 126 -> X = 0.5 -> +2.0 element (0x4) becomes +1.0 (0x3F800000).
    assert decode_block([0x4] * 32, 126)[0] == 0x3F800000
    # zero element stays zero under any scale.
    assert decode_block([0x0] * 32, 130)[0] == 0x00000000
    assert decode_block([0x8] * 32, 130)[0] == 0x80000000  # -0.0 stays -0.0
    # NaN scale poisons every lane.
    assert all(v == 0x7FC00000 for v in decode_block(list(range(16)) + list(range(16)), 0xFF))
    # sanity on float values
    assert abs(fp32_bits_to_float(decode_block([0x7] * 32, 128)[0]) - 12.0) < 1e-6  # 6.0*2
    print("mxfp4_block_golden self-test: OK")


if __name__ == '__main__':
    _selftest()
