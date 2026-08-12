#!/usr/bin/env python3
"""Campaign D, step 2: the two WEIGHT-SPACE predictors, P1 and P2.

Campaign B measured five ways to spend the sixteenth codeword and got a 3.4
percentage-point spread at a fixed alphabet ratio.  The conjecture under test is
that the best place for the new level is the bin carrying the most distortion.
This computes, per model, over exactly the tensors the perplexity measurement
quantises (`target_modules`, K = 32, E8M0):

  P1   BIN MASS                 fraction of elements in the split bin
  P1b  CAPTURED MASS            fraction of elements the NEW level actually wins
  P2   MASS x WIDTH^2           the classical greedy Lloyd-Max criterion
  P2b  MEASURED SSE SHARE       the bin's real share of sum (y - level)^2

"The split bin" is defined once, uniformly: the new level p is inserted between
two existing signed levels; the split bin is the bin of the neighbour NEARER
ZERO.  That reproduces the anchor already in the record -- NEAR0 splits MXFP4's
zero bin -- and extends to all five without a special case.

Bins are SIGNED (15 of them), because MIDN differs from MID only by sign.  The
tie rule is the one `block_tnf.quant` implements: bucketize |y|, so a weight
exactly on a boundary rounds toward zero.  |y| <= 1 always, because E8M0 rounds
the scale UP; that is asserted, and it is what makes the top bin's width finite.
"""
import json
import math
import os
import sys
from fractions import Fraction as F

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
q_e8m0_t = ns["q_e8m0_t"]
K = ns["K"]
W = os.environ.get("WROOT", os.path.dirname(ns["MODEL"]))

import campaignB_books as B
import campaignC_books as C

torch.set_grad_enabled(False)

MX = [F(0)] + [F(u, 12) for u in B.MX_UNITS]          # 0, 1/12 ... 1
assert [float(x) for x in MX] == list(C.MXFP4)
MX_SIGNED = sorted(set([-x for x in MX[1:]] + [F(0)] + list(MX[1:])))
assert len(MX_SIGNED) == 15

# --- the five placements, as (new level, neighbour below, neighbour above) ---
u = [F(x) for x in B.MX_UNITS]
PLACE = {
    "NEAR0": u[0] / 2 / 12,                        # +1/24
    "MID":   (u[5] + u[6]) / 2 / 12,               # +10/12
    "MID2":  (u[3] + u[4]) / 2 / 12,               # +5/12
    "MIDN": -(u[5] + u[6]) / 2 / 12,               # -10/12
    "TOP":   F(16, 12),                            # +16/12, outside the ladder
}


def split_bin(p):
    """Signed level index of the bin the new level p splits: the neighbour
    NEARER ZERO.  Index 0 is the zero bin, +-k the bin of +-MX[k]."""
    below = max([x for x in MX_SIGNED if x < p], default=None)
    above = min([x for x in MX_SIGNED if x > p], default=None)
    if above is None:                              # TOP: nothing above
        near = below
    elif below is None:
        near = above
    else:
        near = below if abs(below) < abs(above) else above
    k = MX.index(abs(near))
    return 0 if k == 0 else (k if near > 0 else -k)


def bin_edges():
    """(lo, hi) of every signed bin in normalised units, |y| <= 1."""
    m = [float(x) for x in MX]
    e = {}
    e[0] = (-m[1] / 2, m[1] / 2)
    for k in range(1, 8):
        lo = (m[k - 1] + m[k]) / 2
        hi = 1.0 if k == 7 else (m[k] + m[k + 1]) / 2
        e[k] = (lo, hi)
        e[-k] = (-hi, -lo)
    return e


EDGES = bin_edges()
SPLIT = {name: split_bin(p) for name, p in PLACE.items()}


def signed_bins(y):
    """y: normalised block values.  Returns signed bin index per element,
    using the SAME tie rule as block_tnf.quant (bucketize on |y|)."""
    mag = torch.tensor([float(x) for x in MX], dtype=torch.float64)
    bnd = (mag[:-1] + mag[1:]) / 2
    k = torch.bucketize(y.abs(), bnd)               # 0..7
    return torch.where(k == 0, torch.zeros_like(k), k * torch.sign(y).to(k.dtype))


def normalised(model):
    """Yield (normalised block values y, block scale s) for every quantised
    tensor.  s is needed only for the s^2-weighted SSE robustness check: the
    codebook lives in y-space, but the error the model actually carries is
    s*(y - level), and the two need not rank the bins the same way."""
    for _, m in target_modules(model):
        w = m.weight.detach().double()
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        head = w[:, :n].reshape(-1, K)
        s = q_e8m0_t((head.abs().amax(dim=1) / 1.0).clamp(min=1e-30)).clamp(min=1e-30)
        yield head / s[:, None], s


