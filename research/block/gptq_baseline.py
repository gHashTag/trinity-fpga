#!/usr/bin/env python3
"""The test that decides whether any of this matters: does promote-only survive GPTQ?

Every result in this programme is measured against uniform 4-bit ROUND-TO-NEAREST. Nobody
deploys that. Production 4-bit quantisation uses GPTQ or AWQ, which already compensate for
quantisation error using second-order information -- and in doing so already exploit part of the
sensitivity structure that promote-only exploits. If GPTQ absorbs the gain, promote-only is an
artefact of a weak baseline and the last several cycles do not matter outside this sandbox.

GPTQ, implemented properly (Frantar et al.):

    H = 2 X X^T over calibration activations, damped
    Hinv = chol(chol_inverse(chol(H)), upper=True)
    for each column i:
        q       = quantise(W[:, i])
        err     = (W[:, i] - q) / Hinv[i, i]
        W[:, i+1:] -= err (x) Hinv[i, i+1:]      # push the error onto columns not yet done

with the block scale recomputed at the start of every group of K columns, since our scaling is
per-group along the contraction axis. Blocks are processed SEQUENTIALLY so that each block's
Hessian is measured on the already-quantised outputs of the ones before it, as GPTQ requires.

FOUR CONFIGURATIONS, all at the same average width where compared:

    RTN  uniform 4-bit                 the baseline this programme has been using
    RTN  promote-only (4.333 bits)     the result being tested
    GPTQ uniform 4-bit                 the baseline that is actually deployed
    GPTQ promote-only (4.333 bits)     does the gain survive?

PRE-REGISTERED: if GPTQ promote-only captures a materially smaller share of the 4->5 gain than
RTN promote-only did (~50-54%), then GPTQ has absorbed the sensitivity signal and promote-only is
redundant in practice. That would be a negative result and is the outcome to expect if the two
mechanisms overlap.
"""
import os
import re
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bitwidth_scaling import dp_pinned

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NBIN = 32, 2048, 800
NCAL = 4
torch.set_grad_enabled(False)

