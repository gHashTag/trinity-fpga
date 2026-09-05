#!/usr/bin/env python3
"""Re-deriving the codebook under the objective the evidence actually supports.

The sensitivity profile showed per-layer perplexity damage spans 41.9x while per-layer MSE spans
1.15x, with correlation r = +0.13. So the unweighted objective every codebook here was derived
under is close to uninformative about the thing being optimised.

TWO weighting errors, not one. Setting this up exposed a second, independent of the first:

  (A) MISSING a^2.  Total squared error over a block is  a^2 * sum (Q(y)-y)^2  where a is the
      block maximum. Our DP histogrammed y with every block counted equally, so it minimised the
      NORMALISED error E[(Q(y)-y)^2], not true MSE. Blocks with large maxima dominate real MSE
      and were being under-weighted. Every "MSE-optimal" codebook in this document is optimal for
      a quantity that is not MSE.

  (B) MISSING per-layer sensitivity.  Weight layer l by  s_l = dppl_l / MSE_l, its measured
      perplexity damage per unit of squared error, from sensitivity_profile.py.

So three codebooks are derived and compared:

    DP-flat        histogram of y, unweighted            (what we had)
    DP-a2          each y weighted by a^2                (genuinely MSE-optimal)
    DP-sens        each y weighted by a^2 * s_l          (sensitivity-weighted)

HOLD-OUT DISCIPLINE. The sensitivity profile was measured on windows 0-5. Perplexity here is
evaluated on windows 6-17, which the profile never saw. The layer weights are still calibrated on
this model, so this tests whether the weighting helps at all, not whether it transfers -- that is
a separate question and is flagged rather than assumed.
"""
import os
import re
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from competitors import FP4_E2M1 as E2M1, NF4

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NBIN = 32, 2048, 800
torch.set_grad_enabled(False)

# measured by sensitivity_profile.py on windows 0-5 (E2M1, one block at a time)
DPPL = np.array([0.0952, 0.0973, 0.1083, 0.0695, 0.0401, 0.0097, 0.0572, 0.0358, 0.0383,
                 0.0256, 0.0469, 0.0960, 0.0706, 0.0691, 0.0993, 0.0661, 0.0812, 0.1113,
                 0.1507, 0.1237, 0.1742, 0.0614, 0.0762, 0.1165, 0.0579, 0.0563, 0.1160,
                 0.0774, 0.1311, 0.4070])
MSE_L = np.array([1438.1943, 1335.6018, 1292.0653, 1306.3311, 1288.1378, 1265.5231, 1302.6299,
                  1273.9641, 1284.8257, 1322.5296, 1346.4854, 1344.9005, 1325.1743, 1318.0615,
                  1283.0718, 1292.2842, 1339.4485, 1299.7285, 1253.3065, 1329.1526, 1307.0804,
                  1315.7523, 1355.9736, 1421.8265, 1403.1751, 1420.1261, 1432.8625, 1397.1226,
                  1432.9144, 1342.9496])
SENS = DPPL / MSE_L
SENS = SENS / SENS.mean()

OURS_OLD = np.array([-1.0000, -0.7805, -0.6094, -0.4645, -0.3361, -0.2183, -0.1066, 0.0000,
                     0.0944, 0.1901, 0.2908, 0.3987, 0.5162, 0.6491, 0.8053, 1.0000])


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def dp_pinned(dens, pins, nlev=16):
    y = np.linspace(-1, 1, NBIN, endpoint=False) + 1.0 / NBIN
    w = dens * (2.0 / NBIN)
    S0 = np.concatenate([[0.0], np.cumsum(w)])
    S1 = np.concatenate([[0.0], np.cumsum(w * y)])
    S2 = np.concatenate([[0.0], np.cumsum(w * y * y)])

    def cost(a, b, k):
        s0, s1, s2 = S0[b] - S0[a], S1[b] - S1[a], S2[b] - S2[a]
        if k in pins:
            r = pins[k]
            return s2 - 2 * r * s1 + r * r * s0
        return np.where(s0 > 0, s2 - s1 * s1 / np.maximum(s0, 1e-300), 0.0)

    M = NBIN
    f = np.full((nlev, M + 1), np.inf)
    bk = np.zeros((nlev, M + 1), dtype=int)
    f[0] = cost(0, np.arange(M + 1), 0)
    for k in range(1, nlev):
        prev = f[k - 1]
        for i in range(1, M + 1):
            j = np.arange(0, i)
            c = prev[j] + cost(j, i, k)
            t = int(np.argmin(c))
            f[k][i], bk[k][i] = c[t], t
    bounds, cur = [M], M
    for k in range(nlev - 1, 0, -1):
        cur = bk[k][cur]
        bounds.append(cur)
    bounds = sorted(set(bounds + [0]))
    while len(bounds) < nlev + 1:
        bounds.append(M)
    bounds = sorted(bounds)
    lv = []
    for c in range(nlev):
        a, b = bounds[c], bounds[c + 1]
        if c in pins:
            lv.append(pins[c])
        else:
            s0 = S0[b] - S0[a]
            lv.append(float((S1[b] - S1[a]) / s0) if s0 > 0 else float(y[min(a, M - 1)]))
    return np.array(sorted(lv))


