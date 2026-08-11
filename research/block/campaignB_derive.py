#!/usr/bin/env python3
"""Derive the two learned-codebook baselines nobody has run here: NF4 and BOF4.

NF4  -- QLoRA's 4-bit NormalFloat. Derived here from scipy's normal quantile
        function following bitsandbytes' create_normal_map (offset 0.9677083,
        use_extra_value=True, i.e. the asymmetric 16-level variant that the
        bitsandbytes CUDA kernel actually hard-codes), then CHECKED against the
        published table. Both are printed so the reader can see they agree.

BOF4 -- "Block-wise Optimal Float", arXiv:2505.06653 (Blumenberg, Graave,
        Fingscheidt). The paper publishes a METHOD -- an EM algorithm based on
        Lloyd's -- and, in its Appendix C, also publishes codebooks. Table 7
        gives BOF4-S (MSE) at block size I=32, which is exactly our K. So we
        have both their artefact and their method.

        Their method, implemented here (their eq. (6), Monte-Carlo form):
            E-step: assign normalised weights x = w / w_b^max to the Voronoi
                    region of the current levels (midpoint boundaries).
            M-step: xhat(l) = sum_{k in R_l} w_k^2 x_k / sum_{k in R_l} w_k^2
                    where w_k is the block maximum of x_k's block. The w_k^2
                    weighting is what makes this minimise the error of the
                    UNNORMALISED weights, which is BOF4's whole point.
            Fixed levels are initialised and never recomputed:
                    BOF4   {-1, 0, +1}    BOF4-S {0, +1}
        BOF4-S replaces the absolute block maximum with the SIGNED one (their
        eq. (4)), so only the right endpoint needs pinning.

        The implementation is validated by re-deriving their Gaussian Table-7
        I=32 column before it is pointed at any model.

Outputs campaignB_codebooks.json. No perplexity is measured here.
"""
import json
import math
import os
import sys

import numpy as np
import torch
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
K = 32
NBLK = 1 << 20          # 1,048,576 blocks x 32 = 2^25 samples, the paper's count
SEED = 0

torch.set_grad_enabled(False)

# ---------------------------------------------------------------- NF4 --------
# bitsandbytes' hard-coded NF4 table (functional.py / dDequantizeNF4 kernel).
NF4_PUBLISHED = sorted([
    -1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
    -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
    0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
    0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
    0.7229568362236023, 1.0])


def derive_nf4(offset=0.9677083):
    """bitsandbytes create_normal_map(use_extra_value=True), 16 levels."""
    v1 = norm.ppf(np.linspace(offset, 0.5, 9)[:-1]).tolist()        # 8 positive
    v2 = [0.0]
    v3 = (-norm.ppf(np.linspace(offset, 0.5, 8)[:-1])).tolist()     # 7 negative
    v = sorted(v1 + v2 + v3)
    top = max(abs(x) for x in v)
    return [x / top for x in v]


# --------------------------------------------------------------- BOF4 --------
def bof4_em(x, wsq, fixed, init, iters=400, tol=1e-12, tag=""):
    """EM/Lloyd of arXiv:2505.06653 eq.(6). x: normalised weights (float32
    tensor). wsq: squared block maximum of each x's block, same shape.
    fixed: {index: value} levels pinned and never recomputed.
    Returns 16 ascending levels."""
    lv = torch.tensor(init, dtype=torch.float64)
    L = lv.numel()
    for it in range(iters):
        bnd = ((lv[:-1] + lv[1:]) / 2).to(torch.float32)
        idx = torch.bucketize(x, bnd)                    # 0..L-1
        num = torch.zeros(L, dtype=torch.float64)
        den = torch.zeros(L, dtype=torch.float64)
        num.index_add_(0, idx, (wsq * x).double())
        den.index_add_(0, idx, wsq.double())
        new = lv.clone()
        for l in range(L):
            if l in fixed:
                continue
            if den[l] > 0:
                new[l] = num[l] / den[l]
        d = float((new - lv).abs().max())
        lv = new
        if d < tol:
            break
    lv_l = [float(v) for v in lv]
    assert lv_l == sorted(lv_l), f"{tag}: levels not monotone: {lv_l}"
    print(f"    {tag}: converged in {it+1} iters, max step {d:.3e}", flush=True)
    return lv_l


def make_init(fixed):
    """Ascending start: NF4's shape, with the pinned levels forced."""
    init = list(NF4_PUBLISHED)
    for i, v in fixed.items():
        init[i] = v
    # keep strictly ascending so the first boundary set is valid
    for i in range(1, len(init)):
        if init[i] <= init[i - 1]:
            init[i] = init[i - 1] + 1e-6
    return init


FIXED_BOF4 = {0: -1.0, 7: 0.0, 15: 1.0}     # absmax normalisation
FIXED_BOF4S = {7: 0.0, 15: 1.0}             # signed absmax normalisation

# Paper Table 7, BOF4-S (MSE), block size I=32 -- their published artefact.
BOF4S_PUB_I32 = [
    -0.8732797503471375, -0.6907446384429932, -0.5437039136886597,
    -0.4173701703548431, -0.3038933575153351, -0.1986017823219299,
    -0.0981557220220566, 0.0, 0.0925938412547112, 0.187048003077507,
    0.2855197489261627, 0.3907126188278198, 0.506283164024353,
    0.6379748582839966, 0.7956376671791077, 1.0]


