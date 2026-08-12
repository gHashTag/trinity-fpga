#!/usr/bin/env python3
"""Can the crossover be DERIVED from thm:latticeexp instead of guessed from D?

Iteration 107 withdrew the strong form of cor:designrule. The identification
N* ~ D was a heuristic: it read a corner SPACING off a theorem that speaks about
a ratio of local slopes to curvature. Across seven codebooks the ratio N*/D ran
0.69 to 3.01 and fell systematically as D rose.

The theorem's two branches are

    smooth   E(h) = g''(t*) h^2 / 24
    corner   E(h) = c_- c_+ h / (2 (c_- + c_+))

and equating them gives the scale at which one stops dominating the other:

    N*_theory = g''(t*) (c_- + c_+) / (12 c_- c_+).

Every term is a local property of the block's own error curve, so this is a
prediction with no fitted constant anywhere.

THREE PREDICTORS ARE COMPARED, all against the same measured N*:

  D            mean corner density near the optimum -- the withdrawn heuristic
  1/w*         reciprocal width of the arc CONTAINING the optimum. This is not
               1/D: the minimiser lands in a wide arc more often than a narrow
               one simply because wide arcs cover more of the line, so w* is
               length-biased, E[w*] = E[w^2]/E[w] >= E[w]. A codebook whose arc
               widths vary a lot -- int8, with 255 levels -- carries a large
               bias; one whose arcs are even carries almost none. That is the
               right shape to explain a ratio that MOVES with the codebook.
  N*_theory    the formula above.

HOW t* IS OBTAINED. From the same fine-lattice sweep the earlier scripts used,
which has been audited (argmin strictly interior; +-3 octave bracket reproduces
bit for bit). Reusing a verified instrument beats writing a third one.

HOW g'' AND THE SLOPES ARE OBTAINED, EXACTLY, WITH NO FINITE DIFFERENCES. On one
arc the rounding indices are frozen, so with s = 2^t and the selected levels L,

    g(t) = s^2 A - 2 s B + C,   A = sum L_i^2,  B = sum L_i v_i,  C = sum v_i^2
    dg/dt   = 2 ln2 . s (s A - B)
    d2g/dt2 = 2 (ln2)^2 s (2 s A - B)

evaluated at t*, and the one-sided slopes at the two bounding corners come from
the same expression with each side's own (A, B). Finite differences over a
lattice would inherit the lattice's own bias, which is the error this whole
programme keeps finding.
"""
import glob
import os
import sys

import numpy as np

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32
MODEL = "smollm2"
LN2 = np.log(2.0)


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


NF4 = np.array([-1.0, -0.6961928, -0.5250731, -0.3949175, -0.2844416,
                -0.1848825, -0.09105004, 0.0, 0.07958029, 0.1609302,
                0.2461123, 0.3379152, 0.4407098, 0.5626170, 0.7229568, 1.0])

# measured N* from the lattice sweeps, iterations 106 and 107
MEASURED = {"e3m0": 36.7, "e2m1": 49.0, "int4": 53.0, "nf4": 54.3,
            "e5m2": 388.0, "e4m3": 530.0, "int8": 598.0}

CODEBOOKS = {
    "e3m0": sym([0.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0]),
    "e2m1": sym([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]),
    "int4": sym(np.arange(0.0, 8.0)),
    "nf4":  NF4.copy(),
    "e5m2": sym(fp(5, 2)),
    "e4m3": sym(fp(4, 3)),
    "int8": sym(np.arange(0.0, 128.0)),
}

NB = int(sys.argv[1]) if len(sys.argv) > 1 else 600
NREF = int(sys.argv[2]) if len(sys.argv) > 2 else 8192
OCT = 0.9


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


V = blocks(NB)
amax = np.abs(V).max(axis=1)
V, amax = V[amax > 0], amax[amax > 0]
t0 = np.log2(amax)
print(f"  {MODEL}: {V.shape[0]:,} блоков, поиск оптимума по {NREF} точкам/бинаду\n")
RES = []
print(f"  {'книга':6s} {'D':>8s} {'1/w*':>9s} {'N* изм':>8s}   отношение свёртки к измеренному")

offs = np.arange(-int(OCT * NREF), int(OCT * NREF) + 1)

