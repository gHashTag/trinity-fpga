#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_vectors.py — генератор проверочных векторов для tb_gf_decode.v.

Использует golden-оракул gf_decode_ref.py: для каждого из 10 FP32-форматов
Фазы A производит текстовый файл `vectors_<name>.txt` вида
    <hex gf_in><пробел><hex fp32_expected>
по одной строке на вектор (exhaustive для малых форматов, representative +
5 классов для крупных — то же покрытие, что и в rtl_bit_model.py).

Запуск: python3 gen_vectors.py [имя_формата ...]  (без аргументов — все 10).
Файлы кладутся рядом, в /home/user/workspace/wave_audit/gf_decode/vectors/.

compute-HW / decode-HW ГАЛОЧКА закрывается ТОЛЬКО реальным прогоном
tb_gf_decode.v на iverilog/Vivado + синтезом+прошивкой AX7203 —
[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]. Этот генератор — SW-side подготовка.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gf_decode_ref as G
import rtl_bit_model as R

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors")


def gen_for(name):
    fmt = G.GF_LINEUP[name]
    if name in R.EXHAUSTIVE_FORMATS:
        raws = list(range(1 << fmt.N))
    else:
        raws = R.five_class_raws(fmt)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"vectors_{name}.txt")
    hexw = (fmt.N + 3) // 4
    with open(path, "w") as f:
        f.write(f"# gf_decode vectors: {name}  N={fmt.N} E={fmt.E} M={fmt.M} BIAS={fmt.BIAS}\n")
        f.write(f"# format: <gf_in hex, {hexw} digits> <fp32_expected hex, 8 digits>\n")
        for raw in raws:
            raw &= (1 << fmt.N) - 1
            expected = G.gf_decode_to_fp32_bits(fmt, raw)
            f.write(f"{raw:0{hexw}x} {expected:08x}\n")
    return path, len(raws)


if __name__ == "__main__":
    names = sys.argv[1:] if len(sys.argv) > 1 else G.FP32_FORMATS
    for name in names:
        path, n = gen_for(name)
        print(f"{name}: {n} vectors -> {path}")