def measure(model):
    mag = torch.tensor([float(x) for x in MX], dtype=torch.float64)
    cnt = np.zeros(15, dtype=np.int64)              # index = bin + 7
    sse = np.zeros(15, dtype=np.float64)
    ssw = np.zeros(15, dtype=np.float64)            # s^2-weighted: real weight space
    tot = 0
    ymax = 0.0
    for y, s in normalised(model):
        ymax = max(ymax, float(y.abs().max()))
        b = signed_bins(y)
        lev = mag[b.abs()] * torch.sign(b).to(y.dtype)
        e2 = (y - lev) ** 2
        idx = (b + 7).reshape(-1)
        cnt += np.bincount(idx.numpy(), minlength=15)
        sse += np.bincount(idx.numpy(), weights=e2.reshape(-1).numpy(), minlength=15)
        ssw += np.bincount(idx.numpy(),
                           weights=(e2 * s[:, None] ** 2).reshape(-1).numpy(),
                           minlength=15)
        tot += y.numel()
    assert ymax <= 1.0 + 1e-12, f"|y| exceeds 1: {ymax}"
    return cnt, sse, ssw, tot, ymax


def captured(model, name):
    """Fraction of elements the NEW level of `name` actually wins."""
    lv = B.mx_family()["MX-asym-" + name]
    lv_t = torch.tensor(sorted(float(x) for x in lv), dtype=torch.float64)
    # the new level, in the renormalised book
    base = set(round(float(x), 12) for x in
               [-y for y in MX[1:]] + [F(0)] + list(MX[1:]))
    if name == "TOP":                               # everything moved; new level is the max
        new = float(lv_t.max())
    else:
        cand = [float(x) for x in lv_t if round(float(x), 12) not in base]
        assert len(cand) == 1, (name, cand)
        new = cand[0]
    j = int(torch.argmin((lv_t - new).abs()))
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    hit = tot = 0
    for y, _ in normalised(model):
        i_lo = torch.bucketize(y, bnd, right=False)
        i_hi = torch.bucketize(y, bnd, right=True)
        idx = torch.where(y < 0, i_hi, i_lo)
        hit += int((idx == j).sum())
        tot += y.numel()
    return hit / tot, new


def main():
    from transformers import AutoModelForCausalLM
    mdir = os.environ.get("MDIR", "smollm2")
    path = os.path.join(W, mdir)
    print(f"model dir = {path}", flush=True)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()

    cnt, sse, ssw, tot, ymax = measure(model)
    mass = cnt / tot
    sse_share = sse / sse.sum()
    ssw_share = ssw / ssw.sum()
    print(f"\nelements quantised = {tot:,}   max|y| = {ymax:.6f}")
    print(f"\n{'bin':>5}{'level':>10}{'lo':>10}{'hi':>10}{'width':>9}"
          f"{'mass %':>9}{'m*w^2':>11}{'SSE %':>8}")
    for b in range(-7, 8):
        lo, hi = EDGES[b]
        wdt = hi - lo
        lv = float(MX[abs(b)]) * (1 if b >= 0 else -1)
        print(f"{b:>5}{lv:>10.5f}{lo:>10.5f}{hi:>10.5f}{wdt:>9.5f}"
              f"{100*mass[b+7]:>9.4f}{mass[b+7]*wdt**2:>11.3e}{100*sse_share[b+7]:>8.4f}")

    rows = {}
    print(f"\n{'placement':<8}{'new level':>11}{'split bin':>10}"
          f"{'P1 mass%':>10}{'P1b capt%':>11}{'P2 m*w^2':>11}{'P2b SSE%':>10}")
    for name in ["NEAR0", "MIDN", "MID", "MID2", "TOP"]:
        b = SPLIT[name]
        lo, hi = EDGES[b]
        wdt = hi - lo
        cap, new = captured(model, name)
        rows[name] = {"split_bin": b, "new_level": new,
                      "P1_mass": float(mass[b + 7]),
                      "P1b_captured": cap,
                      "P2_mass_w2": float(mass[b + 7] * wdt ** 2),
                      "P2b_sse_share": float(sse_share[b + 7]),
                      "P2c_sse_share_weighted": float(ssw_share[b + 7]),
                      "bin_width": wdt}
        print(f"{name:<8}{new:>11.5f}{b:>10}{100*mass[b+7]:>10.4f}{100*cap:>11.4f}"
              f"{mass[b+7]*wdt**2:>11.3e}{100*sse_share[b+7]:>10.4f}")

    out = {"model": mdir, "n_elements": tot, "max_abs_y": ymax,
           "bin_mass": mass.tolist(), "bin_sse_share": sse_share.tolist(),
           "bin_sse_share_weighted": ssw_share.tolist(),
           "bin_edges": {str(b): EDGES[b] for b in EDGES},
           "placements": rows}
    json.dump(out, open(os.path.join(HERE, f"campaignD_pred_{mdir}.json"), "w"), indent=1)
    print(f"\nwrote campaignD_pred_{mdir}.json")


if __name__ == "__main__":
    main()
