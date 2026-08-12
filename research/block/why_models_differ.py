#!/usr/bin/env python3
"""Why does MXFP4 cost Pythia 76% of its perplexity and Qwen only 24%?

Degradation of the reference MXFP4 encoder against fp32, measured in
verify_block_ppl.py:

    Pythia  +75.7%      SmolLM2 +62.7%      Qwen  +23.8%      GPT-2  +20.1%

That is the largest unexplained difference between models in this campaign, and
it sits underneath every number in the block section. The candidate explanation
is the standard one: a block whose maximum is far above its own RMS spends most
of its codebook on headroom no other element in the block reaches. The scale is
pinned by the outlier and the remaining 31 values are quantised on a grid far too
coarse for them.

PREDICTION, registered here before the run: degradation should order the same
way as the block peak ratio E[amax / rms], which is computed by counting alone
-- no error evaluated anywhere, no quantiser invoked.

Reported alongside: the fraction of blocks whose peak ratio exceeds 3, and the
kurtosis of the weights, which is the quantity the outlier literature usually
names.
"""
import os, sys
import numpy as np
import torch
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "verify_block_ppl.py")).read()
g = {"__name__": "vbp"}
exec(compile(src.split("ARMS = [")[0], "vbp", "exec"), g)
targets, W, K = g["targets"], g["W"], g["K"]
torch.set_grad_enabled(False)

DEG = {"pythia": 75.7, "smollm2": 62.7, "qwen": 23.8, "gpt2": 20.1}
print("  ФОРМА БЛОКА — только счёт, ошибка не вычисляется\n")
print(f"  {'модель':9s} {'деград.':>8s} {'E[amax/rms]':>12s} {'доля >3':>9s} {'эксцесс':>10s}")
rows = []
for name in (sys.argv[1:] or ["qwen", "gpt2", "smollm2", "pythia"]):
    path = os.path.join(W, name)
    if not os.path.isdir(path):
        continue
    from transformers import AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    pk, hi, ku, n = 0.0, 0.0, 0.0, 0
    for _, m in targets(model):
        A = m.weight.data.numpy().astype(np.float64)
        nb = A.shape[1] // K
        if nb == 0:
            continue
        V = A[:, :nb * K].reshape(-1, K)
        rms = np.sqrt((V ** 2).mean(axis=1))
        ok = rms > 0
        r = np.abs(V[ok]).max(axis=1) / rms[ok]
        pk += r.sum(); hi += float((r > 3).sum()); n += r.size
        x = V[ok].ravel()
        ku += float(((x - x.mean()) ** 4).mean() / (x.var() ** 2)) * r.size
    rows.append((name, DEG.get(name, float("nan")), pk / n, hi / n * 100, ku / n))
    print(f"  {name:9s} {rows[-1][1]:7.1f}% {rows[-1][2]:12.3f} {rows[-1][3]:8.1f}%"
          f" {rows[-1][4]:10.2f}", flush=True)
    del model

print("\n  ═══ ПОРЯДКОВАЯ ПРОВЕРКА ═══")
for k, i in (("E[amax/rms]", 2), ("доля >3", 3), ("эксцесс", 4)):
    a = [r[0] for r in sorted(rows, key=lambda r: r[i])]
    b = [r[0] for r in sorted(rows, key=lambda r: r[1])]
    print(f"  по {k:12s}: {' < '.join(a)}")
    print(f"  по деградации : {' < '.join(b)}   {'✓ СОВПАЛО' if a == b else '✗ разошлось'}")
