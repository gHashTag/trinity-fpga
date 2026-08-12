#!/usr/bin/env python3
"""Why the scale axis has an exponent strictly between 1 and 2.

MEASURED (verify_block_rmse.py, nested chain 2 c 4 c 8 c 16):
    p = 1.310 then 1.537   (smollm2)
    p = 1.327 then 1.545   (qwen)
Bennett's law requires p = 2, constant. It is neither.

THE CLAIM UNDER TEST. Write g(t) for a block's squared error when the shared
scale is 2^t. Minimising a function over a grid of spacing h = 1/N gives an
excess above the true minimum whose order depends ONLY on the local shape:

    g locally quadratic (g'' > 0, interior minimiser)
        excess = g''(t*) h^2 / 24              ~ h^2   -> p = 2
    g locally a corner (slopes c_- and c_+)
        excess = (c_- + c_+) h / 8             ~ h^1   -> p = 1

g here is PIECEWISE smooth with corners: the E2M1 rounding index of each element
is piecewise constant in t and jumps whenever an element crosses a midpoint
boundary, at t = log2(|v_i| / bnd_j). So g is a chain of smooth arcs joined at
corners, and which regime a ladder of spacing h sees depends on h against the
local corner spacing.

    PREDICTION: p rises from 1 toward 2 as the ladder refines, and the drift is
    the crossover between the two regimes -- not noise, and not a bad fit.

THE TEST avoids fitting anything. For each block compute the true minimum on a
very fine reference grid, then the minimum on grids of spacing 1/N, and read the
exponent straight off successive excesses:

    p(N) = -log2( excess(2N) / excess(N) )

If the claim is right this rises toward 2 and stays below it. If it sits at 2 the
corners do not bind and the earlier measurement needs another explanation; if it
sits at 1 there is no quadratic regime at any reachable width.

A CONTROL comes free. The corner positions t = log2(|v_i|/bnd_j) are computable
without any error evaluation, so the corner density per octave near the optimum
is measured directly and compared against the h at which p crosses 1.5.
"""
import os
import sys

import numpy as np

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32
EMAX = 2
E2M1 = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0])
BND = (E2M1[:-1] + E2M1[1:]) / 2.0
NREF = 512            # reference ladder: 512 points per binade
MODEL = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
NTENS = int(sys.argv[2]) if len(sys.argv) > 2 else 8


def quant_elem(U):
    A = np.abs(U)
    return np.sign(U) * E2M1[np.searchsorted(BND, A)]


def blocks(model, ntens):
    from safetensors.torch import load_file
    import torch
    pats = ("proj", "fc", "mlp", "c_attn", "c_fc")
    out, seen = [], 0
    for f in sorted(glob_safetensors(model)):
        for name, a in load_file(f).items():
            if a.ndim == 2 and any(s in name for s in pats):
                v = a.to(torch.float32).numpy().astype(np.float64).reshape(-1)
                v = v[: (v.size // K) * K].reshape(-1, K)
                out.append(v)
                seen += 1
                if seen >= ntens:
                    return np.vstack(out)
    return np.vstack(out)


def glob_safetensors(model):
    import glob as _g
    return _g.glob(os.path.join(W, model, "*.safetensors"))


V = blocks(MODEL, NTENS)
amax = np.abs(V).max(axis=1)
ok = amax > 0
V, amax = V[ok], amax[ok]
print(f"  {MODEL}: {V.shape[0]:,} блоков, эталонная лестница {NREF} точек/бинаду\n")

# ---------------------------------------------------------------- curve g(t)
# Evaluate g on the reference ladder over a window that contains every ladder's
# optimum. The RMSE verifier's audit showed |d|max = 13 at N=16, i.e. 0.81
# octave, so +-1.5 octaves is comfortably wider than anything binds at.
t0 = np.log2(amax) - EMAX
OCT = 1.5
offs = np.arange(-int(OCT * NREF), int(OCT * NREF) + 1)
G = np.empty((V.shape[0], offs.size))
for j, d in enumerate(offs):
    X = 2.0 ** (t0 + d / NREF)
    G[:, j] = ((quant_elem(V / X[:, None]) * X[:, None] - V) ** 2).sum(axis=1)

ref = G.min(axis=1)                     # the fine-grid minimum, per block

# --------------------------------------------------- excess on ladder 1/N
print("  ИЗБЫТОК НАД ЭТАЛОНОМ И ЛОКАЛЬНЫЙ ПОКАЗАТЕЛЬ")
print("     N   избыток (доля)      p(N→2N)")
NS = [2, 4, 8, 16, 32, 64, 128]
exc = {}
for N in NS:
    stride = NREF // N
    # every phase of the coarse ladder inside the fine one, averaged: the
    # ladder's origin is arbitrary and no result should depend on it
    sub = [G[:, ph::stride].min(axis=1) for ph in range(stride)]
    # NB: np.mean already divides by len(sub). Dividing again scaled every
    # excess by 1/stride = N/NREF, which shifted the exponent by exactly 1.
    # Caught because the number disagreed with verify_block_rmse.py by a
    # factor that turned out to be stride itself.
    exc[N] = float(np.mean([(s - ref).sum() for s in sub]) / ref.sum())
for i, N in enumerate(NS):
    p = ""
    if i + 1 < len(NS):
        p = f"{-np.log2(exc[NS[i+1]] / exc[N]):.3f}"
    print(f"  {N:4d}   {exc[N]:.6e}      {p}")

# ------------------------------------------------------------ corner density
# Corners of g sit at t = log2(|v_i| / bnd_j) - t0, in units of octaves from the
# floor. Count how many land within +-0.25 octave of the block's optimum.
tstar = (offs[G.argmin(axis=1)] / NREF)
S = min(4000, V.shape[0])
sel = np.linspace(0, V.shape[0] - 1, S).astype(int)
cnt = []
for b in sel:
    v = np.abs(V[b])
    v = v[v > 0]
    c = np.log2(v[:, None] / BND[None, :]).ravel() - t0[b]
    cnt.append(np.sum(np.abs(c - tstar[b]) <= 0.25))
cnt = np.array(cnt)
dens = cnt.mean() / 0.5
print(f"\n  изломов на октаву около оптимума: {dens:.1f} "
      f"(медиана {np.median(cnt) / 0.5:.1f})")
print(f"  => типичное расстояние между изломами {1 / dens:.4f} октавы, "
      f"что соответствует лестнице N = {dens:.0f}")
print("\n  ПРЕДСКАЗАНИЕ: p ниже 2 пока шаг 1/N крупнее межизломного расстояния,")
print("  и подходит к 2 когда 1/N становится мельче его.")
