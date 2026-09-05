#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gf_add_ref.py — параметрический ЭТАЛОННЫЙ (golden) программный оракул сложения
для семейства GoldenFloat GF{N} с КОРРЕКТНОЙ поддержкой денормалов
(gradual underflow) и округлением round-half-to-even (ties-to-even) со sticky-битом.

Статус: [смоделировано] — это SW-оракул, НЕ железо. compute-HW галочка
закрывается только bit-exact прогоном на AX7203 (см. cron-83-formats.md §3.5).

Назначение (Wave-луп денормалов):
  - Заменяет багнутый conformance/gf16_ref.py (encode() не входит в денормальный
    диапазон: `while abs_v<1.0 and exp>1` стопится на exp==1).
  - Использует точную рациональную арифметику (fractions.Fraction), поэтому
    round-ties-even ДОКАЗУЕМ, а не зависит от float-погрешности.
  - Параметричен по (EXP_BITS, MANT_BITS, BIAS) → один оракул на все GF-ширины.

Соглашения формата GF{N} (как в каталоге t27 gen/numeric/formats_catalog.py):
  бит[ширина-1]            = sign
  бит[ширина-2 .. MANT]    = exp  (EXP_BITS бит)
  бит[MANT-1 .. 0]         = mant (MANT_BITS бит)
  exp == EXP_MAX  -> Inf (mant==0) / NaN (mant!=0)
  exp == 0        -> zero (mant==0) / denormal: value = mant/2^MANT * 2^(1-BIAS)
  иначе (normal)  -> value = (1 + mant/2^MANT) * 2^(exp-BIAS)

Honesty: Vasilev, ORCID 0009-0008-4294-6159, admin@t27.ai. Только русский в отчётах.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class GFFormat:
    name: str
    exp_bits: int
    mant_bits: int
    bias: int

    @property
    def width(self):
        return 1 + self.exp_bits + self.mant_bits

    @property
    def has_inf(self):
        # ТОЛЬКО GF16 объявляет SPECIAL_EXP/Inf/NaN (gf16.t27:25,35,131).
        # GF6/8/12/20 НЕ имеют Inf: exp=all-ones = КОНЕЧНЫЙ max_value
        # (gf8.t27:115-119, gf20.t27:106-109). [verified из spec]
        return self.name == "gf16"

    @property
    def max_finite(self):
        # Для форматов БЕЗ Inf: наибольшее конечное = {max-exp, all-ones-mant}.
        # Для форматов С Inf (gf16): наибольшее конечное = {max-exp-1, all-ones-mant}.
        e = (self.exp_max - 1) if self.has_inf else self.exp_max
        return (e << self.mant_bits) | self.mant_max

    def pos_overflow(self, sign):
        """Цель насыщения при переполнении, согласно spec-политике формата."""
        if self.has_inf:
            return self.neg_inf if sign else self.pos_inf
        sat = self.max_finite
        return ((1 << self.sign_shift) | sat) if sign else sat

    @property
    def exp_max(self):
        return (1 << self.exp_bits) - 1

    @property
    def mant_max(self):
        return (1 << self.mant_bits) - 1

    @property
    def sign_shift(self):
        return self.exp_bits + self.mant_bits

    # Канонические спец-коды (как в gf16_ref.py, обобщённо)
    @property
    def pos_zero(self):
        return 0

    @property
    def neg_zero(self):
        return 1 << self.sign_shift

    @property
    def pos_inf(self):
        return self.exp_max << self.mant_bits

    @property
    def neg_inf(self):
        return (1 << self.sign_shift) | (self.exp_max << self.mant_bits)

    @property
    def quiet_nan(self):
        # exp=all-ones, mant!=0; берём mant=1 как канонический qNaN
        return (self.exp_max << self.mant_bits) | 1


