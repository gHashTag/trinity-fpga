# selector_vs_intrapocket.py — Вариант B (луп 29.07.2026b).
# [измерено — SW proxy, CPU]. seed=20260729.
#
# ЦЕЛЬ (честная постановка): численно ПРОВЕРИТЬ гипотезу КОМПЛЕМЕНТАРНОСТИ двух ОРТОГОНАЛЬНЫХ
# осей адаптивности при СОПОСТАВИМОМ бит-бюджете — перевести утверждение «оси комплементарны»
# из [открытая гипотеза] в [измерено — SW proxy].
#
#   ОСЬ 1 — catalog-selection (GF+A): построчный дискретный argmin-выбор КАРМАНА из
#           РАЗНОРОДНОГО φ-каталога {φ-сплит, e2, INT, lns/nf4}. Выбор МЕЖДУ форматами.
#           SSOT-реализация gfplus_a_v2 (не дублируем).
#
#   ОСЬ 2 — intra-pocket refinement (dMX-СТИЛЬ, arXiv:2606.04115): при ФИКСИРОВАННОМ семействе
#           (minifloat) — построчный локальный поиск РАЗБИЕНИЯ бит (e,m) при e+m+1=N
#           (аналог непрерывного дифференцируемого поиска разрядности dMX ВНУТРИ одного
#           MXFP-семейства, у нас — дискретный локальный перебор допустимых сплитов).
#           Выбор ВНУТРИ одного формата-семейства, НЕ смена класса формата.
#
#   КОМПОЗИЦИЯ (ось 1 ∘ ось 2): GF+A выбирает карман; если карман = minifloat-подобный,
#           поверх него применяется intra-pocket (e,m)-refinement. Демонстрация, что оси
#           СОСТАВЛЯЮТСЯ и совместно не хуже каждой по отдельности (по MSE-метрике выбора).
#
# BINDING (правила честности):
#   • Это НЕ реимплементация dMX (у них дифференцируемый end-to-end поиск + обучение STE).
#     Мы моделируем ТОЛЬКО ось «bit-allocation refinement внутри одного семейства» как
#     контраст оси «pocket-selection между семействами». Обе оценки — СВОЯ SW-модель, [SW proxy].
#   • Гарантия каждой оси и композиции — на СОБСТВЕННОЙ метрике выбора (MSE весов).
#     Downstream (model BPB) НЕ замеряется (инв. №18: SQNR слоя = суррогат, не окупается по BPB).
#   • НЕ заявлять превосходства ни одной оси над другой и над dMX. Вывод — про
#     ОРТОГОНАЛЬНОСТЬ и КОМПОЗИЦИЮ: композиция ≥ max(ось1, ось2) по MSE по построению.
#   • Сопоставление честное ТОЛЬКО при выравнивании эффективных бит (оверхед метадаты).
#
# Метрика отчёта — SQNR (дБ) round-trip quantize→dequantize + MSE весов + eff.bits.
import numpy as np
import torch
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfplus_adaptive_v2 import gfplus_a_v2, overhead_bpe_v2, e8m0_scale
from gfplus_quant import scaled_qd

torch.manual_seed(20260729)
np.random.seed(20260729)


def sqnr_db(x, q):
    x = x.double(); q = q.double()
    sig = (x * x).sum().item()
    err = ((x - q) ** 2).sum().item()
    if err <= 0:
        return float("inf")
    return 10.0 * np.log10(sig / max(err, 1e-30))


# ─────────── ось 2: intra-pocket (e,m)-refinement внутри minifloat-семейства (dMX-стиль) ───────────
def _valid_splits(N, e_max=8):
    """Допустимые разбиения (e,m) при e+m+1=N, 1≤e≤e_max, m≥0. bias = 2^(e-1)-1 (стандарт).
    e_max ограничен 8 — экспоненты >8 дают нереалистичный диапазон (overflow bias)
    и никогда не выигрывают на per-row-scaled данных (узкий внутристрочный диапазон)."""
    out = []
    for e in range(1, min(N, e_max + 1)):
        m = N - 1 - e
        if m < 0:
            continue
        bias = 2 ** (e - 1) - 1
        out.append((e, m, bias))
    return out


