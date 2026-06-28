#!/usr/bin/env python3
# =============================================================================
# verify_adder_oracle.py — три-оракульная проверка БЕЗ железа/симулятора.
#
# Цель: доказать, что НЕЗАВИСИМЫЙ целочисленный оракул `ref_fpadd`, вшитый в
# formal/gf_adder_property.v, САМ корректен (acceptance-criterion #1:
# «independent oracle, не bug-equals-bug»). Это снимает главный риск формального
# доказательства ДО прогона sby на машине пользователя.
#
# Метод (три оракула на КАЖДУЮ пару входов):
#   O1 = Python-порт RTL gf_adder_param.v (поведенческая модель DUT).
#   O2 = Python-порт ref_fpadd из gf_adder_property.v (формальный оракул).
#   O3 = арифметика точных дробей (fractions.Fraction) + один шаг RNE — золотой
#        эталон, независимый от обеих реализаций GRS-конвейера.
# Гейт: для всех пар O1 == O2 == O3 (bit-exact). Любое расхождение печатается.
#
# Покрытие: GF6 (1/2/3) и GF8 (1/3/4) — EXHAUSTIVE (4096 и 65536 пар).
#           Опционально GF12/GF16 — репрезентативная выборка (§3.5-классы).
#
# Запуск:  python3 formal/verify_adder_oracle.py
# Это SW-доказательство (model==model==Fraction). НЕ HW-conformance.
# =============================================================================
import sys
from fractions import Fraction

# ----------------------------------------------------------------------------
# Общие декодеры формата (S | EXP | MANT), bias = 2^(EXP-1)-1, HAS_INF=0
# ----------------------------------------------------------------------------
def decode_fields(x, EXP, MANT):
    TOTAL = 1 + EXP + MANT
    s = (x >> (TOTAL - 1)) & 1
    e = (x >> MANT) & ((1 << EXP) - 1)
    m = x & ((1 << MANT) - 1)
    return s, e, m

def to_fraction(x, EXP, MANT):
    """Точное рациональное значение кода x (HAS_INF=0, exp=all-ones финитен)."""
    BIAS = (1 << (EXP - 1)) - 1
    s, e, m = decode_fields(x, EXP, MANT)
    sign = -1 if s else 1
    if e == 0:
        if m == 0:
            return Fraction(0)
        # денормал: (m / 2^MANT) * 2^(1-BIAS)
        return sign * Fraction(m, 1 << MANT) * Fraction(2) ** (1 - BIAS)
    # нормал: (1 + m/2^MANT) * 2^(e-BIAS)
    return sign * (1 + Fraction(m, 1 << MANT)) * Fraction(2) ** (e - BIAS)

