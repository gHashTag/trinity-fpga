#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
decimal_ref.py — REFERENCE (golden) oracle for the IEEE 754 decimal BID family.
  decimal32, decimal64, decimal128 (Binary Integer Decimal).

BID encoding (IEEE 754-2008): sign + combination + coefficient C (binary int).
  value = (-1)^s * C * 10^(E - bias)
  Case A (C < 2^M_small): combination top2 != 11; E = exp field, C = lower bits.
  Case B (C in [2^M_small, 2^M_big)): combination top2 == 11, top4 != 1111;
           C = implicit "100" MSBs | lower bits.
  Specials: top4 == 11110 -> Inf ; top4 == 11111 -> NaN.

Coefficient and exponent are exact integers; 10^(E-bias) is an integer power of 10,
so value = C * 10^(E-bias) is EXACTLY representable as a Fraction (int/int).
Round-ties-even on encode (the nearest C is chosen). Patterned on gf_ref.py.

Consistent with conformance/decimal64_decode_conformance_ax7203.py (BID decode).

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class DecimalFormat:
    name: str
    width: int
    exp_bits: int        # width of biased exponent field
    coeff_bits_small: int  # M_small: coefficient bits in case A (C < 2^M_small)
    coeff_bits_big: int    # M_big:   coefficient bits in case B
    bias: int            # E_unbiased = E_field - bias
    max_coeff: int       # maximum representable coefficient (decimal digit count)

    @property
    def mask(self): return (1 << self.width) - 1
    @property
    def sign_shift(self): return self.width - 1
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self): return 1 << self.sign_shift
    @property
    def exp_max(self): return (1 << self.exp_bits) - 1
    @property
    def pos_inf(self):
        # bits [width-2 : width-6] = 11110  (5-bit special tag below sign)
        return (0b11110 << (self.width - 6)) & self.mask
    @property
    def neg_inf(self):
        return self.pos_inf | (1 << self.sign_shift)
    @property
    def quiet_nan(self):
        # bits [width-2 : width-6] = 11111
        return (0b11111 << (self.width - 6)) & self.mask


# IEEE 754-2008 BID parameters.
FORMATS = {
    "decimal32":  DecimalFormat("decimal32",  width=32,  exp_bits=8,
                                coeff_bits_small=23, coeff_bits_big=24, bias=101,
                                max_coeff=9999999),        # 7 digits
    "decimal64":  DecimalFormat("decimal64",  width=64,  exp_bits=10,
                                coeff_bits_small=53, coeff_bits_big=54, bias=398,
                                max_coeff=9999999999999999),  # 16 digits
    "decimal128": DecimalFormat("decimal128", width=128, exp_bits=14,
                                coeff_bits_small=113, coeff_bits_big=114, bias=6176,
                                max_coeff=10**34 - 1),         # 34 digits
}


