#!/usr/bin/env python3
"""Is the corner-density diagnosis a property of E2M1, or a design tool?

Theorem thm:latticeexp says the excess of a lattice-minimised objective is
O(h^2) against a smooth minimum and O(h) against a corner. A block's squared
error g(t), as a function of log2 of the shared scale, is a chain of smooth arcs
joined at corners -- one wherever some element crosses a codebook midpoint. So
the scale-ladder exponent should cross over to Bennett's value of 2 at the
ladder spacing that resolves a single arc, i.e. at N ~ D, the corner density per
octave.

On E2M1 this held: D = 46.5 measured by counting alone, and p reached 2.030
across N = 64->128.

ONE CODEBOOK IS AN ANECDOTE. If the diagnosis is real it is a statement about
ANY element codebook, and D is computable from the codebook and the weights
without evaluating the error even once. That makes it a design tool: count
corners, know the return on scale resolution, before quantising anything.

CODEBOOKS, chosen to spread D as widely as four 4-bit codebooks can:
  e2m1   MXFP4's own; boundaries geometric-ish over ~4.3 octaves
  int4   linear magnitudes 0..7; boundaries BUNCHED at the top in log space
  nf4    QLoRA's NormalFloat4; boundaries from the normal quantile function
  e3m0   pure exponent, magnitudes 0,1,2,4,...,64; boundaries SPREAD over 6.6

PRE-REGISTERED, and the file recording it is committed before this runs:
  1. D is measured first, by counting, with no error evaluation anywhere.
  2. The prediction is that p(N) crosses 2 near N = D, so the ORDERING of the
     four crossover points must follow the ORDERING of the four D values.
  3. The ordinal prediction is the one that counts. A cardinal hit would be
     luck at this level of modelling; a cardinal miss with the ordering intact
     still makes the diagnosis a design tool.

FALSIFIED IF the crossovers do not follow D -- in which case E2M1's agreement
was a coincidence and the paper's diagnosis is about one codebook, not about
codebooks.
"""
import glob
import os
import sys

import numpy as np

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32
NREF = 256
OCT = 1.5
MODEL = "smollm2"
NTENS = 3


# Canonical NF4 (QLoRA, Dettmers et al. 2023), 16 signed levels. It is
# ASYMMETRIC, so it carries 15 distinct magnitudes where a symmetric 4-bit
# codebook carries 8 -- which is the point: it should show a much higher corner
# density, and the diagnosis predicts a correspondingly later crossover.
NF4 = np.array([-1.0, -0.6961928, -0.5250731, -0.3949175, -0.2844416,
                -0.1848825, -0.09105004, 0.0, 0.07958029, 0.1609302,
                0.2461123, 0.3379152, 0.4407098, 0.5626170, 0.7229568, 1.0])


def sym(mags):
    """A symmetric codebook from its magnitude ladder."""
    m = np.asarray(mags, dtype=float)
    return np.unique(np.concatenate([-m, m]))


CODEBOOKS = {
    "e2m1": sym([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]),
    "int4": sym(np.arange(0.0, 8.0)),
    "nf4":  NF4.copy(),
    "e3m0": sym([0.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0]),
}


def blocks(ntens):
    from safetensors.torch import load_file
    import torch
    pats = ("proj", "fc", "mlp")
    out, seen = [], 0
    for f in sorted(glob.glob(os.path.join(W, MODEL, "*.safetensors"))):
        for name, a in load_file(f).items():
            if a.ndim == 2 and any(s in name for s in pats):
                v = a.to(torch.float32).numpy().astype(np.float64).reshape(-1)
                out.append(v[: (v.size // K) * K].reshape(-1, K))
                seen += 1
                if seen >= ntens:
                    return np.vstack(out)
    return np.vstack(out)


V = blocks(NTENS)
amax = np.abs(V).max(axis=1)
V, amax = V[amax > 0], amax[amax > 0]
print(f"  {MODEL}: {V.shape[0]:,} блоков, эталон {NREF} точек/бинаду\n")

offs = np.arange(-int(OCT * NREF), int(OCT * NREF) + 1)
NS = [2, 4, 8, 16, 32, 64, 128]
rows = []

for cb, L in CODEBOOKS.items():
    lev = L / np.abs(L).max()          # normalise: the extreme magnitude is 1
    bnd = (lev[:-1] + lev[1:]) / 2.0   # signed midpoints
    t0 = np.log2(amax)                 # block max sits at the codebook extreme

    G = np.empty((V.shape[0], offs.size))
    for j, d in enumerate(offs):
        X = 2.0 ** (t0 + d / NREF)
        Q = lev[np.searchsorted(bnd, V / X[:, None])]
        G[:, j] = ((Q * X[:, None] - V) ** 2).sum(axis=1)
    ref = G.min(axis=1)
    tstar = offs[G.argmin(axis=1)] / NREF

    # ---- corner density: counting only, the error is never evaluated here ----
    # element v crosses boundary m at t = log2(v/m), which exists only when the
    # two share a sign. Asymmetric codebooks therefore contribute more corners.
    S = min(2500, V.shape[0])
    sel = np.linspace(0, V.shape[0] - 1, S).astype(int)
    nz = bnd[bnd != 0]
    cnt = []
    for b in sel:
        v = V[b]
        v = v[v != 0]
        r = v[:, None] / nz[None, :]
        c = np.log2(np.where(r > 0, r, np.nan)) - t0[b]
        cnt.append(int(np.nansum(np.abs(c - tstar[b]) <= 0.25)))
    D = float(np.mean(cnt)) / 0.5

    exc = {}
    for N in NS:
        st = NREF // N
        sub = [G[:, ph::st].min(axis=1) for ph in range(st)]
        exc[N] = float(np.mean([(s - ref).sum() for s in sub]) / ref.sum())
    ps = [-np.log2(exc[NS[i + 1]] / exc[N]) for i, N in enumerate(NS[:-1])]

    cross = None
    for i, pv in enumerate(ps):
        if pv >= 1.9:
            cross = NS[i]
            break
    rows.append((cb, D, cross, ps))
    print(f"  {cb:5s}  уровней {len(lev):2d}, D={D:6.1f} изломов/окт"
          f"  =>  предсказан переход N≈{D:.0f}")
    print(f"         p: " + "  ".join(f"{x:.3f}" for x in ps))
    print(f"         измеренный переход (p≥1.9): N={cross}\n")

print("  ═══ ПОРЯДКОВАЯ ПРОВЕРКА ═══")
by_d = [r[0] for r in sorted(rows, key=lambda r: r[1])]
by_c = [r[0] for r in sorted(rows, key=lambda r: (r[2] is None, r[2] or 0))]
print(f"  по плотности изломов D : {' < '.join(by_d)}")
print(f"  по измеренному переходу: {' < '.join(by_c)}")
print(f"  {'СОВПАЛО' if by_d == by_c else 'РАЗОШЛОСЬ — диагноз про E2M1, а не про книги'}")