# ----------------------------------------------------------------------------
# O3 — золотой эталон: точная сумма дробей -> ближайший код (RNE), HAS_INF=0.
# ----------------------------------------------------------------------------
def golden_add(a, b, EXP, MANT):
    BIAS = (1 << (EXP - 1)) - 1
    va, vb = to_fraction(a, EXP, MANT), to_fraction(b, EXP, MANT)
    s = va + vb

    # Зеркалим zero-passthrough DUT (сохранение знака):
    az = (to_fraction(a, EXP, MANT) == 0)
    bz = (to_fraction(b, EXP, MANT) == 0)
    if az and bz:
        sa, _, _ = decode_fields(a, EXP, MANT)
        sb, _, _ = decode_fields(b, EXP, MANT)
        return (1 << (1 + EXP + MANT - 1)) if (sa and sb) else 0  # -0 iff both -0
    if az:
        return b
    if bz:
        return a

    if s == 0:
        return 0  # отмена -> +0

    sign = 1 if s < 0 else 0
    mag = abs(s)

    # наименьший денормал-шаг
    unit = Fraction(2) ** (1 - BIAS) * Fraction(1, 1 << MANT)
    max_finite = (1 + Fraction((1 << MANT) - 1, 1 << MANT)) * Fraction(2) ** (((1 << EXP) - 1) - BIAS)

    # найти показатель нормальной формы
    # mag = 2^E * (1 + f), 0<=f<1  -> E = floor(log2(mag))
    E = 0
    if mag >= 1:
        t = mag
        while t >= 2:
            t /= 2; E += 1
    else:
        t = mag
        while t < 1:
            t *= 2; E -= 1

    if E - BIAS < (1 - BIAS):
        # субнормальный диапазон: квантуем кратно unit (RNE)
        q = mag / unit
        n = int(q)
        frac = q - n
        if frac > Fraction(1, 2) or (frac == Fraction(1, 2) and (n & 1)):
            n += 1
        if n == 0:
            return 0
        # n может перейти в нормальную область — нормальная упаковка ниже это поймает
        val = n * unit
        if val < unit * (1 << MANT):  # всё ещё денормал (m < 2^MANT)
            return (sign << (1 + EXP + MANT - 1)) | (0 << MANT) | (n & ((1 << MANT) - 1))
        mag = val  # перешли в нормаль, пересчёт ниже
        E = 0; t = mag
        while t >= 2:
            t /= 2; E += 1
        while t < 1:
            t *= 2; E -= 1

    # нормальная упаковка: мантисса = round((mag/2^E - 1)*2^MANT) RNE
    frac_part = (mag / (Fraction(2) ** E)) - 1  # в [0,1)
    scaled = frac_part * (1 << MANT)
    n = int(scaled)
    rem = scaled - n
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and (n & 1)):
        n += 1
    if n == (1 << MANT):  # перенос мантиссы
        n = 0; E += 1
    e_field = E + BIAS
    if e_field >= (1 << EXP):  # переполнение -> макс-финит (HAS_INF=0)
        return (sign << (1 + EXP + MANT - 1)) | (((1 << EXP) - 1) << MANT) | ((1 << MANT) - 1)
    return (sign << (1 + EXP + MANT - 1)) | (e_field << MANT) | (n & ((1 << MANT) - 1))

# ----------------------------------------------------------------------------
# O2 — порт ref_fpadd из gf_adder_property.v (целочисленный оракул свойства).
# ----------------------------------------------------------------------------
def ref_fpadd(a, b, EXP, MANT):
    BIAS = (1 << (EXP - 1)) - 1
    TOTAL = 1 + EXP + MANT
    ra, ea, ma = decode_fields(a, EXP, MANT)
    rb, eb, mb = decode_fields(b, EXP, MANT)
    az = (ea == 0 and ma == 0)
    bz = (eb == 0 and mb == 0)
    adn = (BIAS > 0 and ea == 0 and ma != 0)
    bdn = (BIAS > 0 and eb == 0 and mb != 0)
    # FIX: (+/-0)+(+/-0) -> -0 только если оба -0 (зеркало DUT)
    if az and bz:
        return (1 << (TOTAL - 1)) if (ra and rb) else 0
    if az:
        return b
    if bz:
        return a
    base_a = (0 if adn else (1 << MANT)) + ma
    base_b = (0 if bdn else (1 << MANT)) + mb
    sh_a = (1 if adn else ea) - 1
    sh_b = (1 if bdn else eb) - 1
    sa_mag = base_a << sh_a
    sb_mag = base_b << sh_b
    ssum = (-sa_mag if ra else sa_mag) + (-sb_mag if rb else sb_mag)
    if ssum == 0:
        return 0
    sg = 1 if ssum < 0 else 0
    mag = -ssum if ssum < 0 else ssum
    lead = 0
    # Граница скана: sh_a = ea-1 (ea до 2^EXP-1), base до 2^(MANT+1).
    # Старший бит mag <= (MANT+1) + (2^EXP - 2). Берём с запасом +4.
    SCAN = (MANT + 1) + ((1 << EXP) - 2) + 4
    for i in range(SCAN):
        if (mag >> i) & 1:
            lead = i
    exp_field = lead - MANT + 1
    frac = 0
    if exp_field >= 1:
        k = lead - MANT
        frac = (mag >> k) & ((1 << MANT) - 1)
        gb = ((mag >> (k - 1)) & 1) if k >= 1 else 0
        tailnz = (1 if (mag & ((1 << (k - 1)) - 1)) != 0 else 0) if k >= 2 else 0
        lsb = frac & 1
        if gb and (tailnz or lsb):
            frac += 1
            if frac == (1 << MANT):
                frac = 0; exp_field += 1
    if exp_field >= (1 << EXP):
        return (sg << (TOTAL - 1)) | (((1 << EXP) - 1) << MANT) | ((1 << MANT) - 1)
    if exp_field <= 0:
        return (sg << (TOTAL - 1)) | (0 << MANT) | (mag & ((1 << MANT) - 1))
    return (sg << (TOTAL - 1)) | ((exp_field & ((1 << EXP) - 1)) << MANT) | (frac & ((1 << MANT) - 1))