def intrapocket_refine(x, N, group=16, scale_mode="e8m0"):
    """dMX-СТИЛЬ: ФИКСИРОВАНО семейство minifloat; на каждую подгрупп из `group` элементов
    построчно ищем ЛУЧШЕЕ разбиение бит (e,m) при e+m+1=N (аналог per-block bit-allocation
    dMX). Заголовок = log2(#splits) бит на подгруппу. per-row контейнерный scale — как в GF+A."""
    x = x.double()
    R, C = x.shape
    splits = _valid_splits(N)
    hdr_bits = float(np.ceil(np.log2(max(len(splits), 1))))
    if scale_mode == "e8m0":
        amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
        s = e8m0_scale(amax)
    else:
        s = torch.ones(R, 1, dtype=x.dtype)
    xin = x / s

    out = torch.zeros_like(xin)
    G = (C + group - 1) // group
    for r in range(R):
        for g in range(G):
            j0, j1 = g * group, min((g + 1) * group, C)
            seg = xin[r, j0:j1].unsqueeze(0)
            best_q, best_e = None, float("inf")
            for (e, m, bias) in splits:                 # локальный перебор разбиения бит
                q = scaled_qd(seg, "mf", block=None, e=e, m=m, bias=bias).squeeze(0)
                err = ((seg.squeeze(0) - q) ** 2).sum().item()
                if err < best_e:
                    best_e, best_q = err, q
            out[r, j0:j1] = best_q
    q_full = out * s
    ov = (8.0 if scale_mode == "e8m0" else 16.0) / C + hdr_bits / group
    return q_full, ov


# ─────────── композиция: GF+A выбор кармана + intra-pocket refinement поверх ───────────
def composed_refine(x, N, group=16, scale_mode="e8m0"):
    """Ось1⊕Ось2 (честная композиция = ОБЪЕДИНЕНИЕ каталогов обеих осей): каждая строка
    получает argmin-выбор МЕЖДУ двумя кандидатами: (а) лучший GF+A-карман из φ-каталога
    и (б) intra-pocket-доуточнённый minifloat. По ПОСТРОЕНИЮ per-row MSE ≤ min(ось1, ось2):
    композиция = единый более широкий каталог карманов (обе оси — ортогональные источники).
    ЗАМЕЧАНИЕ О БЮДЖЕТЕ: ось 2 тратит больше бит (тонкий per-group заголовок) — поэтому
    сравнение SQNR между осями НЕ бит-выровнено; честный вывод — только про ортогональность
    (композиция ≥ каждой оси по MSE), НЕ про «композиция бесплатна»."""
    q1 = gfplus_a_v2(x, N, group_K=1, scale_mode=scale_mode)
    q2, ov2 = intrapocket_refine(x, N, group=group, scale_mode=scale_mode)
    xd = x.double()
    e1 = ((xd - q1.double()) ** 2).sum(dim=-1)
    e2 = ((xd - q2.double()) ** 2).sum(dim=-1)
    take2 = (e2 < e1).unsqueeze(-1)
    out = torch.where(take2, q2.double(), q1.double())
    ov1 = overhead_bpe_v2(x, N, group_K=1, scale_mode=scale_mode)
    # оверхед: объединённый каталог — больший из двух заголовков + 1 бит выбора оси/строку
    ov = max(ov1, ov2) + 1.0 / x.shape[1]
    return out, ov


