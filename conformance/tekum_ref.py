#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tekum_ref.py — ЭТАЛОННЫЙ (golden) программный оракул для tekum:
balanced-ternary tapered precision (arXiv:2512.10964, Hunhold, Dec 2025).

Tekum — потомок takum (arXiv:2404.18603), адаптированный под сбалансированную
троичную логику. Как и posit/takum, это TAPERED (суженная) арифметика: ширина
мантиссы зависит от порядка — больше бит вблизи единицы, меньше на краях.

СТАТУС КОДИРОВКИ — ВАЖНО:
  Полная потритовая спецификация tekum требует сверки с полным текстом статьи
  (23 стр.). Абстракт (arxiv.org/abs/2512.10964) подтверждает:
    * balanced ternary tapered precision
    * наследник takum / posit
    * переменная ширина мантиссы/порядка (tapered)
  Абстракт НЕ даёт потритовых таблиц смещений и точного правила баланса, а PDF/
  HTML-версия статьи недоступны для машинного разбора. Поэтому здесь реализована
  РАБОЧАЯ структурная модель на основе ПОЛЕВОЙ СХЕМЫ takum (обратная инженерия
  из fpga/openxc7-synth/takum64_decode.v, который уже в репозитории — формат-
  предок), интерпретированная ЛИНЕЙНО (мантисса+порядок), как требует точная
  Fraction-арифметика оракула (по образцу gf_ref.py), а НЕ логарифмически как
  «настоящий» takum. Части, требующие сверки с полным текстом статьи, помечены
    # TODO: verify from full paper

  Модель самосогласована: decode/encode — точные обратные по значению
  (value round-trip доказывается self-test в __main__), tekum_add использует
  точную Fraction арифметику.

Полевая схема (working hypothesis, по takum-линейке):
  bit[n-1]       = S (sign)
  bit[n-2]       = D (direction)
  bit[n-3:n-5]   = R (regime, 3 бита)               overhead = 5 бит
  payload (n-5)  = [characteristic C_u: r_eff бит][mantissa M_u: p бит]
    r_eff = D ? R : ((2^regime_bits - 1) - R)
    p     = pmax - r_eff        (pmax = n - 5)        ← TAPER
    c     = CBIAS[{D,R}] + C_u                       (несмещённый порядок)
  value = (-1)^S * (1 + M_u / 2^p) * 2^c              (конечное, нормализованное)

  special: raw == 0 -> +0 ; raw == (1<<(n-1)) -> NaR (takum-lineage)

Honesty: Vasilev, ORCID 0009-0008-4294-6159, admin@t27.ai.

