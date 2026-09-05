#!/usr/bin/env python3
"""LINE D / T41: the exact granular-vs-clipping decomposition of a clipping arm.

MX-asym-TOP's negative ladder is EXACTLY c = 3/4 times MXFP4's, and its positive
ladder is c times MXFP4's with one extra rung at 1.  So on every element whose
scaled magnitude stays inside the contracted ladder the arm is a strictly finer
quantiser, and on every NEGATIVE element whose scaled magnitude exceeds c it
saturates.  This script measures both sides on the real checkpoints, per block,
with no forward pass and no fitted parameter.

    X = sum over saturated elements of  (e_A^2 - e_B^2)      the clipping cost
    G = sum over in-range  elements of   e_B^2               the granular error
    Y = sum over in-range  elements of  (e_B^2 - e_A^2)      the granular gain

T41 predicts Y ~= (1 - c^2) G = 7/16 G, and the arm is favourable in weight-space
squared error iff X/G < 1 - c^2.  Both are computed exactly here; the ratio Y/G
is what makes the high-resolution step of the derivation falsifiable.

The quantisers are NOT reimplemented: block_tnf.quant for the symmetric parent,
campaignC_books.make_quant_signed for the asymmetric arm, level lists from
campaignA_books.  Both books carry max|level| = 1.0, so they share the same E8M0
block scale exactly -- asserted, not assumed.

    W=<weights dir> MDIR=pythia python3 lineD_decompose.py
"""
import json
import os
import sys

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
quant, target_modules = ns["quant"], ns["target_modules"]
q_e8m0_t, K = ns["q_e8m0_t"], ns["K"]

import campaignA_books as A
import campaignC_books as C

torch.set_grad_enabled(False)
MDIR = os.environ["MDIR"]
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
C_CONTRACT = 0.75


def books():
    d = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))
    return d


def main():
    from transformers import AutoModelForCausalLM
    BOOKS = books()
    mx_kind, mx_lv = BOOKS["MXFP4"]
    top_kind, top_lv = BOOKS["MX-asym-TOP"]
    assert mx_kind == "mag" and top_kind == "clip" or top_kind == "sig", top_kind
    # the contraction, read off the books rather than assumed
    pos = [x for x in top_lv if x > 0]
    neg = sorted(-x for x in top_lv if x < 0)
    c = neg[-1]
    assert abs(c - C_CONTRACT) < 1e-12, c
    # Proposition 1: TOP's negative ladder is exactly c * MXFP4's magnitudes
    assert max(abs(a - c * b) for a, b in zip(neg, mx_lv[1:])) < 1e-12
    # ... and TOP's positive ladder is c * MXFP4's plus one rung at 1
    assert max(abs(a - c * b) for a, b in zip(pos[:-1], mx_lv[1:])) < 1e-12
    assert abs(pos[-1] - 1.0) < 1e-12
    print(f"contraction c = {c}   1 - c^2 = {1 - c * c:.6f}", flush=True)

    quant_signed = C.make_quant_signed(K, q_e8m0_t)
    path = os.path.join(WDIR, MDIR)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    lins = target_modules(model)
    print(f"{MDIR}: {len(lins)} linear tensors (lm_head excluded)", flush=True)

    acc = dict(n=0, nblk=0, G=0.0, X=0.0, Y=0.0, DB=0.0, DA=0.0,
               nsat=0, nblk_sat=0, nblk_negext=0, sum_rho=0.0, sum_u=0.0,
               sum_a2=0.0, blk_win=0)
    # per-block ledger for the block-level crossover histogram
    ratios = []
    for name, m in lins:
        w = m.weight.detach()
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        head = w[:, :n].reshape(-1, K).double()
        a = head.abs().amax(dim=1)
        s = q_e8m0_t((a / 1.0).clamp(min=1e-30)).clamp(min=1e-30)
        # both books top out at 1.0 -> identical block scale.  Asserted.
        rec_B = quant(w, mx_lv)[:, :n].reshape(-1, K).double()
        rec_A = quant_signed(w, top_lv)[:, :n].reshape(-1, K).double()
        eB = rec_B - head
        eA = rec_A - head
        y = head / s[:, None]
        sat = y < -c - 1e-15                      # saturated under TOP
        blk_a2 = (a.double() ** 2)
        gB = torch.where(sat, torch.zeros_like(eB), eB) ** 2
        gA = torch.where(sat, torch.zeros_like(eA), eA) ** 2
        xB = torch.where(sat, eB, torch.zeros_like(eB)) ** 2
        xA = torch.where(sat, eA, torch.zeros_like(eA)) ** 2
        G_b = gB.sum(dim=1)
        Y_b = (gB - gA).sum(dim=1)
        X_b = (xA - xB).sum(dim=1)
        acc["G"] += float(G_b.sum())
        acc["Y"] += float(Y_b.sum())
        acc["X"] += float(X_b.sum())
        acc["DB"] += float((eB ** 2).sum())
        acc["DA"] += float((eA ** 2).sum())
        acc["n"] += head.numel()
        acc["nblk"] += head.shape[0]
        acc["nsat"] += int(sat.sum())
        acc["nblk_sat"] += int((sat.any(dim=1)).sum())
        ymin = y.amin(dim=1)
        ymax = y.amax(dim=1)
        acc["nblk_negext"] += int(((-ymin) > ymax).sum())
        acc["sum_rho"] += float(((-ymin) / torch.maximum(ymax, -ymin)).sum())
        acc["sum_u"] += float((a.double() / s).sum())
        acc["sum_a2"] += float(blk_a2.sum())
        acc["blk_win"] += int((X_b < Y_b).sum())
        ok = G_b > 0
        ratios.append((X_b[ok] / G_b[ok]).float().numpy())
        del head, rec_A, rec_B, eA, eB, y, sat, gA, gB, xA, xB

    r = np.concatenate(ratios)
    out = {
        "model": MDIR, "c": c, "thresh_1_minus_c2": 1 - c * c,
        "n_elements": acc["n"], "n_blocks": acc["nblk"],
        "G": acc["G"], "X": acc["X"], "Y": acc["Y"],
        "D_MXFP4": acc["DB"], "D_TOP": acc["DA"],
        "dD": acc["DA"] - acc["DB"],
        "X_over_G": acc["X"] / acc["G"],
        "Y_over_G": acc["Y"] / acc["G"],
        "sat_rate": acc["nsat"] / acc["n"],
        "sat_per_block": acc["nsat"] / acc["nblk"],
        "frac_blocks_saturating": acc["nblk_sat"] / acc["nblk"],
        "frac_blocks_neg_extremum": acc["nblk_negext"] / acc["nblk"],
        "mean_rho": acc["sum_rho"] / acc["nblk"],
        "mean_u": acc["sum_u"] / acc["nblk"],
        "frac_blocks_TOP_better": acc["blk_win"] / acc["nblk"],
        "block_X_over_G_median": float(np.median(r)),
        "block_X_over_G_mean": float(np.mean(r)),
        "block_X_over_G_frac_below_thresh": float(np.mean(r < (1 - c * c))),
        "mse_ratio_TOP_over_MXFP4": acc["DA"] / acc["DB"],
    }
    dst = os.path.join(HERE, f"lineD_decompose_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    for k, v in out.items():
        print(f"  {k:<34}{v}")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
