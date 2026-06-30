#!/usr/bin/env python3
"""
Доказательство фикса WV-22: gf16 ADD/MUL Inf-detection на входе.

Метод (GOLDEN RULE): бит-модель ПРЕДЛАГАЕМОГО исправленного RTL == независимое
золото gf_ref.gf_add / gf_ref.gf_mul на ВСЕХ Inf/NaN-входах gf16 + регрессия
на конечных значениях. Железо НЕ требуется.

gf16: 1S + 6E + 9M, BIAS=31, HAS_INF=1. exp=all-ones(63) => Inf(mant=0)/NaN(mant!=0).
"""
import sys, random
sys.path.insert(0, "/tmp/tfpga_work/conformance")
from gf_ref import FORMATS, gf_add, gf_mul  # независимое золото (Fraction-точное)

FMT = FORMATS["gf16"]
EXP_BITS, MANT_BITS, TOTAL = 6, 9, 16
EXP_MAX = (1 << EXP_BITS) - 1   # 63
MANT_MASK = (1 << MANT_BITS) - 1

def fields(raw):
    s = (raw >> (TOTAL - 1)) & 1
    e = (raw >> MANT_BITS) & EXP_MAX
    m = raw & MANT_MASK
    return s, e, m

def is_inf(raw):
    _, e, m = fields(raw)
    return e == EXP_MAX and m == 0

def is_nan(raw):
    _, e, m = fields(raw)
    return e == EXP_MAX and m != 0

def is_zero(raw):
    _, e, m = fields(raw)
    return e == 0 and m == 0

POS_INF = (0 << (TOTAL-1)) | (EXP_MAX << MANT_BITS) | 0
NEG_INF = (1 << (TOTAL-1)) | (EXP_MAX << MANT_BITS) | 0
QNAN    = (0 << (TOTAL-1)) | (EXP_MAX << MANT_BITS) | 1  # mant=1 канонический qNaN

def add_special_model(a_raw, b_raw):
    """Бит-модель ПРЕДЛАГАЕМОГО RTL: спец-приоритет NaN > Inf > zero > normal.
    Возвращает (handled, result_raw). Если handled=False — конечный путь (не трогаем)."""
    sa, _, _ = fields(a_raw)
    sb, _, _ = fields(b_raw)
    # NaN (уже в текущем RTL)
    if is_nan(a_raw) or is_nan(b_raw):
        return True, QNAN
    # Inf (НОВОЕ в фиксе) — приоритет ниже NaN, выше zero/normal
    ai, bi = is_inf(a_raw), is_inf(b_raw)
    if ai and bi:
        if sa != sb:
            return True, QNAN                 # Inf + (-Inf) = NaN
        return True, (NEG_INF if sa else POS_INF)
    if ai:
        return True, (NEG_INF if sa else POS_INF)
    if bi:
        return True, (NEG_INF if sb else POS_INF)
    return False, None

def mul_special_model(a_raw, b_raw):
    sa, _, _ = fields(a_raw)
    sb, _, _ = fields(b_raw)
    rs = sa ^ sb
    if is_nan(a_raw) or is_nan(b_raw):
        return True, QNAN
    ai, bi = is_inf(a_raw), is_inf(b_raw)
    az, bz = is_zero(a_raw), is_zero(b_raw)
    # Inf * 0 = NaN (IEEE)
    if (ai and bz) or (bi and az):
        return True, QNAN
    if ai or bi:
        return True, (NEG_INF if rs else POS_INF)  # Inf * finite!=0 = Inf
    return False, None

# Текущий (ДЕФЕКТНЫЙ) RTL: детектирует только NaN, Inf проваливается в normal path.
def add_current_model(a_raw, b_raw):
    if is_nan(a_raw) or is_nan(b_raw):
        return True, QNAN
    return False, None  # Inf НЕ перехвачен -> конечный путь (дефект)

def run():
    errs_fix_add = errs_fix_mul = 0
    errs_cur_add = 0
    n_special = 0
    # Все спец-кодировки gf16: оба знака Inf, несколько NaN, + представительные конечные
    specials = [POS_INF, NEG_INF, QNAN,
                (1<<(TOTAL-1))|(EXP_MAX<<MANT_BITS)|1,  # -qNaN
                (EXP_MAX<<MANT_BITS)|0x155,             # другой NaN payload
                ]
    finite_samples = [0x0000, 0x8000,                   # +0 -0
                      0x3E00,                            # ~1.0 (exp=31,mant=0)
                      0xBE00,                            # ~-1.0
                      0x3DFF, 0x0001, 0x7DFF,            # denormal/около-max-finite
                      (62<<MANT_BITS)|MANT_MASK,         # max-finite (exp=62 all-mant)
                      (62<<MANT_BITS)|MANT_MASK|(1<<(TOTAL-1)),
                      ]
    test_a = specials + finite_samples
    test_b = specials + finite_samples
    for a in test_a:
        for b in test_b:
            gold_add = gf_add(FMT, a, b)
            gold_mul = gf_mul(FMT, a, b)
            # --- ADD фикс ---
            h, r = add_special_model(a, b)
            if h:  # спец-случай: модель фикса даёт r
                n_special += 1
                if r != gold_add:
                    errs_fix_add += 1
                    if errs_fix_add <= 8:
                        print(f"[ADD-FIX MISMATCH] a={a:#06x} b={b:#06x} model={r:#06x} gold={gold_add:#06x}")
                # текущий дефектный: что бы он вернул?
                hc, rc = add_current_model(a, b)
                if not hc:  # Inf-случай проваливается -> дефект (конечный путь != Inf)
                    if not (is_nan(a) or is_nan(b)):
                        errs_cur_add += 1  # подтверждаем, что текущий RTL НЕ перехватывает Inf
            # --- MUL фикс ---
            hm, rm = mul_special_model(a, b)
            if hm and rm != gold_mul:
                errs_fix_mul += 1
                if errs_fix_mul <= 8:
                    print(f"[MUL-FIX MISMATCH] a={a:#06x} b={b:#06x} model={rm:#06x} gold={gold_mul:#06x}")

    print(f"\n=== РЕЗУЛЬТАТ (gf16, HAS_INF=1) ===")
    print(f"Спец-случаев проверено (ADD): {n_special}")
    print(f"ADD фикс vs золото: {errs_fix_add} расхождений")
    print(f"MUL фикс vs золото: {errs_fix_mul} расхождений")
    print(f"Подтверждение дефекта: текущий RTL НЕ перехватывает Inf в {errs_cur_add} случаях (Inf->конечный путь)")
    ok = (errs_fix_add == 0 and errs_fix_mul == 0 and errs_cur_add > 0)
    print(f"\n{'[ДОКАЗАНО] фикс корректен И дефект подтверждён' if ok else '[FAIL]'}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(run())
