#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Задача суммирования с катастрофической компенсацией.

Суммируется точная последовательность [2**24] + [1] * 100000 + [-2**24].
Итог задачи равен 100000. Входные значения сначала округляются в формат
кандидата, а каждое сложение выполняется с обязательным float32-накопителем.
Сравниваются наивная и компенсированная (Кэхэна) редукции. Это измеряет итог
численной задачи, а не SQNR представления.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(REPO_ROOT / "conformance"))
import tnf_ref as TNF
import takum_ref as TAK

N_SMALL = 100_000
BASE = 2 ** 24
EXPECTED = float(N_SMALL)


def cast_value(kind, value):
    if kind == "binary32":
        return float(np.float32(value))
    if kind == "TNF(4,8)":
        fmt = TNF.TNFFormat(4, 8)
        return float(TNF.decode(fmt, TNF.encode(fmt, Fraction(value))))
    if kind == "takum16":
        fmt = TAK.FORMATS["takum16"]
        return float(TAK.decode(fmt, TAK.encode(fmt, Fraction(value))))
    raise KeyError(kind)


def run(kind, compensated):
    s = np.float32(0.0)
    correction = np.float32(0.0)
    for value in (BASE, *([1.0] * N_SMALL), -BASE):
        y = np.float32(cast_value(kind, value))
        if compensated:
            corrected = np.float32(y - correction)
            updated = np.float32(s + corrected)
            correction = np.float32((updated - s) - corrected)
            s = updated
        else:
            s = np.float32(s + y)
    return float(s)


def main():
    results = {}
    for kind in ("binary32", "TNF(4,8)", "takum16"):
        for algorithm in ("naive", "kahan"):
            total = run(kind, algorithm == "kahan")
            results[f"{kind}/{algorithm}"] = {
                "format": kind,
                "algorithm": algorithm,
                "final_sum": total,
                "absolute_error": abs(total - EXPECTED),
            }

    payload = {
        "task": "Суммирование [2^24] + [1] * 100000 + [-2^24]",
        "terms": N_SMALL + 2,
        "expected_sum": EXPECTED,
        "accumulator": "float32 for every candidate and every addition",
        "input_rounding": "each term encoded and decoded by the candidate format before accumulation",
        "algorithms": ["naive", "kahan"],
        "results": results,
        "status": "[измерено]",
        "limitations": "стресс-тест отмены; не рейтинг форматов и не измерение скорости, площади или энергии",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["canonical_payload_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    destination = Path(__file__).resolve().parent / "tnf_downstream_kahan_2026-09-01.json"
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"saved {destination}")


if __name__ == "__main__":
    main()
