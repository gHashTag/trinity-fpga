#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
takum_ref.py — ЭТАЛОННЫЙ (golden) оракул для takum-семейства
(tapered logarithmic precision, Hunhold arXiv:2404.18603).
  takum8, takum16, takum32, takum64

СТАТУС КОДИРОВКИ — ВАЖНО (как и в tekum_ref.py):
  Настоящий takum — ЛОГАРИФМИЧЕСКИЙ (value = (-1)^S * exp(ell/2)), поэтому
  значения в общем случае ИРРАЦИОНАЛЬНЫ и не допускают точной Fraction-арифметики.
  Оракул требует точной рациональной арифметики (по образцу gf_ref.py), поэтому
  здесь реализована РАБОЧАЯ СТРУКТУРНАЯ МОДЕЛЬ на основе ПОЛЕВОЙ СХЕМЫ takum
  (обратная инженерия из fpga/openxc7-synth/takum64_decode.v), интерпретированная
  ЛИНЕЙНО (мантисса+порядок), а НЕ логарифмически. Это та же методология, что
  в conformance/tekum_ref.py (формат-наследник).

Полевая схема (n=64: overhead=5, PMAX=59; малые форматы масштабируются):
  bit[n-1]      = S (sign)
  bit[n-2]      = D (direction)
  bit[n-3:n-5]  = R (regime, 3 бита) — для n>=8; overhead = 5 бит
  payload (n-5) = [characteristic C_u: r_eff бит][mantissa M_u: p бит]
    r_eff = D ? R : ((2^regime_bits - 1) - R)
    p     = pmax - r_eff        (pmax = n - 5)        ← TAPER
    c     = CBIAS[{D,R}] + C_u
  value = (-1)^S * (1 + M_u/2^p) * 2^c
  specials: raw==0 -> +0 ; raw==(1<<(n-1)) -> NaR

Проверено против takum8 LUT: коды 0x40→+1, 0xC0→-1, 0x48→+2, 0x50→+8, 0x60→+32768.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


# CBIAS — из fpga/openxc7-synth/takum64_decode.v:22-27.
# Индекс = {D, R} = (D << regime_bits) | R.
CBIAS = (-255, -127, -63, -31, -15, -7, -3, -1,
           0,    1,   3,   7,  15, 31, 63, 127)


@dataclass(frozen=True)
class TakumFormat:
    name: str
    n: int
    regime_bits: int = 3

    @property
    def width(self): return self.n
    @property
    def overhead(self): return 2 + self.regime_bits
    @property
    def payload_bits(self): return self.n - self.overhead
    @property
    def pmax(self): return self.payload_bits
    @property
    def regime_count(self): return 1 << self.regime_bits
    @property
    def mask(self): return (1 << self.n) - 1
    @property
    def sign_shift(self): return self.n - 1
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self):
        # takum has no negative zero. 1 << sign_shift is NaR -- the same code the format
        # reserves for every result outside the reals -- so handing it out under this name
        # put NaR in the specials legend of every takum pack as `neg_zero`.
        #
        # Same shape as pass 188's VAX finding: a format with one zero declaring two, and
        # the second pointing at a code that means something else entirely. AttributeError
        # rather than a raise, so generate_vectors.real_specials probes with getattr and
        # simply omits it.
        raise AttributeError(f"{self.name} has no negative zero: "
                             f"{1 << self.sign_shift:#x} is NaR")
    @property
    def nar(self): return 1 << self.sign_shift


FORMATS = {
    "takum8":  TakumFormat("takum8",  n=8),
    "takum16": TakumFormat("takum16", n=16),
    "takum32": TakumFormat("takum32", n=32),
    "takum64": TakumFormat("takum64", n=64),
}


