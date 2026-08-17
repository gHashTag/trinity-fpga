#!/usr/bin/env python3
"""POST-HOC, and labelled post-hoc: what the squared-error functional misses.

T42's magnitude prediction assumes the loss penalty of an arm is proportional to
its block squared weight error with a per-model constant.  The measurement says
the perplexity benefit is systematically LARGER than the squared-error benefit.
This file measures the obvious candidate for the discrepancy without claiming it
is the explanation.

The band the two books differ in is |y| in [1/48, 1/16) -- SMALL normalised
weights.  Inside it MXFP4 sends everything below y = 1/24 to EXACTLY ZERO, i.e.
it deletes the coefficient.  Deletion is a one-signed error: every deleted weight
moves the row sum toward zero, so the errors ADD along a row instead of
cancelling.  Squared error counts them as if they cancelled.  NEAR0's sixteenth
codeword at +1/24 rescues the positive half of that band from deletion.

Measured per checkpoint, for MXFP4 and for MX-asym-NEAR0:
  * fraction of blocked elements reconstructed as exactly zero;
  * incoherent error  sum_ij dw_ij^2;
  * coherent error    sum_i (sum_j dw_ij)^2   over full input rows.

    python3 campaignE_zeroing.py
"""
import json
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import campaignE_occupancy as E

_s = open("block_tnf.py", encoding="utf-8").read()
ns = {}
exec(compile(_s.split('print("загружаю модель…", flush=True)')[0],
             "block_tnf.py", "exec"), ns)
quant, K = ns["quant"], ns["K"]
import campaignC_books as C
quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])
torch.set_grad_enabled(False)

MODELS = json.load(open(os.path.join(HERE, "campaignE_models.json")))


def run(name, path):
    from transformers import AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    E.assert_same_as_ruler(model)
    acc = {a: {"z": 0, "inc": 0.0, "coh": 0.0} for a in ("MXFP4", "NEAR0")}
    ntot = 0
    for n, m, tr in E.quantisable(model):
        w = E.get_w(m, tr).double()
        cols = (w.shape[1] // K) * K
        if cols == 0:
            continue
        wt = w[:, :cols]
        ntot += wt.numel()
        for a, q in (("MXFP4", lambda x: quant(x, E.MXFP4)),
                     ("NEAR0", lambda x: quant_signed(x, E.NEAR0))):
            r = q(wt)
            dw = (r - wt)
            acc[a]["z"] += int((r == 0).sum())
            acc[a]["inc"] += float((dw * dw).sum())
            acc[a]["coh"] += float((dw.sum(dim=1) ** 2).sum())
    del model
    out = {"n_elem": ntot}
    for a in acc:
        out[a] = {"zero_frac": acc[a]["z"] / ntot,
                  "incoherent": acc[a]["inc"], "coherent": acc[a]["coh"]}
    out["ratio_incoherent"] = 1 - acc["NEAR0"]["inc"] / acc["MXFP4"]["inc"]
    out["ratio_coherent"] = 1 - acc["NEAR0"]["coh"] / acc["MXFP4"]["coh"]
    out["zero_delta"] = acc["MXFP4"]["z"] / ntot - acc["NEAR0"]["z"] / ntot
    return out


if __name__ == "__main__":
    outp = os.path.join(HERE, "campaignE_zeroing.json")
    res = json.load(open(outp)) if os.path.exists(outp) else {}
    for name in (sys.argv[1:] or list(MODELS)):
        if name in res or not os.path.exists(MODELS[name]):
            continue
        res[name] = run(name, MODELS[name])
        r = res[name]
        print(f"{name:<13} zeroed MXFP4 {r['MXFP4']['zero_frac']:.4f} -> NEAR0 "
              f"{r['NEAR0']['zero_frac']:.4f}   dD/D inc {r['ratio_incoherent']:+.5f}"
              f"   coh {r['ratio_coherent']:+.5f}", flush=True)
        json.dump(res, open(outp, "w"), indent=1)
