#!/usr/bin/env python3
"""Campaign D: the same conjecture, tested where it has power.

Five placements give Spearman n = 5, where only a PERFECT order reaches p < 0.05
and the measured order it is scored against has a tie at every adjacent step.
That test cannot distinguish a good predictor from a lucky one.

The conjecture underneath, though, is about BINS, not about placements: "the new
level belongs where the distortion is".  Every one of MXFP4's fifteen signed bins
is a candidate site, and each has a mass, a squared-error share, and a measured
KL contribution.  n = 15 gives the rank test real power, and it needs no
placement ranking at all -- so none of the instability in the five-placement
ordering propagates into it.

Reports Spearman of bin mass and of bin squared error against the bin's measured
KL contribution.
"""
import json
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "campaignD_kl15_smollm2_8win.json"
    kl = json.load(open(os.path.join(HERE, src)))
    pr = json.load(open(os.path.join(HERE, "campaignD_pred_smollm2.json")))
    bins = sorted(int(b) for b in kl["bins"])
    assert len(bins) == 15, bins

    edges = {int(k): v for k, v in pr["bin_edges"].items()}
    mass = np.array([pr["bin_mass"][b + 7] for b in bins])
    sse = np.array([pr["bin_sse_share"][b + 7] for b in bins])
    ssw = np.array([pr["bin_sse_share_weighted"][b + 7] for b in bins])
    wdt = np.array([edges[b][1] - edges[b][0] for b in bins])
    mw2 = mass * wdt ** 2
    klc = np.array([kl["bins"][str(b)]["share"] for b in bins])

    print(f"SmolLM2, {kl['nwin']} windows, KL(fp32||MXFP4) = {kl['kl_mxfp4']:.6f}\n")
    print(f"{'bin':>4}{'mass %':>9}{'m*w^2':>11}{'SSE %':>8}{'SSEw %':>8}{'KL %':>9}")
    for i, b in enumerate(bins):
        print(f"{b:>+4d}{100*mass[i]:>9.4f}{mw2[i]:>11.3e}{100*sse[i]:>8.3f}"
              f"{100*ssw[i]:>8.3f}{100*klc[i]:>9.3f}")

    print(f"\nSpearman against the measured KL contribution, n = 15:")
    for name, v in [("P1  bin mass", mass), ("P2  mass x width^2", mw2),
                    ("P2b SSE share", sse), ("P2c SSE share, weighted", ssw)]:
        r, p = stats.spearmanr(v, klc)
        print(f"  {name:<26} rho = {r:+.3f}   p = {p:.4f}")

    # The sign-symmetry control.  Mass and SSE are mirror-symmetric by
    # construction, so a symmetric predictor is blind to any sign effect.
    print(f"\nmirror pairs (predictors are symmetric by construction):")
    print(f"{'k':>3}{'mass -k/+k':>22}{'SSE -k/+k':>20}{'KL -k/+k':>22}")
    for k in range(1, 8):
        i, j = bins.index(-k), bins.index(k)
        print(f"{k:>3}{100*mass[i]:>10.4f}/{100*mass[j]:<10.4f}"
              f"{100*sse[i]:>9.3f}/{100*sse[j]:<10.3f}"
              f"{100*klc[i]:>10.3f}/{100*klc[j]:<10.3f}")
    sym_mass = float(np.abs(mass[:7][::-1] - mass[8:]).max())
    sym_kl = float(np.abs(klc[:7][::-1] - klc[8:]).max())
    print(f"\nmax mirror asymmetry:  mass {100*sym_mass:.4f} pp"
          f"   KL {100*sym_kl:.3f} pp")


if __name__ == "__main__":
    main()
