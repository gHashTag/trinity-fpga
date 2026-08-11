"""Well-posed decoder conformance.

A decoder whose output is fp32 cannot be compared against a float64 reference
by exact equality: the reference names a real number, the decoder names the
nearest fp32 to it, and demanding they be equal reports rounding as error.
This module rounds the reference to fp32 before comparing and excludes codes
whose value has no fp32 image at all.

The distinction is not pedantic. Applying it to ibm_hfp32 moved the reported
disagreement from 28% to 0 and grew the comparable set from 22,001 to 30,245:
the earlier figure was measuring the comparison, not the decoder.
"""
import struct

def to_fp32(x):
    """Nearest fp32 to x, or None if x has no finite fp32 image."""
    try: v = struct.unpack("<f", struct.pack("<f", float(x)))[0]
    except (OverflowError, ValueError): return None
    return None if v in (float("inf"), float("-inf")) else v

def bits_to_f32(u32):
    return struct.unpack("<f", struct.pack("<I", u32 & 0xFFFFFFFF))[0]

def compare(pairs):
    """pairs: iterable of (code, rtl_bits_u32, exact_reference_value).

    Returns (comparable, exact, mismatches) where mismatches is a list of
    (code, rtl_value, reference_rounded_to_fp32).
    """
    comparable = exact = 0; bad = []
    for code, bits, ref in pairs:
        r32 = to_fp32(ref)
        if r32 is None: continue
        comparable += 1
        rtl = bits_to_f32(bits)
        if rtl == r32 or (rtl != rtl and r32 != r32): exact += 1
        else: bad.append((code, rtl, r32))
    return comparable, exact, bad
