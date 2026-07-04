#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gf_decode_ref.py — параметрический ЭТАЛОННЫЙ (golden) программный decode-оракул
для ВСЕЙ лестницы GoldenFloat GF{N} проекта Trinity (каталог 83 формата, GF-подсемейство
из 17 ячеек по единому phi-правилу).

Статус: [смоделировано] — это SW-оракул на точной рациональной арифметике
(`fractions.Fraction`), НЕ железо. HW-decode каждой ячейки закрывается ТОЛЬКО
4/4 цепью (CI GREEN + SHA256 + UART `HW RESULT: N/N bit-exact (fails=0)` @160000 +
IDCODE 0x13636093) на AX7203 — см. gf_decode_lineup_spec.md и
skills/user/trinity-wave-loop/references/cron-83-formats.md.

Назначение:
  - Единый decode-закон (5 классов: normal / subnormal(e=0) / zero / Inf / NaN)
    применяется параметрически по (N, E, M, BIAS) для ВСЕЙ линейки gf4..gf1024,
    а не переписывается заново для каждого формата — это ключевой аргумент
    для рецензента ARITH (см. arXiv:2606.05017, arXiv:2606.09686).
  - Единое phi-правило (bit-width allocation), ПРОВЕРЕНО против SSOT
    formats_catalog.t27 (master) 2026-07-04, держится ТОЧНО по всей лестнице:
        e = round((N-1) / phi^2)
        m = N - 1 - e
        bias = 2^(e-1) - 1
    Здесь phi = (1+sqrt(5))/2, phi^2 = phi+1 ~= 2.618033988749...
  - encode() — для генерации проверочных векторов (round-half-to-even + sticky,
    gradual underflow), декодирование — decode() на точной Fraction-арифметике.

Формат бит-раскладки GF{N} (как в gen/numeric/formats_catalog.py):
  бит[N-1]          = sign
  бит[N-2 .. M]     = exp   (E бит)
  бит[M-1 .. 0]     = mant  (M бит)
  exp == EXP_MAX (все единицы)  -> Inf (mant==0, HAS_INF-семантика) / NaN (mant!=0)
  exp == 0                       -> zero (mant==0) / subnormal (mant!=0):
                                     value = mant/2^M * 2^(1-BIAS)
  иначе (normal)                  -> value = (1 + mant/2^M) * 2^(exp-BIAS)

ВАЖНО (honesty, binding):
  - Каталог Trinity = 83 формата (НЕ 84 — препринт 2606.09686 требует erratum v2).
  - Никаких "первый/лучший/единственный" — только проверяемые факты.
  - НЕ обещать FP-decode на HW для extended (>FP64, gf96 и выше) — mantissa не
    влезает даже в binary64 (52 бита). Для extended допустим только Python-эталон
    (эта функция) + SW-conformance; аппаратный decode = [открытая гипотеза для HW].
  - Правило phi верифицировано символьно/численно = [Verified как правило].
    HW-decode каждой ячейки = [измерено на FPGA] ТОЛЬКО после полной 4/4 цепи.

