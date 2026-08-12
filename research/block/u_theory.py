"""Is there a u* you can DERIVE, without a forward pass and without a fitted constant?

Two cheap arms.  Both are candidate PREDICTORS, never verdicts: this campaign has a measured
counterexample in which squared error moves opposite to perplexity
(research/block/METRIC_DISAGREEMENT_2026-08-11.md), so nothing here may be reported as a result
on its own.  u_surface.py holds the only judge, which is perplexity.

  ARM S  synthetic.  i.i.d. samples from a named distribution, cut into blocks of K, no model
         anywhere.  The u minimising block-quantisation squared error is then a function of
         (K, element format, source distribution) ONLY.  If u* is a property of the
         block-maximum statistics, this arm should already reproduce its shape.
  ARM W  real weights.  Same objective on the actual nn.Linear weights of each checkpoint,
         no forward pass.  Adds "which model" as an axis.

Both print the two mechanism channels the hypothesis is about: the fraction of ELEMENTS clamped
at the top of the grid, and the fraction flushed to zero at the bottom.

Usage:  u_theory.py synth
        u_theory.py weights [smollm2 qwen pythia opt ...]
"""
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from u_surface import FMTS, W, q_elem, scale_of, linears        # noqa: E402

torch.set_grad_enabled(False)
HERE = os.path.dirname(os.path.abspath(__file__))
UGRID = [round(0.025 * i, 4) for i in range(0, 41)]             # 0.000 .. 1.000 step 0.025
NELEM = 4_000_000                                               # sample size per cell


def sse_of_blocks(b, f, u, tie="even"):
    """Total squared error of block quantisation for a [nblk, K] float64 tensor."""
    amax = b.abs().amax(dim=1)
    s, _ = scale_of(amax, f, u)
    s = s.clamp(min=1e-30)
    y = b / s[:, None]
    rec = torch.sign(b) * q_elem(y, f, tie) * s[:, None]
    ay = y.abs()
    return dict(sse=float(((b - rec) ** 2).sum()),
                sxx=float((b ** 2).sum()),
                nel=int(b.numel()),
                nblk=int(b.shape[0]),
                nel_sat=int((ay > f.max_norm).sum()),
                nel_zero=int(((ay > 0) & (ay < f.bnd[0])).sum()),
                nblk_sat=int((amax / s > f.max_norm).sum()))


def curve(blocks, f, ugrid=UGRID):
    out = []
    for u in ugrid:
        tot = dict(sse=0.0, sxx=0.0, nel=0, nblk=0, nel_sat=0, nel_zero=0, nblk_sat=0)
        for b in blocks:
            st = sse_of_blocks(b, f, u)
            for k in tot:
                tot[k] += st[k]
        out.append(dict(u=u, nsse=tot["sse"] / tot["sxx"],
                        el_clamp=100.0 * tot["nel_sat"] / tot["nel"],
                        el_zero=100.0 * tot["nel_zero"] / tot["nel"],
                        blk_clamp=100.0 * tot["nblk_sat"] / tot["nblk"],
                        nel=tot["nel"], nblk=tot["nblk"]))
    return out


def argmin_parabolic(rows, key="nsse"):
    """Discrete argmin plus a parabolic refinement through its two neighbours."""
    i = int(np.argmin([r[key] for r in rows]))
    if i in (0, len(rows) - 1):
        return rows[i]["u"], rows[i][key], "edge"
    x = [rows[j]["u"] for j in (i - 1, i, i + 1)]
    y = [rows[j][key] for j in (i - 1, i, i + 1)]
    d = y[0] - 2 * y[1] + y[2]
    if d <= 0:
        return rows[i]["u"], rows[i][key], "flat"
    return float(x[1] - 0.5 * (x[2] - x[1]) * (y[2] - y[0]) / d), rows[i][key], "interp"


def basin(rows, key="nsse", frac=0.01):
    """u-interval over which the objective stays within `frac` of its minimum -- an honest
    statement of how well the minimum is located at all."""
    v = [r[key] for r in rows]
    lo = min(v) * (1.0 + frac)
    us = [r["u"] for r, x in zip(rows, v) if x <= lo]
    return min(us), max(us)


