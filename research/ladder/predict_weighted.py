"""Does weighting by measured layer sensitivity rescue the 4-bit prediction?

predict_any.py showed both predictors -- exact codebook error and the closed form -- pick
supergolden at 4 bits while perplexity picks phi, on BOTH models. The two fail identically, so
the fault is not the analytic approximation but the shared premise that unweighted weight-MSE
ranks ladders the way perplexity does.

The block-quantisation line measured, independently and on these same two checkpoints, that
per-layer squared error correlates with per-layer perplexity damage at only r = +0.13, while the
damage itself spans 42x. Those per-layer damages are available, so the premise can be repaired
rather than merely criticised:

    objective  =  sum_l  s_l * MSE_l ,      s_l = (perplexity damage of block l) / MSE_l

s_l is the damage per unit of squared error -- the exchange rate the unweighted sum assumes is
constant. It is not.

TEST: recompute both predictors under this objective. If phi overtakes supergolden at 4 bits on
both models while 3 and 5 bits stay correct, the law survives with a corrected objective. If it
does not, the 4-bit ordering has a cause outside weight statistics and no reweighting will find
it.

The sensitivity profiles were measured with an E2M1 codebook, not a ladder. They are used here
only as a RELATIVE ranking of which blocks matter, which is the part expected to be codebook
independent. That assumption is itself a limitation and is stated, not hidden.
"""
import json
import os
import re

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

# per-block perplexity damage and summed MSE, measured by sensitivity_profile.py
PROF = {
    "smollm2": (
        np.array([0.0952, 0.0973, 0.1083, 0.0695, 0.0401, 0.0097, 0.0572, 0.0358, 0.0383,
                  0.0256, 0.0469, 0.0960, 0.0706, 0.0691, 0.0993, 0.0661, 0.0812, 0.1113,
                  0.1507, 0.1237, 0.1742, 0.0614, 0.0762, 0.1165, 0.0579, 0.0563, 0.1160,
                  0.0774, 0.1311, 0.4070]),
        np.array([1438.1943, 1335.6018, 1292.0653, 1306.3311, 1288.1378, 1265.5231, 1302.6299,
                  1273.9641, 1284.8257, 1322.5296, 1346.4854, 1344.9005, 1325.1743, 1318.0615,
                  1283.0718, 1292.2842, 1339.4485, 1299.7285, 1253.3065, 1329.1526, 1307.0804,
                  1315.7523, 1355.9736, 1421.8265, 1403.1751, 1420.1261, 1432.8625, 1397.1226,
                  1432.9144, 1342.9496])),
    "qwen": (
        np.array([0.0805, 0.0266, 0.1006, 0.0901, 0.0538, 0.0429, 0.0731, 0.0399, 0.0456,
                  0.0548, 0.0498, 0.0635, 0.0448, 0.0674, 0.0510, 0.0619, 0.0933, 0.0811,
                  0.0452, 0.0623, 0.1068, 0.0990, 0.1183, 0.2187]),
        np.array([102.6337, 62.7949, 62.5382, 59.6237, 61.1121, 61.7206, 61.2348, 60.9100,
                  63.1468, 58.3867, 58.9751, 55.5034, 58.5153, 58.5300, 59.5923, 61.3145,
                  63.0638, 61.7509, 62.4228, 63.9112, 65.9136, 67.4416, 66.2654, 62.1705])),
}


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


def c2(r, m=20001):
    u = np.linspace(0, 1, m)
    x = r ** (-u)
    return float(np.mean((np.minimum(np.abs(x - 1.0), np.abs(x - 1.0 / r)) / x) ** 2))


for MDIR in ("smollm2", "qwen"):
    dppl, mse_l = PROF[MDIR]
    sens = dppl / mse_l
    sens = sens / sens.mean()
    ppl = {(r["bits"], r["ladder"]): r["ppl"]
           for r in json.load(open(f"ladder_ppl_{MDIR}.json")) if r["bits"]}
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MDIR), dtype=torch.float32)
    mods = [(nm, mod) for nm, mod in m.named_modules()
            if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
    print(f"\n===== {MDIR}   {len(mods)} layers   sensitivity spread "
          f"{sens.max()/sens.min():.1f}x =====")

    # cache normalised |w| per layer once
    cache = []
    for nm, mod in mods:
        li = layer_index(nm)
        w = mod.weight.data.to(torch.float64)
        s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
        cache.append((sens[li] if 0 <= li < len(sens) else 1.0, (w / s).cpu().numpy()))
    del m

    C2 = {v: c2(v) for v in RAT.values()}
    okU = okW = True
    for bits in (3, 4, 5):
        rows = []
        for nm, r in RAT.items():
            cb = codebook(r, bits)
            mid = (cb[:-1] + cb[1:]) / 2
            n = (2 ** bits - 1) // 2
            t = r ** (-(n - 1)) / 2
            uN = uD = wN = wD = 0.0
            cuN = cwN = 0.0
            for sl, x in cache:
                e = ((cb[np.searchsorted(mid, x)] - x) ** 2).sum()
                uN += e
                wN += sl * e
                a = np.abs(x)
                below = a < t
                ce = C2[r] * (a[~below] ** 2).sum() + (a[below] ** 2).sum()
                cuN += ce
                cwN += sl * ce
                uD += x.size
                wD += sl * x.size
            rows.append((nm, uN / uD, wN / wD, cuN / uD, cwN / wD, ppl[(bits, nm)]))
        short = lambda s: s.split()[0]
        bu = min(rows, key=lambda t_: t_[1])[0]
        bw = min(rows, key=lambda t_: t_[2])[0]
        bcw = min(rows, key=lambda t_: t_[4])[0]
        bp = min(rows, key=lambda t_: t_[5])[0]
        okU &= (bu == bp)
        okW &= (bw == bp)
        print(f"\n  {bits} bits   measured winner = {short(bp)}")
        for nm, u, wv, cu, cw, p in sorted(rows, key=lambda t_: t_[5]):
            print(f"    {nm:24} unweighted={u:.4e}  weighted={wv:.4e}  "
                  f"closed-w={cw:.4e}  ppl={p:11.3f}")
        print(f"    winner: unweighted={short(bu):10} weighted={short(bw):10} "
              f"closed-weighted={short(bcw):10}"
              f"   [{'W ok' if bw == bp else 'W WRONG'}]")
    print(f"\n  {MDIR}: unweighted all-correct={okU}   sensitivity-weighted all-correct={okW}")