for cb, L in CODEBOOKS.items():
    lev = L / np.abs(L).max()
    bnd = (lev[:-1] + lev[1:]) / 2.0
    nz = bnd[bnd != 0]

    # ---- t* from the audited fine-lattice sweep -------------------------
    best = None
    tstar = np.zeros(V.shape[0])
    CH = 2048
    for a in range(0, offs.size, CH):
        blk = offs[a:a + CH]
        X = 2.0 ** (t0[:, None] + blk[None, :] / NREF)
        e = np.empty((V.shape[0], blk.size))
        for j in range(blk.size):
            x = X[:, j]
            e[:, j] = ((lev[np.searchsorted(bnd, V / x[:, None])] * x[:, None] - V) ** 2).sum(axis=1)
        m = e.min(axis=1)
        am = blk[e.argmin(axis=1)] / NREF
        if best is None:
            best, tstar = m, am
        else:
            sel = m < best
            tstar = np.where(sel, am, tstar)
            best = np.where(sel, m, best)

    Ds, ws, Nt = [], [], []
    for b in range(V.shape[0]):
        v = V[b]
        v = v[v != 0]
        r = v[:, None] / nz[None, :]
        c = np.log2(np.where(r > 0, r, np.nan)).ravel() - t0[b]
        c = c[np.isfinite(c)]
        ts = tstar[b]
        Ds.append(np.sum(np.abs(c - ts) <= 0.25) / 0.5)

        below = c[c < ts]
        above = c[c > ts]
        if below.size == 0 or above.size == 0:
            continue
        lo, hi = below.max(), above.min()
        w = hi - lo
        if not (0 < w < 1.0):
            continue
        ws.append(w)

        # exact quadratic on the arc containing t*, and on its two neighbours
        def AB(tt):
            x = 2.0 ** (t0[b] + tt)
            Lq = lev[np.searchsorted(bnd, V[b] / x)]
            return (Lq ** 2).sum(), (Lq * V[b]).sum()

        s = 2.0 ** (t0[b] + ts)
        A, B = AB(ts)
        g2 = 2.0 * LN2 ** 2 * s * (2.0 * s * A - B)
        # one-sided slopes at the bounding corners, each from its own arc
        sl, sh = 2.0 ** (t0[b] + lo), 2.0 ** (t0[b] + hi)
        Al, Bl = AB(lo - 1e-9)
        Ah, Bh = AB(hi + 1e-9)
        cm = abs(2.0 * LN2 * sl * (sl * Al - Bl))
        cp = abs(2.0 * LN2 * sh * (sh * Ah - Bh))
        if g2 > 0 and cm > 0 and cp > 0:
            # the block's own crossover, and the weight with which it enters the
            # AGGREGATE. Measured N* is where the exponent of the SUM reaches 2,
            # and the sum is dominated by blocks whose excess is largest near
            # the crossover -- i.e. blocks with steep corners, whose own
            # crossovers are LATE. A median over blocks therefore has to
            # under-read, which is the direction every ratio below shows.
            Nt.append((g2 * (cm + cp) / (12.0 * cm * cp),
                       cm * cp / (cm + cp),      # corner-regime coefficient
                       g2))                       # quadratic coefficient

    D = float(np.mean(Ds))
    iw = 1.0 / float(np.mean(ws)) if ws else float("nan")
    ms = MEASURED[cb]
    a = np.array(Nt) if Nt else np.zeros((1, 3))
    n_, wc, wg = a[:, 0], a[:, 1], a[:, 2]
    agg = {
        "медиана": float(np.median(n_)),
        "среднее": float(np.mean(n_)),
        "вес c":   float(np.sum(n_ * wc) / np.sum(wc)),
        "вес g''": float(np.sum(n_ * wg) / np.sum(wg)),
        "90-й проц": float(np.percentile(n_, 90)),
    }
    RES.append((cb, D, iw, ms, agg))
    print(f"  {cb:6s} {D:8.1f} {iw:9.1f} {ms:8.1f}   " +
          "  ".join(f"{k}={v / ms:.2f}" for k, v in agg.items()))

print("\n  ═══ КАКАЯ СВЁРТКА ДАЁТ ПОСТОЯННОЕ ОТНОШЕНИЕ ═══")
print("  (предиктор годен, если отношение одно и то же у всех семи книг)")
def cv(xs):
    xs = np.array(xs); return float(np.std(xs) / np.mean(xs)) * 100
cols = {"D": [r[1] / r[3] for r in RES], "1/w*": [r[2] / r[3] for r in RES]}
for k in RES[0][4]:
    cols[k] = [r[4][k] / r[3] for r in RES]
for k, v in sorted(cols.items(), key=lambda kv: cv(kv[1])):
    print(f"  {k:10s} среднее {np.mean(v):5.2f}  разброс(CV) {cv(v):5.1f}%")
