#!/usr/bin/env python3
"""Is the sensitivity ratio a model property or a model-format interaction?

Registered in PREREG_sensitivity_scope_2026-08-12.md before this ran.

Perplexities come from verify_block_ppl.py (four models, four arms). The
perturbations are computed here on the SAME layers with the SAME quantiser,
imported from that harness rather than reimplemented.

    S1 = d_ppl / p        p = ||dW||_F / ||W||_F     -- iteration 111's ratio
    S2 = d_ppl / p^2                                 -- what second order requires

d_ppl is taken as the RELATIVE perplexity rise, (ppl - ppl_fp32)/ppl_fp32, so it
is dimensionless on both sides.
"""
import os
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "verify_block_ppl.py")).read()
g = {"__name__": "vbp"}
exec(compile(src.split("ARMS = [")[0], "vbp", "exec"), g)
quantise, targets, W = g["quantise"], g["targets"], g["W"]
torch.set_grad_enabled(False)

PPL = {  # fp32, floor, argmin, step3, step8
    "gpt2":    (29.9501, 35.9747, 36.1482, 33.5509, 32.6858),
    "qwen":    (13.0687, 16.1795, 15.8346, 14.6979, 14.5698),
    "smollm2": (15.4148, 25.0798, 22.1015, 20.0022, 18.9053),
    "pythia":  (26.6505, 46.8158, 46.8499, 41.0513, 38.3819),
}
ARMS = [("floor", "floor", None), ("argmin", "argmin2", None),
        ("step3", "step", 3), ("step8", "step", 8)]

rows = {}
for name in PPL:
    if not os.path.isdir(os.path.join(W, name)):
        continue
    from transformers import AutoModelForCausalLM
    m0 = AutoModelForCausalLM.from_pretrained(os.path.join(W, name), dtype=torch.float32)
    m0.eval()
    num = {a: 0.0 for a, _, _ in ARMS}
    den = 0.0
    for _, m in targets(m0):
        A = m.weight.data.numpy().astype(np.float64)
        den += float((A ** 2).sum())
        for a, mode, N in ARMS:
            num[a] += float(((quantise(A, mode, N) - A) ** 2).sum())
    p0 = PPL[name][0]
    rows[name] = [(a, np.sqrt(num[a] / den), (PPL[name][i + 1] - p0) / p0)
                  for i, (a, _, _) in enumerate(ARMS)]
    del m0
    print(f"  {name} готов", flush=True)

print("\n  S1 = Δppl/p      S2 = Δppl/p²      p = ‖ΔW‖/‖W‖")
print(f"  {'модель':9s} {'арм':7s} {'p':>8s} {'Δppl':>8s} {'S1':>8s} {'S2':>9s}")
S1, S2 = {}, {}
for name, rs in rows.items():
    S1[name], S2[name] = [], []
    for a, p, d in rs:
        S1[name].append(d / p); S2[name].append(d / p ** 2)
        print(f"  {name:9s} {a:7s} {p:8.4f} {d:8.4f} {d/p:8.3f} {d/p**2:9.2f}")
    print()

def spread(v): return max(v) / min(v)
print("  ═══ РАЗБРОС ВНУТРИ МОДЕЛИ (по четырём армам) ═══")
for name in rows:
    print(f"  {name:9s} S1 {spread(S1[name]):5.2f}×   S2 {spread(S2[name]):5.2f}×"
          f"   {'S2 теснее' if spread(S2[name]) < spread(S1[name]) else 'S1 теснее'}")
b1 = [np.mean(S1[n]) for n in rows]; b2 = [np.mean(S2[n]) for n in rows]
print(f"\n  между моделями: S1 {spread(b1):5.2f}×   S2 {spread(b2):5.2f}×")
w1 = max(spread(S1[n]) for n in rows); w2 = max(spread(S2[n]) for n in rows)
print(f"  худший внутри : S1 {w1:5.2f}×   S2 {w2:5.2f}×")
for k, w, b in (("S1", w1, spread(b1)), ("S2", w2, spread(b2))):
    print(f"  {k}: {'✓ свойство модели' if w < b else '✗ взаимодействие — внутри разброс не меньше'}"
          f"  (внутри {w:.2f}× против между {b:.2f}×)")
o = [n for n in sorted(rows, key=lambda n: np.mean(S2[n]))]
print(f"\n  порядок по S2 : {' < '.join(o)}")
print(f"  порядок ущерба: gpt2 < qwen < smollm2 < pythia"
      f"   {'✓ СОВПАЛО' if o == ['gpt2','qwen','smollm2','pythia'] else '✗ разошлось'}")
