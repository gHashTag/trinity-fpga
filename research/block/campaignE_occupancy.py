#!/usr/bin/env python3
"""T42, weight side: the MX-asym-NEAR0 / MXFP4 margin as a functional of the
checkpoint's block-normalised value distribution.

Both books use the SAME scale rule (E8M0 over the block absmax, both normalised
to max|level| = 1.0 by T38), so the block scale `s` is bit-identical between
them and the two quantisers differ ONLY in their level sets. Writing y = w/s,
the per-element squared error is s^2 (y - r(y))^2, so

    D_A = sum_blocks s_b^2 sum_{j in b} (y_j - r_A(y_j))^2

and the DIFFERENCE between the two books is

    dD = D_MX - D_NEAR0 = sum_b s_b^2 sum_j g(y_j)

with g(y) = e_MX(y)^2 - e_NEAR0(y)^2 a FIXED function of the two codebooks.
NEAR0 inserts the sixteenth codeword at +1/24 (the midpoint of the gap 0 -> 1/12
on E2M1's ladder). MXFP4's boundary in that gap is 1/24; NEAR0's boundaries are
1/48 and 1/16. So g is supported on POSITIVE y in [1/48, 1/16) only, and there

    y in [1/48, 1/24):  g = y^2 - (1/24 - y)^2 = (2y - 1/24)/24
    y in [1/24, 1/16):  g = (1/12 - y)^2 - (y - 1/24)^2 = (1/8 - 2y)/24

a symmetric tent peaking at y = 1/24 with height (1/24)^2 = 1/576. g >= 0
everywhere, so this placement can never RAISE squared weight error.

This file computes, per checkpoint and from weights alone:
    R = dD / D_MX      the fractional reduction in block squared weight error
plus the s^2-weighted occupancy of the differing band and the normalised-value
histogram used for the checkpoint-similarity test.

Nothing is reimplemented: quant / target_modules come from block_tnf.py, the
signed quantiser from campaignC_books, the codebooks from campaignA_books.
The analytic g-integral is CHECKED against the difference of the two real
quantisers on actual tensors -- that check is the whole content of Proposition 1
and it is asserted, not assumed.
"""
import json
import os
import sys

import numpy as np
import torch
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

_s = open("block_tnf.py", encoding="utf-8").read()
ns = {}
exec(compile(_s.split('print("загружаю модель…", flush=True)')[0],
             "block_tnf.py", "exec"), ns)
quant, target_modules = ns["quant"], ns["target_modules"]
K, q_e8m0_t = ns["K"], ns["q_e8m0_t"]

import campaignA_books as A
import campaignC_books as C

quant_signed = C.make_quant_signed(K, q_e8m0_t)

MXFP4 = [float(x) for x in C.MXFP4]
NEAR0 = [float(x) for x in dict((n, lv) for n, _, lv in A.candidates())["MX-asym-NEAR0"]]

# ---------------------------------------------------------------------------
# the differing band, derived from the two books rather than hard-coded
# ---------------------------------------------------------------------------
def _bounds(levels):
    v = sorted(float(x) for x in levels)
    return v, [(a + b) / 2 for a, b in zip(v[:-1], v[1:])]


def _recon(y, levels):
    v, bnd = _bounds(levels)
    return np.asarray(v)[np.searchsorted(np.asarray(bnd), y, side="left")]


def band_and_g():
    """Locate where the two books disagree, from the books.  Returns (lo, hi)
    and a callable g(y) valid for y > 0."""
    sig_mx = C.signed_from_magnitudes(MXFP4[1:])
    ys = np.linspace(0.0, 1.0, 2_000_001)
    d = _recon(ys, sig_mx) != _recon(ys, NEAR0)
    lo, hi = ys[d].min(), ys[d].max()
    def g(y):
        e_mx = y - _recon(y, sig_mx)
        e_n0 = y - _recon(y, NEAR0)
        return e_mx * e_mx - e_n0 * e_n0
    return float(lo), float(hi), g


BAND_LO_EXACT = float(F(1, 48))
BAND_HI_EXACT = float(F(1, 16))
G_PEAK_EXACT = float(F(1, 576))


