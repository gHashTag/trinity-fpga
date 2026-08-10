"""A: is there a boundary, with no fitted constant, that separates the 4-bit winners?

The 4-bit winner is model-dependent: phi on SmolLM2 and Qwen, supergolden on Pythia. Adding a
fitted lambda forced phi everywhere and therefore broke on Pythia -- the wrong kind of fix, since
it tunes a constant rather than reading a property of the model.

The right question is whether some CONTINUOUS quantity, computed from each model's own weights
with no free parameter, puts Pythia on one side and the other two on the other. If one does, the
4-bit budget has a law after all: "measure this number, read off the ladder". If none does, the
honest report is that 4 bits must be measured per model.

Candidates, all parameter-free and computable from weights alone:

  kurt        excess kurtosis of |w|/rowmax
  r_star_mse  the continuous optimum of the SINGLE-term closed form at 4 bits
  gap         relative MSE gap between the two leading ladders, (mse_phi - mse_sg)/mse_sg
  flush_gap   difference in flushed fraction, flush_phi - flush_sg
  p_small     fraction of weights below 0.1 of the row max -- how much mass sits low

A separating quantity must have Pythia strictly outside the interval spanned by SmolLM2 and Qwen.
That is a weak test with three points, and it is stated as such: three models can be separated by
chance on many statistics. What it can do is RULE OUT candidates that fail to separate, and
produce a boundary that the next model tests honestly.
"""
import os

import numpy as np
import torch
from transformers import AutoModelForCausalLM

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
PHI, SG = (1 + 5 ** 0.5) / 2, 1.465571231876768
WINNER4 = {"smollm2": "phi", "qwen": "phi", "pythia": "supergold"}
HEADS = ("lm_head", "embed_out")


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


def mse_flush(x, r, bits):
    n = (2 ** bits - 1) // 2
    cb = codebook(r, bits)
    mid = (cb[:-1] + cb[1:]) / 2
    mse = float(((cb[np.searchsorted(mid, x)] - x) ** 2).mean())
    return mse, float((np.abs(x) < r ** (-(n - 1)) / 2).mean())


rows = {}
for MD in ("smollm2", "qwen", "pythia"):
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MD), dtype=torch.float32)
    acc = []
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and not any(h in nm for h in HEADS):
            w = mod.weight.data.to(torch.float64)
            s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            z = (w / s).cpu().numpy().ravel()
            acc.append(z[:: max(1, z.size // 150000)])
    x = np.concatenate(acc)
    del m
    mp, fp = mse_flush(x, PHI, 4)
    ms, fs = mse_flush(x, SG, 4)
    grid = np.linspace(1.05, 2.6, 200)
    rstar = float(grid[int(np.argmin([mse_flush(x, float(v), 4)[0] for v in grid]))])
    rows[MD] = {
        "kurt": float(((x - x.mean()) ** 4).mean() / x.std() ** 4 - 3),
        "r_star_mse": rstar,
        "gap": (mp - ms) / ms,
        "flush_gap": fp - fs,
        "p_small": float((np.abs(x) < 0.1).mean()),
    }
    print(f"  {MD}: {x.size:,} samples, 4-bit winner = {WINNER4[MD]}")

keys = ["kurt", "r_star_mse", "gap", "flush_gap", "p_small"]
print(f"\n  {'quantity':12}" + "".join(f"{m:>12}" for m in rows) + "   separates?")
for k in keys:
    v = {m: rows[m][k] for m in rows}
    lo, hi = min(v["smollm2"], v["qwen"]), max(v["smollm2"], v["qwen"])
    sep = not (lo <= v["pythia"] <= hi)
    side = ""
    if sep:
        side = f"  Pythia {'above' if v['pythia'] > hi else 'below'}, boundary in " \
               f"({min(hi, v['pythia']):.4g}, {max(lo, v['pythia']):.4g})"
    print(f"  {k:12}" + "".join(f"{v[m]:>12.4g}" for m in rows)
          + ("   YES" + side if sep else "   no"))

print("\n  A separating quantity is necessary, not sufficient: three points can be split by")
print("  chance on many statistics. The value here is that it RULES OUT the ones that fail,")
print("  and any survivor makes a falsifiable prediction for the next family.")
