#!/usr/bin/env python3
"""Campaign B, the disentangling control: the CODEWORD or the near-zero LEVEL?

MX-asym-NEAR0 wins by adding a positive level at 1/24 -- half E2M1's smallest
magnitude -- and paying for it with the sixteenth codeword.  Two things changed
at once: the alphabet grew from 15 values to 16, AND the book acquired a level
near zero where a Gaussian puts most of its mass.  One variable at a time.

So: build SYMMETRIC books (15 values, one codeword still forfeited) that also
carry the 1/24 level, buying it by dropping one of E2M1's magnitudes.

  MX-sym-NEAR0/6   [0, 1/24, 1/12, 1/6, 1/4, 1/3, 1/2, 1]      drops 2/3
  MX-sym-NEAR0/3   [0, 1/24, 1/12, 1/6, 1/3, 1/2, 2/3, 1]      drops 1/4

If either lands near MX-asym-NEAR0's margin, the near-zero level is doing the
work and the codeword is incidental.  If both fall well short, the codeword is.

MXFP4 is re-measured here as an ANCHOR: this is a different process from
campaignB_measure.py, and its per-window NLL vector must come back BIT-IDENTICAL
before the two files may be merged.  Written to campaignB2_<model>.json so it
cannot race the main run's file.

    MDIR=smollm2 NWIN=40 python3 campaignB2_control.py
"""
import json
import math
import os
import sys
import time
from fractions import Fraction as F

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])

import campaignC_books as C

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

MDIR = os.environ.get("MDIR", "smollm2")
NWIN = int(os.environ.get("NWIN", "40"))
DST = os.path.join(HERE, f"campaignB2_{MDIR}.json")

U = [1, 2, 3, 4, 6, 8, 12]                       # E2M1 in units of 1/12


def sym(units):
    lv = [0.0] + [float(F(u, 24) / F(12, 12)) if False else float(F(u) / F(12))
                  for u in units]
    lv = sorted(lv)
    assert abs(lv[-1] - 1.0) < 1e-15 and len(lv) == 8, lv
    return lv


def half_unit_book(drop):
    """E2M1 with 0.5 units added and `drop` units removed -- 7 magnitudes + 0."""
    u = [F(1, 2)] + [F(x) for x in U if x != drop]
    assert len(u) == 7, u
    lv = sorted([0.0] + [float(x / F(12)) for x in u])
    assert abs(lv[-1] - 1.0) < 1e-15, lv
    return lv


BOOKS = [
    ("MXFP4", C.MXFP4),                     # anchor, must match the main run
    ("MX-sym-NEAR0/6", half_unit_book(8)),  # drops 2/3
    ("MX-sym-NEAR0/3", half_unit_book(3)),  # drops 1/4
]


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print("=== control books (symmetric, 15 distinct values, 4.250 b/elem) ===")
    for n, lv in BOOKS:
        top = max(abs(x) for x in lv)
        assert abs(top - 1.0) < 1e-12, (n, top)
        assert len(lv) == 8 and lv[0] == 0.0
        print(f"  {n:<16} " + ", ".join(f"{x:.5f}" for x in lv))

    done = {}
    if os.path.exists(DST):
        prev = json.load(open(DST))
        if prev.get("nwin") == NWIN:
            done = prev.get("per_window_nll", {})

    path = os.path.join(W, MDIR)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"\nmodel {MDIR}  NWIN={NWIN}  {len(lins)} linear tensors", flush=True)

    nlls = {k: np.array(v, dtype=np.float64) for k, v in done.items()}
    for name, lv in BOOKS:
        if name in nlls:
            continue
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))
        nlls[name] = np.array([math.log(perplexity(model, win[i], 1))
                               for i in range(NWIN)], dtype=np.float64)
        json.dump({"model": MDIR, "nwin": NWIN,
                   "ppl": {k: float(np.exp(v.mean())) for k, v in nlls.items()},
                   "per_window_nll": {k: list(map(float, v))
                                      for k, v in nlls.items()},
                   "books": {n: lv for n, lv in BOOKS}},
                  open(DST, "w"), indent=1)
        print(f"  {name:<16}{float(np.exp(nlls[name].mean())):>10.4f}   "
              f"({time.time()-t0:.0f}s)", flush=True)
    for n, m in lins:
        m.weight.copy_(orig[n])

    # anchor: the MXFP4 window vector must be BIT-IDENTICAL to the main run's
    main_path = os.path.join(HERE, f"campaignB_{MDIR}.json")
    if os.path.exists(main_path):
        a = np.array(json.load(open(main_path))["per_window_nll"]["MXFP4"])
        b = nlls["MXFP4"]
        same = bool(np.array_equal(a, b))
        print(f"\nANCHOR MXFP4 vs campaignB_{MDIR}.json: "
              f"max|d| = {np.abs(a-b).max():.3e}  "
              f"{'BIT-IDENTICAL -- files may be merged' if same else 'DIFFERS'}")
        out = json.load(open(DST))
        out["anchor_bit_identical"] = same
        json.dump(out, open(DST, "w"), indent=1)
        return 0 if same else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
