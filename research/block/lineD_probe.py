#!/usr/bin/env python3
"""LINE D probes for T41's corollaries, all from weights, no forward pass.

(1) SCALE-INVARIANCE COROLLARY.  T41's Proposition 1 says the clipping arm is
    the parent book applied to data dilated by 1/c, with errors shrunk by c:
    e_A(y) = c * e_B(y/c).  Therefore the granular gain is
        1 - c^2 * (h(|y|/c) / h(|y|))^2
    per element, where h is the parent ladder's local step.  On a UNIFORM ladder
    h is constant and the gain is exactly 1 - c^2 = 7/16.  On a SCALE-INVARIANT
    (pure float) ladder h(z) is proportional to z, the ratio is 1/c, and the gain
    is exactly ZERO.  E2M1 is uniform below 4/12 and float above it, so the
    prediction is that essentially all of the granular gain comes from below
    4/12 and that the aggregate gain is far under 7/16.  Both are checked here,
    the second against a closed-form prediction that uses only the ladder and the
    measured |y| histogram -- nothing fitted.

(2) WHERE THE CLIPPING COST SITS.  X is split into the block's own extremum
    (the element that set the scale) and the other saturated elements.

(3) COHERENCE.  Squared weight error is blind to the SIGN of the error.  The
    clipping arm's error on a saturated element is always the same sign -- the
    reconstruction is pulled toward zero -- so it is a systematic shrinkage,
    while granular error is near zero-mean.  For an input with a common-mode
    component the output error of a row is
        E[(sum_j dw_j x_j)^2] = m^2 (sum_j dw_j)^2 + v sum_j dw_j^2,
    so the row-sum of the weight error is a second, independent channel that
    squared error does not see.  Measured here as
        COH = sum_rows (sum_j dw_rj)^2      and      kappa = COH / sum dw^2,
    kappa ~ 1 for incoherent error and ~ n_in for perfectly coherent error.

    W=<weights dir> MDIR=pythia python3 lineD_probe.py
"""
import json
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"), ns)
quant, target_modules = ns["quant"], ns["target_modules"]
q_e8m0_t, K = ns["q_e8m0_t"], ns["K"]

import campaignA_books as A
import campaignC_books as C

torch.set_grad_enabled(False)
MDIR = os.environ["MDIR"]
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
UNIFORM_TOP = 4.0 / 12.0        # E2M1's ladder is uniform (step 1/12) below this


def step_fn(L):
    """Local step h(z) of a magnitude ladder, as a torch lookup."""
    Lt = torch.tensor(L, dtype=torch.float64)
    h = Lt[1:] - Lt[:-1]

    def h_of(z):
        i = torch.bucketize(z, Lt[1:-1], right=True)   # index into h
        return h[i.clamp(max=len(h) - 1)]
    return h_of


