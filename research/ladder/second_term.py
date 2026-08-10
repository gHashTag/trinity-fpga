"""Is `flush` the right second term, or merely a lucky proxy for it?

two_term.py added `lambda * flush` -- the FRACTION OF WEIGHTS deleted because they fall below the
smallest representable level -- and one lambda then reproduced all six measured winners. But
flush was the first thing tried, and several other quantities measure "reach" equally well.
If one of them needs no fitting, or admits a much wider lambda window, that one is the physics
and flush was an approximation to it.

CANDIDATES, all measured on the same normalised weights:

  flush_n    fraction of WEIGHTS below the threshold        (current)
  flush_e    fraction of total ENERGY below the threshold   -- weights it by magnitude
  dead_row   fraction of output CHANNELS entirely deleted   -- structural, not statistical
  span_log   -log(span) = -(n-1) log r                      -- pure reach, ignores the data

A term that ranks with a WIDER admissible lambda window is more robust; a term that ranks at
lambda -> 0 or lambda -> inf on its own would mean no fitting is needed at all. Both would beat
the present situation, which is one fitted constant against six binary outcomes.
"""
import json
import os

import numpy as np
import torch
from transformers import AutoModelForCausalLM

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
RAT = {"shift": 2.0, "phi": (1 + 5 ** 0.5) / 2,
       "supergold": 1.465571231876768, "plastic": 1.324717957244746}
NAME = {"shift": "shift  (2^k,   deg 1)", "phi": "phi    (1.618, deg 2)",
        "supergold": "supergold (1.4656, d3)", "plastic": "plastic(1.3247, deg 3)"}


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


DATA = {}
for MDIR in ("smollm2", "qwen"):
    ppl = {(r["bits"], r["ladder"]): r["ppl"]
           for r in json.load(open(f"ladder_ppl_{MDIR}.json")) if r["bits"]}
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MDIR), dtype=torch.float32)
    flat, rows = [], []
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
            w = mod.weight.data.to(torch.float64)
            s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            z = (w / s).cpu().numpy()
            step = max(1, z.shape[0] // 64)
            rows.append(np.abs(z[::step]))                       # keep row structure
            f = z.ravel()
            flat.append(f[:: max(1, f.size // 150000)])
    del m
    # layers have different input widths, so rows cannot be concatenated -- keep them as a
    # list and average dead_row over layers weighted by row count.
    DATA[MDIR] = (np.concatenate(flat), rows, ppl)
    print(f"  {MDIR}: {DATA[MDIR][0].size:,} flat, "
          f"{sum(r.shape[0] for r in rows):,} rows kept across {len(rows)} layers")


def terms(x, rowsabs, r, bits):
    n = (2 ** bits - 1) // 2
    thr = r ** (-(n - 1)) / 2
    cb = codebook(r, bits)
    mid = (cb[:-1] + cb[1:]) / 2
    mse = float(((cb[np.searchsorted(mid, x)] - x) ** 2).mean())
    a = np.abs(x)
    below = a < thr
    return {
        "flush_n": float(below.mean()),
        "flush_e": float((a[below] ** 2).sum() / (a ** 2).sum()),
        "dead_row": float(sum((g < thr).all(axis=1).sum() for g in rowsabs)
                          / sum(g.shape[0] for g in rowsabs)),
        "span_log": float(-(n - 1) * np.log(r)),
    }, mse


LAMS = np.concatenate([[0.0], np.logspace(-5, 1, 61)])

# Precompute every term ONCE. The first version called terms() inside the lambda sweep, which
# re-quantised 150k points and re-scanned every row 1488 times over.
CACHE = {}
for MDIR in ("smollm2", "qwen"):
    x, rows, ppl = DATA[MDIR]
    for bits in (3, 4, 5):
        for k, r in RAT.items():
            CACHE[(MDIR, bits, k)] = terms(x, rows, r, bits)
print("  terms cached")

print("\n  second term    lambdas ranking all 6 winners            window")
for tname in ("flush_n", "flush_e", "dead_row", "span_log"):
    good = []
    for lam in LAMS:
        ok = 0
        for MDIR in ("smollm2", "qwen"):
            ppl = DATA[MDIR][2]
            for bits in (3, 4, 5):
                sc = {k: CACHE[(MDIR, bits, k)][1] + lam * CACHE[(MDIR, bits, k)][0][tname]
                      for k in RAT}
                bp = min(RAT, key=lambda k: ppl[(bits, NAME[k])])
                ok += (min(sc, key=lambda k: sc[k]) == bp)
        if ok == 6:
            good.append(float(lam))
    if not good:
        print(f"  {tname:12} NONE -- cannot rank all six at any lambda")
    elif min(good) == 0.0:
        print(f"  {tname:12} {len(good):>3}/{len(LAMS)} values, INCLUDING lambda=0 "
              f"(no fitting needed)")
    else:
        lo, hi = min(good), max(good)
        print(f"  {tname:12} {len(good):>3}/{len(LAMS)} values   "
              f"[{lo:.2e}, {hi:.2e}]   width {hi/lo:.1f}x")