# Каталожные параметры GF (из gen/numeric/formats_catalog.py, HEAD d386fa7f)
FORMATS = {
    "gf4":  GFFormat("gf4",  exp_bits=1, mant_bits=2, bias=0),
    "gf6":  GFFormat("gf6",  exp_bits=2, mant_bits=3, bias=1),
    "gf8":  GFFormat("gf8",  exp_bits=3, mant_bits=4, bias=3),
    "gf10": GFFormat("gf10", exp_bits=3, mant_bits=6, bias=3),
    "gf12": GFFormat("gf12", exp_bits=4, mant_bits=7, bias=7),
    "gf14": GFFormat("gf14", exp_bits=5, mant_bits=8, bias=15),
    "gf16": GFFormat("gf16", exp_bits=6, mant_bits=9, bias=31),
    "gf20": GFFormat("gf20", exp_bits=7, mant_bits=12, bias=63),
    "gf24": GFFormat("gf24", exp_bits=9, mant_bits=14, bias=255),
    "gf32": GFFormat("gf32", exp_bits=12, mant_bits=19, bias=2047),
    # Canonical φ-rule family (arXiv:2606.05017) — wide formats.
    # E = round((N-1)/φ²) = round((N-1)/2.618), M = (N-1) - E.
    "gf48": GFFormat("gf48", exp_bits=18, mant_bits=29, bias=(1 << 17) - 1),
    "gf64": GFFormat("gf64", exp_bits=24, mant_bits=39, bias=8388607),
    "gf96": GFFormat("gf96", exp_bits=36, mant_bits=59, bias=(1 << 35) - 1),
    "gf128": GFFormat("gf128", exp_bits=49, mant_bits=78, bias=281474976710655),
    "gf256": GFFormat("gf256", exp_bits=97, mant_bits=158, bias=79228162514264337593543950335),
    # Canonical φ-rule family — ultra-wide formats.
    # gf512: E = round(511/φ²) = 195, M = 511-195 = 316, bias = 2^194 - 1.
    # gf1024: E = round(1023/φ²) = 391, M = 1023-391 = 632, bias = 2^390 - 1.
    # Self-test/generation only exercise edge cases (0, ±0): arbitrary raws
    # decode to pow2(≈2^195) which is unconstructible. Value-driven generation
    # stays safe because encoded raws carry small unbiased exponents.
    "gf512":  GFFormat("gf512",  exp_bits=195, mant_bits=316, bias=(1 << 194) - 1),
    "gf1024": GFFormat("gf1024", exp_bits=391, mant_bits=632, bias=(1 << 390) - 1),
}


# -------------------- DECODE (raw -> точное значение Fraction | спец) --------------------

class Special:
    """Маркер не-конечного значения."""
    def __init__(self, kind, sign=0):
        self.kind = kind  # 'inf' | 'nan'
        self.sign = sign

    def __repr__(self):
        if self.kind == "nan":
            return "NaN"
        return ("-" if self.sign else "+") + "Inf"


def decode(fmt: GFFormat, raw: int):
    """raw -> Fraction (точное конечное) или Special. Денормалы корректны."""
    raw &= (1 << fmt.width) - 1
    sign = (raw >> fmt.sign_shift) & 1
    exp = (raw >> fmt.mant_bits) & fmt.exp_max
    mant = raw & fmt.mant_max

    if exp == fmt.exp_max and fmt.has_inf:
        if mant == 0:
            return Special("inf", sign)
        return Special("nan")
    # Форматы без Inf: exp=all-ones — КОНЕЧНОЕ нормальное значение (НЕ спец).
    # Падаем в обычную NORMAL-ветку ниже.

    if exp == 0:
        if mant == 0:
            return Fraction(0)  # знак нуля теряем при decode (как и аппаратно для значения)
        # ДЕНОРМАЛ: implicit bit = 0, масштаб 2^(1-BIAS)
        val = Fraction(mant, 1 << fmt.mant_bits) * pow2(1 - fmt.bias)
    else:
        # NORMAL: implicit bit = 1
        val = (1 + Fraction(mant, 1 << fmt.mant_bits)) * pow2(exp - fmt.bias)

    return -val if sign else val


def pow2(e: int) -> Fraction:
    """Точная 2^e как Fraction для любого целого e."""
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


# -------------------- ENCODE (точное значение -> raw, round-ties-even) --------------------

