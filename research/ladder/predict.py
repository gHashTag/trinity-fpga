"""Does the winning ladder follow from the weights' own dynamic range?

The crossover has an obvious candidate mechanism: at a fixed code budget a
ladder of ratio r spans r^(n-1), and the ladder that wins should be the finest
one whose span still covers the range the weights actually occupy. If that is
right, the winner is predictable from the weights alone, without running a
single perplexity evaluation -- which is the difference between an observation
and a law.
"""
import os, numpy as np, torch
from transformers import AutoModelForCausalLM
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
m = AutoModelForCausalLM.from_pretrained(os.path.join(W, "smollm2"), dtype=torch.float32)
spans = []
for nm, mod in m.named_modules():
    if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
        w = mod.weight.data.abs().to(torch.float64)
        hi = w.amax(dim=1)
        # the floor that matters is not the true min (which is ~0 and unrepresentable
        # in any ladder) but the level below which mass is negligible; take the
        # quantile that leaves 1% of the weights under-ranged.
        lo = torch.quantile(w, 0.01, dim=1).clamp_min(1e-12)
        spans.append((hi / lo).cpu().numpy())
s = np.concatenate(spans)
print(f"  linear-слоёв: {len(spans)},  каналов: {s.size}")
for q in (0.25, 0.5, 0.75, 0.9):
    print(f"    квантиль {q:.2f} динамического диапазона канала: {np.quantile(s, q):8.2f}x")
med = float(np.median(s))
print(f"\n  медианный диапазон канала: {med:.2f}x")
RAT = {"shift": 2.0, "phi": (1+5**0.5)/2, "supergold": 1.465571231876768,
       "plastic": 1.324717957244746}
print(f"\n  ПРЕДСКАЗАНИЕ: самая тонкая лестница, чей охват >= {med:.1f}x")
for bits in (3,4,5):
    n = (2**bits - 1)//2
    ok = [(nm, r, r**(n-1)) for nm, r in RAT.items() if r**(n-1) >= med]
    pick = min(ok, key=lambda t: t[1])[0] if ok else max(RAT, key=RAT.get)
    line = "  ".join(f"{nm}={r**(n-1):.1f}x" for nm, r in RAT.items())
    print(f"    {bits}b  охваты: {line}")
    print(f"         предсказано: {pick}")
