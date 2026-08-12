"""Independent re-measurement of the block-axis RMSE arms.

The perplexity figures behind the stop-rule answer came from a workflow whose
scratch directory was later wiped. The numbers survive in the run journal, but a
number whose only witness is a log is a number with no instrument behind it.
This re-measures the RMSE half from the weights themselves, in code written
here, so the claim rests on something that can be re-run.

Arms, all 4.25 bits/element, block 32, byte-identical E2M1 elements:
  mxfp4_floor  -- OCP Algorithm 1: shared_exp = floor(log2 amax) - emax
  mxfp4_argmin -- same 254 E8M0 codes, chosen by squared error
  step3        -- scale from 2^(k/3), chosen by squared error
  step8        -- scale from 2^(k/8), chosen by squared error
"""
import glob, math, os, sys
import numpy as np

WROOT = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
         "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K, EMAX = 32, 2
E2M1 = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0], dtype=np.float64)

def quant_elem(y):
    """Round each |y| to the nearest E2M1 magnitude, sign preserved."""
    a = np.abs(y); s = np.sign(y)
    idx = np.abs(a[..., None] - E2M1).argmin(axis=-1)
    return s * E2M1[idx]

def arm_rmse(V, mode, N=None):
    amax = np.abs(V).max(axis=1)
    ok = amax > 0
    V, amax = V[ok], amax[ok]
    if mode == "floor":
        X = 2.0 ** (np.floor(np.log2(amax)) - EMAX)
        err = ((quant_elem(V / X[:, None]) * X[:, None] - V) ** 2).sum()
    elif mode == "e4m3":
        # NVFP4's scale grid: an FP8-E4M3 value, i.e. 3 mantissa bits, which is
        # EIGHT POINTS PER BINADE -- the same resolution as the 2^(k/8) ladder,
        # but placed linearly in the mantissa (1 + m/8) instead of geometrically
        # (2^(m/8)). Same 8-bit field as E8M0. This arm tests whether the
        # paper's own law -- error monotone in points per binade and in nothing
        # else -- holds across a change of point PLACEMENT at fixed resolution.
        # Grid only: E4M3's finite range is not modelled, and the index-span
        # measurement already showed these weights fit.
        f = np.floor(np.log2(amax) - EMAX)
        best = None
        for o in (-1.0, 0.0, 1.0):
            for m in range(8):
                X = (2.0 ** (f + o)) * (1.0 + m / 8.0)
                e = ((quant_elem(V / X[:, None]) * X[:, None] - V) ** 2).sum(axis=1)
                best = e if best is None else np.minimum(best, e)
        err = best.sum()
    else:
        step = 1.0 if mode == "argmin2" else 1.0 / N
        # candidate ladder points bracketing amax/2^emax, within +-2 steps
        base = np.floor((np.log2(amax) - EMAX) / step)
        # The bracket must span the same OCTAVE range for every ladder, not the
        # same number of steps: +-2 steps is +-0.67 octave at 2^(k/3) and only
        # +-0.25 at 2^(k/8), which handicaps the finer ladder in its own favour's
        # opposite direction. First version of this script had that bug and
        # reported step8 losing to step3, reversing the published ordering.
        span = max(2, int(round(1.0 / step)) + 1)
        best = None
        for d in range(-span, span + 1):
            X = 2.0 ** ((base + d) * step)
            e = ((quant_elem(V / X[:, None]) * X[:, None] - V) ** 2).sum(axis=1)
            best = e if best is None else np.minimum(best, e)
        err = best.sum()
    return err, V.size

def tensors(model):
    import torch
    from safetensors.torch import load_file
    pats = ("proj", "fc", "mlp", "c_attn", "c_fc")
    for f in sorted(glob.glob(os.path.join(WROOT, model, "*.safetensors"))):
        for name, a in load_file(f).items():
            if a.ndim == 2 and any(s in name for s in pats):
                yield a.to(torch.float32).numpy().astype(np.float64)

ARMS = [("mxfp4_floor", "floor", None), ("mxfp4_argmin", "argmin2", None),
        ("step2", "step", 2), ("step3", "step", 3), ("step4", "step", 4),
        ("step8", "step", 8), ("step16", "step", 16)]

for model in [m for m in ("smollm2", "qwen") if os.path.isdir(os.path.join(WROOT, m))]:
    tot = {n: [0.0, 0] for n, _, _ in ARMS}
    nblk = 0
    for a in tensors(model):
        v = a.reshape(-1)
        v = v[: (v.size // K) * K].reshape(-1, K)
        nblk += v.shape[0]
        for n, mode, N in ARMS:
            e, c = arm_rmse(v, mode, N)
            tot[n][0] += e; tot[n][1] += c
    base = math.sqrt(tot["mxfp4_floor"][0] / tot["mxfp4_floor"][1])
    argm = math.sqrt(tot["mxfp4_argmin"][0] / tot["mxfp4_argmin"][1])
    print(f"\n  {model}: {nblk:,} блоков")
    for n, _, _ in ARMS:
        r = math.sqrt(tot[n][0] / tot[n][1])
        print(f"    {n:13s} RMSE {r:.10f}   против пола {(base-r)/base*100:+6.2f}%"
              f"   против argmin {(argm-r)/argm*100:+6.2f}%")