def encode(fmt: GFFormat, value):
    """
    value: Fraction (точное конечное) | Special | int.
    Возвращает raw с КОРРЕКТНЫМ gradual underflow и round-half-to-even (sticky).
    """
    if isinstance(value, Special):
        if value.kind == "nan":
            return fmt.quiet_nan
        return fmt.neg_inf if value.sign else fmt.pos_inf

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v  # |v| > 0, точное

    # Минимальный normal-exponent поля = 1 -> 2^(1-BIAS). Денормалы ниже.
    # Найдём несмещённый показатель E такой, что 2^E <= a < 2^(E+1).
    E = ilog2_floor(a)

    # Кандидатный нормальный exp-поле:
    exp_field = E + fmt.bias

    if exp_field >= 1:
        # ----- НОРМАЛЬНАЯ ветка -----
        # mant_real = (a / 2^E - 1) в [0,1); квантуем MANT_BITS бит ties-even+sticky.
        frac = a / pow2(E) - 1  # в [0,1)
        mant, carry = round_fraction_to_bits(frac, fmt.mant_bits)
        if carry:
            # frac округлился до 1.0 -> мантисса переполнилась, exp++
            mant = 0
            exp_field += 1
        # OVERFLOW по spec-политике формата (family-split):
        #  - has_inf (gf16): exp=exp_max зарезервирован под Inf/NaN -> overflow при exp>=exp_max -> Inf
        #  - без Inf (gf6/8/12/20): exp=exp_max — последний КОНЕЧНЫЙ -> overflow при exp>exp_max -> saturate-to-max-finite
        if fmt.has_inf:
            if exp_field >= fmt.exp_max:
                return fmt.pos_overflow(sign)
        else:
            if exp_field > fmt.exp_max:
                return fmt.pos_overflow(sign)
        return (sign << fmt.sign_shift) | (exp_field << fmt.mant_bits) | (mant & fmt.mant_max)
    else:
        # ----- ДЕНОРМАЛЬНАЯ / underflow ветка (exp_field <= 0) -----
        # Денормал: value = m / 2^MANT * 2^(1-BIAS), m in [1 .. mant_max].
        # m_real = a / 2^(1-BIAS) * 2^MANT  (точное), квантуем ties-even+sticky к целому.
        scale = pow2(1 - fmt.bias)
        m_real = a / scale * (1 << fmt.mant_bits)  # точная Fraction
        m, carry = round_fraction_to_int(m_real)
        if m == 0:
            # underflow к нулю по round-to-nearest-even
            return (sign << fmt.sign_shift) | 0
        if m > fmt.mant_max:
            # округление вытолкнуло в наименьший НОРМАЛ (exp_field=1, mant=0)
            return (sign << fmt.sign_shift) | (1 << fmt.mant_bits) | 0
        return (sign << fmt.sign_shift) | (m & fmt.mant_max)


def ilog2_floor(a: Fraction) -> int:
    """floor(log2(a)) для точной положительной Fraction a."""
    assert a > 0
    n, d = a.numerator, a.denominator
    # 2^E <= n/d < 2^(E+1)  <=>  bit_length сравнение
    # Найдём E через сравнение n vs d*2^E.
    e = n.bit_length() - d.bit_length()
    # уточняем
    if Fraction(n, d) < pow2(e):
        e -= 1
    while Fraction(n, d) >= pow2(e + 1):
        e += 1
    return e


def round_fraction_to_bits(frac: Fraction, bits: int):
    """
    Квантовать frac in [0,1) к `bits` дробным битам, round-half-to-even со sticky.
    Возвращает (целое_мантиссы in [0, 2^bits], carry_bool).
    carry=True если результат == 2^bits (т.е. округлилось до 1.0).
    """
    scaled = frac * (1 << bits)  # точная Fraction
    return _round_half_even(scaled, cap=(1 << bits))


def round_fraction_to_int(x: Fraction):
    """round-half-to-even точной Fraction к целому. Возвращает (int, carry=False)."""
    return _round_half_even(x, cap=None)


def _round_half_even(x: Fraction, cap):
    """round-half-to-even точного x>=0. cap: если не None и результат>cap, вернуть (cap, carry/clip)."""
    floor_i = x.numerator // x.denominator  # >=0
    rem = x - floor_i  # in [0,1)
    half = Fraction(1, 2)
    if rem < half:
        r = floor_i
    elif rem > half:
        r = floor_i + 1
    else:  # ровно .5 -> к чётному
        r = floor_i if (floor_i % 2 == 0) else floor_i + 1
    if cap is not None and r >= cap:
        return cap, True
    return r, False


# -------------------- СЛОЖЕНИЕ (golden) --------------------