def blocks_to_xw(blocks, signed):
    """blocks: (n, K) float32. Returns flat x and flat squared block max."""
    a = blocks.abs()
    amax, arg = a.max(dim=1)
    if signed:
        m = torch.gather(blocks, 1, arg[:, None])[:, 0]
        m = torch.where(m == 0, torch.ones_like(m), m)
    else:
        m = amax.clamp(min=1e-30)
    keep = amax > 0
    blocks, m = blocks[keep], m[keep]
    x = (blocks / m[:, None]).reshape(-1)
    wsq = (m * m)[:, None].expand(-1, blocks.shape[1]).reshape(-1).contiguous()
    return x.contiguous(), wsq


def main():
    out = {}

    print("=== NF4: derived vs published ===")
    nf4 = derive_nf4()
    dev = max(abs(a - b) for a, b in zip(nf4, NF4_PUBLISHED))
    print(f"  max |derived - published| = {dev:.3e}")
    for a, b in zip(nf4, NF4_PUBLISHED):
        print(f"    {a:+.16f}   {b:+.16f}")
    print(f"  -> using the PUBLISHED bitsandbytes table (derivation agrees to "
          f"{dev:.1e})")
    out["NF4_published"] = NF4_PUBLISHED
    out["NF4_derived"] = nf4
    out["NF4_derivation_max_dev"] = dev

    # ---- implementation check: re-derive their Gaussian Table 7 I=32 --------
    print("\n=== BOF4 EM implementation check: Gaussian, I=32, 2^25 samples ===")
    g = torch.Generator().manual_seed(SEED)
    gauss = torch.randn(NBLK, K, generator=g, dtype=torch.float32)
    xg, wg = blocks_to_xw(gauss, signed=True)
    mine_g = bof4_em(xg, wg, FIXED_BOF4S, make_init(FIXED_BOF4S),
                     tag="BOF4-S(MSE) gaussian I=32")
    dev_g = max(abs(a - b) for a, b in zip(mine_g, BOF4S_PUB_I32))
    print(f"  vs paper Table 7 (I=32): max abs deviation = {dev_g:.3e}")
    for a, b in zip(mine_g, BOF4S_PUB_I32):
        print(f"    mine {a:+.10f}   paper {b:+.10f}   d {abs(a-b):.2e}")
    out["BOF4S_gaussian_mine"] = mine_g
    out["BOF4S_published_I32"] = BOF4S_PUB_I32
    out["BOF4S_gaussian_max_dev"] = dev_g
    del gauss, xg, wg

    # ---- derive on SmolLM2's own weights ------------------------------------
    print("\n=== BOF4 EM on SmolLM2-135M's own weights, K=32 ===")
    from transformers import AutoModelForCausalLM
    W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
         "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
    model = AutoModelForCausalLM.from_pretrained(os.path.join(W, "smollm2"),
                                                 dtype=torch.float32)
    lins = [(n, m) for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
    print(f"  {len(lins)} linear tensors (same rule as target_modules)")
    chunks = []
    for n, m in lins:
        w = m.weight.detach()
        c = (w.shape[1] // K) * K
        if c == 0:
            continue
        chunks.append(w[:, :c].reshape(-1, K).clone())
    allb = torch.cat(chunks, 0)
    del chunks, model
    print(f"  {allb.shape[0]} blocks total; subsampling {NBLK} (seed {SEED})")
    g = torch.Generator().manual_seed(SEED)
    sel = torch.randperm(allb.shape[0], generator=g)[:NBLK]
    blk = allb[sel].contiguous()
    del allb

    xa, wa = blocks_to_xw(blk, signed=False)
    bof4 = bof4_em(xa, wa, FIXED_BOF4, make_init(FIXED_BOF4),
                   tag="BOF4(MSE) smollm2")
    del xa, wa
    xs, ws = blocks_to_xw(blk, signed=True)
    bof4s = bof4_em(xs, ws, FIXED_BOF4S, make_init(FIXED_BOF4S),
                    tag="BOF4-S(MSE) smollm2")
    del xs, ws, blk

    out["BOF4_smollm2"] = bof4
    out["BOF4S_smollm2"] = bof4s

    print("\n  l   BOF4(mine,smollm2)   BOF4-S(mine,smollm2)  BOF4-S(paper,gauss)")
    for i in range(16):
        print(f"  {i+1:2d}  {bof4[i]:+.10f}        {bof4s[i]:+.10f}       "
              f"{BOF4S_PUB_I32[i]:+.10f}")
    d_ms = max(abs(a - b) for a, b in zip(bof4s, BOF4S_PUB_I32))
    print(f"\n  BOF4-S: smollm2-fitted vs paper's Gaussian, max dev = {d_ms:.3e}")
    out["BOF4S_smollm2_vs_published_max_dev"] = d_ms

    # every book must have top exactly 1.0 (T38 phase phi = 0)
    for k in ("NF4_published", "BOF4_smollm2", "BOF4S_smollm2",
              "BOF4S_published_I32", "BOF4S_gaussian_mine"):
        v = out[k]
        assert len(v) == 16, k
        assert v == sorted(v), k
        assert abs(max(abs(z) for z in v) - 1.0) < 1e-12, f"{k}: top != 1.0"
    print("\nall 16-level books: top magnitude exactly 1.0 (T38 phase phi=0)")

    dst = os.path.join(HERE, "campaignB_codebooks.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