def quantise(w, lv):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    s = b.abs().amax(1).clamp(min=1e-30)
    idx = torch.bucketize(b / s[:, None], (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
    out = w.clone()
    out[:, :n] = (lv[idx] * s[:, None]).reshape(-1, n).to(w.dtype)
    return out


tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
BASE = {n: m.weight.detach().clone() for n, m in lins}

# three weighted histograms in one pass
h_flat = np.zeros(NBIN)
h_a2 = np.zeros(NBIN)
h_sens = np.zeros(NBIN)
for n, m in lins:
    li = layer_index(n)
    w = BASE[n].double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    b, a = b[ok], a[ok]
    y = (b / a[:, None]).reshape(-1).numpy()
    wa2 = np.repeat((a ** 2).numpy(), K)
    h_flat += np.histogram(y, bins=NBIN, range=(-1, 1))[0]
    h_a2 += np.histogram(y, bins=NBIN, range=(-1, 1), weights=wa2)[0]
    h_sens += np.histogram(y, bins=NBIN, range=(-1, 1), weights=wa2 * SENS[li])[0]

PINS = {0: -1.0, 15: 1.0, 7: 0.0}
DP_FLAT = dp_pinned(h_flat / (h_flat.sum() * (2.0 / NBIN)), PINS)
DP_A2 = dp_pinned(h_a2 / (h_a2.sum() * (2.0 / NBIN)), PINS)
DP_SENS = dp_pinned(h_sens / (h_sens.sum() * (2.0 / NBIN)), PINS)


def ppl(lo, hi):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[lo:hi]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


LO, HI = 6, 18                       # windows the sensitivity profile never saw
p0 = ppl(LO, HI)
print(f"RULER CHECK -- fp32 baseline {p0:.4f} (windows {LO}-{HI-1}, unseen by the profile)")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible")

print(f"\n  sensitivity weights: min {SENS.min():.3f}  max {SENS.max():.3f}  "
      f"ratio {SENS.max()/SENS.min():.1f}x")
print(f"\n  DP-flat  " + " ".join(f"{v:+.3f}" for v in DP_FLAT))
print(f"  DP-a2    " + " ".join(f"{v:+.3f}" for v in DP_A2))
print(f"  DP-sens  " + " ".join(f"{v:+.3f}" for v in DP_SENS))
print(f"\n  max level shift  flat->a2 {np.abs(DP_FLAT-DP_A2).max():.4f}"
      f"   a2->sens {np.abs(DP_A2-DP_SENS).max():.4f}")

print(f"\n  {'codebook':<26}{'perplexity':>12}{'vs fp32':>10}")
for name, lv in (("E2M1 (correct)", E2M1), ("NF4 (real)", NF4),
                 ("DP-flat (what we had)", OURS_OLD), ("DP-a2 (true MSE-optimal)", DP_A2),
                 ("DP-sens (weighted)", DP_SENS)):
    lvt = torch.tensor(lv, dtype=torch.float64)
    for n, m in lins:
        m.weight.copy_(quantise(BASE[n].double(), lvt).to(m.weight.dtype))
    p = ppl(LO, HI)
    print(f"  {name:<26}{p:>12.4f}{p - p0:>+10.4f}")
for n, m in lins:
    m.weight.copy_(BASE[n])