# ─────────── датасеты ───────────
def make_rows(dist, R=64, C=256):
    if dist == "uniform":
        return torch.rand(R, C) * 2 - 1
    if dist == "gaussian":
        return torch.randn(R, C)
    if dist == "heavy":
        return torch.distributions.StudentT(2.5).sample((R, C))
    if dist == "mixed_outlier":
        base = torch.randn(R, C)
        idx = torch.randperm(R)[: R // 4]
        base[idx] *= 12.0
        return base
    raise ValueError(dist)


def load_microlm_weights():
    for p in ("/home/user/workspace/trinity-fpga/parameter_golf_gf8_ablation/"
              "gfplus_line/micro_lm.pt",
              "/home/user/workspace/micro_lm.pt"):
        if os.path.exists(p):
            sd = torch.load(p, map_location="cpu")
            mats = [v for v in sd.values() if v.ndim == 2 and min(v.shape) >= 32]
            if mats:
                return mats
    return None


def run_class(N, group=16):
    print(f"\n{'='*84}\n  Класс N={N} бит  (подгруппа dMX-стиля = {group}, splits={len(_valid_splits(N))})\n{'='*84}")
    print(f"  {'данные':<16}{'ось':<28}{'SQNR дБ':>10}{'MSE':>13}{'эфф.бит':>10}")
    rows = []
    for dist in ("uniform", "gaussian", "heavy", "mixed_outlier"):
        x = make_rows(dist, R=64, C=256)
        # ось 1: catalog-selection (GF+A)
        q1 = gfplus_a_v2(x, N, group_K=1, scale_mode="e8m0")
        ov1 = overhead_bpe_v2(x, N, group_K=1, scale_mode="e8m0")
        s1, m1 = sqnr_db(x, q1), ((x.double() - q1.double()) ** 2).mean().item()
        # ось 2: intra-pocket refinement (dMX-стиль)
        q2, ov2 = intrapocket_refine(x, N, group=group, scale_mode="e8m0")
        s2, m2 = sqnr_db(x, q2), ((x.double() - q2.double()) ** 2).mean().item()
        # композиция 1∘2
        q3, ov3 = composed_refine(x, N, group=group, scale_mode="e8m0")
        s3, m3 = sqnr_db(x, q3), ((x.double() - q3.double()) ** 2).mean().item()
        print(f"  {dist:<16}{'1 catalog GF+A':<28}{s1:>10.2f}{m1:>13.3e}{N+ov1:>10.3f}")
        print(f"  {dist:<16}{'2 intra-pocket dMX-стиль':<28}{s2:>10.2f}{m2:>13.3e}{N+ov2:>10.3f}")
        print(f"  {dist:<16}{'1∘2 композиция':<28}{s3:>10.2f}{m3:>13.3e}{N+ov3:>10.3f}")
        rows.append(dict(dist=dist, N=N,
                         sqnr_catalog=round(s1, 3), sqnr_intra=round(s2, 3), sqnr_comp=round(s3, 3),
                         mse_catalog=m1, mse_intra=m2, mse_comp=m3,
                         effbits_catalog=round(N + ov1, 4), effbits_intra=round(N + ov2, 4),
                         effbits_comp=round(N + ov3, 4)))
    return rows


def main():
    all_rows = []
    for N in (4, 6, 8, 12, 16):
        all_rows += run_class(N)

    mats = load_microlm_weights()
    real_rows = []
    if mats:
        print(f"\n{'='*84}\n  Реальные веса микро-LM ({len(mats)} матриц)\n{'='*84}")
        for N in (4, 8):
            sc = si = so = 0.0
            for W in mats:
                sc += sqnr_db(W, gfplus_a_v2(W, N, group_K=1, scale_mode="e8m0"))
                qi, _ = intrapocket_refine(W, N, scale_mode="e8m0"); si += sqnr_db(W, qi)
                qo, _ = composed_refine(W, N, scale_mode="e8m0"); so += sqnr_db(W, qo)
            sc /= len(mats); si /= len(mats); so /= len(mats)
            print(f"  N={N:<3} catalog GF+A={sc:6.2f} | intra dMX-стиль={si:6.2f} | "
                  f"композиция 1∘2={so:6.2f} дБ")
            real_rows.append(dict(N=N, sqnr_catalog=round(sc, 3), sqnr_intra=round(si, 3),
                                  sqnr_comp=round(so, 3), source="micro_lm_real"))
    else:
        print("\n[инфо] micro_lm.pt не найден — только синтетика.")

    # проверка инварианта: композиция ≥ max(catalog, intra) по MSE (метрика выбора) на синтетике
    viol = [r for r in all_rows if r["mse_comp"] > min(r["mse_catalog"], r["mse_intra"]) + 1e-12]
    print(f"\n[инвариант] строк, где композиция ХУЖЕ лучшей одиночной оси по MSE: {len(viol)} из {len(all_rows)}")

    out = dict(seed=20260729,
               note="[измерено — SW proxy, CPU] Вариант B (луп 29.07b): ось1 catalog-select "
               "(GF+A, выбор МЕЖДУ форматами) vs ось2 intra-pocket refinement (dMX-стиль, поиск "
               "(e,m)-разбиения ВНУТРИ minifloat-семейства) + композиция 1∘2. Гарантия на MSE-"
               "метрике выбора, НЕ downstream. Превосходство НЕ заявляется — вывод про "
               "ортогональность и композицию (композиция ≥ max одиночных по MSE по построению).",
               invariant_violations=len(viol),
               synthetic=all_rows, real=real_rows)
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "selector_vs_intrapocket_results.json")
    with open(fn, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {fn}")


if __name__ == "__main__":
    main()