class Special:
    def __init__(self, kind="nar", sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        if self.kind in ("nar", "nan"):
            return "NaR"
        return ("-" if self.sign else "+") + "Inf"


def pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def ilog2_floor(a: Fraction) -> int:
    assert a > 0
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < pow2(e):
        e -= 1
    while Fraction(n, d) >= pow2(e + 1):
        e += 1
    return e


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


def _regime_params(fmt: TakumFormat, D, R):
    r_eff_nom = R if D else (fmt.regime_count - 1 - R)
    r_eff = max(0, min(r_eff_nom, fmt.payload_bits))
    p = fmt.payload_bits - r_eff
    cidx = (D << fmt.regime_bits) | R
    cbias = CBIAS[cidx]
    return r_eff, p, cbias


def _enumerate_regimes(fmt: TakumFormat):
    out = []
    for D in (0, 1):
        for R in range(fmt.regime_count):
            r_eff, p, cbias = _regime_params(fmt, D, R)
            c_lo = cbias
            c_hi = cbias + ((1 << r_eff) - 1) if r_eff > 0 else cbias
            out.append((D, R, r_eff, p, cbias, c_lo, c_hi))
    return out


def _pack(fmt, sign, D, R, r_eff, p, C_u, M_u):
    lower = (((C_u & ((1 << r_eff) - 1)) << p) if r_eff > 0 else 0) \
            | ((M_u & ((1 << p) - 1)) if p > 0 else 0)
    lower &= (1 << fmt.payload_bits) - 1
    raw = ((sign << (fmt.n - 1))
           | (D << (fmt.n - 2))
           | (R << (fmt.n - 2 - fmt.regime_bits))
           | lower)
    return raw & fmt.mask


def decode(fmt: TakumFormat, raw: int):
    raw &= fmt.mask
    if raw == 0:
        return Fraction(0)
    if raw == fmt.nar:
        return Special("nar")

    S = (raw >> (fmt.n - 1)) & 1
    D = (raw >> (fmt.n - 2)) & 1
    R = (raw >> (fmt.n - 2 - fmt.regime_bits)) & (fmt.regime_count - 1)
    lower = raw & ((1 << fmt.payload_bits) - 1)

    r_eff, p, cbias = _regime_params(fmt, D, R)
    C_u = (lower >> p) & ((1 << r_eff) - 1) if r_eff > 0 else 0
    M_u = lower & ((1 << p) - 1) if p > 0 else 0

    c = cbias + C_u
    # The negative branch is NOT a sign flip of the positive one.
    #
    # libtakum's reference decode (src/codec.c,
    # codec_s_and_linear_l_to_float64) derives the linear value from the
    # logarithmic pair (c, m):
    #
    #     e = (1 - 2s)(c + s)
    #     s == 0:  h = e,               g = m
    #     s == 1:  h = e + 1, g = 0     if m == 0
    #              h = e,     g = 1 - m otherwise
    #     value = (-1)^s (1 + g) 2^h
    #
    # For s = 1 the exponent's SIGN flips, so negation is close to
    # reciprocation -- the defining behaviour of a tapered logarithmic format,
    # and exactly what a plain `-val` discards. Before this fix the oracle
    # matched the reference on 32768 of 65535 takum16 codes: every positive one,
    # and no negative one.
    m_frac = Fraction(M_u, 1 << p) if p > 0 else Fraction(0)
    e = (1 - 2 * S) * (c + S)
    if S == 0:
        h, g = e, m_frac
    elif m_frac == 0:
        h, g = e + 1, Fraction(0)
    else:
        h, g = e, 1 - m_frac
    val = (1 + g) * pow2(h)
    return -val if S else val


def encode(fmt: TakumFormat, value):
    if isinstance(value, Special):
        return fmt.nar

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v

    # Invert the decode's negative branch before choosing fields.
    #
    # decode packs (c, m) and reads them back as
    #     s = 0:  value =  (1 + m) 2^c
    #     s = 1:  value = -(1 + g) 2^h  with h = -(c+1), g = 1 - m
    #                     (or h = -c, g = 0 when m = 0)
    #
    # so a negative target does NOT share fields with its absolute value. Map it
    # to the POSITIVE value that the same (c, m) would decode to, encode that,
    # and set the sign bit. Without this, encode and decode disagree on every
    # negative code: measured, 4681 of 9362 round trips held -- exactly the
    # positive half.
    if sign:
        h = ilog2_floor(a)
        g = a / pow2(h) - 1
        if g == 0:
            c_t, m_t = -h, Fraction(0)
        else:
            c_t, m_t = -h - 1, 1 - g
        a = (1 + m_t) * pow2(c_t)

    E = ilog2_floor(a)
    frac = a / pow2(E) - 1

    regimes = _enumerate_regimes(fmt)
    finite = [r for r in regimes if r[3] >= 0]
    candidates = [r for r in finite if r[5] <= E <= r[6]]

    if not candidates:
        max_c = max(r[6] for r in finite)
        if E > max_c:
            r = max(finite, key=lambda r: (r[6], r[3]))
            D, R, r_eff, p, cbias, c_lo, c_hi = r
            return _pack(fmt, sign, D, R, r_eff, p, c_hi - cbias,
                         (1 << p) - 1 if p > 0 else 0)
        return (sign << fmt.sign_shift)

    D, R, r_eff, p, cbias, c_lo, c_hi = max(
        candidates, key=lambda r: (r[3], -r[2], -(r[0] << fmt.regime_bits | r[1])))

    c = E
    C_u = c - cbias
    M_u = 0
    if p > 0:
        mant, carry = _round_half_even(frac * (1 << p), cap=(1 << p))
        if carry:
            c += 1
            C_u = c - cbias
            if (C_u > ((1 << r_eff) - 1) if r_eff > 0 else (C_u > 0)):
                cand2 = [r for r in finite if r[5] <= c <= r[6]]
                if cand2:
                    D, R, r_eff, p, cbias, c_lo, c_hi = max(
                        cand2, key=lambda r: (r[3], -r[2]))
                    C_u = c - cbias
            M_u = 0
        else:
            M_u = mant

    return _pack(fmt, sign, D, R, r_eff, p, C_u, M_u)


def format_add(fmt: TakumFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.nar
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    if a == 0 and b == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero
    if a == 0:
        return b_raw
    if b == 0:
        return a_raw
    s = a + b
    if s == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero
    return encode(fmt, s)


def format_mul(fmt: TakumFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.nar
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb
    if a == 0 or b == 0:
        return fmt.neg_zero if rsign else fmt.pos_zero
    return encode(fmt, a * b)


def _selftest():
    import random
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # takum8 known vectors (linear model verification against RTL LUT)
    t8 = FORMATS["takum8"]
    check(decode(t8, 0x40) == 1, "takum8: 0x40 -> +1")
    check(decode(t8, 0xC0) == -1, "takum8: 0xC0 -> -1")
    check(decode(t8, 0x48) == 2, "takum8: 0x48 -> +2")
    check(decode(t8, 0x50) == 8, "takum8: 0x50 -> +8")
    check(decode(t8, 0x60) == 32768, "takum8: 0x60 -> +32768")

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: +0")
        check(isinstance(decode(fmt, fmt.nar), Special), f"{fname}: NaR")
        one = encode(fmt, Fraction(1))
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")

        # Multiplication was checked nowhere. Pass 221's mutation gate corrupted format_mul and
        # this self-test did not notice, while takum*_mul.json is generated from it. Six of sixteen
        # oracles had the same hole and every one of them was multiplication -- addition is
        # checked everywhere, mul nowhere.
        #
        # Properties of the OPERATION, not of the implementation: unity is neutral and zero
        # absorbs. Both hold in every format here regardless of width or rounding.
        check(format_mul(fmt, one, one) == one, f"{fname}: 1*1=1")
        check(decode(fmt, format_mul(fmt, one, fmt.pos_zero)) == 0, f"{fname}: 1*0=0")

        if fmt.n <= 16:
            codes = range(0, 1 << fmt.n)
        else:
            rng = random.Random(0x7A6B + fmt.n)
            codes = [rng.randrange(1 << fmt.n) for _ in range(20000)]
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special):
                continue
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")
            back = decode(fmt, encode(fmt, v))
            check(back == v, f"{fname}: round-trip 0x{raw:x}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (takum linear: known-vectors/zero/nar/unity/1+1/x+0/round-trip)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
