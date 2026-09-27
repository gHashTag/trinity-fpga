"""fpga/tnet/tnf16_core.v in Python, stage for stage. Not a reference: tnf_ref.py is.

It exists for two reasons. The datapath is narrow (3 guard bits and a jammed sticky bit
instead of an exact wide sum), and that choice is checked here against tnf_ref over every
board request before any Verilog is trusted. And the host's --self-test uses it as the
device on the other end of a fake serial port.

Add: order the operands by magnitude, shift the smaller right by the offset difference
into a 15-bit field (12 significand bits + 3), OR every bit shifted out into bit 0, add or
subtract, normalise to bit 15, round to nearest even. A jammed sum is odd whenever it is
inexact, so it can never sit on a tie and is on the same side of every rounding boundary
as the exact sum. Mul: the 24-bit product is exact.
"""
from tnf16_board_params import SPEC

M = SPEC["MANT_BITS"]
SIGN_SHIFT = SPEC["SIGN_SHIFT"]
EXP_SHIFT = SPEC["EXP_SHIFT"]
OFF_MASK = SPEC["OFF_CODES"] - 1
MANT_MASK = SPEC["MANT_SCALE"] - 1
OFFSET_MAX = SPEC["OFFSET_MAX"]
EXP_OFFSET = SPEC["EXP_OFFSET"]
NAN = SPEC["CANON_NAN"]
HIDDEN = 1 << M
G = SPEC["GUARD_BITS"]     # guard bits below the significand
AW = M + 1 + G             # aligned width, 15
DW = AW + 1                # sum width, 16


def fields(w):
    return (w >> SIGN_SHIFT) & 1, (w >> EXP_SHIFT) & OFF_MASK, w & MANT_MASK


def pack(is_zero, sign, off, mant, rbit, sticky, uf_zero):
    inf = (sign << SIGN_SHIFT) | (OFFSET_MAX << EXP_SHIFT)
    if is_zero:
        return 0
    if off >= OFFSET_MAX:
        return inf
    if off < 1:
        return (sign << SIGN_SHIFT) | (0 if uf_zero else 1 << EXP_SHIFT)
    m = mant + (1 if rbit and (sticky or mant & 1) else 0)
    if m == HIDDEN:
        m, off = 0, off + 1
        if off >= OFFSET_MAX:
            return inf
    return (sign << SIGN_SHIFT) | (off << EXP_SHIFT) | m


def add(a, b):
    sa, oa, ma = fields(a)
    sb, ob, mb = fields(b)
    if oa == OFFSET_MAX or ob == OFFSET_MAX:
        return NAN
    ka = (oa << M) | ma if oa else 0
    kb = (ob << M) | mb if ob else 0
    if ka >= kb:
        sl, ol, ml, ss, os_, ms = sa, oa, ma, sb, ob, mb
    else:
        sl, ol, ml, ss, os_, ms = sb, ob, mb, sa, oa, ma
    sig_l = HIDDEN | ml if ol else 0
    sig_s = HIDDEN | ms if os_ else 0
    d = ol - os_
    full = sig_s << G
    if d >= AW:
        a_s, lost = 0, full != 0
    else:
        a_s, lost = full >> d, (full & ((1 << d) - 1)) != 0
    a_s |= int(lost)
    a_l = sig_l << G
    s = a_l - a_s if sl != ss else a_l + a_s
    if s == 0:
        return pack(True, 0, 0, 0, 0, 0, 0)
    p = s.bit_length() - 1
    n = s << (DW - 1 - p)
    mant = (n >> (DW - 1 - M)) & MANT_MASK
    rbit = (n >> (DW - 2 - M)) & 1
    sticky = (n & ((1 << (DW - 2 - M)) - 1)) != 0
    off = p + ol - (AW - 1)
    uf_zero = ol <= AW - 1 and s <= 1 << (AW - 1 - ol)
    return pack(False, sl, off, mant, rbit, sticky, uf_zero)


def mul(a, b):
    sa, oa, ma = fields(a)
    sb, ob, mb = fields(b)
    if oa == OFFSET_MAX or ob == OFFSET_MAX:
        return NAN
    if oa == 0 or ob == 0:
        return pack(True, 0, 0, 0, 0, 0, 0)
    prod = (HIDDEN | ma) * (HIDDEN | mb)          # 2^22 <= prod < 2^24
    top = prod >> (2 * M + 1)
    n = prod if top else prod << 1
    mant = (n >> (M + 1)) & MANT_MASK
    rbit = (n >> M) & 1
    sticky = (n & ((1 << M) - 1)) != 0
    # |x| = prod * 2^(oa + ob - 2 * (EXP_OFFSET + M)); its offset is floor_log2 + EXP_OFFSET.
    bias = 2 * M + EXP_OFFSET
    off = 2 * M + top + oa + ob - bias
    # Only read when off < 1, where k >= 2 * M: |x| <= 2^-EXP_OFFSET iff prod <= 2^k.
    k = bias - oa - ob
    uf_zero = k >= 2 * M + 2 or (k >= 0 and prod <= 1 << k)
    return pack(False, sa ^ sb, off, mant, rbit, sticky, uf_zero)


def compute(op, a, b):
    if op == SPEC["OP_ADD"]:
        return add(a, b)
    if op == SPEC["OP_MUL"]:
        return mul(a, b)
    return None
