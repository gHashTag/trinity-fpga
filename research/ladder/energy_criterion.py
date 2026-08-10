"""B: rebuild everything on the energy term, since it admits a 5x wider lambda window.

second_term.py found that the reach term should be the ENERGY below the smallest representable
level, not the COUNT of weights below it: energy ranks all six measured winners over a 10x range
of lambda, count over only 2x. Every earlier conclusion -- the three regimes, the continuous r*,
the activation predictions -- was computed with count.

Rebuilding on energy is not cosmetic. The two terms differ most exactly where the criterion was
weakest: small weights are numerous but carry little energy, so switching to energy demotes
precisely the population that the count term over-weights. If the activation predictions were
wrong because count over-counted tiny values, energy should fix them; if they were wrong for some
other reason, energy will not.

    score(r, b) = MSE(r, b) + lambda_e * flush_energy(r, b)

Three things are recomputed and compared against the count version:
  1. does it still rank all six weight winners  (it should -- that is how lambda_e was chosen)
  2. where does the continuous r* land now
  3. does it predict the MEASURED activation winners, where count scored 1 of 3
"""
import json
import os

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
LAM_N, LAM_E = 0.01, 0.79            # count window [5e-3,1e-2]; energy window [2.5e-1,2.5e0]
RAT = {"shift": 2.0, "phi": (1 + 5 ** 0.5) / 2,
       "supergold": 1.465571231876768, "plastic": 1.324717957244746}
NAME = {"shift": "shift  (2^k,   deg 1)", "phi": "phi    (1.618, deg 2)",
        "supergold": "supergold (1.4656, d3)", "plastic": "plastic(1.3247, deg 3)"}

# measured activation winners from sixbit_and_acts_ppl.py (SmolLM2, activations quantised)
ACT_TRUTH = {3: "phi", 4: "shift", 5: "plastic"}


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


def parts(x, r, bits):
    n = (2 ** bits - 1) // 2
    cb = codebook(r, bits)
    mid = (cb[:-1] + cb[1:]) / 2
    mse = float(((cb[np.searchsorted(mid, x)] - x) ** 2).mean())
    a = np.abs(x)
    below = a < r ** (-(n - 1)) / 2
    return mse, float(below.mean()), float((a[below] ** 2).sum() / (a ** 2).sum())


def winner(x, bits, lam, energy):
    def sc(k):
        m, fn, fe = parts(x, RAT[k], bits)
        return m + lam * (fe if energy else fn)
    return min(RAT, key=sc)


def r_star(x, bits, lam, energy, grid=np.linspace(1.05, 2.6, 80)):
    def sc(v):
        m, fn, fe = parts(x, float(v), bits)
        return m + lam * (fe if energy else fn)
    return float(grid[int(np.argmin([sc(v) for v in grid]))])


# ---------------------------------------------------------------- weights, both models
print("1 & 2 -- WEIGHTS: winners and continuous optimum under each term\n")
print(f"  {'model':9}{'bits':>5}{'measured':>11}{'count':>10}{'energy':>10}"
      f"{'r* count':>10}{'r* energy':>11}")
for MDIR in ("smollm2", "qwen"):
    ppl = {(r["bits"], r["ladder"]): r["ppl"]
           for r in json.load(open(f"ladder_ppl_{MDIR}.json")) if r["bits"]}
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MDIR), dtype=torch.float32)
    acc = []
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
            w = mod.weight.data.to(torch.float64)
            s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            z = (w / s).cpu().numpy().ravel()
            acc.append(z[:: max(1, z.size // 120000)])
    x = np.concatenate(acc)
    del m
    for bits in (3, 4, 5):
        meas = min(RAT, key=lambda k: ppl[(bits, NAME[k])])
        wn = winner(x, bits, LAM_N, False)
        we = winner(x, bits, LAM_E, True)
        print(f"  {MDIR:9}{bits:>5}{meas:>11}"
              f"{wn + ('' if wn == meas else ' X'):>10}"
              f"{we + ('' if we == meas else ' X'):>10}"
              f"{r_star(x, bits, LAM_N, False):>10.4f}"
              f"{r_star(x, bits, LAM_E, True):>11.4f}")

# ---------------------------------------------------------------- activations
print("\n\n3 -- ACTIVATIONS: does energy fix what count got wrong?\n")
tok = AutoTokenizer.from_pretrained(os.path.join(W, "smollm2"))
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0][:2048].view(1, 2048)
m = AutoModelForCausalLM.from_pretrained(os.path.join(W, "smollm2"),
                                         dtype=torch.float32).eval()
caps = []


def mk():
    def h(mod, inp):
        if len(caps) < 60:
            a = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
            s = a.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            caps.append((a / s).cpu().numpy().ravel()[::37])
        return None
    return h


hs = [mod.register_forward_pre_hook(mk()) for n, mod in m.named_modules()
      if isinstance(mod, torch.nn.Linear) and "lm_head" not in n]
m(ids)
for h in hs:
    h.remove()
xa = np.concatenate(caps)
del m
print(f"  activation samples: {xa.size:,}\n")
print(f"  {'bits':>5}{'MEASURED':>11}{'count pred':>13}{'energy pred':>14}"
      f"{'r* count':>10}{'r* energy':>11}")
nc = ne = 0
for bits in (3, 4, 5):
    wn = winner(xa, bits, LAM_N, False)
    we = winner(xa, bits, LAM_E, True)
    t = ACT_TRUTH[bits]
    nc += (wn == t)
    ne += (we == t)
    print(f"  {bits:>5}{t:>11}{wn + ('' if wn == t else ' X'):>13}"
          f"{we + ('' if we == t else ' X'):>14}"
          f"{r_star(xa, bits, LAM_N, False):>10.4f}"
          f"{r_star(xa, bits, LAM_E, True):>11.4f}")
print(f"\n  activations correct:  count {nc}/3   energy {ne}/3")
