#!/usr/bin/env python3
"""Instrument check for Campaign B: the asymmetric quantiser IS the symmetric one.

Every Campaign B arm that spends the sixteenth codeword is measured with
`quant_signed` (an explicit SIGNED level list); every reference arm is measured
with `block_tnf.quant` (a MAGNITUDE list plus sign(w)).  If those two are not
the same instrument the comparison is meaningless.

So: for each symmetric book actually used here, hand `quant_signed` the level
set +/-magnitudes u {0} and demand BIT-EXACT equality with `quant`, on every
quantised tensor of all four checkpoints.

The single place the two rules could ever differ is a weight landing exactly on
a decision boundary: `quant` bucketizes |w|, so a tie rounds toward zero on both
signs, whereas a naive signed bucketize rounds toward -inf.  `quant_signed`
reproduces round-half-toward-ZERO explicitly.  The tie counter below reports how
often that case is even reachable.

    python3 campaignB_agree.py
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

import campaignB_books as B
import campaignC_books as C

torch.set_grad_enabled(False)
quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

MODELS = ["smollm2", "qwen", "pythia", "opt"]


def main():
    from transformers import AutoModelForCausalLM
    sym = [(n, lv) for n, kind, lv in B.books() if kind == "mag"]
    print("symmetric books checked:", ", ".join(n for n, _ in sym), flush=True)
    allok = True
    ncmp = 0
    for md in MODELS:
        model = AutoModelForCausalLM.from_pretrained(
            os.path.join(W, md), dtype=torch.float32)
        model.eval()
        lins = target_modules(model)
        worst = 0.0
        for name, mags in sym:
            sig = C.signed_from_magnitudes(mags)
            assert len(sig) == 15, (name, len(sig))
            for _, m in lins:
                w = m.weight.detach()
                d = (quant(w, mags) - quant_signed(w, sig)).abs().max().item()
                worst = max(worst, d)
                ncmp += 1
        # how often is a weight exactly on a decision boundary at all?
        nties = 0
        lv_t = torch.tensor(dict(sym)["MXFP4"], dtype=torch.float64)
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
        print(f"{md:<9} {len(lins):3d} tensors x {len(sym)} books   "
              f"max|quant - quant_signed| = {worst:.3e}  "
              f"{'BIT-EXACT' if ok else 'MISMATCH'}   "
              f"(weights exactly on an MXFP4 boundary: {nties})", flush=True)
        del model
    print(f"\n{ncmp} tensor-book comparisons")
    print("AGREEMENT:", "PROVEN" if allok else "FAILED")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