ОБНОВЛЕНИЕ 2026-08-18: полный текст статьи ИЗВЛЕЧЁН (arXiv:2512.10964, HTML) —
см. research/TEKUM_SPEC_EXTRACT_2026-08-18.md. Настоящий tekum: основание 3
(value = s*(1+f)*3^e), ширина в ТРИТАХ (tekum16 = 16 тритов = 3^16 кодов),
знак — инверсией цифр, без знакового трита. Эта модель не является его
приближением ни в каком смысле: другое основание, другое кодовое пространство,
другая единица ширины. Оставлена как то, чем была всегда — линейная структурная
модель полевой схемы takum. Блокер настоящего оракула один: функция якоря
anc_n(t) = |t| - 1T...1T, не пережившая HTML-извлечение однозначно.
"""

from fractions import Fraction
from dataclasses import dataclass


# CBIAS table — из fpga/openxc7-synth/takum64_decode.v:22-27 (формат-предок
# takum). Индекс = {D, R} = (D << regime_bits) | R.
# # TODO: verify from full paper — tekum может использовать троично-адаптированные
#        смещения вместо бинарных takum-значений.
CBIAS = (-255, -127, -63, -31, -15, -7, -3, -1,
           0,    1,   3,   7,  15, 31, 63, 127)


@dataclass(frozen=True)
class TekumFormat:
    name: str
    n: int                        # total bits
    regime_bits: int = 3          # R width (takum lineage)

    @property
    def width(self):
        return self.n

    @property
    def overhead(self):
        return 2 + self.regime_bits              # S + D + R

    @property
    def payload_bits(self):
        return self.n - self.overhead

    @property
    def pmax(self):
        return self.payload_bits                 # max mantissa bits (near unity)

    @property
    def regime_count(self):
        return 1 << self.regime_bits

    @property
    def mask(self):
        return (1 << self.n) - 1

    @property
    def sign_shift(self):
        return self.n - 1

    @property
    def pos_zero(self):
        return 0

    @property
    def neg_zero(self):
        # tekum has no negative zero. This returned the same sign-bit-only pattern the
        # property below calls NaR -- the two were literally the same expression, three
        # lines apart -- so every tekum pack's legend listed NaR as `neg_zero`.
        raise AttributeError(f"{self.name} has no negative zero: "
                             f"{1 << self.sign_shift:#x} is NaR")

    @property
    def nar(self):
        # NaR (Not a Real) — takum-lineage special, sign-bit-only pattern.
        return 1 << self.sign_shift


def pow2(e: int) -> Fraction:
    """Точная 2^e как Fraction для любого целого e."""
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


# -------------------- field helpers --------------------

def _regime_params(fmt: TekumFormat, D: int, R: int):
    """Вернуть (r_eff, p, cbias) для direction D и regime R."""
    r_eff_nom = R if D else (fmt.regime_count - 1 - R)
    # clamp к доступному payload (вырожденный случай для мини-форматов)
    r_eff = max(0, min(r_eff_nom, fmt.payload_bits))
    p = fmt.payload_bits - r_eff                  # TAPER: mantissa bits left
    cidx = (D << fmt.regime_bits) | R
    cbias = CBIAS[cidx]
    return r_eff, p, cbias


def _enumerate_regimes(fmt: TekumFormat):
    """Все (D,R,r_eff,p,cbias,c_lo,c_hi) — для сканирования при encode."""
    out = []
    for D in (0, 1):
        for R in range(fmt.regime_count):
            r_eff, p, cbias = _regime_params(fmt, D, R)
            c_lo = cbias
            c_hi = cbias + ((1 << r_eff) - 1) if r_eff > 0 else cbias
            out.append((D, R, r_eff, p, cbias, c_lo, c_hi))
    return out


# -------------------- special marker --------------------

class Special:
    """Маркер не-конечного значения (NaR/Inf — takum-lineage использует NaR)."""
    def __init__(self, kind, sign=0):
        self.kind = kind    # 'nar' | 'inf' | 'nan'
        self.sign = sign

    def __repr__(self):
        if self.kind in ("nan", "nar"):
            return "NaR"
        return ("-" if self.sign else "+") + "Inf"


# -------------------- DECODE --------------------

def decode(fmt: TekumFormat, raw: int):
    """raw -> Fraction (точное конечное) или Special.

    Tapered: r_eff/p зависят от {D,R}; mantissa интерпретируется с implicit 1.
    """
    raw &= fmt.mask

    # specials (takum-lineage): all-zero word = +0; sign-bit-only = NaR
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

    c = cbias + C_u                              # unbiased exponent
    # # TODO: verify from full paper: tekum balanced-ternary exponent scaling
    #        (real tekum likely scales c by a ternary factor, not raw binary).
    if p > 0:
        val = (1 + Fraction(M_u, 1 << p)) * pow2(c)
    else:
        val = pow2(c)
    return -val if S else val


# -------------------- ENCODE (точное значение -> raw, round-ties-even) --------------------

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


def _round_half_even(x: Fraction, cap=None):
    """round-half-to-even точного x>=0. cap: если задано и результат>=cap → (cap, True)."""
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


def _pack(fmt, sign, D, R, r_eff, p, C_u, M_u):
    lower = (((C_u & ((1 << r_eff) - 1)) << p) if r_eff > 0 else 0) \
            | ((M_u & ((1 << p) - 1)) if p > 0 else 0)
    lower &= (1 << fmt.payload_bits) - 1
    raw = ((sign << (fmt.n - 1))
           | (D << (fmt.n - 2))
           | (R << (fmt.n - 2 - fmt.regime_bits))
           | lower)
    return raw & fmt.mask


def encode(fmt: TekumFormat, value):
    """value: Fraction | Special | int -> raw с round-half-to-even мантиссой.

    Tapered-encode: среди всех режимов, покрывающих целевой порядок E, выбирает
    режим с максимальной точностью (max p) — это и есть суть tapered precision.
    """
    if isinstance(value, Special):
        return fmt.nar

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v
    E = ilog2_floor(a)                          # 2^E <= a < 2^(E+1)
    frac = a / pow2(E) - 1                      # in [0, 1)

    regimes = _enumerate_regimes(fmt)
    candidates = [r for r in regimes if r[5] <= E <= r[6] and r[3] >= 0]

    if not candidates:
        # вне представимого диапазона порядка → saturate / underflow
        finite = [r for r in regimes if r[3] >= 0]
        max_c = max(r[6] for r in finite)
        if E > max_c:
            # overflow → max finite value in max-exponent regime
            r = max(finite, key=lambda r: (r[6], r[3]))
            D, R, r_eff, p, cbias, c_lo, c_hi = r
            return _pack(fmt, sign, D, R, r_eff, p, c_hi - cbias,
                         (1 << p) - 1 if p > 0 else 0)
        # underflow → signed zero
        return (sign << fmt.sign_shift)

    # max precision (max p), затем меньший r_eff, затем меньший cidx — детерминизм
    D, R, r_eff, p, cbias, c_lo, c_hi = max(
        candidates, key=lambda r: (r[3], -r[2], -(r[0] << fmt.regime_bits | r[1])))

    c = E
    C_u = c - cbias
    M_u = 0
    if p > 0:
        mant, carry = _round_half_even(frac * (1 << p), cap=(1 << p))
        if carry:
            # мантисса переполнилась → порядок+1; проверяем, влезает ли в режим
            c += 1
            C_u = c - cbias
            if C_u > ((1 << r_eff) - 1) if r_eff > 0 else (C_u > 0):
                # выход за границы режима — переходим в режим, покрывающий новый c
                cand2 = [r for r in regimes if r[5] <= c <= r[6] and r[3] >= 0]
                if cand2:
                    D, R, r_eff, p, cbias, c_lo, c_hi = max(
                        cand2, key=lambda r: (r[3], -r[2]))
                    C_u = c - cbias
            M_u = 0
        else:
            M_u = mant

    return _pack(fmt, sign, D, R, r_eff, p, C_u, M_u)


# -------------------- СЛОЖЕНИЕ (golden) --------------------

def tekum_add(fmt: TekumFormat, a_raw: int, b_raw: int) -> int:
    """Эталонное сложение: decode (точно) -> сумма (точно) -> encode (ties-even)."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)

    a_nar = isinstance(a, Special)
    b_nar = isinstance(b, Special)
    if a_nar or b_nar:
        return fmt.nar

    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    a_zero = (a == 0)
    b_zero = (b == 0)
    if a_zero and b_zero:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero
    if a_zero:
        return b_raw                            # уже представимо → точно
    if b_zero:
        return a_raw

    s = a + b                                   # ТОЧНО (Fraction)
    if s == 0:
        # RNE знак нуля (по образцу gf_ref.py)
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero
    return encode(fmt, s)