Автор: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
"""

from fractions import Fraction
from dataclasses import dataclass
from decimal import Decimal, getcontext
import math

getcontext().prec = 80


# --------------------------------------------------------------------------
# 1. phi-правило: генератор (E, M, BIAS) из N — проверено против SSOT 2026-07-04
# --------------------------------------------------------------------------

def phi_squared_hi_precision() -> Fraction:
    """phi^2 = phi + 1 c высокой точностью как Fraction (через Decimal)."""
    # phi = (1+sqrt5)/2 ; phi^2 = (3+sqrt5)/2
    sqrt5 = Decimal(5).sqrt()
    phi2 = (Decimal(3) + sqrt5) / Decimal(2)
    # к Fraction с большим знаменателем сохраняя точность Decimal
    return Fraction(phi2).limit_denominator(10**40)


PHI2 = phi_squared_hi_precision()  # ~2.618033988749894848...


def round_half_away_from_zero(x: Fraction) -> int:
    """Python round() использует banker's rounding; phi-правило в каталоге
    использует обычное math.round-политику (round half to nearest, ties away
    from .5 в сторону чётности как в стандартной round()) — ЭТО СВЕРЕНО
    построчно с SSOT-таблицей ниже (все 17 строк совпадают), поэтому берём
    Python round() как эталонную семантику округления e."""
    return round(x)


def gf_params_from_N(N: int):
    """
    Каноническое phi-правило Trinity:
        e = round((N-1)/phi^2)
        m = N - 1 - e
        bias = 2^(e-1) - 1
    Возвращает (E, M, BIAS). Не используется в decode() напрямую (та работает
    от явных E/M/BIAS), а служит для верификации SSOT-таблицы ниже и для
    генерации параметров форматов вне явного списка (gf-линейка).
    """
    val = Fraction(N - 1) / PHI2
    # представим как float для round() по общепринятой round-half-to-even,
    # т.к. SSOT сверялась именно с этой стандартной семантикой
    e = round_half_away_from_zero(float(val))
    m = N - 1 - e
    bias = (1 << (e - 1)) - 1 if e >= 1 else 0
    return e, m, bias


# --------------------------------------------------------------------------
# 2. Каталог GF-линейки (SSOT formats_catalog.t27, сверено 2026-07-04)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GFFormat:
    name: str
    N: int              # полная ширина в битах (1 + E + M)
    E: int               # ширина экспоненты
    M: int               # ширина мантиссы
    BIAS: int            # смещение экспоненты
    status: str          # Verified / Open / Experimental (каталожный статус)
    decode_target: str   # "FP32" | "FP64" | "extended"

    def __post_init__(self):
        assert self.N == 1 + self.E + self.M, \
            f"{self.name}: N != 1+E+M ({self.N} != 1+{self.E}+{self.M})"

    @property
    def exp_max(self):
        return (1 << self.E) - 1

    @property
    def mant_max(self):
        return (1 << self.M) - 1

    @property
    def sign_shift(self):
        return self.E + self.M

    @property
    def pos_zero(self):
        return 0

    @property
    def neg_zero(self):
        return 1 << self.sign_shift

    @property
    def pos_inf(self):
        return self.exp_max << self.M

    @property
    def neg_inf(self):
        return (1 << self.sign_shift) | (self.exp_max << self.M)

    @property
    def quiet_nan(self):
        return (self.exp_max << self.M) | 1


# Полная лестница GF (17 ячеек), точные параметры из gf_decode_lineup_spec.md,
# сверенные против живого SSOT formats_catalog.t27 (master) 2026-07-04.
GF_LINEUP = {
    "gf4":   GFFormat("gf4",   4,   1,   2,             0, "Experimental", "FP32"),
    "gf6":   GFFormat("gf6",   6,   2,   3,             1, "Open",         "FP32"),
    "gf8":   GFFormat("gf8",   8,   3,   4,             3, "Verified",     "FP32"),
    "gf10":  GFFormat("gf10",  10,  3,   6,             3, "Open",         "FP32"),
    "gf12":  GFFormat("gf12",  12,  4,   7,             7, "Verified",     "FP32"),
    "gf14":  GFFormat("gf14",  14,  5,   8,            15, "Open",         "FP32"),
    "gf16":  GFFormat("gf16",  16,  6,   9,            31, "Verified",     "FP32"),
    "gf20":  GFFormat("gf20",  20,  7,  12,            63, "Experimental", "FP32"),
    "gf24":  GFFormat("gf24",  24,  9,  14,           255, "Experimental", "FP32"),
    "gf32":  GFFormat("gf32",  32, 12,  19,          2047, "Verified",     "FP32"),
    "gf48":  GFFormat("gf48",  48, 18,  29,        131071, "Open",         "FP64"),
    "gf64":  GFFormat("gf64",  64, 24,  39,       8388607, "Verified",     "FP64"),
    "gf96":  GFFormat("gf96",  96, 36,  59,   (1 << 35)-1, "Open",         "extended"),
    "gf128": GFFormat("gf128", 128, 49, 78,   (1 << 48)-1, "Open",         "extended"),
    "gf256": GFFormat("gf256", 256, 97, 158,  (1 << 96)-1, "Open",         "extended"),
    "gf512": GFFormat("gf512", 512, 195, 316, (1 << 194)-1, "Open",        "extended"),
    "gf1024":GFFormat("gf1024",1024, 391, 632,(1 << 390)-1, "Open",        "extended"),
}

# 10 форматов Фазы A (decode-target FP32) — фокус этого лупа
FP32_FORMATS = ["gf4", "gf6", "gf8", "gf10", "gf12", "gf14", "gf16", "gf20", "gf24", "gf32"]
FP64_FORMATS = ["gf48", "gf64"]
EXTENDED_FORMATS = ["gf96", "gf128", "gf256", "gf512", "gf1024"]


def verify_phi_rule():
    """Сверяет phi-правило против ВСЕЙ SSOT-таблицы (17 строк). Возвращает
    список (name, ok, e_calc, m_calc, bias_calc) для отчёта."""
    rows = []
    for name, fmt in GF_LINEUP.items():
        e_calc, m_calc, bias_calc = gf_params_from_N(fmt.N)
        ok = (e_calc == fmt.E) and (m_calc == fmt.M) and (bias_calc == fmt.BIAS)
        rows.append((name, ok, e_calc, m_calc, bias_calc))
    return rows


# --------------------------------------------------------------------------
# 3. DECODE (raw int -> точное значение Fraction | Special) — 5 классов
# --------------------------------------------------------------------------

class Special:
    """Маркер не-конечного значения (Inf с явным знаком / тихий NaN)."""
    __slots__ = ("kind", "sign")

    def __init__(self, kind, sign=0):
        self.kind = kind  # 'inf' | 'nan'
        self.sign = sign

    def __repr__(self):
        if self.kind == "nan":
            return "NaN"
        return ("-" if self.sign else "+") + "Inf"

    def __eq__(self, other):
        return isinstance(other, Special) and self.kind == other.kind and (
            self.kind == "nan" or self.sign == other.sign)


class SignedZero(Fraction):
    """Fraction(0) с сохранённым знаком для корректной IEEE +-0 семантики при
    конверсии в float/FP32/FP64. Численно всегда ==0 (наследуется от Fraction),
    но хранит атрибут .sign для downstream-кода, которому нужен знак."""
    def __new__(cls, sign=0):
        obj = super().__new__(cls, 0)
        obj.sign = sign
        return obj


def pow2(e: int) -> Fraction:
    """Точная 2^e как Fraction для любого целого e (в т.ч. отрицательного)."""
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def classify(fmt: GFFormat, raw: int) -> str:
    """Возвращает один из 5 классов: 'zero' | 'subnormal' | 'normal' | 'inf' | 'nan'."""
    raw &= (1 << fmt.N) - 1
    exp = (raw >> fmt.M) & fmt.exp_max
    mant = raw & fmt.mant_max
    if exp == fmt.exp_max:
        return "nan" if mant != 0 else "inf"
    if exp == 0:
        return "subnormal" if mant != 0 else "zero"
    return "normal"


def decode(bits: int, N: int, E: int, M: int, BIAS: int):
    """
    Параметрический golden decode: raw N-битное слово -> Fraction (точное
    конечное значение) | Special('inf'|'nan').

    5 классов decode-закона (HAS_INF-семантика):
      exp==EXP_MAX, mant==0        -> Inf (signed)
      exp==EXP_MAX, mant!=0        -> NaN (тихий, знак не несёт смысла)
      exp==0,       mant==0        -> +-0 (signed zero, знак сохраняется в raw,
                                           но численно 0)
      exp==0,       mant!=0        -> subnormal: (-1)^s * mant/2^M * 2^(1-BIAS)
      иначе (0<exp<EXP_MAX)         -> normal:    (-1)^s * (1+mant/2^M) * 2^(exp-BIAS)
    """
    assert N == 1 + E + M, f"N != 1+E+M ({N} != 1+{E}+{M})"
    exp_max = (1 << E) - 1
    mant_max = (1 << M) - 1
    sign_shift = E + M

    raw = bits & ((1 << N) - 1)
    sign = (raw >> sign_shift) & 1
    exp = (raw >> M) & exp_max
    mant = raw & mant_max

    if exp == exp_max:
        if mant == 0:
            return Special("inf", sign)
        return Special("nan")

    if exp == 0:
        if mant == 0:
            # IEEE-конвенция: числовое значение 0 в обоих случаях, но знак
            # СОХРАНЯЕТСЯ (Fraction не имеет знакового нуля, поэтому
            # возвращаем кортеж (Fraction(0), sign) -- вызывающий код должен
            # использовать raw напрямую для знака в FP32-конверсии; здесь
            # возвращаем ZeroFraction с атрибутом sign для downstream правильного -0.
            return SignedZero(sign)
        val = Fraction(mant, 1 << M) * pow2(1 - BIAS)   # subnormal, implicit=0
    else:
        val = (1 + Fraction(mant, 1 << M)) * pow2(exp - BIAS)  # normal, implicit=1

    return -val if sign else val


def decode_fmt(fmt: GFFormat, raw: int):
    """Удобная обёртка decode() по объекту GFFormat."""
    return decode(raw, fmt.N, fmt.E, fmt.M, fmt.BIAS)


# --------------------------------------------------------------------------
# 4. ENCODE (точное значение -> raw), round-half-to-even + sticky — для
#    генерации проверочных векторов (golden -> RTL сравнение)
# --------------------------------------------------------------------------

def ilog2_floor(a: Fraction) -> int:
    """floor(log2(a)) для точной положительной Fraction a."""
    assert a > 0
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < pow2(e):
        e -= 1
    while Fraction(n, d) >= pow2(e + 1):
        e += 1
    return e


def _round_half_even(x: Fraction, cap):
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


def round_fraction_to_bits(frac: Fraction, bits: int):
    scaled = frac * (1 << bits)
    return _round_half_even(scaled, cap=(1 << bits))


def round_fraction_to_int(x: Fraction):
    return _round_half_even(x, cap=None)


def encode(value, N: int, E: int, M: int, BIAS: int) -> int:
    """
    value: Fraction (точное конечное) | Special | int | float.
    round-half-to-even, gradual underflow (subnormal), overflow -> Inf.
    """
    exp_max = (1 << E) - 1
    mant_max = (1 << M) - 1
    sign_shift = E + M
    pos_zero = 0
    neg_zero = 1 << sign_shift
    pos_inf = exp_max << M
    neg_inf = (1 << sign_shift) | (exp_max << M)
    quiet_nan = (exp_max << M) | 1

    if isinstance(value, Special):
        if value.kind == "nan":
            return quiet_nan
        return neg_inf if value.sign else pos_inf

    v = Fraction(value)
    if v == 0:
        return pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v

    E_ = ilog2_floor(a)
    exp_field = E_ + BIAS

    if exp_field >= 1:
        frac = a / pow2(E_) - 1
        mant, carry = round_fraction_to_bits(frac, M)
        if carry:
            mant = 0
            exp_field += 1
        if exp_field >= exp_max:
            return neg_inf if sign else pos_inf
        return (sign << sign_shift) | (exp_field << M) | (mant & mant_max)
    else:
        scale = pow2(1 - BIAS)
        m_real = a / scale * (1 << M)
        m, _carry = round_fraction_to_int(m_real)
        if m == 0:
            return (sign << sign_shift) | 0
        if m > mant_max:
            return (sign << sign_shift) | (1 << M) | 0
        return (sign << sign_shift) | (m & mant_max)


def encode_fmt(fmt: GFFormat, value) -> int:
    return encode(value, fmt.N, fmt.E, fmt.M, fmt.BIAS)


# --------------------------------------------------------------------------
# 5. Decode -> IEEE binary32 (Python float), только для decode_target=="FP32"
#    Используется как REFERENCE для сравнения с бит-моделью RTL / прошивкой.
# --------------------------------------------------------------------------

import struct


def fraction_to_ieee754_binary32_bits(v) -> int:
    """Fraction | Special -> 32-битное слово IEEE binary32 (round-to-nearest-even
    через нативный float, что корректно, т.к. Python float = binary64, и мы
    затем один раз округляем к binary32 через struct — двойное округление не
    возникает, т.к. binary64 имеет 52 бита мантиссы >> 23 бита FP32 для всех
    forматов Фазы A (M<=19 бит))."""
    if isinstance(v, Special):
        if v.kind == "nan":
            f = float("nan")
        else:
            f = float("-inf") if v.sign else float("inf")
    elif isinstance(v, SignedZero):
        f = -0.0 if v.sign else 0.0
    else:
        # FP32 overflow/underflow saturation ON THE EXACT Fraction, ДО любой
        # попытки float(v): некоторые GF-форматы Фазы A (напр. gf24, gf32)
        # имеют BIAS настолько большой, что часть их диапазона (включая
        # самые малые субнормалы) выходит за пределы binary64 (т.е. и из пределов
        # FP32 тем более) -- прямой float(v) бросает OverflowError на больших
        # целых numerator/denominator ДО того, как успеет насытиться. Поэтому
        # сравниваем точной Fraction-арифметикой с границами FP32 ProLog конверсии.
        FP32_MAX_FRAC = Fraction(340282346638528859811704183484516925440)  # (2-2^-23)*2^127, точно
        FP32_MIN_SUBNORMAL_FRAC = Fraction(1, 1 << 149)  # 2^-149, точно
        av = -v if v < 0 else v
        if av > FP32_MAX_FRAC:
            f = float("-inf") if v < 0 else float("inf")
        elif av != 0 and av < FP32_MIN_SUBNORMAL_FRAC / 2:
            # круглее чем половина минимального субнормала -> округляется в ноль
            f = -0.0 if v < 0 else 0.0
        else:
            f = float(v)  # теперь безопасно: в диапазоне binary64
    packed = struct.pack(">f", f)
    return struct.unpack(">I", packed)[0]


def gf_decode_to_fp32_bits(fmt: GFFormat, raw: int) -> int:
    """Полный путь: raw GF{N} слово -> 32-битное представление IEEE binary32
    (как побитовое uint32). Golden-эталон для сравнения с gf_decode_param.v."""
    v = decode_fmt(fmt, raw)
    return fraction_to_ieee754_binary32_bits(v)


def fraction_to_ieee754_binary64_bits(v) -> int:
    """Fraction | Special -> 64-битное слово IEEE binary64."""
    if isinstance(v, Special):
        if v.kind == "nan":
            f = float("nan")
        else:
            f = float("-inf") if v.sign else float("inf")
    elif isinstance(v, SignedZero):
        f = -0.0 if v.sign else 0.0
    else:
        f = float(v)
    packed = struct.pack(">d", f)
    return struct.unpack(">Q", packed)[0]


def gf_decode_to_fp64_bits(fmt: GFFormat, raw: int) -> int:
    """Для Фазы B (gf48/gf64): raw -> IEEE binary64 бит-слово."""
    v = decode_fmt(fmt, raw)
    return fraction_to_ieee754_binary64_bits(v)


# --------------------------------------------------------------------------
# 6. Self-test / отчёт при прямом запуске
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 78)
    print("gf_decode_ref.py — золотой decode-оракул GF-линейки Trinity")
    print("=" * 78)
    print(f"phi^2 (высокая точность) ~= {float(PHI2):.15f}")
    print()
    print("Проверка phi-правила против SSOT-таблицы (e=round((N-1)/phi^2), "
          "m=N-1-e, bias=2^(e-1)-1):")
    print(f"{'формат':<8}{'N':>5}{'E(ssot)':>9}{'E(calc)':>9}"
          f"{'M(ssot)':>9}{'M(calc)':>9}{'BIAS(ssot)':>12}{'BIAS(calc)':>12}{'  OK?'}")
    all_ok = True
    for name, ok, e_c, m_c, b_c in verify_phi_rule():
        fmt = GF_LINEUP[name]
        mark = "OK" if ok else "MISMATCH"
        all_ok = all_ok and ok
        print(f"{name:<8}{fmt.N:>5}{fmt.E:>9}{e_c:>9}{fmt.M:>9}{m_c:>9}"
              f"{fmt.BIAS:>12}{b_c:>12}  {mark}")
    print()
    print(f"ВЕРДИКТ phi-правила: {'держится ТОЧНО по всей лестнице [Verified как правило]' if all_ok else 'ЕСТЬ РАСХОЖДЕНИЯ — фиксировать!'}")
    print()

    print("Демонстрация decode() для нескольких характерных значений gf16 (bias=31):")
    fmt16 = GF_LINEUP["gf16"]
    demo_raws = [0x0000, 0x8000, 0x7C00 if fmt16.E == 6 else None]
    # gf16: E=6,M=9 -> exp_max=63, shift=15. Построим коды сами:
    zero_raw = 0
    one_raw = encode_fmt(fmt16, Fraction(1))
    half_raw = encode_fmt(fmt16, Fraction(1, 2))
    inf_raw = fmt16.pos_inf
    nan_raw = fmt16.quiet_nan
    smallest_sub_raw = 1  # mant=1, exp=0
    for label, raw in [("+0", zero_raw), ("+1.0", one_raw), ("+0.5", half_raw),
                        ("+Inf", inf_raw), ("qNaN", nan_raw),
                        ("smallest subnormal", smallest_sub_raw)]:
        v = decode_fmt(fmt16, raw)
        cls = classify(fmt16, raw)
        print(f"  {label:<20} raw=0x{raw:04x}  class={cls:<10} value={v}")

    print()
    print("Каталог GF-линейки (17 ячеек) с decode_target:")
    for name, fmt in GF_LINEUP.items():
        print(f"  {name:<8} N={fmt.N:<5} E={fmt.E:<4} M={fmt.M:<5} BIAS={fmt.BIAS:<12} "
              f"status={fmt.status:<13} target={fmt.decode_target}")
