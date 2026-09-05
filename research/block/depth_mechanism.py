"""What sets the DEPTH of the alignment optimum? The floor is explained; the depth is not.

Established: the tie-rule FLOOR is ~2^-m in the checkpoint's stored mantissa width (predicted 8x
for bf16:fp16, measured 7.96). Resolvability is depth/floor, and the floor is only one term. The
other term -- depth -- decides whether an optimum exists at all, and nothing explains it:

    smollm2  depth 0.5104   gpt2  depth 0.5127   pythia  depth 0.2457   opt  depth 0.0087

That is a 59x range across four models and it does not track the quantisation damage
(pythia has the largest damage and nearly the smallest depth).

HYPOTHESIS, and it is measurable from the weights alone with no perplexity run.

Alignment moves a window over the block maxima. What it can achieve depends on how the maxima sit
inside their binades. Write each block maximum as a = 2^e * 2^f with f = frac(log2 a) in [0,1).
The alignment constant decides which f are clamped: with c = max_norm/2^(1-u), a block clamps iff
f exceeds a threshold set by u. So:

  * if f is UNIFORM on [0,1), then moving u trades one set of clamped blocks for an equally
    numerous set -- the cost changes smoothly and shallowly. FLAT optimum.
  * if f is CONCENTRATED, some placements of the window dodge the mass and others hit it.
    DEEP optimum.

So depth should track the NON-UNIFORMITY of frac(log2 amax), and it should do so without any
reference to the model's loss, its size, or its damage.

Two non-uniformity statistics, both parameter-free:
  KS   sup |F_n(f) - f|            Kolmogorov-Smirnov distance from uniform
  TV   0.5 * sum |p_i - 1/B|       total variation from uniform on B bins

Falsifier: if neither statistic orders the four models the way depth does, the hypothesis is
wrong and depth needs a different explanation. Reported either way.
"""
import json
import math
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32
torch.set_grad_enabled(False)

# measured earlier: depth of the alignment optimum against the next-best alignment, and the
# tie-rule floor. Both from flatness.py over the stored sweeps.
MEAS = {"smollm2": (0.5104, 0.2398), "gpt2": (0.5127, 0.0003),
        "pythia": (0.2457, 0.5358), "opt": (0.0087, 0.0667)}
HEADS = ("lm_head", "embed_out")

try:
    from transformers.pytorch_utils import Conv1D
except Exception:
    Conv1D = ()


def targets(m):
    out = []
    for nm, mod in m.named_modules():
        if any(h in nm for h in HEADS):
            continue
        if isinstance(mod, torch.nn.Linear) or (Conv1D and isinstance(mod, Conv1D)):
            if getattr(mod, "weight", None) is not None and mod.weight.dim() == 2:
                out.append((nm, mod))
    return out


def frac_log2_maxima(tag):
    """frac(log2 |block max|) over every block of every quantisable 2-D weight."""
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, tag), dtype=torch.float32)
    tg = targets(m)
    if not tg:
        sys.exit(f"{tag}: no target layers matched — refusing to report")
    fr = []
    for nm, mod in tg:
        w = mod.weight.data.to(torch.float64)
        ax = 1 if isinstance(mod, torch.nn.Linear) else 0     # Conv1D stores [in, out]
        n = (w.shape[ax] // K) * K
        if n == 0:
            continue
        b = (w[:, :n].reshape(-1, K) if ax == 1 else w[:n, :].T.reshape(-1, K))
        a = b.abs().amax(dim=1)
        a = a[a > 0]
        l = torch.log2(a)
        fr.append((l - torch.floor(l)).cpu().numpy())
    del m
    f = np.concatenate(fr)
    return f, len(tg)


def ks_uniform(f):
    """sup |F_n(x) - x| for x in [0,1)."""
    x = np.sort(f)
    n = len(x)
    i = np.arange(1, n + 1)
    return float(max((i / n - x).max(), (x - (i - 1) / n).max()))


def tv_uniform(f, bins=64):
    h, _ = np.histogram(f, bins=bins, range=(0.0, 1.0))
    p = h / h.sum()
    return float(0.5 * np.abs(p - 1.0 / bins).sum())


print("Does the non-uniformity of frac(log2 blockmax) explain the DEPTH of the optimum?\n")
print(f"  {'model':<9}{'layers':>7}{'blocks':>12}{'KS':>9}{'TV':>9}"
      f"{'depth':>9}{'floor':>9}{'depth/floor':>13}")
rows = []
for tag in ("smollm2", "qwen", "pythia", "opt", "gpt2"):
    if not os.path.isdir(os.path.join(W, tag)):
        print(f"  {tag:<9}  absent")
        continue
    f, nl = frac_log2_maxima(tag)
    ks, tv = ks_uniform(f), tv_uniform(f)
    d, fl = MEAS.get(tag, (float("nan"), float("nan")))
    rows.append((tag, ks, tv, d, fl, len(f)))
    print(f"  {tag:<9}{nl:>7}{len(f):>12,}{ks:>9.4f}{tv:>9.4f}"
          + (f"{d:>9.4f}{fl:>9.4f}{d/fl:>13.2f}" if d == d else f"{'—':>9}{'—':>9}{'—':>13}"))

known = [r for r in rows if r[3] == r[3]]
if len(known) >= 3:
    ks = np.array([r[1] for r in known]); tv = np.array([r[2] for r in known])
    dp = np.array([r[3] for r in known])
    def spearman(a, b):
        ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
        return float(np.corrcoef(ra, rb)[0, 1])
    print(f"\n  models with a measured depth: {[r[0] for r in known]}")
    print(f"  Spearman(KS, depth) = {spearman(ks, dp):+.3f}"
          f"    Pearson = {float(np.corrcoef(ks, dp)[0,1]):+.3f}")
    print(f"  Spearman(TV, depth) = {spearman(tv, dp):+.3f}"
          f"    Pearson = {float(np.corrcoef(tv, dp)[0,1]):+.3f}")
    print("\n  Order by non-uniformity (KS):", [r[0] for r in sorted(known, key=lambda r: -r[1])])
    print("  Order by depth:               ", [r[0] for r in sorted(known, key=lambda r: -r[3])])
    print("\n  n = 4. A rank correlation on four points is weak evidence at best; the ORDERING")
    print("  is the informative part, and a mismatch refutes the hypothesis outright.")
json.dump([{"tag": r[0], "ks": r[1], "tv": r[2], "depth": r[3], "floor": r[4], "nblocks": r[5]}
           for r in rows], open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "depth_mechanism.json"), "w"), indent=1)
