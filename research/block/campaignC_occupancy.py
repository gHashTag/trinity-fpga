#!/usr/bin/env python3
"""How many weights does each MXFP4 level own? Weights only -- no forward pass.

Context: in the one-level sweep some levels behave smoothly and monotonically
and others wiggle. Occupancy is the cheapest candidate explanation -- a level
that owns a large share of the weights reassigns a large number of them when its
two bin boundaries move, so its effect is a sum of many competing per-tensor
contributions. This measures the share; it does not prove the mechanism.
"""
import json
import os

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"), ns)
fp_levels, target_modules = ns["fp_levels"], ns["target_modules"]
q_e8m0_t, K = ns["q_e8m0_t"], ns["K"]
W = os.path.dirname(ns["MODEL"])
torch.set_grad_enabled(False)

MDIR = os.environ.get("MDIR", "smollm2")
v = sorted(fp_levels(2, 1))
MXFP4 = [x / v[-1] for x in v]

from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained(os.path.join(W, MDIR),
                                             dtype=torch.float32)
model.eval()
lv = torch.tensor(MXFP4, dtype=torch.float64)
bnd = (lv[:-1] + lv[1:]) / 2
cnt = torch.zeros(8, dtype=torch.float64)
err = torch.zeros(8, dtype=torch.float64)
for _, m in target_modules(model):
    w = m.weight.detach().double()
    n = (w.shape[1] // K) * K
    if n == 0:
        continue
    head = w[:, :n].reshape(-1, K)
    s = q_e8m0_t((head.abs().amax(dim=1) / lv[-1]).clamp(min=1e-30))
    y = (head / s[:, None]).abs()
    idx = torch.bucketize(y, bnd)
    cnt += torch.bincount(idx.reshape(-1), minlength=8).double()
    err += torch.bincount(idx.reshape(-1), minlength=8,
                          weights=((y - lv[idx]) ** 2).reshape(-1)).double()
tot = float(cnt.sum())
print(f"model={MDIR}  weights bucketed = {tot:,.0f}\n")
print(f"{'lvl':>4}{'L':>10}{'count':>16}{'share':>9}{'cum':>9}"
      f"{'sq.err share':>14}")
cum = 0.0
rows = []
for j in range(8):
    sh = float(cnt[j]) / tot
    cum += sh
    rows.append({"level": j, "value": MXFP4[j], "count": float(cnt[j]),
                 "share": sh, "sqerr_share": float(err[j] / err.sum())})
    print(f"{j:>4}{MXFP4[j]:>10.5f}{float(cnt[j]):>16,.0f}{100*sh:>8.2f}%"
          f"{100*cum:>8.2f}%{100*float(err[j]/err.sum()):>13.2f}%")
json.dump({"model": MDIR, "total": tot, "levels": rows},
          open(os.path.join(HERE, f"campaignC_occupancy_{MDIR}.json"), "w"),
          indent=1)
print(f"\nlevels 1-3 own {100*sum(r['share'] for r in rows[1:4]):.2f}% "
      f"of all weights; levels 4-6 own "
      f"{100*sum(r['share'] for r in rows[4:7]):.2f}%")
