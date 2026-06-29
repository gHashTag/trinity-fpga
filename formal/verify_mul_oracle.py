#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# verify_mul_oracle.py — три-оракульная проверка GF-MUL БЕЗ железа/симулятора.
#
# Цель: доказать, что НЕЗАВИСИМЫЙ целочисленный оракул `ref_fpmul`, вшитый в
# formal/gf_mul_property.v, САМ корректен (acceptance-criterion #1:
# «independent oracle, не bug-equals-bug»). Снимает главный риск формального
# доказательства MUL ДО прогона sby (движок CI smtbmc z3).
#
# Метод (три оракула на КАЖДУЮ пару входов):
#   O1 = Python-порт RTL gf_mul_param.v (conformance/gf_mul_verify.rtl_mul) —
#        faithful-транскрипция DUT с reg_mask (моделирует fixed-width wrap).
#   O2 = Python-порт ref_fpmul из gf_mul_property.v (формальный оракул) —
#        exact integer product + единственный RNE, СТРУКТУРНО иной, чем DUT.
#   O3 = золотой эталон gf_ref.gf_mul (fractions.Fraction) — точная рациональная
#        арифметика, независим от обеих GRS-реализаций.
# Гейт: для всех пар O1 == O2 == O3 (bit-exact). Любое расхождение печатается.
#
# Покрытие: GF6 (2/3) и GF8 (3/4) — EXHAUSTIVE (4096 и 65536 пар).
#           GF12/GF16/GF20/GF24 — представительная случайная выборка.
#   (GF4 BIAS=0 вырожден: pack_denorm -> ±0; умножитель НЕ обслуживает GF4 —
#    его compute-ядро отдельное, как и в gf_mul_param.v pack_denorm BIAS==0.)
#
# Запуск:  python3 formal/verify_mul_oracle.py
# Это SW-доказательство (model==model==Fraction). НЕ HW-conformance.
# Honesty: Vasilev, ORCID 0009-0008-4294-6159, admin@t27.ai. [смоделировано], не железо.
# =============================================================================
import sys, os, random

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "conformance"))

from gf_ref import FORMATS, gf_mul as golden_mul        # O3 — золотой Fraction-эталон
from gf_mul_verify import rtl_mul as dut_mul            # O1 — порт RTL DUT (reg_mask)


# ----------------------------------------------------------------------------
# O2 — порт ref_fpmul из formal/gf_mul_property.v (целочисленный оракул свойства).
#      Exact integer product of significands + единственный RNE; family-split
#      overflow; денормал-результат прямым округлением от iprod. НЕ воспроизводит
#      MSB-скан / GRS-конвейер / pack_denorm DUT -> независимый свидетель.
# ----------------------------------------------------------------------------
def ref_fpmul(fmt, a, b):
    EXP, MANT, BIAS = fmt.exp_bits, fmt.mant_bits, fmt.bias
    HAS_INF = 1 if fmt.has_inf else 0
    SS = EXP + MANT
    EMASK = (1 << EXP) - 1
    MMASK = (1 << MANT) - 1

    sa = (a >> SS) & 1; ea = (a >> MANT) & EMASK; ma = a & MMASK
    sb = (b >> SS) & 1; eb = (b >> MANT) & EMASK; mb = b & MMASK
    sg = sa ^ sb
    az = (ea == 0) and (ma == 0)
    bz = (eb == 0) and (mb == 0)
    adn = (ea == 0) and (ma != 0)
    bdn = (eb == 0) and (mb != 0)
    a_spec = HAS_INF and (ea == EMASK)
    b_spec = HAS_INF and (eb == EMASK)
    a_nan = a_spec and (ma != 0); b_nan = b_spec and (mb != 0)
    a_inf = a_spec and (ma == 0); b_inf = b_spec and (mb == 0)

    qnan = (EMASK << MANT) | 1
    pinf = (EMASK << MANT); ninf = (1 << SS) | (EMASK << MANT)
    pzero = 0; nzero = (1 << SS)

    if a_nan or b_nan:
        return qnan
    if (a_inf and bz) or (b_inf and az):
        return qnan
    if a_inf or b_inf:
        return ninf if sg else pinf
    if az or bz:
        return nzero if sg else pzero

    base_a = (0 if adn else (1 << MANT)) + ma
    base_b = (0 if bdn else (1 << MANT)) + mb
    iprod = base_a * base_b
    if iprod == 0:
        return nzero if sg else pzero

    lead = iprod.bit_length() - 1
    exp_field = ((1 if adn else ea) + (1 if bdn else eb) - BIAS) + (lead - 2 * MANT)

    if exp_field >= 1:
        k = lead - MANT
        frac = (iprod >> k) & ((1 << MANT) - 1)
        gb = ((iprod >> (k - 1)) & 1) if k >= 1 else 0
        tailnz = 1 if (k >= 2 and (iprod & ((1 << (k - 1)) - 1)) != 0) else 0
        lsb_bit = frac & 1
        if gb and (tailnz or lsb_bit):
            frac += 1
            if frac == (1 << MANT):
                frac = 0; exp_field += 1
        if HAS_INF:
            if exp_field >= EMASK:
                return ninf if sg else pinf
            return (sg << SS) | (exp_field << MANT) | (frac & MMASK)
        else:
            if exp_field > EMASK:
                return (sg << SS) | (EMASK << MANT) | MMASK   # max-finite
            return (sg << SS) | (exp_field << MANT) | (frac & MMASK)
    else:
        # денормал-результат: прямое округление от iprod (единственное RNE)
        k = (1 - exp_field) + (lead - MANT)
        if k <= 0:
            m_int = iprod << (-k)
        else:
            frac = (iprod >> k) & ((1 << (MANT + 2)) - 1)
            gb = (iprod >> (k - 1)) & 1
            tailnz = 1 if (k >= 2 and (iprod & ((1 << (k - 1)) - 1)) != 0) else 0
            lsb_bit = frac & 1
            m_int = frac + (1 if (gb and (tailnz or lsb_bit)) else 0)
        if m_int >= (1 << MANT):
            return (sg << SS) | (1 << MANT) | 0       # наименьший нормал
        if m_int == 0:
            return nzero if sg else pzero
        return (sg << SS) | (m_int & MMASK)