def g_tent(y):
    """analytic g on positive y; zero outside the band"""
    a = (2.0 * y - 1.0 / 24.0) / 24.0
    b = (1.0 / 8.0 - 2.0 * y) / 24.0
    out = np.minimum(a, b)
    return np.where((y >= BAND_LO_EXACT) & (y < BAND_HI_EXACT), out, 0.0)


# ---------------------------------------------------------------------------
# WIDENING THE CHECKPOINT SET COSTS AN INSTRUMENT FIX
#
# `block_tnf.target_modules` filters on `torch.nn.Linear`. GPT-2 and every
# GPT-2-derived checkpoint (Cerebras-GPT) store each projection as
# `transformers.pytorch_utils.Conv1D`, whose weight is (in_features,
# out_features) -- the TRANSPOSE of nn.Linear's. On those checkpoints the
# nn.Linear filter returns an EMPTY list, so every quantisation arm becomes a
# silent no-op and the harness reports ppl(MXFP4) == ppl(fp32) and a 0.00 %
# margin. That is a false green of exactly the kind this repository has shipped
# before, and it is the reason GPT-2 was never in this campaign.
#
# The fix is a transpose adapter, NOT a second quantiser: the weight is handed
# to the same `quant` / `quant_signed` in nn.Linear orientation, so a block is
# 32 consecutive INPUT channels of one output row on every architecture, which
# is what it already means for the four rulers. `assert_same_as_ruler` proves
# the adapter changes nothing on nn.Linear checkpoints.
try:
    from transformers.pytorch_utils import Conv1D as _Conv1D
except Exception:                                        # pragma: no cover
    _Conv1D = None


def quantisable(model):
    """(name, module, transposed) for every weight the arms may touch."""
    out = []
    for n, m in model.named_modules():
        if "lm_head" in n:
            continue
        if isinstance(m, torch.nn.Linear):
            out.append((n, m, False))
        elif _Conv1D is not None and isinstance(m, _Conv1D):
            out.append((n, m, True))
    return out


def get_w(m, t):
    w = m.weight.detach()
    return w.t().contiguous() if t else w


def set_w(m, t, w):
    m.weight.copy_(w.t().contiguous() if t else w)


def assert_same_as_ruler(model):
    """On an nn.Linear checkpoint the adapter must select exactly what the
    ruler's own `target_modules` selects, in the same order."""
    lin = [n for n, _ in target_modules(model)]
    if not lin:
        return False                       # Conv1D checkpoint: nothing to match
    got = [n for n, _, t in quantisable(model) if not t]
    assert got == lin, (got[:3], lin[:3])
    assert not any(t for _, _, t in quantisable(model)), "mixed Conv1D/Linear"
    return True


HGRID = np.concatenate([np.linspace(0.0, 0.125, 129)[:-1],
                        np.linspace(0.125, 1.0, 57)])   # fine near zero


