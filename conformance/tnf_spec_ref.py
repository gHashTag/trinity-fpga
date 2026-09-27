"""Reference for TNF32 and TNF64 at their specified parameters.

The paper's width table gives TNF32 as E_t = 6, M = 25 and TNF64 as E_t = 7,
M = 52. The RTL that had been measured for both implemented something else --
twelve trits and eleven mantissa bits for TNF32, twenty-four and twenty-four for
TNF64 -- and held ranks three and four of the throughput table on those numbers.

There was no reference for either, which is why the divergence survived. This is
that reference, derived from the specification rather than from the RTL, so the
two can disagree.

GRID NOTICE (2026-09-27): the offset field is off_bits wide and 2^off_bits >
3^et, so a raw code can carry an offset above offset_max. Such a code is not a
TNF word, and decode() raises ValueError on it; is_word() filters an
enumeration of raw codes. Until this date decode() read those codes as ordinary
powers of two. The long form, with the counts, is the GRID NOTICE in tnf_ref.py.
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
}


def _pow2(k: int) -> Fraction:
    return Fraction(1 << k) if k >= 0 else Fraction(1, 1 << -k)


def is_word(fmt: TNFSpec, raw: int) -> bool:
    """True when the offset field holds a trit offset (0 .. offset_max)."""
    return ((raw >> fmt.mant_bits) & ((1 << fmt.off_bits) - 1)) <= fmt.offset_max


def decode(fmt: TNFSpec, raw: int):
    sign = (raw >> (fmt.width - 1)) & 1
    off = (raw >> fmt.mant_bits) & ((1 << fmt.off_bits) - 1)
    m = raw & (fmt.mant - 1)
    if off > fmt.offset_max:
        raise ValueError(f"not a TNF word: offset {off} > offset_max "
                         f"{fmt.offset_max} in {fmt.name} (raw {raw:#x})")
    if off == fmt.offset_max:
        return math.nan if m else (-math.inf if sign else math.inf)
    if off == 0:
        return Fraction(0)
    val = (Fraction(1) + Fraction(m, fmt.mant)) * _pow2(off - fmt.exp_offset)
    return -val if sign else val


def _selftest():
    """Only trit offsets are words: count them and check decode refuses the rest.

    tnf8 and tnf16 are enumerated code by code; tnf32 and tnf64 are counted by
    field, with decode probed at the boundary offsets. A word count is
    2 * (offset_max + 1) * 2^M; finite non-zero words are 2 * (offset_max - 1) * 2^M.
    """
    want = {"tnf8": (864, 800), "tnf16": (82944, 80896)}
    for name, (want_words, want_finite) in want.items():
        f = FORMATS[name]
        words = finite = refused = 0
        for raw in range(1 << f.width):
            if not is_word(f, raw):
                try:
                    decode(f, raw)
                except ValueError:
                    refused += 1
                    continue
                raise AssertionError(f"decode accepted non-word {raw:#x} in {name}")
            words += 1
            v = decode(f, raw)
            if isinstance(v, Fraction) and v != 0:
                finite += 1
        assert words == want_words, (name, words, want_words)
        assert finite == want_finite, (name, finite, want_finite)
        assert refused == (1 << f.width) - words, (name, refused)
        print(f"  {name} {f.width}b: {words} words ({finite} finite non-zero), "
              f"{refused} non-word codes refused")
    for name in ("tnf32", "tnf64"):
        f = FORMATS[name]
        words = 2 * (f.offset_max + 1) * f.mant
        one = f.exp_offset << f.mant_bits
        assert decode(f, one) == 1 and decode(f, (1 << (f.width - 1)) | one) == -1
        assert decode(f, f.offset_max << f.mant_bits) == math.inf
        for off in (f.offset_max + 1, (1 << f.off_bits) - 1):
            try:
                decode(f, off << f.mant_bits)
            except ValueError:
                continue
            raise AssertionError(f"decode accepted offset {off} in {name}")
        print(f"  {name} {f.width}b: {words} of {1 << f.width} codes are words "
              f"(by field count); offsets above {f.offset_max} refused")
    print("tnf_spec_ref SELF-TEST: PASS")


if __name__ == "__main__":
    _selftest()
