"""Reference for BNF16: the binary-exponent sibling of TNF16.

The paper's own definition is that BNF and TNF differ in one thing -- the radix
of the exponent field -- and nothing else. TNF16 carries four trits in a seven-bit
field with nine mantissa bits, 1 + 7 + 9 = 17 stored. BNF16 is therefore a
seven-bit binary exponent with nine mantissa bits, the same 17.

The module that had been measured was 1 + 7 + 8 = 16, one mantissa bit short --
the same defect TNF16's module carried, and it survived for the same reason:
there was no reference to disagree with.
"""
import math
from fractions import Fraction

EXP_BITS = 7
MANT_BITS = 9
MANT = 1 << MANT_BITS
BIAS = (1 << (EXP_BITS - 1)) - 1        # 63
EXP_MAX = (1 << EXP_BITS) - 1           # 127, reserved
WIDTH = 1 + EXP_BITS + MANT_BITS        # 17


def _pow2(k: int) -> Fraction:
    return Fraction(1 << k) if k >= 0 else Fraction(1, 1 << -k)


def decode(raw: int):
    sign = (raw >> (WIDTH - 1)) & 1
    e = (raw >> MANT_BITS) & EXP_MAX
    m = raw & (MANT - 1)
    if e == EXP_MAX:
        return math.nan if m else (-math.inf if sign else math.inf)
    if e == 0:
        return Fraction(0)
    val = (Fraction(1) + Fraction(m, MANT)) * _pow2(e - BIAS)
    return -val if sign else val