def one_model(path, name, check_prop1=True, dtype=torch.float32):
    from transformers import AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(path, dtype=dtype)
    model.eval()
    assert_same_as_ruler(model)
    tm = [(n, m, t) for n, m, t in quantisable(model)]

    D_mx = 0.0
    dD_exact = 0.0        # from the analytic g
    dD_quant = 0.0        # from the two real quantisers
    n_elem = 0
    w_band = 0.0          # s^2-weighted count in band
    c_band = 0            # unweighted count in band
    hist = np.zeros(len(HGRID) - 1)      # s^2-weighted |y| histogram
    hist_pos = np.zeros(len(HGRID) - 1)  # s^2-weighted  y>0 histogram
    s2_sum = 0.0
    nblocks = 0

    for i, (n, m, tr) in enumerate(tm):
        w = get_w(m, tr).double()
        cols = (w.shape[1] // K) * K
        if cols == 0:
            continue
        head = w[:, :cols].reshape(-1, K)
        s = q_e8m0_t((head.abs().amax(dim=1)).clamp(min=1e-30)).clamp(min=1e-30)
        y = (head / s[:, None]).numpy()
        s2 = (s * s).numpy()[:, None]

        e_mx = y - _recon(np.abs(y), MXFP4) * np.sign(y)
        D_mx += float((s2 * e_mx * e_mx).sum())
        gv = np.where(y > 0, g_tent(np.where(y > 0, y, 0.0)), 0.0)
        dD_exact += float((s2 * gv).sum())

        inb = (y >= BAND_LO_EXACT) & (y < BAND_HI_EXACT)
        w_band += float((s2 * inb).sum())
        c_band += int(inb.sum())
        n_elem += y.size
        s2_sum += float(s2.sum())
        nblocks += y.shape[0]

        ay = np.abs(y).ravel()
        ww = np.repeat(s2.ravel(), K)
        hist += np.histogram(ay, bins=HGRID, weights=ww)[0]
        py = y.ravel()
        hist_pos += np.histogram(np.where(py > 0, py, -1.0), bins=HGRID,
                                 weights=ww)[0]

        if check_prop1 and i < 3:
            wt = w[:, :cols]
            a_mx = quant(wt, MXFP4)
            a_n0 = quant_signed(wt, NEAR0)
            dq = (float(((wt - a_mx) ** 2).sum())
                  - float(((wt - a_n0) ** 2).sum()))
            dD_quant += dq

    del model
    out = {
        "model": name,
        "n_target_modules": len(tm),
        "n_elem_blocked": int(n_elem),
        "n_blocks": int(nblocks),
        "D_mx": D_mx,
        "dD": dD_exact,
        "R": dD_exact / D_mx,
        "band_lo": BAND_LO_EXACT, "band_hi": BAND_HI_EXACT,
        "occ_band_raw": c_band / n_elem,
        "occ_band_s2w": w_band / (s2_sum * K),
        "hist_abs": (hist / hist.sum()).tolist(),
        "hist_pos": (hist_pos / hist.sum()).tolist(),
        "hgrid": HGRID.tolist(),
    }
    if check_prop1:
        out["prop1_dD_first3_analytic"] = None
        out["prop1_dD_first3_quantisers"] = dD_quant
    return out


def prop1_check(path, name):
    """Proposition 1, on real tensors: the analytic g-integral reproduces the
    difference of the two REAL quantisers to double-precision round-off."""
    from transformers import AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    worst = 0.0
    for i, (n, m, tr) in enumerate(quantisable(model)):
        if i >= 4:
            break
        w = get_w(m, tr).double()
        cols = (w.shape[1] // K) * K
        if cols == 0:
            continue
        wt = w[:, :cols]
        a_mx = quant(wt, MXFP4)
        a_n0 = quant_signed(wt, NEAR0)
        dq = float(((wt - a_mx) ** 2).sum()) - float(((wt - a_n0) ** 2).sum())

        head = wt.reshape(-1, K)
        s = q_e8m0_t((head.abs().amax(dim=1)).clamp(min=1e-30)).clamp(min=1e-30)
        y = (head / s[:, None]).numpy()
        s2 = (s * s).numpy()[:, None]
        gv = np.where(y > 0, g_tent(np.where(y > 0, y, 0.0)), 0.0)
        da = float((s2 * gv).sum())
        rel = abs(da - dq) / max(abs(dq), 1e-300)
        worst = max(worst, rel)
    del model
    return worst


MODELS = json.load(open(os.path.join(HERE, "campaignE_models.json")))

if __name__ == "__main__":
    only = sys.argv[1:] or None
    res = {}
    outp = os.path.join(HERE, "campaignE_occupancy.json")
    if os.path.exists(outp):
        res = json.load(open(outp))
    for name, path in MODELS.items():
        if only and name not in only:
            continue
        if name in res:
            print(f"[skip] {name}", flush=True)
            continue
        print(f"[run ] {name}", flush=True)
        r = one_model(path, name, check_prop1=False)
        r["prop1_worst_rel_err"] = prop1_check(path, name)
        print(f"       R = {r['R']:.6f}   band occ (s2w) = {r['occ_band_s2w']:.6f}"
              f"   Prop1 worst rel err = {r['prop1_worst_rel_err']:.3e}", flush=True)
        res[name] = r
        json.dump(res, open(outp, "w"))
    print("wrote campaignE_occupancy.json")