class Special:
    def __init__(self, kind, sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        if self.kind == "nan":
            return "NaN"
        return ("-" if self.sign else "+") + "Inf"


def pow10(e: int):
    return 10 ** e if e >= 0 else Fraction(1, 10 ** (-e))


def _bid_decode(fmt: DecimalFormat, code: int):
    """Return ('finite', sign, C, E_field) | ('inf', sign) | ('nan', sign)."""
    code &= fmt.mask
    sign = (code >> fmt.sign_shift) & 1
    cf_hi = (code >> (fmt.sign_shift - 2)) & 0x3          # top 2 bits of combination
    if cf_hi != 0b11:                                      # case A
        E = (code >> fmt.coeff_bits_small) & fmt.exp_max
        C = code & ((1 << fmt.coeff_bits_small) - 1)
        return ("finite", sign, C, E)
    cf_top4 = (code >> (fmt.sign_shift - 4)) & 0xF
    if cf_top4 == 0b1111:
        is_nan = (code >> (fmt.sign_shift - 5)) & 1
        return ("nan", sign) if is_nan else ("inf", sign)
    # case B: implicit "100" prefix on coefficient
    E = (code >> fmt.coeff_bits_big - 3) & fmt.exp_max     # exp field right above lower coeff bits
    C = (0b100 << (fmt.coeff_bits_big - 3)) | (code & ((1 << (fmt.coeff_bits_big - 3)) - 1))
    if C > fmt.max_coeff:
        # Non-canonical. IEEE 754-2008 3.5.2: a significand above the format's maximum
        # makes the encoding non-canonical, and its value is zero -- not the number the
        # bits would otherwise spell.
        #
        # Case B is where this bites. decimal32 reaches 2^23 + 2^21 - 1 = 10,485,759 while
        # the format stops at 9,999,999, so 485,760 case-B codes per sign are non-canonical
        # and every one of them decoded here as a number. Case A cannot overflow: its
        # coefficient field is narrower than max_coeff for all three widths.
        #
        # Found in pass 185 from the 35 decimal32 vectors still disagreeing with gcc after
        # the coefficient and exponent-range fixes. gcc returned 0 for a product our
        # decode called 1.08e-61; the operand was a case-B code with C = 10,460,030.
        # The arithmetic was never the problem in these -- the decode was.
        return ("finite", sign, 0, E)
    return ("finite", sign, C, E)


def is_canonical(fmt: DecimalFormat, code: int) -> bool:
    """Does this encoding spell a value, or is it one of the words that decode to zero?

    Needed because making _bid_decode obey 3.5.2 silently killed a guard in a consumer.
    research/verify_decimal_monotonic.py skipped non-canonical codes with
    `if C > fmt.max_coeff: continue` -- reading the coefficient the decoder returned. Once
    the decoder started returning 0 for exactly those codes, the condition could never be
    true again, and 174 of them swept through as genuine zeros and were reported as
    monotonicity violations.

    The guard was right and its evidence disappeared. Callers that need to tell "zero
    because non-canonical" from "zero because the value is zero" must ask here rather than
    infer it from a decode that has, correctly, stopped saying.
    """
    code &= fmt.mask
    if (code >> (fmt.sign_shift - 2)) & 0x3 != 0b11:
        return True                        # case A cannot overflow max_coeff
    if (code >> (fmt.sign_shift - 4)) & 0xF == 0b1111:
        return True                        # infinity or NaN: no coefficient to judge
    C = (0b100 << (fmt.coeff_bits_big - 3)) | (code & ((1 << (fmt.coeff_bits_big - 3)) - 1))
    return C <= fmt.max_coeff


def _bid_encode_fields(fmt: DecimalFormat, sign: int, C: int, E: int) -> int:
    """Pack finite (sign, C, E_field) -> BID code (case A or B)."""
    small_cap = 1 << fmt.coeff_bits_small
    if C < small_cap:
        return ((sign << fmt.sign_shift)
                | ((E & fmt.exp_max) << fmt.coeff_bits_small)
                | C) & fmt.mask
    # case B: C must fit in coeff_bits_big with implicit 100 prefix
    assert (C >> (fmt.coeff_bits_big - 3)) == 0b100, "case B coeff prefix"
    lower_bits = fmt.coeff_bits_big - 3
    return ((sign << fmt.sign_shift)
            | (0b11 << (fmt.sign_shift - 2))
            | ((E & fmt.exp_max) << lower_bits)
            | (C & ((1 << lower_bits) - 1))) & fmt.mask


def decode(fmt: DecimalFormat, raw: int):
    kind = _bid_decode(fmt, raw)
    if kind[0] == "inf":
        return Special("inf", kind[1])
    if kind[0] == "nan":
        return Special("nan", kind[1])
    _, sign, C, E = kind
    if C == 0:
        return Fraction(0)
    de = E - fmt.bias
    val = Fraction(C) * pow10(de)
    return -val if sign else val


def _round_half_even(x: Fraction, cap=None):
    floor_i = x.numerator // x.denominator
    rem = x - floor_i
    half = Fraction(1, 2)
    if rem < half:
        r = floor_i
    elif rem > half:
        r = floor_i + 1
    else:
        r = floor_i if (floor_i % 2 == 0) else floor_i + 1
    if cap is not None and r >= cap:
        return cap, True
    return r, False


def encode(fmt: DecimalFormat, value):
    if isinstance(value, Special):
        if value.kind == "nan":
            return fmt.quiet_nan
        return fmt.neg_inf if value.sign else fmt.pos_inf

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v          # exact positive Fraction

    # value = C * 10^(E - bias), 0 < C <= max_coeff (integer), E in [0, exp_max].
    # Factor a into integer coeff * power of 10. Extract powers of 2 and 5.
    num = a.numerator
    den = a.denominator
    # remove powers of 10 (2*5) from denominator and numerator to get C as integer
    e10 = 0
    # cancel common 2/5 between num and den first (Fraction already reduced, but den
    # may still contain 2s and 5s representing the negative power of 10).
    # decompose denominator into 2^a * 5^b * rest
    def split(n, base):
        k = 0
        while n > 1 and n % base == 0:
            n //= base
            k += 1
        return k, n
    n2, rest = split(den, 2)
    n5, rest = split(rest, 5)
    if rest != 1:
        # denominator has primes other than 2,5 -> value not exactly representable
        # as C * 10^e. Round: choose E to maximize coefficient precision.
        return _encode_round(fmt, sign, a)
    den10 = max(n2, n5)
    # bring to common power of 10: denominator currently 2^n2 * 5^n5, target 10^den10 = 2^den10 * 5^den10
    C = num
    if n2 < den10:
        C *= 2 ** (den10 - n2)    # compensate missing factors of 2 in denominator
    if n5 < den10:
        C *= 5 ** (den10 - n5)    # compensate missing factors of 5 in denominator
    # a = C * 10^(-den10). Pull factors of 10 out of C (minimize C, maximize exponent):
    # C = 10*C'  =>  a = C' * 10^(1-den10), so den10 decreases by 1.
    while C % 10 == 0 and C > 0:
        C //= 10
        den10 -= 1
    E = fmt.bias - den10
    # now value = C * 10^(E - bias). Fold exponent into C while E exceeds range.
    #
    # Against _exp_field_max, not fmt.exp_max. The latter is `(1 << exp_bits) - 1` and is
    # the mask _bid_encode_fields ands with, not the range: BID spends the `11` prefix on
    # case B and the specials, so decimal32 stops at 191, never 255. Comparing against 255
    # let a biased exponent of 215 through, and `E & 255` folded its top two bits into the
    # `11` pattern -- 1607e57 squared, which overflows decimal32 and should be infinity,
    # came back as 0.0887. gcc's BID says +Inf. Found in pass 185 by looking at the 39
    # decimal32 vectors still disagreeing after the coefficient fix.
    e_field_max = _exp_field_max(fmt)
    while E > e_field_max and C * 10 <= fmt.max_coeff:
        C *= 10
        E -= 1
    if E < 0 or E > e_field_max or C > fmt.max_coeff or C == 0:
        return _encode_round(fmt, sign, a)
    return _bid_encode_fields(fmt, sign, C, E)


def _ilog10(a: Fraction) -> int:
    """floor(log10(a)) for a > 0, exactly.

    float(a) loses this for the values that matter: decimal128 spans 10^-6176 to 10^6111
    and float overflows or flushes long before either end. Digit counts get within one,
    and the two comparisons settle which.
    """
    e = len(str(a.numerator)) - len(str(a.denominator))
    if a < pow10(e):
        e -= 1
    elif a >= pow10(e + 1):
        e += 1
    return e


def _exp_field_max(fmt: DecimalFormat) -> int:
    """Largest biased exponent the format can actually encode.

    Not `fmt.exp_max`, which is `(1 << exp_bits) - 1` and is a *mask*, not a range. BID
    spends the `11` combination prefix on case B and on the specials, so only three
    quarters of the field is reachable: 3 * 2^(exp_bits-2) - 1, giving 191 / 767 / 12287.
    Each matches the standard's quantum range exactly -- decimal32 q in [-101, 90] is 192
    values against bias 101, and so on for the other two.

    The +/-3 scan this replaced could emit a biased exponent up to 255 for decimal32. It
    almost never did, because the window stayed near the value's own magnitude, and
    `E & fmt.exp_max` would have quietly folded such a code into the 11 prefix -- an
    infinity or a NaN where a finite number was meant. A search that actually looks for
    the best exponent walks into it immediately.
    """
    return 3 * (1 << (fmt.exp_bits - 2)) - 1


def _encode_round(fmt: DecimalFormat, sign: int, a: Fraction) -> int:
    """Round-to-nearest-even encode of an exact positive Fraction.

    The previous version scanned biased exponents in a +/-3 window around
    log10(value) and kept whichever candidate had the least error. That cannot reach the
    exponent which holds the format's full precision: to place all 34 significant digits
    of a decimal128 into an integer coefficient the exponent must sit up to 34 steps below
    log10(value), and outside the window the closest candidate is a truncated one. Pass
    185 measured it against gcc's Intel BID: 412 of 6,942 vectors, our answers carrying
    four significant digits where decimal32 holds seven.

    There is nothing to search. The exponent that maximises precision is the one that
    makes the coefficient exactly `p` digits, and it is arithmetic:

        e = floor(log10(a)) - (p - 1)

    clamped to the encodable range. Only two things can go wrong afterwards, and both are
    handled rather than searched for: rounding can carry the coefficient to `p + 1` digits
    (9.9999995 -> 10000000), and clamping `e` up at the bottom of the range can round the
    whole value away to zero.
    """
    p = len(str(fmt.max_coeff))              # significant digits: 7, 16, 34
    e_min = -fmt.bias
    e_max = _exp_field_max(fmt) - fmt.bias

    e = _ilog10(a) - (p - 1)
    if e < e_min:
        e = e_min                            # subnormal: fewer than p digits survive
    if e > e_max:
        e = e_max

    C, _ = _round_half_even(a / pow10(e))
    while C > fmt.max_coeff:
        # The carry case. One step is always enough -- 10^p / 10 is 10^(p-1) -- but the
        # loop also covers the clamp above having started too low.
        e += 1
        if e > e_max:
            return fmt.neg_inf if sign else fmt.pos_inf
        C, _ = _round_half_even(a / pow10(e))

    if C == 0:
        # Underflow. Signed zero, not an exception: the sign of a rounded-away value is
        # the sign it had.
        return (sign << fmt.sign_shift)
    return _bid_encode_fields(fmt, sign, C, e + fmt.bias)


def format_add(fmt: DecimalFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) and a.kind == "nan": return fmt.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return fmt.quiet_nan
    if isinstance(a, Special) and a.kind == "inf":
        if isinstance(b, Special) and b.kind == "inf" and b.sign != a.sign:
            return fmt.quiet_nan
        return fmt.neg_inf if a.sign else fmt.pos_inf
    if isinstance(b, Special) and b.kind == "inf":
        return fmt.neg_inf if b.sign else fmt.pos_inf
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    if a == 0 and b == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero
    return encode(fmt, a + b)


def format_mul(fmt: DecimalFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) and a.kind == "nan": return fmt.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return fmt.quiet_nan
    a_inf = isinstance(a, Special) and a.kind == "inf"
    b_inf = isinstance(b, Special) and b.kind == "inf"
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb
    if a_inf or b_inf:
        if a == 0 or b == 0:
            return fmt.quiet_nan
        return fmt.neg_inf if rsign else fmt.pos_inf
    if a == 0 or b == 0:
        return fmt.neg_zero if rsign else fmt.pos_zero
    return encode(fmt, a * b)


def _selftest():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: +0")
        check(encode(fmt, 0) == 0, f"{fname}: encode 0")

        # unity: C=1, E=bias
        one = _bid_encode_fields(fmt, 0, 1, fmt.bias)
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        check(encode(fmt, Fraction(1)) == one, f"{fname}: encode 1")

        # 1 + 1 = 2
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")

        # 2*C + 0 == identity for representible values
        two = format_add(fmt, one, one)
        check(format_add(fmt, two, 0) == two, f"{fname}: x+0==x")

        # Inf / NaN
        check(isinstance(decode(fmt, fmt.pos_inf), Special), f"{fname}: +Inf")
        check(isinstance(decode(fmt, fmt.quiet_nan), Special), f"{fname}: NaN")

        # decimal arithmetic exactness: 0.5 + 0.5 = 1
        half = encode(fmt, Fraction(1, 2))
        check(decode(fmt, format_add(fmt, half, half)) == 1, f"{fname}: 0.5+0.5=1")

    # Pass 185's three regressions run inside the existing self-test rather than beside
    # it. They were first appended as a second `if __name__ == "__main__"` block, which
    # never executed: this one is earlier in the file and exits first. A check nothing can
    # reach is the failure this campaign keeps finding, and it found it here too.
    rc = _regressions_185(check)

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (decimal BID: zero/unity/inf/nan/1+1/0.5+0.5/x+0"
          " + pass-185 precision/range/canonicality)")
    return rc


def _regressions_185(check) -> int:
    """The three defects gcc's Intel BID exposed in pass 185.

    Each is stated as arithmetic that can be redone by hand rather than as a golden word
    copied out of the fix. A regression asserting only what the code currently does would
    pass again the moment the code regresses the same way.
    """
    d32 = FORMATS["decimal32"]
    d128 = FORMATS["decimal128"]

    # 1. Precision. The +/-3 exponent scan could not reach the exponent that puts every
    #    significant digit into the coefficient, so results came back truncated.
    #    decimal32 holds 7; the old code returned 4 here.
    got = _encode_round(d32, 0, Fraction(18809569, 25) / 10 ** 43)
    _, _, C, _ = _bid_decode(d32, got)
    check(len(str(C)) == 7, "185: decimal32 keeps 7 significant digits, not 4")

    # 2. Exponent range. 1607e57 squared is 2.582449e120, above decimal32's largest
    #    finite value, so it must be infinity. Comparing against fmt.exp_max -- a mask of
    #    255 -- rather than the encodable maximum of 191 let a biased exponent of 215
    #    through, and `E & 255` folded its top two bits into the `11` prefix.
    big = _bid_encode_fields(d32, 0, 1607, 57 + d32.bias)
    check(format_mul(d32, big, big) == d32.pos_inf,
          "185: decimal32 overflow gives infinity")

    # 3. Canonicality. Case B reaches a coefficient of 10,460,030 while decimal32 stops
    #    at 9,999,999. IEEE 754-2008 3.5.2 makes such an encoding non-canonical with
    #    value zero, and gcc's BID agrees.
    check(decode(d32, 0x6A1F9D7E) == 0,
          "185: non-canonical case-B coefficient decodes as zero")
    check(decode(d32, _bid_encode_fields(d32, 0, d32.max_coeff, d32.bias))
          == d32.max_coeff,
          "185: the largest canonical coefficient still decodes")

    check(not is_canonical(d32, 0x6A1F9D7E),
          "185: is_canonical rejects the case-B code that decodes to zero")
    check(is_canonical(d32, encode(d32, Fraction(0))),
          "185: is_canonical accepts a genuine zero")

    # 4. The range constant matches the standard's quantum range for all three widths.
    for name, lo, hi in (("decimal32", -101, 90), ("decimal64", -398, 369),
                         ("decimal128", -6176, 6111)):
        f = FORMATS[name]
        check((-f.bias, _exp_field_max(f) - f.bias) == (lo, hi),
              f"185: {name} exponent range is [{lo}, {hi}]")

    # 5. A value needing an exponent far outside any small window round-trips exactly.
    v = Fraction(10 ** 34 - 1, 10 ** 34)
    check(decode(d128, encode(d128, v)) == v,
          "185: decimal128 round-trips a 34-digit value exactly")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
