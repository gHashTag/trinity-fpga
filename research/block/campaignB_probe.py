#!/usr/bin/env python3
"""Probe before the campaign: (a) prove the signed quantiser I must add is the
SAME map as the harness quant() on a symmetric book, (b) time one window so the
arm count can be chosen from measurement rather than guess.

The harness quant() takes 8 MAGNITUDES and applies sign(w) separately. NF4 and
BOF4 are 16-level ASYMMETRIC books, which that path cannot express, so one new
function is unavoidable. It is validated against the old one instead of trusted.
"""
import math
import os
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
fp_levels, q_e8m0_t = ns["fp_levels"], ns["q_e8m0_t"]
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])
torch.set_grad_enabled(False)


def quant_signed(w, lv, signed_scale=False):
    """Block quantiser for a FULL signed codebook (levels may be asymmetric).

    Same block size K, same E8M0 shared scale, same midpoint decision rule as
    quant(). Only two things differ, and both are forced by the format:
      * the level table carries its own signs, so no sign(w) factor is applied;
      * signed_scale=True implements BOF4-S's signed block maximum (their eq. 4),
        which needs ONE EXTRA BIT per block on top of E8M0. That bit is charged
        in the bit-budget column of the results table.
    """
    lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
    top = float(lv_t.abs().max())
    orig = w.shape
    n = (orig[1] // K) * K
    if n == 0:
        return w
    head = w[:, :n].reshape(-1, K).double()
    amax, arg = head.abs().max(dim=1)
    if signed_scale:
        m = torch.gather(head, 1, arg[:, None])[:, 0]
        sgn = torch.where(m < 0, -1.0, 1.0).double()
        s = q_e8m0_t((m.abs() / top).clamp(min=1e-30)).clamp(min=1e-30) * sgn
    else:
        s = q_e8m0_t((amax / top).clamp(min=1e-30)).clamp(min=1e-30)
    y = head / s[:, None]
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    # Tie rule. quant() bucketizes |y| with right=False, so a value sitting
    # EXACTLY on a midpoint takes the smaller magnitude -- ties toward zero.
    # Applying right=False to signed y would send negative ties the other way.
    # Dyadic midpoints are reachable: y = -0.125 is exact whenever the block
    # scale is a power of two, and it happens 94462 times in SmolLM2 alone.
    idx = torch.where(y < 0,
                      torch.bucketize(y, bnd, right=True),
                      torch.bucketize(y, bnd, right=False))
    rec = lv_t[idx] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def mirror(mag):
    """8 magnitudes -> the 15 distinct signed levels they generate."""
    return sorted(set([-x for x in mag if x != 0.0] + list(mag)))


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, "smollm2")
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    lins = target_modules(model)
    print(f"{len(lins)} linear tensors", flush=True)

    MX = sorted(float(x) for x in fp_levels(2, 1))
    MX = [x / MX[-1] for x in MX]
    LL = [x / 0.96567 for x in [0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                                0.59031, 0.75635, 0.96567]]

    print("\n=== EQUIVALENCE: quant(mag) vs quant_signed(mirror(mag)) ===")
    for nm, mag in (("MXFP4", MX), ("Lloyd-Max", LL)):
        worst = 0.0
        nel = 0
        for n, m in lins:
            w = m.weight.detach()
            a = quant(w, mag)
            b = quant_signed(w, mirror(mag))
            d = float((a - b).abs().max())
            worst = max(worst, d)
            nel += w.numel()
        print(f"  {nm:<12} max |quant - quant_signed| = {worst:.3e} "
              f"over {nel} elements")
        assert worst == 0.0, f"{nm}: the two paths are NOT the same map"
    print("  -> the new path reproduces the harness path EXACTLY (0.000e+00)")

    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    t0 = time.time()
    p = perplexity(model, win[0], 1)
    dt = time.time() - t0
    print(f"\n=== TIMING === smollm2 one window ppl={p:.4f} in {dt:.1f}s "
          f"-> 40 windows ~= {dt*40/60:.1f} min per arm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