# ----------------------------------------------------------------------------
# O1 — порт поведенческой RTL gf_adder_param.v (DUT). HAS_INF=0.
# ----------------------------------------------------------------------------
def dut_add(a, b, EXP, MANT):
    BIAS = (1 << (EXP - 1)) - 1
    TOTAL = 1 + EXP + MANT
    sa, ea, ma = decode_fields(a, EXP, MANT)
    sb, eb, mb = decode_fields(b, EXP, MANT)
    a_zero = (ea == 0 and ma == 0)
    b_zero = (eb == 0 and mb == 0)
    if a_zero and b_zero:
        return (1 << (TOTAL - 1)) if (sa and sb) else 0
    if a_zero:
        return b
    if b_zero:
        return a
    a_dn = (BIAS > 0 and ea == 0 and ma != 0)
    b_dn = (BIAS > 0 and eb == 0 and mb != 0)
    ea_eff = 1 if a_dn else ea
    eb_eff = 1 if b_dn else eb
    ma_f = (0 << MANT | ma) if a_dn else ((1 << MANT) | ma)
    mb_f = (0 << MANT | mb) if b_dn else ((1 << MANT) | mb)
    a_larger = (ea_eff > eb_eff) or (ea_eff == eb_eff and ma_f >= mb_f)
    ediff = (ea_eff - eb_eff) if a_larger else (eb_eff - ea_eff)
    # sticky из меньшего операнда
    shifted = mb_f if a_larger else ma_f
    sticky = 0
    for j in range(MANT + 1):
        if j < ediff - 2:
            sticky |= (shifted >> j) & 1
    ma_ext = ma_f << 3
    mb_ext = mb_f << 3
    if a_larger:
        ma_al = ma_ext
        mb_al_raw = mb_ext >> ediff
        mb_al = (mb_al_raw & ~1) | ((mb_al_raw & 1) | sticky)
    else:
        ma_al_raw = ma_ext >> ediff
        ma_al = (ma_al_raw & ~1) | ((ma_al_raw & 1) | sticky)
        mb_al = mb_ext
    er = ea_eff if a_larger else eb_eff
    sr = sa if a_larger else sb
    same_sign = (sa == sb)
    if same_sign:
        mant_raw = ma_al + mb_al
    else:
        mant_raw = (ma_al - mb_al) if a_larger else (mb_al - ma_al)
    MW_TOP = MANT + 4  # индекс старшего бита mw (ширина MANT+5)
    sg = sr
    mw = mant_raw & ((1 << (MANT + 5)) - 1)
    ew = er
    # overflow add
    if same_sign and ((mw >> (MANT + 4)) & 1):
        old = mw & 1
        mw >>= 1
        mw |= old
        ew += 1
    # subtraction normalize
    if (not same_sign) and mw != 0:
        for _ in range(MANT + 3):
            if (not ((mw >> (MANT + 3)) & 1)) and ew != 0:
                mw = (mw << 1) & ((1 << (MANT + 5)) - 1)
                ew -= 1
    # subnormal subtraction shift
    if (not same_sign) and BIAS > 0 and mw != 0 and ew == 0:
        old = mw & 1
        mw >>= 1
        mw |= old
    # RNE
    g = (mw >> 2) & 1
    r = (mw >> 1) & 1
    s0 = mw & 1
    lsb = (mw >> 3) & 1
    mant_rounded = (mw >> 3)
    if g and (r or s0 or lsb):
        mant_rounded += 1
    if (mant_rounded >> (MANT + 1)) & 1:
        mant_rounded >>= 1
        ew += 1
    # denormal result (add)
    if same_sign and BIAS > 0 and (not ((mw >> (MANT + 3)) & 1)) and ew <= 1:
        ew = 0
    # pack
    if mw == 0:
        return 0
    if (ew >> EXP) & 1:  # ew[EXP] carry -> overflow, HAS_INF=0 -> max finite
        return (sg << (TOTAL - 1)) | (((1 << EXP) - 1) << MANT) | ((1 << MANT) - 1)
    if (ew & ((1 << EXP) - 1)) == 0:
        return (sg << (TOTAL - 1)) | (0 << MANT) | (mant_rounded & ((1 << MANT) - 1))
    return (sg << (TOTAL - 1)) | ((ew & ((1 << EXP) - 1)) << MANT) | (mant_rounded & ((1 << MANT) - 1))

