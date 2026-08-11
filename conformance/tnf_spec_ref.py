"""Reference for TNF32 and TNF64 at their specified parameters.

The paper's width table gives TNF32 as E_t = 6, M = 25 and TNF64 as E_t = 7,
M = 52. The RTL that had been measured for both implemented something else --
twelve trits and eleven mantissa bits for TNF32, twenty-four and twenty-four for
TNF64 -- and held ranks three and four of the throughput table on those numbers.

There was no reference for either, which is why the divergence survived. This is
that reference, derived from the specification rather than from the RTL, so the
two can disagree.
"""
import math
from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class TNFSpec:
    name: str
    et: int          # exponent trits
    mant_bits: int

    @property
    def off_bits(self) -> int:
        return math.ceil(self.et * math.log2(3))

    @property
    def offset_max(self) -> int:
        return 3 ** self.et - 1

    @property
    def exp_offset(self) -> int:
        return (3 ** self.et - 1) // 2

    @property
    def mant(self) -> int:
        return 1 << self.mant_bits

    @property
    def width(self) -> int:
        return 1 + self.off_bits + self.mant_bits


FORMATS = {
    "tnf8":  TNFSpec("tnf8",  et=3, mant_bits=4),
    "tnf16": TNFSpec("tnf16", et=4, mant_bits=9),
    "tnf32": TNFSpec("tnf32", et=6, mant_bits=25),
    "tnf64": TNFSpec("tnf64", et=7, mant_bits=52),
    # Two candidate rungs that fill exactly 16 stored bits, so the catalogue
    # has a width class where one of ours meets binary16 head-on.
    "tnf16a": TNFSpec("tnf16a", et=4, mant_bits=8),
    "tnf16b": TNFSpec("tnf16b", et=3, mant_bits=10),
    # E_t=5 wastes only 5.08% of its binary field against E_t=4's 36.7%, because
    # 3^5=243 sits just under 2^8. The ladder's natural rungs on binary fabric
    # are the k where 3^k comes closest to a power of two from below.
    "tnf16c": TNFSpec("tnf16c", et=5, mant_bits=7),
}


def _pow2(k: int) -> Fraction:
    return Fraction(1 << k) if k >= 0 else Fraction(1, 1 << -k)


def decode(fmt: TNFSpec, raw: int):
    sign = (raw >> (fmt.width - 1)) & 1
    off = (raw >> fmt.mant_bits) & ((1 << fmt.off_bits) - 1)
    m = raw & (fmt.mant - 1)
    if off == fmt.offset_max:
        return math.nan if m else (-math.inf if sign else math.inf)
    if off == 0:
        return Fraction(0)
    val = (Fraction(1) + Fraction(m, fmt.mant)) * _pow2(off - fmt.exp_offset)
    return -val if sign else val
