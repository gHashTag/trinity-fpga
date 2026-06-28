#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_mul_rtl.py — НЕЗАВИСИМАЯ верификация behavioral-ядра умножения gf_mul_param.v.

Метод: Python-транскрипция RTL-алгоритма (rtl_mul) — оракул №1 в песочнице
(НЕ зависит от iverilog), сверяется с золотым эталоном gf_mul (точная Fraction)
из gf_add_ref.py — оракул №0.

!!! КРИТИЧЕСКИЙ УРОК (28.06.2026) !!!
  Python-транскрипция с native-int НЕ ловит fixed-width wrap/overflow баги RTL.
  Реальный пример: mant_rnd был reg[MANT:0] (MANT+1 бит); +1 к all-ones давал
  wrap->0 в Verilog, и carry (exp++) терялся. Python-инт без маски carry
  СОХРАНЯЛ -> транскрипция была точнее самого RTL и ПРОПУСТИЛА баг
  (1376/65536 GF8). Независимый from-spec iverilog-оракул №2 его поймал.
  ФИКС: каждый reg[N:0] в транскрипции ДОЛЖЕН маскироваться reg_mask(x,N+1)
  в точках присваивания. ВСЁ РАВНО Python-транскрипция СЛАБЕЕ from-spec
  integer-reference на настоящем iverilog — последний ОБЯЗАТЕЛЕН.

Совпадение rtl_mul == gf_mul = логика подтверждена [смоделировано] — но
ТОЛЬКО при верном моделировании ширины регистров. DSP48E1-версия здесь НЕ
моделируется (UNISIM требует Vivado).

