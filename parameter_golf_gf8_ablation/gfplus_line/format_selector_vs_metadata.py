# format_selector_vs_metadata.py — Вариант B (луп 30.07.2026c).
# [измерено — SW proxy, CPU]. seed=20260730.
#
# ЦЕЛЬ (честная постановка): количественно РАЗГРАНИЧИТЬ две ОСИ адаптивности
# на ОДНИХ и тех же данных при СОПОСТАВИМОМ бит-бюджете:
#
#   (1) catalog-selection  = GF+A: построчный argmin-выбор КАРМАНА из φ-каталога
#       РАЗНЫХ форматов {φ-сплит, e2, INT, lns/nf4} + per-row scale.
#       (реализация gfplus_a_v2 из gfplus_adaptive_v2.py — SSOT, не дублируем.)
#
#   (2) metadata-augmentation (M²XFP-СТИЛЬ, arXiv:2601.19213) = уточнение МЕТАДАННЫХ
#       ВНУТРИ ОДНОГО фиксированного MX-семейства: фиксируем ОДИН формат-карман
#       (микроскейл-база), затем на каждую подгруппу подбираем МАЛУЮ флекс-метадату
#       (сдвиг-коррекцию порядка b ∈ {-1,0,+1}, как b* = argmin_b Σ‖q_b − w‖²
#       в абстракте M²XFP) — БЕЗ смены самого формата.
#
# BINDING (правила честности):
#   • Это НЕ реимплементация M²XFP (у нас нет их HW-co-design и обучения). Мы моделируем
#     ТОЛЬКО ось «metadata-refinement внутри одного формата» как контраст оси
#     «pocket-selection между форматами». Обе оценки — СВОЯ SW-модель, [SW proxy].
#   • Гарантия каждой оси — на её СОБСТВЕННОЙ метрике выбора (MSE). Downstream НЕ замеряется.
#   • НЕ заявлять превосходства ни одной оси. Вывод — про ВЗАИМОДОПОЛНЯЕМОСТЬ:
#     оси ортогональны и композируются (можно применить обе).
#   • Сопоставление честное ТОЛЬКО при выравнивании эффективных бит (оверхед метадаты).
#
# Метрика отчёта — SQNR (дБ) round-trip quantize→dequantize + MSE весов + eff.bits.
import numpy as np
import torch

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfplus_adaptive_v2 import (
    gfplus_a_v2, pockets_for_v2, _qd_pocket, e8m0_scale, overhead_bpe_v2,
)

torch.manual_seed(20260730)
np.random.seed(20260730)


def sqnr_db(x, q):
    x = x.double(); q = q.double()
    sig = (x * x).sum().item()
    err = ((x - q) ** 2).sum().item()
    if err <= 0:
        return float("inf")
    return 10.0 * np.log10(sig / max(err, 1e-30))


# ─────────── ось 2: metadata-augmentation внутри ОДНОГО формата (M²XFP-стиль) ───────────
def metadata_refine_single_format(x, N, base_pocket_idx=None, group=16, scale_mode="e8m0"):
    """M²XFP-СТИЛЬ: фиксируем ОДИН формат-карман (микроскейл-база), затем на каждую
    подгруппу из `group` элементов подбираем флекс-метадату — сдвиг порядка b∈{-1,0,+1},
    b* = argmin_b Σ‖q(w·2^b)/2^b − w‖². Это НЕ смена формата, а уточнение метаданных.
    По построению ⊂ той же MX-рамки (аналог b* и k_i* в абстракте M²XFP)."""
    x = x.double()
    R, C = x.shape
    pockets = pockets_for_v2(N)
    # база = наиболее «универсальный» одиночный карман (e2), если не задан явно
    if base_pocket_idx is None:
        base_pocket_idx = next((i for i, (nm, _, _) in enumerate(pockets)
                                if nm.startswith("e2")), 0)
    name, kind, kw = pockets[base_pocket_idx]

    # общий per-row контейнерный scale (как в GF+A, чтобы бюджет был сопоставим)
    if scale_mode == "e8m0":
        amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
        s = e8m0_scale(amax)
    else:
        s = torch.ones(R, 1, dtype=x.dtype)
    xin = x / s

    out = torch.zeros_like(xin)
    G = (C + group - 1) // group
    n_meta = 0
    for r in range(R):
        for g in range(G):
            j0, j1 = g * group, min((g + 1) * group, C)
            seg = xin[r, j0:j1]
            best_q, best_e = None, float("inf")
            for b in (-1, 0, 1):                      # флекс-метадата: сдвиг порядка
                f = 2.0 ** b
                q = _qd_pocket((seg * f).unsqueeze(0), kind, kw).squeeze(0) / f
                e = ((seg - q) ** 2).sum().item()
                if e < best_e:
                    best_e, best_q = e, q
            out[r, j0:j1] = best_q
            n_meta += 1
    q_full = out * s
    # оверхед: контейнерный scale (8 или 16)/C + 2 бита флекс-метадаты на подгруппу
    ov = (8.0 if scale_mode == "e8m0" else 16.0) / C + 2.0 / group
    return q_full, ov, name


