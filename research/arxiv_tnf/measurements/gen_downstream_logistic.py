#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Третья downstream-проба TNF: устойчивость логистического отображения.

x_{n+1} = r x_n (1 - x_n) при r = 3.9 (хаотический режим). Состояние на каждом
шаге приводится к формату-кандидату; произведение считается в float32, float64
служит только эталоном. Измеряется НЕ SQNR представления, а результат задачи:
номер шага, на котором траектория кандидата расходится с эталонной больше
чем на 1e-2 по абсолютной величине (показатель Ляпунова делает расхождение
неизбежным, вопрос лишь в том, на каком шаге оно наступает).

Все значения лежат в [0,1], поэтому диапазон формата роли не играет: проба
изолирует точность представления от запаса по порядкам.
"""
import json, math, os, sys
from fractions import Fraction
from pathlib import Path
import numpy as np

# Resolve imports from the checkout rather than from a fixed temporary clone.
# This keeps the command in the paper reproducible after the working directory
# or the checkout path changes.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / 'conformance'))
import tnf_ref as TNF
import takum_ref as TAK

SEED = 20260814
R = 3.9
X0 = 0.4
STEPS = 400
DIVERGENCE = 1e-2


def qcast(fmt, x):
    x = float(x)
    if fmt is None:
        return x
    if not math.isfinite(x):
        return x
    if isinstance(fmt, TNF.TNFFormat):
        raw = TNF.encode(fmt, Fraction(x)); d = TNF.decode(fmt, raw)
    else:
        raw = TAK.encode(fmt, Fraction(x)); d = TAK.decode(fmt, raw)
    return float(d) if d is not None else x


def trajectory(fmt, binary16=False):
    """Один прогон. Умножение в float32 (эталон — float64)."""
    x = qcast(fmt, X0) if fmt is not None else X0
    if binary16:
        x = float(np.float16(X0))
    out = []
    for _ in range(STEPS):
        if fmt is None and not binary16:
            x = R * x * (1.0 - x)                      # эталон float64
        else:
            xf = np.float32(x)
            xn = np.float32(R) * xf * (np.float32(1.0) - xf)   # аккумулятор fp32
            x = float(np.float16(xn)) if binary16 else qcast(fmt, float(xn))
        out.append(x)
    return out


def main():
    ladder = TNF.LADDER_RESEARCH
    tnf48 = TNF.TNFFormat(4, 8)
    tak16 = TAK.FORMATS['takum16']

    ref = trajectory(None)
    cands = {
        'binary16': ('binary16', None),
        'TNF(4,8)': ('tnf', tnf48),
        'takum16': ('takum', tak16),
    }
    res = {}
    for name, (kind, fmt) in cands.items():
        traj = trajectory(fmt, binary16=(kind == 'binary16'))
        step = None
        for i, (a, b) in enumerate(zip(traj, ref), start=1):
            if abs(a - b) > DIVERGENCE:
                step = i
                break
        # средняя абсолютная ошибка на первых 20 шагах (до развала)
        mae20 = sum(abs(a - b) for a, b in zip(traj[:20], ref[:20])) / 20.0
        res[name] = {
            'steps_before_divergence': step,
            'mean_abs_error_first_20_steps': mae20,
            'divergence_threshold': DIVERGENCE,
        }

    out = {
        'task': 'Устойчивость логистического отображения x_{n+1}=r x_n (1-x_n), r=3.9, x0=0.4',
        'seed': SEED, 'r': R, 'x0': X0, 'steps': STEPS,
        'divergence_threshold': DIVERGENCE,
        'accumulator': 'float32 for all candidates; float64 only for reference',
        'note': 'все значения в [0,1]; проба изолирует точность от запаса диапазона',
        'results': res,
    }
    dst = Path(__file__).resolve().parent / 'tnf_downstream_logistic_2026-08-14.json'
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print('saved', dst)


if __name__ == '__main__':
    main()
