"""The block-maximum distribution itself, measured -- the object the u reparameterisation is
defined against.

u is "the clamp fraction under LOG-UNIFORM block maxima".  That model is an assumption, and it is
the assumption that makes u base-independent.  This file measures how good it is, and measures the
within-block depth distribution that the bottom of the element grid has to reach.

Per (model, K) it prints
    frac(log2 amax)   KS distance from uniform on [0,1)  -- 0 means exactly log-uniform, so
                      "target clamp fraction u" is exactly realised for every format at once
    realised clamp    the actual fraction of blocks whose maximum exceeds max_norm at a given u,
                      per format, next to the target u
    depth quantiles   quantiles of log2(|w| / amax) inside a block: how far below its own maximum
                      a typical weight sits.  This is what grows with K and what the bottom of the
                      element grid (min_pos / max_norm below the top) has to cover.

Usage:  u_blockstats.py [smollm2 qwen pythia opt]
"""
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from u_surface import FMTS, W, linears, scale_of                # noqa: E402

torch.set_grad_enabled(False)
HERE = os.path.dirname(os.path.abspath(__file__))
NELEM = 4_000_000


def main(tags):
    from transformers import AutoModelForCausalLM
    res = []
    for tag in tags:
        m = AutoModelForCausalLM.from_pretrained(os.path.join(W, tag), dtype=torch.float32)
        ws = [mod.weight.data for _, mod in linears(m)]
        nparam = sum(int(t.numel()) for t in ws)
        print(f"\n  {tag}: {len(ws)} tensors, {nparam:,} weights", flush=True)
        for K in (16, 32, 64, 128):
            nb_all = sum(int(t.shape[0]) * ((t.shape[1] + K - 1) // K) for t in ws)
            stride = max(1, (nb_all * K) // NELEM)
            sub = []
            for t in ws:
                pad = (-t.shape[1]) % K
                tt = t if not pad else torch.cat(
                    [t, torch.zeros(t.shape[0], pad, dtype=torch.float32)], dim=1)
                sub.append(tt.reshape(-1, K)[::stride].double().clone())
            b = torch.cat(sub, dim=0)
            del sub
            amax = b.abs().amax(dim=1)
            good = amax > 0
            b, amax = b[good], amax[good]
            nb = int(amax.numel())

            # --- is log2(amax) uniform in its fractional part?
            fr = torch.log2(amax)
            fr = fr - torch.floor(fr)
            fs, _ = torch.sort(fr)
            i = torch.arange(1, nb + 1, dtype=torch.float64)
            ks = float(torch.max(torch.maximum(i / nb - fs, fs - (i - 1) / nb)))

            # --- depth of a typical weight below its own block maximum
            d = torch.log2((b.abs() / amax[:, None]).clamp(min=1e-300)).flatten()
            d = d[torch.isfinite(d)]
            qs = [float(torch.quantile(d[torch.randperm(d.numel())[:2000000]]
                                       if d.numel() > 2000000 else d, q))
                  for q in (0.5, 0.25, 0.1, 0.02)]

            print(f"    K={K:<4} blocks {nb:,} (of {nb_all:,}, stride {stride})  "
                  f"KS(frac log2 amax, uniform) = {ks:.4f}", flush=True)
            print(f"          depth log2(|w|/amax) quantiles  median {qs[0]:+.3f}  "
                  f"q25 {qs[1]:+.3f}  q10 {qs[2]:+.3f}  q02 {qs[3]:+.3f}", flush=True)
            row = dict(model=tag, K=K, nblk=nb, nblk_all=nb_all, stride=stride, ks=ks,
                       depth_q50=qs[0], depth_q25=qs[1], depth_q10=qs[2], depth_q02=qs[3],
                       clamp={})
            for fn in ("E2M1", "E3M0", "INT4"):
                f = FMTS[fn]
                line = []
                for u in (0.125, 0.25, 0.375, 0.5):
                    s, _ = scale_of(amax, f, u)
                    obs = float((amax / s.clamp(min=1e-30) > f.max_norm).double().mean())
                    line.append((u, obs))
                    row["clamp"].setdefault(fn, []).append([u, obs])
                print(f"          realised block-max clamp {fn}: " +
                      "  ".join(f"u={u:.3f}->{o:.4f}({o - u:+.4f})" for u, o in line), flush=True)
            res.append(row)
            del b, amax, d
        del m, ws
        import gc
        gc.collect()
    with open(os.path.join(HERE, "u_blockstats.json"), "w") as fh:
        json.dump(res, fh, indent=1)


if __name__ == "__main__":
    torch.set_num_threads(2)
    main(sys.argv[1:] or ["smollm2", "qwen"])
