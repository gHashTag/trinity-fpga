#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legacy_ref.py — REFERENCE (golden) oracle for legacy floating-point formats.
  vax_f, vax_d, vax_g, vax_h        — DEC VAX (base 2, hidden 1, bias 128/1024/16384)
  ibm_hfp32, ibm_hfp64, ibm_hfp128   — IBM hex FP (base 16, no hidden bit, bias 64)
  cray_float                         — Cray-1 (base 2, explicit leading 1, bias 16384)
  pdp11_float                        — PDP-11 F (predecessor of VAX F, bias 128)
  x87_fp80                           — Intel 80-bit extended (explicit integer bit, bias 16383)
  x87_48bit                          — 48-bit x87-style truncated (bias 16383)

Each format has its own encoding rule; shared by all: round-ties-even and exact
Fraction arithmetic. Patterned on gf_ref.py.

Consistent with conformance/ibm_hfp32_decode_conformance_ax7203.py and
conformance/vax_f_decode_conformance_ax7203.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyFormat:
    name: str
    width: int
    kind: str               # 'vax' | 'ibm' | 'cray' | 'x87' | 'mbf'
    exp_bits: int
    mant_bits: int
    bias: int
    base: int = 2           # 2 or 16
    explicit_int_bit: bool = False   # Cray/x87: leading bit explicit (no hidden)
    min_exp_field: int = 1  # exp fields below this are reserved (flush to zero)
                             # VAX=1, MBF=3 (Microsoft Binary Format reserves 0..2)

    @property
    def mask(self): return (1 << self.width) - 1
    @property
    def sign_shift(self): return self.width - 1
    @property
    def exp_max(self): return (1 << self.exp_bits) - 1
    @property
    def mant_max(self): return (1 << self.mant_bits) - 1
    @property
    def mant_shift(self): return 0   # mantissa occupies low bits
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self):
        # VAX has no negative zero, and neither does its PDP-11 ancestor. The VAX
        # Architecture Reference Manual defines sign 1 with a zero exponent as the
        # *reserved operand*: it does not name a number, it faults. Exponent 0 with sign 0
        # is true zero whatever the fraction holds.
        #
        # Handing that pattern out as "neg_zero" put it in the published legend of 15
        # packs and, worse, made it the ANSWER to 467 vectors -- the corpus asserted that
        # certain VAX additions produce a value real VAX hardware traps on.
        #
        # AttributeError rather than a raise, so `getattr(fmt, "neg_zero", None)` -- how
        # generate_vectors.real_specials probes -- gets its default and simply omits it.
        if self.kind == 'vax':
            raise AttributeError(f"{self.name} has no negative zero: sign 1 with a "
                                 f"zero exponent is the reserved operand")
        return 1 << self.sign_shift
    @property
    def quiet_nan(self):
        # VAX, IBM HFP, MBF and Cray have no NaN at all, so a reserved pattern is as good
        # a marker as any and nothing decodes it back.
        #
        # x87 does have one, and this pattern was not it: with the explicit integer bit
        # clear, exp all-ones is a *pseudo*-NaN -- an invalid operand every x87 since the
        # 80387 refuses, not a quiet NaN. A real one sets the integer bit and the leading
        # fraction bit. It went unnoticed while decode() had no notion of x87 specials to
        # read it back with.
        if self.kind == 'x87':
            return (self.exp_max << self.mant_bits) | (0b11 << (self.mant_bits - 2))
        return (self.exp_max << self.mant_bits) | 1

    @property
    def pos_inf(self):
        # Only x87 has one. Asking any other legacy format for an infinity is a bug in
        # the caller, and saturating quietly would hide it.
        # AttributeError, not AssertionError, so `getattr(fmt, "pos_inf", None)` --
        # how generate_vectors.real_specials probes -- gets its default instead of an
        # exception. Asking VAX or IBM HFP for an infinity is still a bug; it is just a
        # bug the probing idiom is allowed to ask about.
        if self.kind != 'x87':
            raise AttributeError(f"{self.name} has no infinity")
        return (self.exp_max << self.mant_bits) | (1 << (self.mant_bits - 1))

    @property
    def neg_inf(self):
        return (1 << self.sign_shift) | self.pos_inf


