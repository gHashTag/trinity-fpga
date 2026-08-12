#!/usr/bin/env python3
"""Independent re-measurement of the block-axis PERPLEXITY claim.

Companion to verify_block_rmse.py, and written for the same reason: the
published perplexity figures came from a run whose working directory no longer
exists, so the number the stop-rule turns on has exactly one witness. The RMSE
half now has two. This supplies the second for the half that matters more.

Written from the protocol, not from the original script: quantise every linear
weight, blocks along the contraction axis, scales in the same 8-bit field,
embeddings / norms / lm_head left alone, wikitext-2 test at SEQLEN 2048.

ARMS
  fp32          no quantisation -- the ruler. If this is not sane for the model,
                nothing downstream means anything and we refuse to report.
  mxfp4_floor   MXFP4 Algorithm 1: scale = 2^(floor(log2 amax) - emax).
  mxfp4_argmin  same E8M0 ladder, scale chosen by argmin of block squared error.
                Emits a byte-legal MXFP4 stream -- this is the BASELINE'S OWN
                best, and the honest thing to compare a new format against.
  step3         scale from 2^(k/3) -- five trits, ours.
  step8         scale from 2^(k/8) -- plain binary, the RMSE winner.

The floor-vs-argmin split is the whole point. A gain measured against the floor
credits our format for fixing the baseline's encoder; a gain measured against
argmin is what the algebra actually bought.
"""
import glob
import math
import os
import sys

import numpy as np
import torch

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32
SEQLEN = 2048
EMAX = 2                      # E2M1's largest magnitude is 6 = 1.5 * 2^2
E2M1 = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0])
torch.set_grad_enabled(False)


def quant_elem(U):
    """Round |U| to the E2M1 magnitude grid, keeping sign. Midpoint boundaries."""
    A = np.abs(U)
    bnd = (E2M1[:-1] + E2M1[1:]) / 2.0
    idx = np.searchsorted(bnd, A)
    return np.sign(U) * E2M1[idx]


def quantise(A, mode, N=None):
    """A is [out, in] float64. Blocks run along the contraction axis."""
    out, inn = A.shape
    nb = inn // K
    if nb == 0:
        return A
    head, tail = A[:, : nb * K], A[:, nb * K:]
    V = head.reshape(-1, K)
    amax = np.abs(V).max(axis=1)
    live = amax > 0
    Q = np.zeros_like(V)
    Vl, al = V[live], amax[live]

    if mode == "floor":
        X = 2.0 ** (np.floor(np.log2(al)) - EMAX)
        Q[live] = quant_elem(Vl / X[:, None]) * X[:, None]
    else:
        step = 1.0 if mode == "argmin2" else 1.0 / N
        base = np.floor((np.log2(al) - EMAX) / step)
        # Bracket spans the same octave range for every ladder. The first
        # version of the RMSE verifier used a fixed number of STEPS, which is a
        # narrower octave search for a finer ladder, and it reversed the
        # published ordering. Audited there: the argmin is strictly interior and
        # widening to +-3 octaves reproduces every figure bit for bit.
        span = max(2, int(round(1.0 / step)) + 1)
        best_e = None
        best_q = None
        for d in range(-span, span + 1):
            X = 2.0 ** ((base + d) * step)
            q = quant_elem(Vl / X[:, None]) * X[:, None]
            e = ((q - Vl) ** 2).sum(axis=1)
            if best_e is None:
                best_e, best_q = e, q
            else:
                m = e < best_e
                best_e = np.where(m, e, best_e)
                best_q = np.where(m[:, None], q, best_q)
        Q[live] = best_q

    return np.concatenate([Q.reshape(out, nb * K), tail], axis=1)


def load_text(tok):
    import pyarrow.parquet as pq
    tbl = pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
    col = "text" if "text" in tbl.column_names else tbl.column_names[0]
    txt = [s for s in tbl.column(col).to_pylist() if s is not None]
    return tok("\n\n".join(txt), return_tensors="pt").input_ids


def perplexity(model, ids):
    n = ids.shape[1] // SEQLEN
    tot, cnt = 0.0, 0
    for i in range(n):
        chunk = ids[:, i * SEQLEN:(i + 1) * SEQLEN]
        out = model(chunk, labels=chunk)
        tot += out.loss.float().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return math.exp(tot / cnt)


def targets(model):
    """Every linear weight except the tied head and the embeddings."""
    out = []
    for name, mod in model.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in name:
            out.append((name, mod))
    return out


ARMS = [("mxfp4_floor", "floor", None), ("mxfp4_argmin", "argmin2", None),
        ("step3", "step", 3), ("step8", "step", 8)]

# A 135M model on wikitext-2 sits in the low twenties; a 0.5B model in the
# mid-teens. Outside this band the ruler is broken and comparisons are void.
SANE = (5.0, 60.0)

MODELS = sys.argv[1:] or ["smollm2", "qwen"]
for name in [m for m in MODELS if os.path.isdir(os.path.join(W, m))]:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, name)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.float32)
    model.eval()
    ids = load_text(tok)
    print(f"\n  {name}: {ids.shape[1] // SEQLEN} окон по {SEQLEN}")

    orig = {n: m.weight.data.clone() for n, m in targets(model)}
    base = perplexity(model, ids)
    if not (SANE[0] <= base <= SANE[1]):
        print(f"    ❗ ЛИНЕЙКА СЛОМАНА: fp32 ppl = {base:.4f} вне {SANE}. Отказ.")
        continue
    print(f"    fp32 (линейка)   ppl {base:9.4f}")

    res = {}
    for arm, mode, N in ARMS:
        for n, m in targets(model):
            A = orig[n].numpy().astype(np.float64)
            m.weight.data = torch.from_numpy(quantise(A, mode, N)).float()
        res[arm] = perplexity(model, ids)
        print(f"    {arm:14s} ppl {res[arm]:9.4f}", flush=True)
    for n, m in targets(model):
        m.weight.data = orig[n]

    fl, am = res["mxfp4_floor"], res["mxfp4_argmin"]
    print(f"    --- против пола / против argmin (лучший кодировщик с обеих сторон) ---")
    for arm in ("mxfp4_argmin", "step3", "step8"):
        print(f"    {arm:14s} {(1 - res[arm] / fl) * 100:+7.2f}% "
              f"{(1 - res[arm] / am) * 100:+7.2f}%")
    del model