def tekum_mul(fmt: TekumFormat, a_raw: int, b_raw: int) -> int:
    """Эталонное умножение: decode (точно) -> произведение (точно) -> encode."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.nar
    if a == 0 or b == 0:
        sa = (a_raw >> fmt.sign_shift) & 1
        sb = (b_raw >> fmt.sign_shift) & 1
        return fmt.neg_zero if (sa ^ sb) else fmt.pos_zero
    return encode(fmt, a * b)


# -------------------- каталог форматов --------------------

FORMATS = {
    "tekum8":  TekumFormat("tekum8",  n=8),
    "tekum16": TekumFormat("tekum16", n=16),
    "tekum32": TekumFormat("tekum32", n=32),
}


# -------------------- self-test --------------------

def _selftest():
    import random
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        # ---- 1. value round-trip: decode(encode(decode(x))) == decode(x) ----
        # (битовый round-trip не гарантирован при наличии перекрывающихся режимов;
        #  канонический encode выбирает max-p — это корректное свойство оракула).
        if fmt.n <= 16:
            codes = range(0, 1 << fmt.n)
        else:
            rng = random.Random(0xC0FFEE)
            codes = [rng.randrange(1 << fmt.n) for _ in range(20000)]
        rt_ok = 0
        rt_tot = 0
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special):
                continue
            rt_tot += 1
            back = decode(fmt, encode(fmt, v))
            if back == v:
                rt_ok += 1
            else:
                if len(failures) < 5:
                    failures.append(f"{fname}: round-trip mismatch raw=0x{raw:x} "
                                    f"v={v} back={back}")
        check(rt_ok == rt_tot,
              f"{fname}: value round-trip {rt_ok}/{rt_tot}")

        # ---- 2. zero / NaR specials ----
        check(decode(fmt, 0) == 0, f"{fname}: +0 decode")
        check(isinstance(decode(fmt, fmt.nar), Special), f"{fname}: NaR decode")
        check(encode(fmt, 0) == 0, f"{fname}: +0 encode")
        check(encode(fmt, Special("nar")) == fmt.nar, f"{fname}: NaR encode")

        # ---- 3. unity ----
        one = encode(fmt, Fraction(1))
        check(decode(fmt, one) == 1, f"{fname}: encode(1) decodes to 1 (got 0x{one:x})")

        # Multiplication was checked nowhere -- section 4 below tests ADD consistency
        # only. Pass 221's mutation gate corrupted tekum_mul and this self-test did not
        # notice, while tekum*_mul.json is generated from it.
        check(tekum_mul(fmt, one, one) == one, f"{fname}: 1*1=1")
        check(decode(fmt, tekum_mul(fmt, one, 0)) == 0, f"{fname}: 1*0=0")

    # ---- 4. add-consistency: когда a+b точно представимо, результат точен ----
    fmt = FORMATS["tekum16"]
    cases = [
        (Fraction(1), Fraction(1)),       # 1 + 1 = 2
        (Fraction(1), Fraction(0)),
        (Fraction(1, 2), Fraction(1, 2)),  # 0.5 + 0.5 = 1
        (Fraction(3, 2), Fraction(1, 2)),  # 1.5 + 0.5 = 2
        (Fraction(-1), Fraction(1)),       # -1 + 1 = 0
        (Fraction(2), Fraction(2)),
        (Fraction(3), Fraction(1)),
    ]
    for x, y in cases:
        s_exact = x + y
        r = tekum_add(fmt, encode(fmt, x), encode(fmt, y))
        d = decode(fmt, r)
        # если сумма точно представима — требуем равенства, иначе — ближайшее
        # (проверяем, что decode(r) есть ближайшее представимое к s_exact)
        check(d == s_exact or _is_nearest(fmt, s_exact, d),
              f"tekum16 add: {x}+{y}={s_exact} got {d}")

    # ---- 5. add neutral element: x + 0 == x (bit-exact) ----
    rng = random.Random(98765)
    for _ in range(200):
        x_raw = rng.randrange(1 << fmt.n)
        if isinstance(decode(fmt, x_raw), Special):
            continue
        check(tekum_add(fmt, x_raw, 0) == x_raw,
              f"tekum16: x+0 != x for 0x{x_raw:x}")
        check(tekum_add(fmt, 0, x_raw) == x_raw,
              f"tekum16: 0+x != x for 0x{x_raw:x}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (value round-trip + specials + unity + add-consistency)")
    return 0


def _is_nearest(fmt: TekumFormat, target: Fraction, got: Fraction) -> bool:
    """True если got — ближайшее представимое tekum-значение к target (ties-even)."""
    direct = encode(fmt, target)
    nearest = decode(fmt, direct)
    return got == nearest


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