def gf_add(fmt: GFFormat, a_raw: int, b_raw: int) -> int:
    """Эталонное сложение: decode (точно) -> сумма (точно) -> encode (ties-even)."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)

    # Спец-правила (минимальные, как gf16_ref)
    a_nan = isinstance(a, Special) and a.kind == "nan"
    b_nan = isinstance(b, Special) and b.kind == "nan"
    if a_nan or b_nan:
        return fmt.quiet_nan
    a_inf = isinstance(a, Special) and a.kind == "inf"
    b_inf = isinstance(b, Special) and b.kind == "inf"
    if a_inf and b_inf:
        if a.sign != b.sign:
            return fmt.quiet_nan  # Inf + (-Inf) = NaN
        return fmt.neg_inf if a.sign else fmt.pos_inf
    if a_inf:
        return fmt.neg_inf if a.sign else fmt.pos_inf
    if b_inf:
        return fmt.neg_inf if b.sign else fmt.pos_inf

    # Знак нуля по IEEE 754 RNE (gf16.t27:219): (−0)+(−0) = −0; иначе +0.
    # decode теряет знак нуля, поэтому восстанавливаем из raw-бит.
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    a_is_zero = (a == 0) and not isinstance(a, Special)
    b_is_zero = (b == 0) and not isinstance(b, Special)
    if a_is_zero and b_is_zero:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero

    s = a + b  # ТОЧНО (Fraction)
    return encode(fmt, s)


def gf_mul(fmt: GFFormat, a_raw: int, b_raw: int) -> int:
    """
    Эталонное умножение: decode (точно) -> произведение (точно) -> encode (ties-even).
    Семантика по spec gf16.t27:356-379 + family-split overflow (как в ADD).
    Знак ВСЕГДА result_sign = sa ^ sb (включая нулевой результат — IEEE 754).
    """
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    # Знак результата = XOR знаков операндов (decode теряет знак нуля -> берём из raw)
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    result_sign = sa ^ sb

    a_nan = isinstance(a, Special) and a.kind == "nan"
    b_nan = isinstance(b, Special) and b.kind == "nan"
    if a_nan or b_nan:
        return fmt.quiet_nan
    a_inf = isinstance(a, Special) and a.kind == "inf"
    b_inf = isinstance(b, Special) and b.kind == "inf"
    if a_inf or b_inf:
        za = (not isinstance(a, Special)) and a == 0
        zb = (not isinstance(b, Special)) and b == 0
        if za or zb:
            return fmt.quiet_nan  # 0 * Inf = NaN (IEEE 754, gf16_mul.v:54-55)
        return fmt.neg_inf if result_sign else fmt.pos_inf

    a_is_zero = (a == 0) and not isinstance(a, Special)
    b_is_zero = (b == 0) and not isinstance(b, Special)
    if a_is_zero or b_is_zero:
        # 0 * x = 0 со знаком XOR (spec gf16.t27:360-365)
        return fmt.neg_zero if result_sign else fmt.pos_zero

    # Конечное ненулевое произведение: ТОЧНО -> encode (family-split overflow, RNE).
    # encode() сам выбирает знак по value<0; для произведения это согласовано с XOR,
    # т.к. value = a*b имеет знак sa^sb. Денормал-произведения обрабатываются
    # gradual-underflow веткой encode() (НЕ flush-to-zero — отличие от старой gf16-спеки).
    return encode(fmt, a * b)


# -------------------- SELF-TEST --------------------

def _selftest():
    ok = 0
    for name, fmt in sorted(FORMATS.items()):
        if fmt.width > 32:
            continue  # skip wide formats (slow Fraction)
        # Zero
        assert gf_add(fmt, 0, 0) == 0, f"{name}: 0+0 != 0"
        # -0 + 0 = +0
        assert gf_add(fmt, fmt.neg_zero, 0) == 0, f"{name}: -0+0 != +0"
        # Round-trip 0
        assert encode(fmt, decode(fmt, 0)) == 0, f"{name}: round-trip 0 failed"
        # For bias > 0: test 1.0 + 0 = 1.0
        if fmt.bias > 0:
            one = fmt.bias << fmt.mant_bits
            assert gf_add(fmt, one, 0) == one, f"{name}: 1+0 != 1"
            assert gf_add(fmt, one, one) != one, f"{name}: 1+1 == 1"

            # Multiplication was checked nowhere. Pass 221's mutation gate corrupted
            # gf_mul and this self-test did not notice, while gf*_mul.json is generated
            # from it. Six of sixteen oracles had the same hole and every one was
            # multiplication: addition is checked everywhere, mul nowhere.
            #
            # Properties of the operation, not of the implementation.
            assert gf_mul(fmt, one, one) == one, f"{name}: 1*1 != 1"
            assert decode(fmt, gf_mul(fmt, one, 0)) == 0, f"{name}: 1*0 != 0"
        ok += 1
    # Wide / ultra-wide formats: edge-case only (0+0=0, -0+0=+0). Random raws
    # would decode to pow2(≈2^195) for gf512/gf1024 — unconstructible; the
    # value-driven generator keeps generation safe, but the self-test sticks
    # to zero-identities which never touch the exponent field.
    for name in ["gf48", "gf64", "gf96", "gf128", "gf256", "gf512", "gf1024"]:
        fmt = FORMATS[name]
        assert gf_add(fmt, 0, 0) == 0, f"{name}: 0+0 != 0"
        assert gf_add(fmt, fmt.neg_zero, 0) == 0, f"{name}: -0+0 != +0"
        ok += 1
    print(f"SELF-TEST: PASS ({ok} formats: zero/-0+0/round-trip/identity)")


if __name__ == "__main__":
    _selftest()
