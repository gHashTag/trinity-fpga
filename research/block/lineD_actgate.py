#!/usr/bin/env python3
r"""LINE D: the activation gate that T41's two-channel split says is missing.

PRE-REGISTERED, written before this script was run even once.

lineD_probe.py found the same thing on every checkpoint measured so far: the
clipping arm LOWERS the sum of squared weight errors and RAISES their row-level
coherence.  Those are two channels of the same layer-output error and they move
in OPPOSITE directions, so no statistic computed from weights alone can decide
between them.  For a linear layer whose input x has per-feature mean mu and
variance v, the expected squared output error of row r is exactly

    E[(sum_j dw_rj x_j)^2] = (sum_j dw_rj mu_j)^2  +  sum_j dw_rj^2 v_j
                              \____coherent____/     \____incoherent____/

so the missing weight is mu^2 relative to v -- a property of the ACTIVATIONS,
not of the weights.  It is measurable, and measuring it is not fitting: there is
no free parameter here, only a quantity the derivation names and the weight-only
predictor omitted.

PREDICTION UNDER TEST: the activation-gated total above orders the four models
better than the pure weight MSE ratio does.  Whatever it gives is reported.

Activations are taken from the UNQUANTISED model on one calibration window --
a first-order proxy, stated as such; the quantised model's own activations
differ and that is a known limitation, not a hidden one.

    W=<weights dir> MDIR=pythia python3 lineD_actgate.py
"""
import json
import os

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"), ns)
quant, target_modules = ns["quant"], ns["target_modules"]
q_e8m0_t, K, SEQLEN = ns["q_e8m0_t"], ns["K"], ns["SEQLEN"]

import campaignA_books as A
import campaignC_books as C

torch.set_grad_enabled(False)
MDIR = os.environ["MDIR"]
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
NCAL = int(os.environ.get("NCAL", "1"))


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    BOOKS = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))
    mx_lv, top_lv = BOOKS["MXFP4"][1], BOOKS["MX-asym-TOP"][1]
    quant_signed = C.make_quant_signed(K, q_e8m0_t)

    path = os.path.join(WDIR, MDIR)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    txt = "\n\n".join(__import__("pyarrow.parquet", fromlist=["parquet"])
                      .read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
                      .column("text").to_pylist())
    flat = tok(txt, return_tensors="pt").input_ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)

    lins = target_modules(model)
    stats = {n: None for n, _ in lins}
    handles = []

    def mk(nm):
        def hook(mod, args):
            x = args[0].detach().double().reshape(-1, args[0].shape[-1])
            s, sq, c = x.sum(0), (x * x).sum(0), x.shape[0]
            if stats[nm] is None:
                stats[nm] = [s, sq, c]
            else:
                stats[nm][0] += s
                stats[nm][1] += sq
                stats[nm][2] += c
        return hook

    for nm, m in lins:
        handles.append(m.register_forward_pre_hook(mk(nm)))
    for i in range(NCAL):
        model(win[i:i + 1])
    for h in handles:
        h.remove()

    tot = {"MXFP4": [0.0, 0.0], "MX-asym-TOP": [0.0, 0.0]}   # [coh, inc]
    for nm, m in lins:
        s, sq, cnt = stats[nm]
        mu = s / cnt
        v = (sq / cnt - mu * mu).clamp(min=0.0)
        w = m.weight.detach()
        n = (w.shape[1] // K) * K
        for bk, lv in (("MXFP4", mx_lv), ("MX-asym-TOP", top_lv)):
            f = quant if bk == "MXFP4" else quant_signed
            dw = (f(w, lv) - w).double()[:, :n]
            tot[bk][0] += float(((dw @ mu[:n]) ** 2).sum())
            tot[bk][1] += float(((dw * dw) @ v[:n]).sum())

    out = {"model": MDIR, "n_cal_windows": NCAL,
           "coh_MXFP4": tot["MXFP4"][0], "inc_MXFP4": tot["MXFP4"][1],
           "coh_TOP": tot["MX-asym-TOP"][0], "inc_TOP": tot["MX-asym-TOP"][1],
           "total_MXFP4": sum(tot["MXFP4"]), "total_TOP": sum(tot["MX-asym-TOP"]),
           "coherent_share_MXFP4": tot["MXFP4"][0] / sum(tot["MXFP4"]),
           "coherent_share_TOP": tot["MX-asym-TOP"][0] / sum(tot["MX-asym-TOP"]),
           "gated_ratio_TOP_over_MXFP4": sum(tot["MX-asym-TOP"]) / sum(tot["MXFP4"])}
    dst = os.path.join(HERE, f"lineD_actgate_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    for k, val in out.items():
        print(f"  {k:<32}{val}")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
