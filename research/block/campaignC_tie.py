#!/usr/bin/env python3
"""Which bin boundary do the 189,406 tied weights sit on? Weights only.

The cliff run showed an IDENTICAL 189,406 weights change bin for a -0.001%,
-0.005% and -0.02% move of MXFP4's level 1. A count that does not scale with
the step size is an exact tie, not a density crossing. This finds the tie.

MXFP4 normalised is [0, 1/12, 1/6, 1/4, 1/3, 1/2, 2/3, 1], so its midpoints are
    1/24, 1/8, 5/24, 7/24, 5/12, 7/12, 5/6
and 1/8 is a dyadic rational -- exactly representable, and reachable exactly by
y = |w|/s because s is a power of two and w is a float32. The other midpoints
are not dyadic. If the tie is at 1/8, then MXFP4's own perplexity depends on
torch.bucketize's tie-breaking rule.
"""
import os
from fractions import Fraction

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"),
     ns)
fp_levels, q_e8m0_t, target_modules = (ns["fp_levels"], ns["q_e8m0_t"],
                                       ns["target_modules"])
K, W = ns["K"], os.path.dirname(ns["MODEL"])
torch.set_grad_enabled(False)

v = sorted(fp_levels(2, 1))
MX = [x / v[-1] for x in v]
MX[-1] = 1.0
t = torch.tensor(MX, dtype=torch.float64)
bnd = (t[:-1] + t[1:]) / 2

print("MXFP4 normalised midpoints, and whether each is a dyadic rational")
print(f"{'i':>3}{'midpoint':>22}{'exact':>12}{'dyadic?':>10}")
for i, b in enumerate(bnd.tolist()):
    fr = Fraction(MX[i]).limit_denominator(10 ** 6) + \
        Fraction(MX[i + 1]).limit_denominator(10 ** 6)
    fr = fr / 2
    dy = (fr.denominator & (fr.denominator - 1)) == 0
    print(f"{i:>3}{b:>22.17f}{str(fr):>12}{'YES' if dy else 'no':>10}")

from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained(os.path.join(W, "smollm2"),
                                             dtype=torch.float32)
model.eval()
ties = torch.zeros(7, dtype=torch.int64)
tot = 0
for _, m in target_modules(model):
    w = m.weight.detach().double()
    n = (w.shape[1] // K) * K
    if n == 0:
        continue
    head = w[:, :n].reshape(-1, K)
    s = q_e8m0_t((head.abs().amax(dim=1) / t[-1]).clamp(min=1e-30))
    y = (head / s[:, None]).abs().reshape(-1)
    tot += y.numel()
    for i in range(7):
        ties[i] += int((y == bnd[i]).sum())
print(f"\nweights examined: {tot:,}")
print(f"{'i':>3}{'midpoint':>22}{'exact ties':>14}{'share':>10}")
for i in range(7):
    print(f"{i:>3}{bnd[i].item():>22.17f}{int(ties[i]):>14,}"
          f"{100*int(ties[i])/tot:>9.4f}%")
print(f"\ntotal weights sitting exactly on a bin boundary: "
      f"{int(ties.sum()):,}")
print("the cliff run measured 189,406 weights changing bin when level 1 "
      "moved down")