Honesty: Vasilev, ORCID 0009-0008-4294-6159. [смоделировано], не железо.
"""
import sys, random
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_mul as ref_mul


def reg_mask(x, nbits):
    """Модель Verilog reg[nbits-1:0]: усекает к nbits битам (wrap, как в железе).
    ОБЯЗАТЕЛЬНО применять в каждой точке присваивания reg в транскрипции,
    иначе native-int Python скроет fixed-width wrap/overflow баги RTL."""
    return x & ((1 << nbits) - 1)


def rtl_mul(fmt, a_raw, b_raw):
    """Faithful транскрипция алгоритма gf_mul_param.v (behavioral-ядро)."""
    EXP = fmt.exp_bits
    MANT = fmt.mant_bits
    BIAS = fmt.bias
    TOTAL = fmt.width
    HAS_INF = 1 if fmt.has_inf else 0
    EXP_MAX = (1 << EXP) - 1
    MANT_MAX = (1 << MANT) - 1
    SS = EXP + MANT  # sign shift

    def field(raw):
        s = (raw >> SS) & 1
        e = (raw >> MANT) & EXP_MAX
        m = raw & MANT_MAX
        return s, e, m

    sa, ea, ma = field(a_raw)
    sb, eb, mb = field(b_raw)
    result_sign = sa ^ sb

    # спец-коды
    CODE_PINF = (EXP_MAX << MANT)
    CODE_NINF = (1 << SS) | (EXP_MAX << MANT)
    CODE_NAN = (EXP_MAX << MANT) | 1   # канонический quiet-NaN, знак=0 (как fmt.quiet_nan)
    CODE_PZERO = 0
    CODE_NZERO = (1 << SS)

    a_zero = (ea == 0) and (ma == 0)
    b_zero = (eb == 0) and (mb == 0)
    a_denorm = (BIAS > 0) and (ea == 0) and (ma != 0)
    b_denorm = (BIAS > 0) and (eb == 0) and (mb != 0)
    a_special = (HAS_INF != 0) and (ea == EXP_MAX)
    b_special = (HAS_INF != 0) and (eb == EXP_MAX)
    a_inf = a_special and (ma == 0)
    b_inf = b_special and (mb == 0)
    a_nan = a_special and (ma != 0)
    b_nan = b_special and (mb != 0)

    # --- спец-края (NaN > 0*Inf > Inf > zero) ---
    if a_nan or b_nan:
        return CODE_NAN
    if (a_inf and b_zero) or (b_inf and a_zero):
        return CODE_NAN
    if a_inf or b_inf:
        return CODE_NINF if result_sign else CODE_PINF
    if a_zero or b_zero:
        return CODE_NZERO if result_sign else CODE_PZERO

    # --- значащие (implicit = !denorm) ---
    ma_f = ((0 if a_denorm else 1) << MANT) | ma
    mb_f = ((0 if b_denorm else 1) << MANT) | mb
    ea_eff = 1 if a_denorm else ea
    eb_eff = 1 if b_denorm else eb

    prod = ma_f * mb_f                       # ширина 2*(MANT+1) [erratum 2M+2]
    # er_real = ea_real + eb_real, где per-operand real exp:
    #   normal: ea-BIAS ; denorm: 1-BIAS. Значит er_real = ea_eff+eb_eff-2*BIAS.
    # val = prod * 2^(er_real - 2*MANT). exp_field = E+BIAS, E = msb-2*MANT+er_real.
    er_real = ea_eff + eb_eff - 2 * BIAS

    if prod == 0:
        return CODE_NZERO if result_sign else CODE_PZERO

    # MSB произведения
    msb = prod.bit_length() - 1
    # exp_field = E + BIAS = (msb - 2*MANT + er_real) + BIAS
    exp_field = (msb - 2 * MANT + er_real) + BIAS

    # Решение normal-vs-denormal ПО НЕОКРУГЛЁННОМУ exp_field (до округления).
    # Денормал-ветка работает НАПРЯМУЮ от prod (единственное округление,
    # без потери sticky-битов — отличие от старой логики с двойным округлением).
    if exp_field < 1:
        return pack_denorm(fmt, result_sign, prod, er_real)

    # ----- НОРМАЛЬНАЯ ветка (exp_field >= 1 по MSB) -----
    # дробная часть значащей: MANT бит ниже MSB + G,R,S
    mant_field = 0
    for k in range(MANT + 1):
        pos = msb - MANT + k
        if pos >= 0:
            mant_field |= ((prod >> pos) & 1) << k
    guard = (prod >> (msb - MANT - 1)) & 1 if (msb - MANT - 1) >= 0 else 0
    round_b = (prod >> (msb - MANT - 2)) & 1 if (msb - MANT - 2) >= 0 else 0
    sticky = 0
    lim = msb - MANT - 2
    if lim > 0:
        if (prod & ((1 << lim) - 1)) != 0:
            sticky = 1

    # RNE.
    # mant_rnd моделирует Verilog reg[MANT+1:0] = MANT+2 бит (ФИКС 28.06):
    #   раньше был reg[MANT:0] (MANT+1 бит) -> +1 к all-ones wrap->0,
    #   carry-check не срабатывал, exp++ терялся. reg_mask делает
    #   транскрипцию faithful к фиксированной ширине.
    REG_W = MANT + 2  # ширина mant_rnd в битах (= MANT_BITS+1 : 0)
    lsb = mant_field & 1
    if guard and (round_b or sticky or lsb):
        mant_rnd = reg_mask((mant_field & ((1 << (MANT + 1)) - 1)) + 1, REG_W)
    else:
        mant_rnd = reg_mask(mant_field & ((1 << (MANT + 1)) - 1), REG_W)
    # carry из округления (значащая стала 2.0): mant_rnd > 1.111..1
    if mant_rnd > ((1 << (MANT + 1)) - 1):
        mant_rnd >>= 1
        exp_field += 1

    # упаковка family-split overflow
    if HAS_INF != 0:
        if exp_field >= EXP_MAX:
            return CODE_NINF if result_sign else CODE_PINF
        return (result_sign << SS) | (exp_field << MANT) | (mant_rnd & MANT_MAX)
    else:
        if exp_field > EXP_MAX:
            sat = (EXP_MAX << MANT) | MANT_MAX
            return (result_sign << SS) | sat
        return (result_sign << SS) | (exp_field << MANT) | (mant_rnd & MANT_MAX)


def pack_denorm(fmt, sgn, prod, er_real):
    """gradual-underflow упаковка НАПРЯМУЮ от точного prod (единственное округление).
    Истинное значение = prod * 2^(er_real - 2*MANT).
    Денормал-поле (MANT бит, без implicit) = round( value / 2^(1-BIAS-MANT) )
      = round( prod * 2^(er_real - 2*MANT + MANT + BIAS - 1) )
      = round( prod * 2^(er_real - MANT + BIAS - 1) ) = round( prod * 2^p ).
    p>=0 -> точный left-shift; p<0 -> right-shift на (-p) с RNE+sticky.
    """
    MANT = fmt.mant_bits
    BIAS = fmt.bias
    SS = fmt.exp_bits + fmt.mant_bits
    if BIAS == 0:
        return (sgn << SS)  # GF4 вырожден
    p = er_real - MANT + BIAS - 1
    if p >= 0:
        mant_out = prod << p          # точно, без округления
    else:
        shift = -p                    # >=1
        if shift >= prod.bit_length() + 2:
            return (sgn << SS)        # всё уходит в underflow к ±0
        guard = (prod >> (shift - 1)) & 1
        sticky = 1 if (prod & ((1 << (shift - 1)) - 1)) else 0
        q = prod >> shift
        lsb = q & 1
        if guard and (sticky or lsb):
            q += 1
        mant_out = q
    # перенос в наименьший нормал (mant_out достигло 2^MANT)?
    if mant_out >= (1 << MANT):
        return (sgn << SS) | (1 << MANT)
    if mant_out == 0:
        return (sgn << SS)            # округлилось к ±0
    return (sgn << SS) | (0 << MANT) | mant_out


def run(name, sample=None, seed=0):
    fmt = FORMATS[name]
    W = fmt.width
    N = 1 << W
    rng = random.Random(seed)
    mism = []
    skipped = 0

    def one(a, b):
        nonlocal skipped
        ref = ref_mul(fmt, a, b)
        got = rtl_mul(fmt, a, b)
        if ref != got:
            return (a, b, ref, got)
        return None

    if sample is None:
        total = 0
        for a in range(N):
            for b in range(N):
                total += 1
                r = one(a, b)
                if r:
                    mism.append(r)
        mode = f"exhaustive {total}"
    else:
        for _ in range(sample):
            a = rng.randrange(N)
            b = rng.randrange(N)
            r = one(a, b)
            if r:
                mism.append(r)
        mode = f"representative {sample}"

    status = "OK" if not mism else f"FAIL ({len(mism)})"
    print(f"{name}: {mode} -> mismatches = {len(mism)}  [{status}]")
    for (a, b, ref, got) in mism[:8]:
        print(f"    a={a:0{(W+3)//4}x} b={b:0{(W+3)//4}x} ref={ref:0{(W+3)//4}x} got={got:0{(W+3)//4}x}")
    return len(mism)


if __name__ == "__main__":
    total = 0
    total += run("gf6", sample=None)
    total += run("gf8", sample=None)
    total += run("gf12", sample=300000)
    total += run("gf16", sample=300000)
    total += run("gf20", sample=300000)
    print(f"\nTOTAL mismatches (rtl_mul vs gf_mul golden) = {total}")