# ------------------------------------------------------------------ ARM S: synthetic
def synth(nelem=NELEM, seed=0):
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    print("\n  ARM S -- synthetic i.i.d. blocks.  No model, no weights, no forward pass.")
    print("  u* here can depend ONLY on (K, element format, source distribution).")
    print(f"  denominator: {nelem:,} elements per (dist, K, fmt) cell; u grid "
          f"{UGRID[0]}..{UGRID[-1]} step {UGRID[1]}\n", flush=True)
    dists = {
        "gauss": lambda n: torch.randn(n, generator=gen, dtype=torch.float64),
        "laplace": lambda n: torch.sign(torch.rand(n, generator=gen, dtype=torch.float64) - 0.5)
        * -torch.log1p(-0.999999 * torch.rand(n, generator=gen, dtype=torch.float64)),
        "t5": lambda n: torch.randn(n, generator=gen, dtype=torch.float64)
        / torch.sqrt(torch.distributions.Chi2(torch.tensor(5.0)).sample((n,)).double() / 5.0),
    }
    res = []
    print(f"  {'dist':<9}{'K':>5}{'fmt':>7}{'u*(nsse)':>11}{'nsse*':>11}{'how':>9}"
          f"{'1% basin':>18}{'elclamp@u*':>12}{'el->0@u*':>11}{'nblk':>10}", flush=True)
    for dn, dfun in dists.items():
        for K in (16, 32, 64, 128):
            nb = nelem // K
            x = dfun(nb * K).reshape(nb, K)
            for fn in ("E2M1", "E3M0", "INT4"):
                f = FMTS[fn]
                rows = curve([x], f)
                us, v, how = argmin_parabolic(rows)
                b0, b1 = basin(rows)
                near = min(rows, key=lambda r: abs(r["u"] - us))
                print(f"  {dn:<9}{K:>5}{fn:>7}{us:11.4f}{v:11.6f}{how:>9}"
                      f"   [{b0:5.3f},{b1:6.3f}]{near['el_clamp']:12.3f}"
                      f"{near['el_zero']:11.3f}{nb:>10,}", flush=True)
                res.append(dict(dist=dn, K=K, fmt=fn, ustar=us, nsse=v, how=how,
                                basin=[b0, b1], nblk=nb, nelem=nb * K, rows=rows))
            del x
    with open(os.path.join(HERE, "u_theory_synth.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    return res


# ------------------------------------------------------------------ ARM W: real weights
def weights(tags, nelem=NELEM):
    from transformers import AutoModelForCausalLM
    print("\n  ARM W -- real nn.Linear weights (lm_head excluded).  No forward pass.")
    print(f"  blocks are subsampled with a fixed stride to about {nelem:,} elements per cell;"
          f" the realised block count is printed.\n", flush=True)
    res = []
    for tag in tags:
        m = AutoModelForCausalLM.from_pretrained(os.path.join(W, tag), dtype=torch.float32)
        ws = [mod.weight.data for _, mod in linears(m)]        # float32 views into the model
        nparam = sum(int(t.numel()) for t in ws)
        print(f"\n  {tag}: {len(ws)} tensors, {nparam:,} weights, shapes "
              f"{sorted({tuple(t.shape) for t in ws})}", flush=True)
        print(f"  {'K':>5}{'fmt':>7}{'u*(nsse)':>11}{'nsse*':>11}{'how':>9}{'1% basin':>18}"
              f"{'nblk_used':>12}{'of':>14}{'partialblk':>12}{'elclamp@u*':>12}"
              f"{'el->0@u*':>11}", flush=True)
        for K in (16, 32, 64, 128):
            npart = sum(int(t.shape[0]) for t in ws if t.shape[1] % K)
            # subsample blocks with a fixed stride BEFORE widening to float64: holding every
            # weight of a 0.5B model in float64 puts 2.9 GB on a machine that is already
            # swapping, which is how the first attempt at this arm died.
            nb_all = sum(int(t.shape[0]) * ((t.shape[1] + K - 1) // K) for t in ws)
            stride = max(1, (nb_all * K) // nelem)
            sub = []
            for t in ws:
                pad = (-t.shape[1]) % K
                tt = t if not pad else torch.cat(
                    [t, torch.zeros(t.shape[0], pad, dtype=torch.float32)], dim=1)
                sub.append(tt.reshape(-1, K)[::stride].double().clone())
                del tt
            nb_used = sum(int(b.shape[0]) for b in sub)
            for fn in ("E2M1", "E3M0", "INT4"):
                f = FMTS[fn]
                rows = curve(sub, f)
                us, v, how = argmin_parabolic(rows)
                b0, b1 = basin(rows)
                near = min(rows, key=lambda r: abs(r["u"] - us))
                print(f"  {K:>5}{fn:>7}{us:11.4f}{v:11.6f}{how:>9}   [{b0:5.3f},{b1:6.3f}]"
                      f"{nb_used:>12,}{nb_all:>14,}{npart:>12,}{near['el_clamp']:12.3f}"
                      f"{near['el_zero']:11.3f}", flush=True)
                res.append(dict(model=tag, K=K, fmt=fn, ustar=us, nsse=v, how=how,
                                basin=[b0, b1], nblk_used=nb_used, nblk_all=nb_all,
                                stride=stride, nparam=nparam, npart=npart, rows=rows))
                with open(os.path.join(HERE, "u_theory_weights.json"), "w") as fh:
                    json.dump(res, fh, indent=1)
            del sub
        del m, ws
        import gc
        gc.collect()
    return res


if __name__ == "__main__":
    torch.set_num_threads(2)
    if sys.argv[1] == "synth":
        synth()
    else:
        weights(sys.argv[2:] or ["smollm2", "qwen", "pythia", "opt"])