# ----------------------------------------------------------------------------
# Прогон трёх оракулов
# ----------------------------------------------------------------------------
def run(name, exhaustive=True, samples=300000, seed=27):
    fmt = FORMATS[name]
    W = fmt.width
    N = 1 << W
    mism_12 = mism_23 = mism_13 = 0
    examples = []
    if exhaustive:
        pairs = ((a, b) for a in range(N) for b in range(N))
        total = N * N
    else:
        rng = random.Random(seed)
        pairs = ((rng.randrange(N), rng.randrange(N)) for _ in range(samples))
        total = samples
    cnt = 0
    for a, b in pairs:
        cnt += 1
        o1 = dut_mul(fmt, a, b)     # DUT (RTL-порт)
        o2 = ref_fpmul(fmt, a, b)   # формальный оракул (ref_fpmul)
        o3 = golden_mul(fmt, a, b)  # Fraction-золото
        if o1 != o2:
            mism_12 += 1
            if len(examples) < 8:
                examples.append(("DUT!=ORACLE", a, b, o1, o2, o3))
        if o2 != o3:
            mism_23 += 1
            if len(examples) < 8:
                examples.append(("ORACLE!=GOLDEN", a, b, o1, o2, o3))
        if o1 != o3:
            mism_13 += 1
    ok = (mism_12 == 0 and mism_23 == 0 and mism_13 == 0)
    print(f"[{name}] EXP={fmt.exp_bits} MANT={fmt.mant_bits} HAS_INF={int(fmt.has_inf)} "
          f"pairs={cnt}/{total} {'EXHAUSTIVE' if exhaustive else 'sample'}")
    print(f"    DUT!=ORACLE: {mism_12}   ORACLE!=GOLDEN: {mism_23}   DUT!=GOLDEN: {mism_13}   "
          f"-> {'PASS (O1==O2==O3)' if ok else 'FAIL'}")
    for tag, a, b, o1, o2, o3 in examples:
        wd = (W + 3) // 4
        print(f"      {tag}: a=0x{a:0{wd}x} b=0x{b:0{wd}x} dut=0x{o1:x} orc=0x{o2:x} gld=0x{o3:x}")
    return ok


if __name__ == "__main__":
    print("=== Три-оракульная проверка GF-MUL (SW, без железа) ===")
    print("    O1=DUT(RTL-порт gf_mul_param)  O2=formal-оракул(ref_fpmul)  O3=Fraction-золото\n")
    all_ok = True
    all_ok &= run("gf6", exhaustive=True)        # 4096 пар
    all_ok &= run("gf8", exhaustive=True)        # 65536 пар
    all_ok &= run("gf12", exhaustive=False, samples=300000)
    all_ok &= run("gf16", exhaustive=False, samples=300000)
    all_ok &= run("gf20", exhaustive=False, samples=300000)
    all_ok &= run("gf24", exhaustive=False, samples=300000)
    print()
    if all_ok:
        print("ИТОГ: формальный оракул ref_fpmul доказан bit-exact против независимого "
              "Fraction-золота И против RTL-порта DUT (GF6/GF8 exhaustive, GF12-24 sample). "
              "Формальное доказательство sby де-рисковано: оракул корректен, нет bug-vs-bug.")
        sys.exit(0)
    else:
        print("ИТОГ: НАЙДЕНЫ РАСХОЖДЕНИЯ — оракул/DUT требует правки до прогона sby.")
        sys.exit(1)
