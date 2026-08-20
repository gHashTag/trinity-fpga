#!/usr/bin/env python3
"""W949: is 'range is the mechanism' an artefact of PER-TENSOR scaling?

Every stability run in this project scaled by the maximum of the WHOLE tensor. Under
that rule a format must span the tensor's entire dynamic range by itself, and TNF4's
14.6 binades against fp6 e2m3's 5.9 is decisive -- that is our surviving claim.

But nobody deploys per-tensor scaling at four to six bits. The OCP microscaling (MX)
formats give every block of 32 elements its own shared exponent, so the ELEMENT format
only has to span the range found INSIDE a block. If that range is small, a narrow grid
is sufficient and our advantage is an artefact of the scaling rule, not a property of
the lattice.

This measures the crossover directly: underflow fraction and relative RMS error for
each grid, as a function of block size, on distributions with the shape of weights and
of post-ReLU activations. No datasets, no training -- only the grids and the arithmetic.
"""
import json, sys, pathlib
import numpy as np

S = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(S / "oracles"))
import tnf_ref as T, fp8_ref as F8

RNG = np.random.default_rng(20260820)
N = 1 << 18


def grid(mod, fmt, bits):
    v = []
    for c in range(1 << bits):
        try:
            x = float(mod.decode(fmt, c))
        except Exception:
            continue
        if np.isfinite(x):
            v.append(x)
    a = np.unique(np.array(sorted(set(v)), dtype=np.float64))
    assert (a < 0).any(), "grid has no negatives"
    return a


GRIDS = {
    "TNF4":    grid(T,  T.TNFFormat(2, 1),          6),
    "fp6e3m2": grid(F8, F8.FORMATS["fp6_e3m2"],     6),
    "fp6e2m3": grid(F8, F8.FORMATS["fp6_e2m3"],     6),
    "fp4e2m1": grid(F8, F8.FORMATS["fp4_e2m1"],     4),
}


def binades(g):
    p = g[g > 0]
    return float(np.log2(p.max() / p.min()))


def snap(x, g):
    i = np.searchsorted(g, x).clip(1, len(g) - 1)
    lo, hi = g[i - 1], g[i]
    return np.where(np.abs(x - lo) <= np.abs(hi - x), lo, hi)


def measure(x, g, block):
    """Scale by the max of each block, quantise, report underflow and rel RMS.

    W949 correction: the grid is normalised to unit maximum first, so the block
    peak lands on the format's LARGEST representable value. That is the standard
    max rule, and it is the convention under which this project's published
    mechanism (0.0041 % / 0.22 % / 1.67 % underflow thresholds) was computed. The
    first version of this rig snapped onto the RAW grid, which maps the peak to
    grid value 1.0 instead -- and produced identical underflow for TNF4 and
    fp6 e2m3, the anomaly that exposed the same defect in the training rig.
    """
    g = g / g.max()
    n = (len(x) // block) * block
    xb = x[:n].reshape(-1, block)
    s = np.abs(xb).max(axis=1, keepdims=True)
    s = np.where(s > 0, s, 1.0)
    q = snap(xb / s, g) * s
    nz = xb != 0
    under = float((nz & (q == 0)).sum() / max(nz.sum(), 1))
    err = float(np.sqrt(((q - xb) ** 2).sum() / max((xb ** 2).sum(), 1e-30)))
    return under, err


def main():
    # weights: Gaussian, as at init and approximately after training.
    # activations: post-ReLU, i.e. half-normal with a hard zero mass -- the case
    # where a max-rule scale is most punishing, and the one that failed in W946.
    dists = {
        "weights_gauss":  RNG.standard_normal(N),
        "acts_relu":      np.maximum(RNG.standard_normal(N), 0.0),
        "acts_heavy":     np.maximum(RNG.standard_t(3, N), 0.0),
    }
    # 32 is the OCP microscaling block size; N is per-tensor, what we always used.
    blocks = [8, 16, 32, 64, 128, 1024, N]
    out = {"n": N, "blocks": blocks,
           "binades": {k: round(binades(g), 2) for k, g in GRIDS.items()},
           "grid_size": {k: int(len(g)) for k, g in GRIDS.items()},
           "res": {}}
    print("  диапазон грида (бинады):",
          ", ".join(f"{k} {v}" for k, v in out["binades"].items()), flush=True)
    for dn, x in dists.items():
        out["res"][dn] = {}
        print(f"\n  == {dn}", flush=True)
        print(f"  {'блок':>7} " + " ".join(f"{k:>22}" for k in GRIDS), flush=True)
        for b in blocks:
            row, cells = {}, []
            for k, g in GRIDS.items():
                u, e = measure(x, g, b)
                row[k] = {"underflow": u, "rel_rmse": e}
                cells.append(f"{u*100:8.2f}% / {e*100:6.2f}%")
            out["res"][dn][str(b)] = row
            lab = "тензор" if b == N else str(b)
            print(f"  {lab:>7} " + " ".join(f"{c:>22}" for c in cells), flush=True)
    p = S / "blockscale_w949.json"
    p.write_text(json.dumps(out, indent=1))
    print("\n  (в ячейке: доля обнулённых ненулевых / относительная RMS-ошибка)")
    print("WROTE " + str(p), flush=True)


if __name__ == "__main__":
    main()
