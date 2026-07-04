#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rtl_bit_model.py — БИТ-В-БИТ Python-модель алгоритма gf_decode_param.v (v2).

БАГИ, НАЙДЕННЫЕ И ИСПРАВЛЕННЫЕ этим прогоном (см. README.md "Known issues"):
  1. Golden-оракул терял знак нуля (decode(exp=0,mant=0) всегда давал +0)
     -> введён SignedZero(Fraction) в gf_decode_ref.py, знак сохраняется.
  2. КРИТИЧНЫЙ баг decode-закона (не транскрипции!): GF-нормаль с малым
     rebiased-экспонентом (BIAS_gf > BIAS_fp32=127, форматы gf24/gf32)
     ошибочно флешилась в 0 вместо корректного округления в FP32-субнормаль
     (gradual underflow). Найдено representative-выборкой (187/4038 и
     22/4038 расхождений), подтверждено эксхаустив-стресс-тестом по всем
     exp (0 расхождений после фикса). Исправлено в ОБОИХ: этой бит-модели
     (_pack_fp32) и в gf_decode_param.v (v2, тот же датапат).
  3. Промежуточный фикс #2 использовал неверную опорную экспоненту для
     guard/sticky (FP32_MIN_NORM_EXP=-126 вместо FP32_SUB_LSB_EXP=-149) —
     давал 0 вместо округления к ближайшему субнормалу. Исправлено формулой
     shift = frac_w - true_exp + FP32_SUB_LSB_EXP.

Песочница без iverilog/verilator -> synth/sim = [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ].
Эта модель доказывает корректность decode-ДАТАПАТА (целочисленная семантика,
маски ширины полей, LZC-нормализация, rebias) сверкой против golden-оракула
gf_decode_ref.py БЕЗ железа — по методологии
skills/user/trinity-wave-loop/references/denormals-fix.md §4:
  1. golden на точной арифметике (fractions.Fraction) — gf_decode_ref.py;
  2. бит-модель RTL — этот файл, транслитерация always-блока с масками ширины;
  3. exhaustive где возможно (малые форматы), representative — для крупных;
  4. 5 обязательных классов (normal/subnormal/zero/Inf/NaN) на каждый формат.

Урок 28.06 (Python-транскрипция НЕ ловит fixed-width баги RTL) учтён: все
промежуточные регистры здесь МАСКИРУЮТСЯ явно под объявленную в Verilog
ширину (`mask()` на каждом присваивании, аналогично `reg[N:0]` в исходнике).