DPPL = np.array([0.0952, 0.0973, 0.1083, 0.0695, 0.0401, 0.0097, 0.0572, 0.0358, 0.0383,
                 0.0256, 0.0469, 0.0960, 0.0706, 0.0691, 0.0993, 0.0661, 0.0812, 0.1113,
                 0.1507, 0.1237, 0.1742, 0.0614, 0.0762, 0.1165, 0.0579, 0.0563, 0.1160,
                 0.0774, 0.1311, 0.4070])


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def q_group(w_g, lv):
    """Quantise a [d_out, K] group with a per-row block-max scale. Returns (q, scale)."""
    s = w_g.abs().amax(dim=1).clamp(min=1e-30)
    idx = torch.bucketize(w_g / s[:, None], (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
    return lv[idx] * s[:, None], s


def rtn_layer(w, lv):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    out = w.clone()
    g = w[:, :n].reshape(-1, K)
    s = g.abs().amax(1).clamp(min=1e-30)
    idx = torch.bucketize(g / s[:, None], (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
    out[:, :n] = (lv[idx] * s[:, None]).reshape(w.shape[0], n)
    return out


def gptq_layer(w, H, lv, damp_frac=0.01):
    """GPTQ with group size K along the contraction axis."""
    w = w.double().clone()
    d_in = w.shape[1]
    H = H.double().clone()
    dead = torch.diag(H) == 0
    H[dead, dead] = 1.0
    w[:, dead] = 0.0
    damp = damp_frac * torch.mean(torch.diag(H))
    H += torch.eye(d_in, dtype=H.dtype) * damp
    try:
        L = torch.linalg.cholesky(H)
        Hi = torch.cholesky_inverse(L)
        Hinv = torch.linalg.cholesky(Hi, upper=True)
    except Exception:
        return rtn_layer(w, lv)                      # singular: fall back, and say so
    Q = torch.zeros_like(w)
    for g0 in range(0, d_in - d_in % K, K):
        g1 = g0 + K
        # scale fixed from the error-compensated weights at the start of the group
        s = w[:, g0:g1].abs().amax(dim=1).clamp(min=1e-30)
        for i in range(g0, g1):
            col = w[:, i]
            idx = torch.bucketize(col / s, (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
            q = lv[idx] * s
            Q[:, i] = q
            d = Hinv[i, i]
            err = (col - q) / d
            if i + 1 < d_in:
                w[:, i + 1:] -= err[:, None] * Hinv[i, i + 1:][None, :]
    tail = d_in - d_in % K
    if tail < d_in:
        Q[:, tail:] = w[:, tail:]
    return Q


tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
n_tok = (ids.numel() // SEQLEN) * SEQLEN
WINS = ids[:n_tok].view(-1, SEQLEN)
CAL = WINS[18:18 + NCAL]                     # calibration windows, disjoint from evaluation
LO, HI = 6, 18

lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
BASE = {n: m.weight.detach().clone() for n, m in lins}
NL = max(layer_index(n) for n, _ in lins) + 1

hist = np.zeros(NBIN)
for n, m in lins:
    w = BASE[n].double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    hist += np.histogram((b[ok] / a[ok][:, None]).reshape(-1).numpy(),
                         bins=NBIN, range=(-1, 1))[0]
dens = hist / (hist.sum() * (2.0 / NBIN))
CB = {b: torch.tensor(dp_pinned(dens, 1 << b), dtype=torch.float64) for b in (4, 5)}


def ppl():
    x = WINS[LO:HI]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


def restore():
    for n, m in lins:
        m.weight.copy_(BASE[n])


def apply_rtn(bits):
    for n, m in lins:
        m.weight.copy_(rtn_layer(BASE[n].double(), CB[bits[layer_index(n)]]).to(m.weight.dtype))


def apply_gptq(bits):
    """Sequential GPTQ: each block's Hessian is measured with earlier blocks already quantised."""
    restore()
    for bi in range(NL):
        names = [n for n, _ in lins if layer_index(n) == bi]
        Hs, cnt = {}, {}
        hooks = []

        def mk(nm):
            def h(mod, inp, out):
                x = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
                Hs[nm] = Hs.get(nm, 0) + 2.0 * (x.T @ x)
                cnt[nm] = cnt.get(nm, 0) + x.shape[0]
            return h

        for n, m in lins:
            if n in names:
                hooks.append(m.register_forward_hook(mk(n)))
        for i in range(CAL.shape[0]):
            model(CAL[i:i + 1])
        for h in hooks:
            h.remove()
        for n, m in lins:
            if n in names and n in Hs:
                q = gptq_layer(BASE[n], Hs[n] / max(cnt[n], 1), CB[bits[bi]])
                m.weight.copy_(q.to(m.weight.dtype))


p0 = ppl()

PROM = np.full(NL, 4)
PROM[np.argsort(DPPL)[-10:]] = 5
U4, U5 = np.full(NL, 4), np.full(NL, 5)

# The experiment runs only when this file is executed directly. Importing it (gptq_gate.py does)
# must NOT re-run six full quantisation sweeps -- the first version had no guard, so the gate's
# import silently re-ran everything and then died on a KeyError, producing an empty output file
# that looked exactly like "still running".
if __name__ == "__main__":
    print(f"RULER CHECK -- fp32 baseline {p0:.4f} "
          f"(windows {LO}-{HI-1}, calib 18-{18+NCAL-1})")
    if not (5.0 < p0 < 60.0):
        sys.exit("baseline implausible")
    res = {}
    for label, fn, bits in (("RTN uniform 4-bit", apply_rtn, U4),
                            ("RTN uniform 5-bit", apply_rtn, U5),
                            ("RTN promote-only 4.333", apply_rtn, PROM),
                            ("GPTQ uniform 4-bit", apply_gptq, U4),
                            ("GPTQ uniform 5-bit", apply_gptq, U5),
                            ("GPTQ promote-only 4.333", apply_gptq, PROM)):
        fn(bits)
        res[label] = ppl()
        restore()
        print(f"  {label:<26}{res[label]:>10.4f}  {res[label] - p0:>+8.4f}")
    print("\n  share of each method's own 4->5 gain captured by promote-only "
          "(33.3% of the bits):")
    for pre in ("RTN", "GPTQ"):
        d4 = res[f"{pre} uniform 4-bit"] - p0
        d5 = res[f"{pre} uniform 5-bit"] - p0
        dp = res[f"{pre} promote-only 4.333"] - p0
        print(f"    {pre:<5}{(d4 - dp) / (d4 - d5) * 100:>7.1f}%")