FORMATS = {
    "vax_f":       LegacyFormat("vax_f",       width=32,  kind='vax',  exp_bits=8,  mant_bits=23, bias=128),
    "vax_d":       LegacyFormat("vax_d",       width=64,  kind='vax',  exp_bits=8,  mant_bits=55, bias=128),
    "vax_g":       LegacyFormat("vax_g",       width=64,  kind='vax',  exp_bits=11, mant_bits=52, bias=1024),
    "vax_h":       LegacyFormat("vax_h",       width=128, kind='vax',  exp_bits=15, mant_bits=112, bias=16384),
    "ibm_hfp32":   LegacyFormat("ibm_hfp32",   width=32,  kind='ibm',  exp_bits=7,  mant_bits=24, bias=64, base=16),
    "ibm_hfp64":   LegacyFormat("ibm_hfp64",   width=64,  kind='ibm',  exp_bits=7,  mant_bits=56, bias=64, base=16),
    "ibm_hfp128":  LegacyFormat("ibm_hfp128",  width=128, kind='ibm',  exp_bits=7,  mant_bits=120, bias=64, base=16),
    "cray_float":  LegacyFormat("cray_float",  width=64,  kind='cray', exp_bits=15, mant_bits=48, bias=16384, explicit_int_bit=True),
    "pdp11_float": LegacyFormat("pdp11_float", width=32,  kind='vax',  exp_bits=8,  mant_bits=23, bias=128),
    "x87_fp80":    LegacyFormat("x87_fp80",    width=80,  kind='x87',  exp_bits=15, mant_bits=64, bias=16383, explicit_int_bit=True),
    "x87_48bit":   LegacyFormat("x87_48bit",   width=48,  kind='x87',  exp_bits=15, mant_bits=32, bias=16383, explicit_int_bit=True),
    # Microsoft Binary Format (pre-IEEE, bias=129). exp_field 0..2 reserved (zero).
    # Matches conformance/ms_mbf32_decode_conformance_ax7203.py:golden_mbf32.
    "ms_mbf32":    LegacyFormat("ms_mbf32",    width=32,  kind='mbf',  exp_bits=8,  mant_bits=23, bias=129, min_exp_field=3),
    "ms_mbf64":    LegacyFormat("ms_mbf64",    width=64,  kind='mbf',  exp_bits=8,  mant_bits=55, bias=129, min_exp_field=3),
}