def main():
    from transformers import AutoModelForCausalLM
    BOOKS = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))
    mx_lv = BOOKS["MXFP4"][1]
    top_lv = BOOKS["MX-asym-TOP"][1]
    c = max(-x for x in top_lv)
    h_of = step_fn(mx_lv)
    quant_signed = C.make_quant_signed(K, q_e8m0_t)

    model = AutoModelForCausalLM.from_pretrained(os.path.join(WDIR, MDIR),
                                                 dtype=torch.float32)
    model.eval()
    lins = target_modules(model)

    a = dict(G=0.0, Y=0.0, Y_unif=0.0, G_unif=0.0, Y_pred=0.0,
             X=0.0, X_ext=0.0, X_rest=0.0, n_ext_sat=0, n_rest_sat=0,
             X_above_beta=0.0, X_below_beta=0.0, n_above_beta=0,
             nblk_exposed=0, nblk=0, nelem=0, nblk_u_above_beta=0,
             cohA=0.0, cohB=0.0, sqA=0.0, sqB=0.0, rows=0, sum_nin=0)
    for name, m in lins:
        w = m.weight.detach()
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        head = w[:, :n].reshape(-1, K).double()
        amax = head.abs().amax(dim=1)
        s = q_e8m0_t((amax / 1.0).clamp(min=1e-30)).clamp(min=1e-30)
        eB = quant(w, mx_lv)[:, :n].reshape(-1, K).double() - head
        eA = quant_signed(w, top_lv)[:, :n].reshape(-1, K).double() - head
        y = head / s[:, None]
        ay = y.abs()
        sat = y < -c - 1e-15
        inr = ~sat

        # (1) granular gain, split by ladder region, plus the closed-form
        epsB = torch.where(inr, eB, torch.zeros_like(eB)) ** 2
        gain = epsB - torch.where(inr, eA, torch.zeros_like(eA)) ** 2
        a["G"] += float(epsB.sum())
        a["Y"] += float(gain.sum())
        unif = inr & (ay <= UNIFORM_TOP)
        a["G_unif"] += float(torch.where(unif, epsB, torch.zeros_like(epsB)).sum())
        a["Y_unif"] += float(torch.where(unif, gain, torch.zeros_like(gain)).sum())
        ratio = h_of(ay / c) / h_of(ay)
        gpred = (1.0 - c * c * ratio * ratio) * epsB
        a["Y_pred"] += float(gpred.sum())

        # (2) clipping cost, extremum vs the rest, and split at the derived
        #     break-even magnitude beta = (1 + c) / 2 -- above beta saturating
        #     costs more than the parent's own rounding, below it costs less.
        is_ext = ay >= (amax / s)[:, None] - 1e-15
        dx = (torch.where(sat, eA, torch.zeros_like(eA)) ** 2
              - torch.where(sat, eB, torch.zeros_like(eB)) ** 2)
        z = torch.zeros_like(dx)
        beta = (1.0 + c) / 2.0
        above = sat & (ay > beta)
        a["X"] += float(dx.sum())
        a["X_ext"] += float(torch.where(sat & is_ext, dx, z).sum())
        a["X_rest"] += float(torch.where(sat & ~is_ext, dx, z).sum())
        a["X_above_beta"] += float(torch.where(above, dx, z).sum())
        a["X_below_beta"] += float(torch.where(sat & ~above, dx, z).sum())
        a["n_ext_sat"] += int((sat & is_ext).sum())
        a["n_rest_sat"] += int((sat & ~is_ext).sum())
        a["n_above_beta"] += int(above.sum())
        a["nblk_exposed"] += int(above.any(dim=1).sum())
        # T38 phase gate: a block can expose anything above beta only if its
        # headroom u = a/s exceeds beta.  Log-uniform phase predicts -log2(beta).
        a["nblk_u_above_beta"] += int(((amax / s) > beta).sum())
        a["nblk"] += head.shape[0]
        a["nelem"] += head.numel()

        # (3) coherence, on the full rows of the ORIGINAL matrix
        dB = (quant(w, mx_lv) - w)[:, :n].double()
        dA = (quant_signed(w, top_lv) - w)[:, :n].double()
        a["cohB"] += float((dB.sum(dim=1) ** 2).sum())
        a["cohA"] += float((dA.sum(dim=1) ** 2).sum())
        a["sqB"] += float((dB ** 2).sum())
        a["sqA"] += float((dA ** 2).sum())
        a["rows"] += dB.shape[0]
        a["sum_nin"] += dB.shape[0] * n
        del head, eA, eB, y, ay, sat, inr, epsB, gain, dA, dB

    nbar = a["sum_nin"] / a["rows"]
    out = {
        "model": MDIR, "c": c, "one_minus_c2": 1 - c * c,
        "Y_over_G": a["Y"] / a["G"],
        "Y_over_G_predicted_from_ladder": a["Y_pred"] / a["G"],
        "share_of_gain_from_uniform_region": a["Y_unif"] / a["Y"],
        "share_of_granular_error_in_uniform_region": a["G_unif"] / a["G"],
        "beta_break_even": (1.0 + c) / 2.0,
        "X": a["X"], "X_extremum": a["X_ext"], "X_other": a["X_rest"],
        "X_above_beta": a["X_above_beta"], "X_below_beta": a["X_below_beta"],
        "n_sat_extremum": a["n_ext_sat"], "n_sat_other": a["n_rest_sat"],
        "exposure_rate_elements": a["n_above_beta"] / a["nelem"],
        "exposure_rate_blocks": a["nblk_exposed"] / a["nblk"],
        "frac_blocks_u_above_beta": a["nblk_u_above_beta"] / a["nblk"],
        "loguniform_prediction_u_above_beta": -__import__("math").log2((1.0 + c) / 2.0),
        "coh_MXFP4": a["cohB"], "coh_TOP": a["cohA"],
        "sq_MXFP4": a["sqB"], "sq_TOP": a["sqA"],
        "kappa_MXFP4": a["cohB"] / a["sqB"], "kappa_TOP": a["cohA"] / a["sqA"],
        "coh_ratio_TOP_over_MXFP4": a["cohA"] / a["cohB"],
        "sq_ratio_TOP_over_MXFP4": a["sqA"] / a["sqB"],
        "mean_n_in": nbar, "rows": a["rows"],
    }
    dst = os.path.join(HERE, f"lineD_probe_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    for k, v in out.items():
        print(f"  {k:<44}{v}")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
