#!/usr/bin/env python3
"""Does cor:designrule survive a doubling of element width?

The rule was derived and tested on four FOUR-bit codebooks, whose corner
densities span 28 to 53 per octave. That is a narrow lever. If D predicts the
crossover for EIGHT-bit codebooks too -- whose boundary densities are 4.7x to
8.4x higher -- then the rule is about block formats, and not about four-bit
block formats.

Run in two stages so the prediction is cheap and committed before the expensive
part:

  STAGE 1  (--count)  D by counting only, no error evaluated anywhere.
  STAGE 2  (--measure) the exponent sweep, with the reference ladder chosen
                       from stage 1's answer.

WHY THE REFERENCE LADDER MATTERS HERE, AND BURNED US ONCE. Iteration 106's
sweep reported p ~ 2.29 for all four codebooks on its last doubling, because at
a reference of 256 points/binade the N=128 grid is only 2x the reference and its
excess is biased low. A crossover near N=400 therefore needs a reference of at
least 4096, not 512, and the last doubling is discarded on principle rather than
on inspection.
"""
import glob
import os
import sys

import numpy as np

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32
MODEL = "smollm2"


def fp(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    return np.array(sorted(out))


def sym(m):
    m = np.asarray(m, dtype=float)
    return np.unique(np.concatenate([-m, m]))


CODEBOOKS = {
    "e5m2": sym(fp(5, 2)),      # widest range, sparsest boundaries per octave
    "e4m3": sym(fp(4, 3)),      # NVFP4's scale format, used here as an element grid
    "int8": sym(np.arange(0.0, 128.0)),   # densest boundaries per octave
}


def blocks(nb):
    from safetensors.torch import load_file
    import torch
    pats = ("proj", "fc", "mlp")
    out, tot = [], 0
    for f in sorted(glob.glob(os.path.join(W, MODEL, "*.safetensors"))):
        for name, a in load_file(f).items():
            if a.ndim == 2 and any(s in name for s in pats):
                v = a.to(torch.float32).numpy().astype(np.float64).reshape(-1)
                v = v[: (v.size // K) * K].reshape(-1, K)
                out.append(v)
                tot += v.shape[0]
                if tot >= nb:
                    V = np.vstack(out)
                    return V[np.linspace(0, V.shape[0] - 1, nb).astype(int)]
    return np.vstack(out)


MODE = sys.argv[1] if len(sys.argv) > 1 else "--count"

if MODE == "--count":
    V = blocks(20_000)
    amax = np.abs(V).max(axis=1)
    V, amax = V[amax > 0], amax[amax > 0]
    t0 = np.log2(amax)
    print(f"  {MODEL}: {V.shape[0]:,} блоков — СЧЁТ ИЗЛОМОВ, ошибка не вычисляется\n")
    # Without evaluating g we do not know t*, so count corners in a window
    # centred on the floor convention. The 4-bit run showed t* within 0.81
    # octave of it, and the density is what is wanted, not its exact centre.
    for cb, L in CODEBOOKS.items():
        lev = L / np.abs(L).max()
        bnd = (lev[:-1] + lev[1:]) / 2.0
        nz = bnd[bnd != 0]
        S = min(1500, V.shape[0])
        sel = np.linspace(0, V.shape[0] - 1, S).astype(int)
        cnt = []
        for b in sel:
            v = V[b]
            v = v[v != 0]
            r = v[:, None] / nz[None, :]
            c = np.log2(np.where(r > 0, r, np.nan)) - t0[b]
            cnt.append(int(np.nansum(np.abs(c) <= 0.25)))
        D = float(np.mean(cnt)) / 0.5
        print(f"  {cb:5s}  уровней {len(lev):4d}   D = {D:7.1f} изломов/окт"
              f"   ⇒ предсказан переход N ≈ {D:.0f}")
    sys.exit(0)

# ------------------------------------------------------------------- measure
NREF = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
OCT = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
NB = int(sys.argv[4]) if len(sys.argv) > 4 else 12_000
NS = [16, 32, 64, 128, 256, 512, 1024]

V = blocks(NB)
amax = np.abs(V).max(axis=1)
V, amax = V[amax > 0], amax[amax > 0]
t0 = np.log2(amax)
offs = np.arange(-int(OCT * NREF), int(OCT * NREF) + 1)
print(f"  {MODEL}: {V.shape[0]:,} блоков, эталон {NREF} точек/бинаду, окно ±{OCT} окт")
print(f"  последнее удвоение (N={NS[-2]}→{NS[-1]}) отбрасывается: эталон лишь "
      f"{NREF // NS[-1]}× мельче\n")

for cb, L in CODEBOOKS.items():
    lev = L / np.abs(L).max()
    bnd = (lev[:-1] + lev[1:]) / 2.0
    G = np.empty((V.shape[0], offs.size))
    for j, d in enumerate(offs):
        X = 2.0 ** (t0 + d / NREF)
        G[:, j] = ((lev[np.searchsorted(bnd, V / X[:, None])] * X[:, None] - V) ** 2).sum(axis=1)
    ref = G.min(axis=1)
    tstar = offs[G.argmin(axis=1)] / NREF

    nz = bnd[bnd != 0]
    S = min(1200, V.shape[0])
    sel = np.linspace(0, V.shape[0] - 1, S).astype(int)
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
        sub = [G[:, ph::st].min(axis=1) for ph in range(min(st, 64))]
        exc[N] = float(np.mean([(s - ref).sum() for s in sub]) / ref.sum())
    ps = [-np.log2(exc[NS[i + 1]] / exc[N]) for i, N in enumerate(NS[:-1])]
    mid = [np.sqrt(NS[i] * NS[i + 1]) for i in range(len(NS) - 1)]

    use = ps[:-1]                       # discard the last doubling on principle
    x, y = np.log2(mid[:len(use)]), np.array(use)
    n = None
    if len(use) >= 3:
        a, b = np.polyfit(x[-3:], y[-3:], 1)
        if a > 0:
            n = 2.0 ** ((2.0 - b) / a)
    print(f"  {cb:5s}  D={D:7.1f}   p: " + "  ".join(f"{v:.3f}" for v in ps))
    print(f"         переход по интерполяции: "
          f"{'N=%.0f' % n if n else 'вне охвата'}   "
          f"отношение {'%.2f' % (n / D) if n else '—'}\n")