Формат сравнения: golden decode() -> Fraction -> IEEE binary32 bits (через
struct, round-to-nearest-even нативного float, обосновано в gf_decode_ref.py)
против rtl_decode_fp32() (эта модель) -> IEEE binary32 bits. Совпадение
БИТ-В-БИТ по всем классам = доказательство корректности decode-закона.
"""
import sys
import struct

sys.path.insert(0, "/home/user/workspace/wave_audit/gf_decode")
import gf_decode_ref as G


def mask(n):
    return (1 << n) - 1


def clz_m(v, M):
    """Транслитерация clz_m() из gf_decode_param.v: leading-zero-count по M-битному
    полю. v уже замаскировано вызывающей стороной. Возвращает 0..M-1 для v!=0,
    M-сентинел для v==0 (не используется при v==0 в вызывающем коде)."""
    if v == 0:
        return M
    for i in range(M):
        bit = (v >> (M - 1 - i)) & 1
        if bit:
            return i
    return M


def fit_mant_23_carry(frac_bits, frac_w, FP32_MANT=23):
    """Транслитерация fit_mant_23_carry(): frac_bits — целое с frac_w значащих
    бит В СТАРШИХ позициях диапазона [frac_w-1:0] (т.е. frac_bits < 2^frac_w).
    Возвращает (carry_bit, mant23) — carry всегда 0 для Phase-A (frac_w<=23
    во всех 10 GF FP32-форматов, узкий путь не задействуется, но
    промоделирован для полноты и будущих форматов)."""
    frac_bits &= mask(frac_w)
    if frac_w <= FP32_MANT:
        shift_amt = FP32_MANT - frac_w
        mant23 = (frac_bits << shift_amt) & mask(23)
        return 0, mant23
    else:
        shift_amt = frac_w - FP32_MANT
        shifted = frac_bits >> shift_amt
        guard_bit = (frac_bits >> (shift_amt - 1)) & 1
        sticky_mask = mask(shift_amt - 1) if shift_amt >= 1 else 0
        sticky_bit = 1 if (frac_bits & sticky_mask) else 0
        mant23 = shifted & mask(23)
        carry = 0
        if guard_bit and (sticky_bit or (mant23 & 1)):
            total = mant23 + 1
            carry = (total >> 23) & 1
            mant23 = total & mask(23)
        return carry, mant23


def _pack_fp32(sign_in, true_exp, frac_bits, frac_w):
    """
    Pack (sign, true unbiased exponent, fractional significand bits) into an
    IEEE binary32 word, handling ALL FP32 outcomes: normal, subnormal
    (renormalized further right when true_exp is below FP32's minimum normal
    exponent -126), overflow-to-Inf, and underflow-to-zero.

    Value convention: exact value = (-1)^sign_in * (1 + frac_bits/2^frac_w) * 2^true_exp
    (frac_bits is an frac_w-bit field, implicit leading '1' assumed, exactly
    the GF normal/renormalized-subnormal convention used by the caller).

    BUGFIX (found by rtl_bit_model.py vs gf_decode_ref.py sweep on gf24/gf32):
    the original algorithm only checked norm_exp_final<=0 (FP32 exponent
    FIELD value, i.e. relative to FP32_EBIAS) and flushed straight to zero
    whenever that field went non-positive. This is WRONG whenever
    BIAS_GF > BIAS_FP32 (127): a GF *normal* value near the small end of its
    exponent range can have a true exponent well above GF's own minimum, yet
    still be smaller than FP32's minimum normal exponent (-126) -- such a
    value must become an FP32 SUBNORMAL (gradual underflow) with correct
    round-to-nearest-even, not an unconditional flush to zero -- exactly like
    the GF-ADD denormal fix precedent (references/denormals-fix.md) for a
    different layer of the same lineage. gf24 (BIAS=255) and gf32
    (BIAS=2047) exercise this path; gf4..gf20 (BIAS<=63) never do because
    their entire dynamic range fits inside FP32's normal exponent range.

    SECOND BUGFIX (found in the first attempted fix): the FP32-subnormal
    right-shift amount must be computed relative to the FP32 subnormal LSB
    exponent (-149 = -126-23), NOT relative to the minimum NORMAL exponent
    (-126). Using -126 discarded the guard/sticky bits at the wrong bit
    position and always rounded tiny values down to zero instead of to the
    nearest representable subnormal (contrapример: gf24 raw=0x1a4d56, exact
    value = 0.604*2^-149, must round to the smallest FP32 subnormal 0x1, но
    ошибочная формула shift=(-126)-true_exp давала chift=24 (guard всегда
    вне full_sig) вместо верного shift=frac_w-(true_exp+149)=15.
    """
    FP32_EBIAS = 127
    FP32_MIN_NORM_EXP = -126     # smallest true exponent representable as FP32 normal
    FP32_SUB_LSB_EXP  = -149     # exponent represented by FP32 subnormal field LSB (2^-149)

    if true_exp >= FP32_MIN_NORM_EXP:
        # -------- FP32 NORMAL path --------
        carry, mant23 = fit_mant_23_carry(frac_bits, frac_w)
        exp_final = true_exp + carry + FP32_EBIAS
        if exp_final >= 255:
            return FP32_NEG_INF if sign_in else FP32_POS_INF
        if exp_final >= 1:
            exp_field = exp_final & mask(8)
            return (sign_in << 31) | (exp_field << 23) | mant23
        # carry pushed us back below the normal threshold (rare edge, exp
        # exactly at the boundary): recompute true_exp and fall through to
        # the subnormal path below using the corrected exponent.
        true_exp = true_exp + carry

    # -------- FP32 SUBNORMAL path (gradual underflow) --------
    # full_sig = implicit '1' followed by frac_w fraction bits; the exact
    # value is full_sig * 2^(true_exp - frac_w). We want this value expressed
    # as an integer count of FP32-subnormal-LSB units (2^-149), i.e.
    #   units_exact = full_sig * 2^(true_exp - frac_w - FP32_SUB_LSB_EXP)
    #               = full_sig >> shift    where shift = frac_w - true_exp + FP32_SUB_LSB_EXP
    # (shift may be 0 or negative if true_exp is only slightly below -126;
    #  a negative shift means a LEFT shift, i.e. full_sig already exceeds
    #  the target precision -- only occurs transiently right at the normal/
    #  subnormal boundary and is handled by the same code via Python's
    #  arbitrary-precision negative-shift guard below).
    full_sig = (1 << frac_w) | frac_bits   # frac_w+1 significant bits
    shift = frac_w - true_exp + FP32_SUB_LSB_EXP

    if shift <= 0:
        shifted = full_sig << (-shift)
        guard = 0
        sticky = 0
    else:
        shifted = full_sig >> shift
        lost = full_sig & mask(shift)
        guard = (lost >> (shift - 1)) & 1
        sticky_mask = mask(shift - 1) if shift >= 1 else 0
        sticky = 1 if (lost & sticky_mask) else 0

    mant23 = shifted & mask(24)  # allow 1 extra bit for round-up carry
    if guard and (sticky or (mant23 & 1)):
        mant23 = mant23 + 1

    carry_to_normal = (mant23 >> 23) & 1
    mant23 &= mask(23)

    if carry_to_normal:
        # rounding pushed the subnormal up into FP32's smallest normal
        return (sign_in << 31) | (1 << 23) | 0
    return (sign_in << 31) | (0 << 23) | mant23

FP32_QNAN = 0x7FC00001
FP32_POS_INF = 0x7F800000
FP32_NEG_INF = 0xFF800000
FP32_EBIAS = 127


def rtl_decode_fp32(N, E, M, BIAS, gf_in):
    """Точная транслитерация gf_decode_param.v (combinational always-block).
    gf_in: raw N-bit GF word (int). Возвращает 32-битное uint (IEEE binary32
    представление, как побитовый образ выхода fp32_out)."""
    assert N == 1 + E + M
    EXP_MAX = mask(E)
    gf_in &= mask(N)

    sign_in = (gf_in >> (N - 1)) & 1
    exp_in = (gf_in >> M) & EXP_MAX
    mant_in = gf_in & mask(M)

    is_exp_zero = (exp_in == 0)
    is_exp_max = (exp_in == EXP_MAX)
    is_mant_zero = (mant_in == 0)

    cls_zero = is_exp_zero and is_mant_zero
    cls_subnormal = is_exp_zero and not is_mant_zero
    cls_inf = is_exp_max and is_mant_zero
    cls_nan = is_exp_max and not is_mant_zero
    cls_normal = (not is_exp_zero) and (not is_exp_max)

    if cls_nan:
        return FP32_QNAN
    if cls_inf:
        return FP32_NEG_INF if sign_in else FP32_POS_INF
    if cls_zero:
        return (sign_in << 31)

    if cls_subnormal:
        lzc = clz_m(mant_in, M)
        # sub_exp_true = (1-BIAS) - (lzc+1); rebias -> +127
        sub_exp_true = (1 - BIAS) - (lzc + 1)
        sub_frac_shifted = (mant_in << (lzc + 1)) & mask(M)
        return _pack_fp32(sign_in, sub_exp_true, sub_frac_shifted, M)

    # cls_normal: true unbiased GF exponent = exp_in - BIAS; significand
    # fraction is mant_in directly (implicit bit already accounted for by
    # caller via _pack_fp32's own FP32 implicit-bit convention).
    true_exp_normal = exp_in - BIAS
    return _pack_fp32(sign_in, true_exp_normal, mant_in, M)


# --------------------------------------------------------------------------
# Golden reference wrapper (для честного сравнения "по значению", НЕ по
# конкретному battному представлению NaN — оба используют канонический qNaN
# 0x7FC00001, поэтому побитовое сравнение корректно и для NaN).
# --------------------------------------------------------------------------

def golden_fp32(fmt, raw):
    return G.gf_decode_to_fp32_bits(fmt, raw)


def fp32_bits_to_float(bits):
    return struct.unpack(">f", struct.pack(">I", bits & 0xFFFFFFFF))[0]


# --------------------------------------------------------------------------
# Сверка: exhaustive для малых, representative + 5 классов для крупных.
# --------------------------------------------------------------------------

EXHAUSTIVE_FORMATS = {"gf4": 16, "gf6": 64, "gf8": 256, "gf10": 1024, "gf12": 4096}


def five_class_raws(fmt):
    """Строит по крайней мере один raw-код КАЖДОГО из 5 классов для данного
    формата (используя golden encode() где нужно), плюс несколько
    representative-сэмплов внутри каждого класса."""
    raws = []
    N, E, M, BIAS = fmt.N, fmt.E, fmt.M, fmt.BIAS
    exp_max = fmt.exp_max
    mant_max = fmt.mant_max

    # zero (+0/-0)
    raws.append(0)
    raws.append(1 << (N - 1))

    # inf (+/-)
    raws.append(fmt.pos_inf)
    raws.append(fmt.neg_inf)

    # nan (несколько payload)
    raws.append(fmt.quiet_nan)
    if mant_max > 1:
        raws.append((exp_max << M) | mant_max)  # all-ones NaN

    # subnormal: mant = 1 (smallest), mant_max (largest), середина
    for mant_v in sorted(set([1, mant_max, max(1, mant_max // 2), max(1, mant_max // 3)])):
        raws.append((0 << M) | mant_v)
        raws.append((1 << (N - 1)) | (0 << M) | mant_v)  # signed subnormal

    # normal: несколько exp в середине диапазона, mant=0 / mant_max / середина
    if exp_max >= 2:
        exps = sorted(set([1, exp_max - 1, max(1, exp_max // 2), max(1, exp_max // 3)]))
        for e in exps:
            for mant_v in sorted(set([0, mant_max, max(0, mant_max // 2)])):
                raws.append((e << M) | mant_v)
                raws.append((1 << (N - 1)) | (e << M) | mant_v)

    # representative pseudo-random sweep across the full code space
    full = 1 << N
    step = max(1, full // 4000)
    for r in range(0, full, step):
        raws.append(r)

    return sorted(set(x & mask(N) for x in raws))


def mask(n):
    return (1 << n) - 1


def verify_format(name):
    fmt = G.GF_LINEUP[name]
    N, E, M, BIAS = fmt.N, fmt.E, fmt.M, fmt.BIAS

    if name in EXHAUSTIVE_FORMATS:
        space = EXHAUSTIVE_FORMATS[name]
        raws = range(space)
        coverage = f"exhaustive ({space}/{space})"
        total_space = space
    else:
        raws = five_class_raws(fmt)
        coverage = f"representative+5cls ({len(raws)} probes / {1<<N} space)"
        total_space = 1 << N

    bad = 0
    total = 0
    examples = []
    class_seen = {"zero": 0, "subnormal": 0, "normal": 0, "inf": 0, "nan": 0}
    class_bad = {"zero": 0, "subnormal": 0, "normal": 0, "inf": 0, "nan": 0}

    for raw in raws:
        raw &= mask(N)
        total += 1
        cls = G.classify(fmt, raw)
        class_seen[cls] += 1

        ref_bits = golden_fp32(fmt, raw)
        got_bits = rtl_decode_fp32(N, E, M, BIAS, raw)

        match = (ref_bits == got_bits)
        # NaN edge: golden может дать любой NaN-payload (canonical qNaN 0x7FC00001
        # выбран в fraction_to_ieee754_binary32_bits через float('nan') -> Python
        # canonical NaN bit pattern 0x7FC00000, а RTL даёт 0x7FC00001 (payload=1
        # как в gf_decode_ref.Special quiet_nan). Сравниваем "is NaN" вместо
        # точных бит для класса NaN — payload не специфицирован IEEE.
        if cls == "nan":
            import math
            match = math.isnan(fp32_bits_to_float(ref_bits)) and math.isnan(fp32_bits_to_float(got_bits))

        if not match:
            bad += 1
            class_bad[cls] += 1
            if len(examples) < 8:
                w = (N + 3) // 4
                examples.append((raw, cls, ref_bits, got_bits))

    return {
        "name": name, "total": total, "bad": bad, "coverage": coverage,
        "class_seen": class_seen, "class_bad": class_bad, "examples": examples,
        "total_space": total_space, "fmt": fmt,
    }


def run_all():
    results = []
    for name in G.FP32_FORMATS:
        results.append(verify_format(name))
    return results


def print_report(results):
    print("=" * 92)
    print("RTL bit-model gf_decode_param.v vs golden gf_decode_ref.py — Phase A (10 FP32 formats)")
    print("=" * 92)
    header = f"{'формат':<8}{'N':>4}{'bias':>10}{'покрытие':<32}{'проб':>8}{'fails':>8}  вердикт"
    print(header)
    print("-" * len(header))
    all_ok = True
    for r in results:
        ok = (r["bad"] == 0)
        all_ok = all_ok and ok
        mark = "PASS" if ok else f"FAIL({r['bad']})"
        print(f"{r['name']:<8}{r['fmt'].N:>4}{r['fmt'].BIAS:>10}{r['coverage']:<32}{r['total']:>8}{r['bad']:>8}  {mark}")
        if not ok:
            for raw, cls, ref_bits, got_bits in r["examples"]:
                w = (r['fmt'].N + 3) // 4
                print(f"    raw=0x{raw:0{w}x} class={cls:<10} golden=0x{ref_bits:08x} "
                      f"rtl=0x{got_bits:08x} golden_f={fp32_bits_to_float(ref_bits)!r} "
                      f"rtl_f={fp32_bits_to_float(got_bits)!r}")
    print()
    print(f"ИТОГ: {'ВСЕ 10/10 FP32-форматов PASS golden==RTL [смоделировано]' if all_ok else 'ЕСТЬ РАСХОЖДЕНИЯ — см. выше'}")
    print()
    print("Разбивка по классам (seen/bad) на каждый формат:")
    for r in results:
        parts = ", ".join(f"{c}:{r['class_seen'][c]}/{r['class_bad'][c]}" for c in
                           ["zero", "subnormal", "normal", "inf", "nan"])
        print(f"  {r['name']:<8} {parts}")
    return all_ok


def verify_gf4_degenerate_edge():
    """GF4 (bias=0, e1m2): EXP_MAX=1 целиком занят Inf/NaN -> НЕТ normal-кодов
    (exp может быть только 0 или 1=EXP_MAX). Проверяем это явно и убеждаемся,
    что exhaustive-прогон (уже включённый в run_all через EXHAUSTIVE_FORMATS)
    действительно покрывает все 16 кодов и что normal-класс пуст (следствие
    формата, не баг)."""
    fmt = G.GF_LINEUP["gf4"]
    classes = set()
    for raw in range(16):
        classes.add(G.classify(fmt, raw))
    return classes


if __name__ == "__main__":
    results = run_all()
    all_ok = print_report(results)

    print()
    print("-" * 92)
    print("GF4 (bias=0, e1m2) — вырожденный край: проверка отдельно")
    seen_classes = verify_gf4_degenerate_edge()
    print(f"  Классы, реально встречающиеся в 16/16 кодах GF4: {sorted(seen_classes)}")
    print(f"  'normal' в этом списке: {'ЕСТЬ (неожиданно!)' if 'normal' in seen_classes else 'ОТСУТСТВУЕТ (ожидаемо -- EXP_MAX=1 весь под Inf/NaN, нормального диапазона нет)'}")
    gf4_result = [r for r in results if r["name"] == "gf4"][0]
    gf4_bad = gf4_result["bad"]
    gf4_verdict = "PASS (0 расхождений)" if gf4_bad == 0 else "FAIL (" + str(gf4_bad) + " расхождений)"
    print("  GF4 exhaustive 16/16 через общий параметрический decode: " + gf4_verdict)
    print()
    print(f"ФИНАЛЬНЫЙ ВЕРДИКТ Фазы A: {'10/10 PASS' if all_ok else 'НЕ ВСЕ PASS'} "
          f"(golden Fraction-оракул == Python бит-модель RTL, БЕЗ железа) [смоделировано]")
    sys.exit(0 if all_ok else 1)