# ----------------------------------------------------------------------------
# Прогон
# ----------------------------------------------------------------------------
def run(EXP, MANT, exhaustive=True, samples=20000, label=""):
    TOTAL = 1 + EXP + MANT
    N = 1 << TOTAL
    mism_12 = mism_23 = mism_13 = 0
    examples = []
    if exhaustive:
        pairs = ((a, b) for a in range(N) for b in range(N))
        total = N * N
    else:
        import random
        random.seed(27)
        pairs = ((random.randrange(N), random.randrange(N)) for _ in range(samples))
        total = samples
    cnt = 0
    for a, b in pairs:
        cnt += 1
        o1 = dut_add(a, b, EXP, MANT)
        o2 = ref_fpadd(a, b, EXP, MANT)
        o3 = golden_add(a, b, EXP, MANT)
        if o1 != o2:
            mism_12 += 1
            if len(examples) < 8:
                examples.append(("DUT≠ORACLE", a, b, o1, o2, o3))
        if o2 != o3:
            mism_23 += 1
            if len(examples) < 8:
                examples.append(("ORACLE≠GOLDEN", a, b, o1, o2, o3))
        if o1 != o3:
            mism_13 += 1
    ok = (mism_12 == 0 and mism_23 == 0 and mism_13 == 0)
    print(f"[{label}] EXP={EXP} MANT={MANT} pairs={cnt}/{total} "
          f"{'EXHAUSTIVE' if exhaustive else 'sample'}")
    print(f"    DUT≠ORACLE: {mism_12}   ORACLE≠GOLDEN: {mism_23}   DUT≠GOLDEN: {mism_13}   "
          f"-> {'PASS (O1==O2==O3)' if ok else 'FAIL'}")
    for tag, a, b, o1, o2, o3 in examples:
        print(f"      {tag}: a={a:0{TOTAL}b} b={b:0{TOTAL}b} dut={o1:0{TOTAL}b} "
              f"orc={o2:0{TOTAL}b} gld={o3:0{TOTAL}b}")
    return ok

if __name__ == "__main__":
    print("=== Три-оракульная проверка GF-ADD (SW, без железа) ===")
    print("    O1=DUT(RTL-порт)  O2=formal-оракул(ref_fpadd)  O3=Fraction-золото(RNE)\n")
    all_ok = True
    all_ok &= run(2, 3, exhaustive=True, label="GF6")    # 4096 пар
    all_ok &= run(3, 4, exhaustive=True, label="GF8")    # 65536 пар
    all_ok &= run(4, 7, exhaustive=False, samples=40000, label="GF12")
    all_ok &= run(6, 9, exhaustive=False, samples=40000, label="GF16")
    print()
    if all_ok:
        print("ИТОГ: формальный оракул ref_fpadd доказан bit-exact против "
              "независимого Fraction-золота (GF6/GF8 exhaustive). "
              "Формальное доказательство sby теперь де-рисковано: оракул корректен.")
        sys.exit(0)
    else:
        print("ИТОГ: НАЙДЕНЫ РАСХОЖДЕНИЯ — оракул/DUT требует правки до прогона sby.")
        sys.exit(1)
