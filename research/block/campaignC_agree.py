#!/usr/bin/env python3
"""Instrument check: the asymmetric quantiser IS the symmetric one.

Runs block_tnf.quant(w, magnitudes) and quant_signed(w, +/-magnitudes u {0}) over
every quantised tensor of every model and demands bit-exact equality. Without
this the NF4 arm and the seven symmetric arms are measured by two different
rulers and nothing in Campaign C is comparable.

    python3 campaignC_agree.py
"""
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
_s = open(os.path.join(HERE, "block_tnf.py"), encoding="utf-8").read()
ns = {}
exec(compile(_s.split('print("загружаю модель…", flush=True)')[0],
             "block_tnf.py", "exec"), ns)
quant, target_modules = ns["quant"], ns["target_modules"]
K = ns["K"]
W = os.path.dirname(ns["MODEL"])

import campaignC_books as C

torch.set_grad_enabled(False)
quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

MODELS = ["smollm2", "qwen", "pythia", "opt"]


def main():
    from transformers import AutoModelForCausalLM
    bs = C.books()
    sym = [(n, lv) for n, kind, lv in bs if kind == "mag"]
    allok = True
    ntens = 0
    for md in MODELS:
        model = AutoModelForCausalLM.from_pretrained(
            os.path.join(W, md), dtype=torch.float32)
        model.eval()
        lins = target_modules(model)
        worst = 0.0
        nties = 0
        for name, mags in sym:
            sig = C.signed_from_magnitudes(mags)
            assert len(sig) == 15, (name, len(sig))
            for _, m in lins:
                w = m.weight.detach()
                a = quant(w, mags)
                b = quant_signed(w, sig)
                d = (a - b).abs().max().item()
                worst = max(worst, d)
                ntens += 1
        # how often does a weight land exactly on a decision boundary?
        # (the only place the two rules could ever have differed)
        mags = dict(sym)["MXFP4"]
        lv_t = torch.tensor(mags, dtype=torch.float64)
        bnd = (lv_t[:-1] + lv_t[1:]) / 2
        for _, m in lins:
            w = m.weight.detach()
            n = (w.shape[1] // K) * K
            head = w[:, :n].reshape(-1, K).double()
            s = ns["q_e8m0_t"]((head.abs().amax(dim=1) / lv_t[-1]).clamp(min=1e-30))
            y = (head / s[:, None]).abs()
            nties += int((y[..., None] == bnd).any(-1).sum())
        ok = worst == 0.0
        allok &= ok
        print(f"{md:<9} tensors x books checked, max|quant - quant_signed| = "
              f"{worst:.3e}  {'BIT-EXACT' if ok else 'MISMATCH'}   "
              f"(exact-boundary weights under MXFP4: {nties})", flush=True)
        del model
    print(f"\n{ntens} tensor-book comparisons")
    print("AGREEMENT:", "PROVEN" if allok else "FAILED")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
