"""Does the law predict a model's ladder winners from that model's OWN weights?

predict2.py established that weight-MSE reproduces the measured perplexity ordering on
SmolLM2. That is one histogram, so the closed form could still be a fit rather than a law.
This runs the same test on any model, and in particular on Qwen2.5-0.5B, whose measured
winners are already recorded in ladder_ppl_qwen.json.

TWO PREDICTORS ARE SCORED SEPARATELY, because they are different claims:

  EXACT      quantise the real weights against the real codebook and sum squared error.
             No modelling assumption; only asserts that weight-MSE tracks perplexity.

  CLOSED     the analytic form  MSE(r,b) = c(r)^2 * E[x^2 | x>t] + E[x^2 | x<t],
             t = r^-(n-1)/2, with c(r)^2 a data-independent integral. This is the law.
             It sees only the histogram -- never a codebook, never a model run.

If EXACT succeeds and CLOSED fails, the ordering is real but the analytic form is wrong.
If both succeed on a second model, the closed form is transferable.

PERFORMANCE NOTE. predict2.py built a full |x - codebook| distance matrix, which allocates
n_weights * n_codes doubles -- that is what made Qwen "heavy". Nearest-level assignment on a
sorted codebook is a searchsorted against midpoints, O(n log k) with no large temporary.
"""
import json
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)

RAT = {"shift  (2^k,   deg 1)": 2.0,
       "phi    (1.618, deg 2)": (1 + 5 ** 0.5) / 2,
       "supergold (1.4656, d3)": 1.465571231876768,
       "plastic(1.3247, deg 3)": 1.324717957244746}

MDIR = os.environ.get("MDIR", "qwen")
PPL_JSON = os.environ.get("PPL", f"ladder_ppl_{'qwen' if MDIR == 'qwen' else 'smollm2'}.json")


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


def c2(r, m=20001):
    """Mean-square RELATIVE error of a geometric ladder of ratio r. Data-independent."""
    u = np.linspace(0, 1, m)
    x = r ** (-u)
    return float(np.mean((np.minimum(np.abs(x - 1.0), np.abs(x - 1.0 / r)) / x) ** 2))


def exact_mse(mods, r, bits):
    """Nearest-level squared error against the real codebook, per-row absmax scaling."""
    cb = codebook(r, bits)
    mid = (cb[:-1] + cb[1:]) / 2
    num = den = 0.0
    for _, mod in mods:
        w = mod.weight.data.to(torch.float64)
        s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
        x = (w / s).cpu().numpy()
        q = cb[np.searchsorted(mid, x)]
        num += float(((q - x) ** 2).sum())
        den += x.size
    return num / den


def closed_mse(absx, r, bits, C2):
    """The law: relative rounding above the clip threshold, full truncation below it."""
    n = (2 ** bits - 1) // 2
    t = r ** (-(n - 1)) / 2
    below = absx < t
    return (C2[r] * float((absx[~below] ** 2).sum())
            + float((absx[below] ** 2).sum())) / absx.size


print(f"  model dir: {MDIR}   measured perplexities: {PPL_JSON}")
m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MDIR), dtype=torch.float32)
mods = [(nm, mod) for nm, mod in m.named_modules()
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
print(f"  linear layers: {len(mods)}")

# one pooled sample of |w|/rowmax for the closed form (subsampled: it only needs the shape)
parts = []
for _, mod in mods:
    w = mod.weight.data.to(torch.float64)
    s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
    a = (w / s).abs().cpu().numpy().ravel()
    parts.append(a[:: max(1, a.size // 300000)])
absx = np.concatenate(parts)
print(f"  histogram samples: {absx.size:,}")

C2 = {v: c2(v) for v in RAT.values()}
ppl = {(r["bits"], r["ladder"]): r["ppl"] for r in json.load(open(PPL_JSON)) if r["bits"]}

ok_exact = ok_closed = True
for bits in (3, 4, 5):
    rows = []
    for nm, r in RAT.items():
        rows.append((nm, exact_mse(mods, r, bits), closed_mse(absx, r, bits, C2),
                     ppl[(bits, nm)]))
    short = lambda t: t[0].split()[0]
    be, bc, bp = (min(rows, key=lambda t: t[i])[0] for i in (1, 2, 3))
    ok_exact &= (be == bp)
    ok_closed &= (bc == bp)
    print(f"\n  {bits} bits")
    for nm, e, c, p in sorted(rows, key=lambda t: t[3]):
        print(f"    {nm:24} exact={e:.4e}  closed={c:.4e}  ppl={p:12.3f}")
    print(f"    winner  exact={short((be,)):10} closed={short((bc,)):10} "
          f"ppl={short((bp,)):10}  "
          f"{'EXACT ok' if be == bp else 'EXACT WRONG'} / "
          f"{'CLOSED ok' if bc == bp else 'CLOSED WRONG'}")
    for tag, i in (("exact", 1), ("closed", 2), ("ppl  ", 3)):
        print(f"      order {tag}: {[short(t) for t in sorted(rows, key=lambda z: z[i])]}")

print(f"\n  EXACT  weight-MSE predicts every winner: {'YES' if ok_exact else 'NO'}")
print(f"  CLOSED analytic form predicts every winner: {'YES' if ok_closed else 'NO'}")
