#!/usr/bin/env python3
"""Is GPT-2's sign inversion a property of the METRIC or of the MODEL?

Iteration 109 found that on GPT-2 the squared-error-optimal encoder makes
PERPLEXITY worse than MXFP4's reference rule -- an encoder share of -7.2%, where
SmolLM2 gives +58.7% and Qwen +23.3%. That retired a sentence in the paper.

It leaves one question, and only one measurement answers it.

  If squared error on GPT-2 also prefers the reference rule, the inversion is a
  property of the MODEL and says nothing about the two metrics disagreeing.

  If squared error prefers argmin -- as it must, since argmin minimises squared
  error by construction -- then the inversion is a genuine METRIC disagreement,
  and it is the strongest instance of it in this paper.

The second is close to a tautology and that is exactly why the measurement is
worth making: the argmin encoder minimises squared error over the E8M0 ladder
BLOCK BY BLOCK, so its squared-error share must be positive. Confirming it
turns a tautology into a control -- if the number came out negative, the harness
would be wrong, not the theory.

DESIGN. Same layers, same blocking, same quantiser, same weights as
verify_block_ppl.py, imported rather than reimplemented. ONLY the metric
changes. Reimplementing the blocking here would reintroduce exactly the
apples-to-oranges risk that produced thirteen withdrawals in this campaign --
and GPT-2 is the case where it bites hardest, since Conv1D stores its weight
transposed relative to nn.Linear and blocking the wrong axis would silently
compare two different partitions.
"""
import importlib.util
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("vbp", os.path.join(HERE, "verify_block_ppl.py"))
src = open(os.path.join(HERE, "verify_block_ppl.py")).read()
g = {"__name__": "vbp"}
exec(compile(src.split("ARMS = [")[0], "vbp", "exec"), g)
quantise, targets, W, K = g["quantise"], g["targets"], g["W"], g["K"]
torch.set_grad_enabled(False)

MODELS = sys.argv[1:] or ["smollm2", "qwen", "gpt2", "pythia"]
ARMS = [("floor", "floor", None), ("argmin", "argmin2", None), ("step3", "step", 3)]

print("  ДОЛЯ КОДИРОВЩИКА ПО КВАДРАТИЧНОЙ ОШИБКЕ")
print("  те же слои, то же разбиение, тот же квантователь, что и у перплексии\n")
print(f"  {'модель':9s} {'слоёв':>6s} {'RMSE пол':>12s} {'RMSE argmin':>12s}"
      f" {'RMSE step3':>12s} {'доля кодировщика':>18s}")

for name in MODELS:
    path = os.path.join(W, name)
    if not os.path.isdir(path):
        continue
    from transformers import AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    tg = targets(model)
    if not tg:
        print(f"  {name:9s}  ❗ ни одного целевого слоя — отказ")
        del model
        continue

    tot = {a: [0.0, 0] for a, _, _ in ARMS}
    for _, m in tg:
        A = m.weight.data.numpy().astype(np.float64)
        for a, mode, N in ARMS:
            Q = quantise(A, mode, N)
            tot[a][0] += float(((Q - A) ** 2).sum())
            tot[a][1] += A.size
    r = {a: np.sqrt(v[0] / v[1]) for a, v in tot.items()}
    # the encoder's share of the achievable improvement, same definition the
    # perplexity table uses: (floor - argmin) / (floor - step3)
    denom = r["floor"] - r["step3"]
    share = (r["floor"] - r["argmin"]) / denom * 100 if denom != 0 else float("nan")
    flag = ""
    if r["argmin"] > r["floor"]:
        flag = "  ❗ argmin ХУЖЕ пола по квадратичной ошибке — прибор сломан"
    print(f"  {name:9s} {len(tg):6d} {r['floor']:12.8f} {r['argmin']:12.8f}"
          f" {r['step3']:12.8f} {share:17.1f}%{flag}", flush=True)
    del model