class Special:
    def __init__(self, kind="nan", sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        return "NaN" if self.kind == "nan" else ("-" if self.sign else "+") + "Inf"


def pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def ilog2_base(a: Fraction, base: int) -> int:
    """floor(log_base(a)) for an exact positive Fraction (base 2 or 16)."""
    assert a > 0
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < pow2(e):
        e -= 1
    while Fraction(n, d) >= pow2(e + 1):
        e += 1
    if base == 2:
        return e
    # base 16: floor(log16(a)) = floor(log2(a) / 4)  (Python // floors toward -inf)
    return e // 4


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


def decode(fmt: LegacyFormat, raw: int):
    raw &= fmt.mask
    if raw == 0:
        return Fraction(0)

    sign = (raw >> fmt.sign_shift) & 1
    exp = (raw >> fmt.mant_bits) & fmt.exp_max
    mant = raw & fmt.mant_max

    if fmt.kind == 'ibm':
        if exp == 0:
            return Fraction(0)
        value = Fraction(mant, 1 << fmt.mant_bits) * (Fraction(fmt.base) ** (exp - fmt.bias))
        return -value if sign else value

    if fmt.kind in ('vax', 'mbf'):
        min_e = getattr(fmt, 'min_exp_field', 1)
        if exp < min_e:
            return Fraction(0)        # VAX/MBF reserves exp<min_exp_field for zero
        value = (1 + Fraction(mant, 1 << fmt.mant_bits)) * pow2(exp - fmt.bias)
        return -value if sign else value

    if fmt.kind in ('cray', 'x87'):
        # x87 is IEEE 754 double-extended, not a legacy format in the sense the rest of
        # this module means. _sat_raw's comment -- "legacy formats have no Inf" -- is true
        # of VAX, IBM HFP, MBF and Cray and was carried one format too far. Without this
        # branch the all-ones exponent decoded as an ordinary exponent, so +Inf came back
        # as 2^16384 (a 4,933-digit integer) and every NaN came back as a number.
        #
        # The corpus already disagreed with itself about this:
        # conformance/x87_fp80_decode_conformance_ax7203.py maps exp == 0x7FFF to a quiet
        # NaN, which is right. Only the oracle behind the arithmetic packs did not.
        #
        # Nothing in the packs had to change to hide it. edge_raws builds its edge codes
        # through this decoder, so a format whose specials are unimplemented cannot
        # produce a special edge, and 0 of 3,792 x87 vectors touched an all-ones exponent.
        # The coverage looked complete because the missing piece was also the piece that
        # would have shown it missing.
        if fmt.kind == 'x87' and exp == fmt.exp_max:
            int_bit = (mant >> (fmt.mant_bits - 1)) & 1
            frac = mant & ((1 << (fmt.mant_bits - 1)) - 1)
            if int_bit == 0:
                # pseudo-infinity and pseudo-NaN: the 80387 and everything after it
                # rejects these as invalid operands rather than reading a value.
                return Special("nan", sign)
            return Special("nan", sign) if frac else Special("inf", sign)
        if fmt.kind == 'x87' and exp == 0:
            if mant == 0:
                return Fraction(0)
            value = Fraction(mant, 1 << (fmt.mant_bits - 1)) * pow2(1 - fmt.bias)
            return -value if sign else value
        value = Fraction(mant, 1 << (fmt.mant_bits - 1)) * pow2(exp - fmt.bias)
        return -value if sign else value

    raise ValueError(fmt.kind)


def _signed_zero(fmt: LegacyFormat, sign: int) -> int:
    """A zero of the given sign, or the only zero the format has.

    VAX and PDP-11 have exactly one. Returning `neg_zero` for them produced the reserved
    operand as an arithmetic result, which is a fault on hardware and was the answer to
    467 vectors."""
    if fmt.kind == 'vax' or not sign:
        return fmt.pos_zero
    return fmt.neg_zero


def is_canonical(fmt: LegacyFormat, raw: int) -> bool:
    """Does this encoding spell a value its format actually defines?

    Added for the same reason as decimal_ref.is_canonical in pass 185: a consumer that
    needs to tell "the decoder returned zero because the value is zero" from "because the
    encoding is not a value" must be able to ask, not infer.

    Per format:

      x87       an explicit integer bit that contradicts the exponent. exp != 0 with the
                integer bit clear is an *unnormal*; exp all-ones with it clear is a
                pseudo-infinity or pseudo-NaN. The 80387 and every x87 since raise
                invalid-operand on all of them. exp == 0 with the bit set is a
                pseudo-denormal, which hardware *does* evaluate, so it stays canonical.
      vax/pdp11 sign 1 with exponent 0 is the VAX reserved operand -- a trap, not a
                number. Its PDP-11 ancestor calls the same encoding an undefined variable.
      cray/ibm/mbf  every encoding denotes a value.

    Deliberately not merged into decode(): decode answers "what number is this", and for
    a non-value the honest answer is not another number.
    """
    raw &= fmt.mask
    sign = (raw >> fmt.sign_shift) & 1
    exp = (raw >> fmt.mant_bits) & fmt.exp_max
    mant = raw & fmt.mant_max

    if fmt.kind == 'x87':
        int_bit = (mant >> (fmt.mant_bits - 1)) & 1
        if exp == 0:
            return True                      # zero, denormal, or pseudo-denormal
        return int_bit == 1                  # unnormal / pseudo-inf / pseudo-NaN
    if fmt.kind == 'vax':
        return not (sign == 1 and exp == 0)  # reserved operand / undefined variable
    return True


def _sat_raw(fmt: LegacyFormat, sign: int) -> int:
    """Saturate to max-magnitude finite (legacy formats have no Inf)."""
    sat = (fmt.exp_max << fmt.mant_bits) | fmt.mant_max
    return ((1 << fmt.sign_shift) | sat) if sign else sat


def encode(fmt: LegacyFormat, value):
    if isinstance(value, Special):
        if fmt.kind == 'x87' and value.kind == "inf":
            return fmt.neg_inf if value.sign else fmt.pos_inf
        return fmt.quiet_nan

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v

    if fmt.kind == 'ibm':
        # value = (F/2^M) * 16^(E-bias), F normalized in [2^(M-4), 2^M) when E >= 1.
        # IBM allows UNNORMALIZED encodings: at the minimum exponent E=1, a sub-normal
        # region (leading-zero hex digits) covers [0, 16^(1-bias)) gradually.
        M = fmt.mant_bits
        g = ilog2_base(a, 16)                 # 16^g <= a < 16^(g+1)
        E = g + 1 + fmt.bias                   # biased; normalized fraction in [1/16,1)
        sub = E < 1
        if sub:
            E = 1                              # clamp to minimum exponent (gradual underflow)
        F_real = a / (Fraction(fmt.base) ** (E - fmt.bias)) * (1 << M)
        F, _ = _round_half_even(F_real)
        if F == 0:
            return fmt.pos_zero                # underflow
        if F >= (1 << M):
            if sub:
                F = (1 << M) - 1               # clamp at max sub-normal fraction
            else:                              # rounded up to 1.0 -> renormalize
                F = 1 << (M - 4)
                E += 1
        if E > fmt.exp_max:
            return _sat_raw(fmt, sign)
        return (sign << fmt.sign_shift) | (E << M) | (F & fmt.mant_max)

    if fmt.kind in ('vax', 'mbf'):
        M = fmt.mant_bits
        min_e = getattr(fmt, 'min_exp_field', 1)
        E2 = ilog2_base(a, 2)
        frac = a / pow2(E2) - 1                # [0,1)
        F, carry = _round_half_even(frac * (1 << M), cap=(1 << M))
        e = E2 + fmt.bias
        if carry:
            F = 0
            e += 1
        if e < min_e:
            return fmt.pos_zero                # VAX/MBF flushes denormals to zero
        if e > fmt.exp_max:
            return _sat_raw(fmt, sign)
        return (sign << fmt.sign_shift) | (e << M) | (F & fmt.mant_max)

    if fmt.kind in ('cray', 'x87'):
        M = fmt.mant_bits
        E2 = ilog2_base(a, 2)
        e = E2 + fmt.bias
        # significand with explicit integer bit: sig = a/2^E2 * 2^(M-1), in [2^(M-1), 2^M) normal
        if fmt.kind == 'x87' and e <= 0:
            # 8087 gradual underflow at exp=0 (integer bit 0): sig scaled by 2^(bias-1)
            if e < 1 - fmt.bias - (M - 1):
                return fmt.pos_zero
            sigd, _ = _round_half_even(a * (1 << (M - 1)) * pow2(fmt.bias - 1))
            if sigd == 0:
                return fmt.pos_zero
            return (sign << fmt.sign_shift) | (sigd & fmt.mant_max)
        if e < 1:
            # Cray: no exp=0 denormals, but allows UNNORMALIZED (integer bit 0) at exp=1
            e = 1
            sub = True
        else:
            sub = False
        sig_real = (a / pow2(e - fmt.bias)) * (1 << (M - 1))
        sig, carry = _round_half_even(sig_real, cap=(1 << M))
        if sig == 0:
            return fmt.pos_zero
        if carry:
            if sub:
                sig = (1 << M) - 1
            else:
                sig = 1 << (M - 1)
                e += 1
        if e > fmt.exp_max:
            return _sat_raw(fmt, sign)
        return (sign << fmt.sign_shift) | (e << M) | (sig & fmt.mant_max)

    raise ValueError(fmt.kind)


def _x87_special_add(fmt, a, b):
    """IEEE infinity rules, for the one legacy format that is IEEE.

    The Special branch here used to return a quiet NaN for every case, which is right for
    formats with no infinity and wrong for x87: +Inf + 1 is +Inf. The branch was written
    before decode() could produce a Special at all, so nothing ever reached it and nothing
    ever contradicted it.
    """
    an, bn = isinstance(a, Special), isinstance(b, Special)
    if (an and a.kind == "nan") or (bn and b.kind == "nan"):
        return fmt.quiet_nan
    if an and bn:
        return fmt.quiet_nan if a.sign != b.sign else (
            fmt.neg_inf if a.sign else fmt.pos_inf)
    inf = a if an else b
    return fmt.neg_inf if inf.sign else fmt.pos_inf


def _x87_special_mul(fmt, a, b):
    an, bn = isinstance(a, Special), isinstance(b, Special)
    if (an and a.kind == "nan") or (bn and b.kind == "nan"):
        return fmt.quiet_nan
    other = b if an else a
    if not (an and bn) and other == 0:
        return fmt.quiet_nan                 # Inf * 0
    sign = (a.sign if an else (1 if a < 0 else 0)) ^ \
           (b.sign if bn else (1 if b < 0 else 0))
    return fmt.neg_inf if sign else fmt.pos_inf


def format_add(fmt: LegacyFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        if fmt.kind == 'x87':
            return _x87_special_add(fmt, a, b)
        return fmt.quiet_nan
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    if a == 0 and b == 0:
        return _signed_zero(fmt, 1 if (sa == 1 and sb == 1) else 0)
    return encode(fmt, a + b)


def format_mul(fmt: LegacyFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        if fmt.kind == 'x87':
            return _x87_special_mul(fmt, a, b)
        return fmt.quiet_nan
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb
    if a == 0 or b == 0:
        return _signed_zero(fmt, rsign)
    return encode(fmt, a * b)


def _selftest():
    import random
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # IBM HFP32 known vectors
    ibm32 = FORMATS["ibm_hfp32"]
    check(decode(ibm32, 0x41100000) == 1, "ibm_hfp32: 0x41100000 -> +1")
    check(decode(ibm32, 0xC1100000) == -1, "ibm_hfp32: 0xC1100000 -> -1")
    check(decode(ibm32, 0x41200000) == 2, "ibm_hfp32: 0x41200000 -> +2")

    # MBF32 known vectors from conformance/ms_mbf32_decode_conformance_ax7203.py
    # MBF32 raw → IEEE-754 binary32 raw equivalence: code 0x40800000 (exp=129, mant=0)
    # equals 1.0; decoded Fraction here is the exact value, not IEEE raw.
    mbf32 = FORMATS["ms_mbf32"]
    check(decode(mbf32, 0x00000000) == 0, "ms_mbf32: 0 -> 0")
    check(decode(mbf32, 0x40800000) == 1, "ms_mbf32: 0x40800000 -> +1 (bias 129)")
    check(decode(mbf32, 0xC0800000) == -1, "ms_mbf32: 0xC0800000 -> -1")
    check(decode(mbf32, 0x41000000) == 2, "ms_mbf32: 0x41000000 -> +2")
    check(decode(mbf32, 0x41400000) == Fraction(3), "ms_mbf32: 0x41400000 -> +3")
    # exp_field <= 2 reserved as zero (MBF convention).
    check(decode(mbf32, 0x01000000) == 0, "ms_mbf32: exp_field=2 flushes to 0")
    check(encode(mbf32, Fraction(1)) == 0x40800000, "ms_mbf32: encode 1.0")
    check(encode(mbf32, Fraction(2)) == 0x41000000, "ms_mbf32: encode 2.0")
    check(encode(mbf32, Fraction(-1)) == 0xC0800000, "ms_mbf32: encode -1.0")

    # MBF64 known vectors from conformance/ms_mbf64_decode_conformance_ax7203.py
    mbf64 = FORMATS["ms_mbf64"]
    check(decode(mbf64, 0x0000000000000000) == 0, "ms_mbf64: 0 -> 0")
    check(decode(mbf64, 0x4080000000000000) == 1, "ms_mbf64: bias-129 +1.0")
    check(decode(mbf64, 0xC080000000000000) == -1, "ms_mbf64: -1.0")
    check(decode(mbf64, 0x4100000000000000) == 2, "ms_mbf64: +2.0")
    check(encode(mbf64, Fraction(1)) == 0x4080000000000000, "ms_mbf64: encode 1.0")

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: +0")
        check(encode(fmt, 0) == 0, f"{fname}: encode 0")
        one = encode(fmt, Fraction(1))
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")

        if fmt.width <= 16:
            codes = range(0, 1 << fmt.width)
        else:
            rng = random.Random(0x1E6A + fmt.width)
            codes = [rng.randrange(1 << fmt.width) for _ in range(20000)]
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special) or v == 0:
                continue
            # x + 0 preserves VALUE (bit-exact for uniquely-encoded formats;
            # IBM/VAX may normalize to a canonical pattern — value must match).
            r0 = format_add(fmt, raw, 0)
            check(decode(fmt, r0) == v, f"{fname}: x+0 value 0x{raw:x}")

    _regressions_186(check)

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (legacy: known-ibm/zero/unity/1+1/x+0"
          " + pass-186 x87 specials/canonicality"
          " + pass-188 no VAX negative zero)")
    return 0


def _regressions_186(check):
    """x87 is IEEE 754 double-extended. Before pass 186 this module treated the all-ones
    exponent as an ordinary exponent, so +Inf decoded as 2^16384 and every NaN decoded as
    a number. Stated as the format's own definition, not as words copied from the fix."""
    for fname in ("x87_fp80", "x87_48bit"):
        f = FORMATS[fname]
        one = (f.bias << f.mant_bits) | (1 << (f.mant_bits - 1))
        inf, ninf, nan = f.pos_inf, f.neg_inf, f.quiet_nan

        check(isinstance(decode(f, inf), Special) and decode(f, inf).kind == "inf",
              f"186: {fname} all-ones exponent with integer bit is an infinity")
        check(decode(f, ninf).sign == 1, f"186: {fname} -Inf keeps its sign")
        check(isinstance(decode(f, nan), Special) and decode(f, nan).kind == "nan",
              f"186: {fname} quiet NaN decodes as NaN")
        check(decode(f, one) == 1, f"186: {fname} one is still one")

        # The old quiet_nan had the integer bit clear, which is a pseudo-NaN: an invalid
        # operand, not a quiet NaN.
        check(is_canonical(f, nan), f"186: {fname} quiet NaN is a canonical encoding")
        check(not is_canonical(f, (f.exp_max << f.mant_bits) | 1),
              f"186: {fname} integer bit clear at all-ones exponent is not canonical")
        check(not is_canonical(f, 1 << f.mant_bits),
              f"186: {fname} an unnormal is not canonical")
        check(is_canonical(f, 1 << (f.mant_bits - 1)),
              f"186: {fname} a pseudo-denormal is canonical -- hardware evaluates it")

        # IEEE propagation. The Special branch existed but returned NaN for everything,
        # because decode could not produce a Special for it to see.
        check(format_add(f, inf, one) == inf, f"186: {fname} Inf + 1 = Inf")
        check(format_add(f, inf, ninf) == nan, f"186: {fname} Inf + (-Inf) = NaN")
        check(format_mul(f, inf, one) == inf, f"186: {fname} Inf * 1 = Inf")
        check(format_mul(f, ninf, one) == ninf, f"186: {fname} -Inf * 1 = -Inf")
        check(format_mul(f, inf, 0) == nan, f"186: {fname} Inf * 0 = NaN")

    # pass 188: no VAX format may hand out a negative zero, as an operand or an answer.
    for fname in ("vax_f", "vax_d", "vax_g", "vax_h", "pdp11_float"):
        f = FORMATS[fname]
        try:
            f.neg_zero
            ok = False
        except AttributeError:
            ok = True
        check(ok, f"188: {fname} has no negative zero")
        neg_one = encode(f, -1)
        check(format_add(f, neg_one, encode(f, 1)) == f.pos_zero,
              f"188: {fname} (-1) + 1 is the one zero it has")
        check(format_mul(f, neg_one, f.pos_zero) == f.pos_zero,
              f"188: {fname} (-1) * 0 does not produce a reserved operand")
    for fname in ("ibm_hfp32", "ms_mbf32", "cray_float", "x87_fp80"):
        f = FORMATS[fname]
        check(f.neg_zero == 1 << f.sign_shift,
              f"188: {fname} keeps its negative zero")

    # VAX reserved operand: sign 1 with exponent 0 traps rather than naming a value.
    vf = FORMATS["vax_f"]
    check(not is_canonical(vf, 1 << vf.sign_shift),
          "186: vax_f reserved operand is not canonical")
    check(is_canonical(vf, 0), "186: vax_f true zero is canonical")

    # The formats that genuinely have no infinity must not grow one.
    for fname in ("vax_f", "ibm_hfp32", "ms_mbf32", "cray_float"):
        f = FORMATS[fname]
        try:
            f.pos_inf
            ok = False
        except AttributeError:
            ok = True
        check(ok, f"186: {fname} still has no infinity")


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