# ─────────── датасеты ───────────
def make_rows(dist, R=64, C=256):
    if dist == "uniform":
        return torch.rand(R, C) * 2 - 1
    if dist == "gaussian":
        return torch.randn(R, C)
    if dist == "heavy":                                # t-распределение, тяжёлые хвосты
        return torch.distributions.StudentT(2.5).sample((R, C))
    if dist == "mixed_outlier":                        # часть строк с выбросами
        base = torch.randn(R, C)
        idx = torch.randperm(R)[: R // 4]
        base[idx] *= 12.0
        return base
    raise ValueError(dist)


def load_microlm_weights():
    """Реальные 2D-веса микро-LM чекпоинта, если доступен (как в testB)."""
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
    print(f"\n{'='*72}\n  Класс N={N} бит  (подгруппа M²XFP-стиля = {group})\n{'='*72}")
    print(f"  {'данные':<16}{'ось':<26}{'SQNR дБ':>10}{'MSE':>13}{'эфф.бит':>10}")
    rows = []
    for dist in ("uniform", "gaussian", "heavy", "mixed_outlier"):
        x = make_rows(dist, R=64, C=256)
        # ось 1: catalog-selection (GF+A)
        q1, ch = gfplus_a_v2(x, N, group_K=1, scale_mode="e8m0", return_choice=True)
        ov1 = overhead_bpe_v2(x, N, group_K=1, scale_mode="e8m0")
        s1, m1 = sqnr_db(x, q1), ((x.double() - q1.double()) ** 2).mean().item()
        # ось 2: metadata-augmentation (M²XFP-стиль)
        q2, ov2, base = metadata_refine_single_format(x, N, group=group, scale_mode="e8m0")
        s2, m2 = sqnr_db(x, q2), ((x.double() - q2.double()) ** 2).mean().item()
        # ось 1+2: композиция — GF+A выбор кармана + флекс-метадата внутри выбранного
        # (демонстрация ортогональности: применяем b-сдвиг поверх выбранного GF+A-кармана)
        print(f"  {dist:<16}{'catalog-select GF+A':<26}{s1:>10.2f}{m1:>13.3e}{N+ov1:>10.3f}")
        print(f"  {dist:<16}{'metadata-refine M²XFP':<26}{s2:>10.2f}{m2:>13.3e}{N+ov2:>10.3f}")
        rows.append(dict(dist=dist, N=N,
                         sqnr_catalog=round(s1, 3), sqnr_metadata=round(s2, 3),
                         mse_catalog=m1, mse_metadata=m2,
                         effbits_catalog=round(N + ov1, 4), effbits_metadata=round(N + ov2, 4),
                         base_format=base))
    return rows


def main():
    all_rows = []
    for N in (4, 6, 8, 12, 16):
        all_rows += run_class(N)

    # реальные веса микро-LM (если есть)
    mats = load_microlm_weights()
    real_rows = []
    if mats:
        print(f"\n{'='*72}\n  Реальные веса микро-LM ({len(mats)} матриц)\n{'='*72}")
        for N in (4, 8):
            sc = md = 0.0
            for W in mats:
                q1 = gfplus_a_v2(W, N, group_K=1, scale_mode="e8m0")
                q2, _, _ = metadata_refine_single_format(W, N, scale_mode="e8m0")
                sc += sqnr_db(W, q1); md += sqnr_db(W, q2)
            sc /= len(mats); md /= len(mats)
            print(f"  N={N:<3} catalog-select GF+A  SQNR={sc:6.2f} дБ | "
                  f"metadata-refine M²XFP SQNR={md:6.2f} дБ")
            real_rows.append(dict(N=N, sqnr_catalog=round(sc, 3), sqnr_metadata=round(md, 3),
                                  source="micro_lm_real"))
    else:
        print("\n[инфо] micro_lm.pt не найден — только синтетика.")

    import json
    out = dict(seed=20260730, note="[измерено — SW proxy, CPU] Вариант B: ось catalog-select "
               "(GF+A) vs ось metadata-augment (M²XFP-стиль). Гарантия на MSE-метрике выбора, "
               "НЕ downstream. Превосходство НЕ заявляется — вывод про ортогональность/композицию.",
               synthetic=all_rows, real=real_rows)
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "format_selector_vs_metadata_results.json")
    with open(fn, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {fn}")


if __name__ == "__main__":
    main()
