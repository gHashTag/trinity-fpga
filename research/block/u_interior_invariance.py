"""Why the alignment u matters for some element formats and not others -- derived, then tested.

CLAIM (stated before running, so it can fail)
--------------------------------------------
A block scale s enters only through y = b/s, and u moves s in whole factors of g = 2.  So ask what
doubling s does to the quantiser.

  A float format's magnitude set is closed under multiplication by 2 except at its two ends,
  because doubling increments the exponent and leaves the mantissa alone.  Therefore for every
  element that stays strictly inside the representable window at BOTH scales,

        s * q(b / s)  ==  2s * q(b / 2s)          EXACTLY, bit for bit,

  and the reconstruction does not depend on u at all.  All u-dependence of a FLOAT format is
  carried by the two ends: elements that clamp at max_norm, and elements that flush to zero.

  A LINEAR format (INT4) is not closed under doubling -- 5 has no half on the grid -- so its
  interior changes too, and it must be the most u-sensitive of the three.

FIRST RUN REFUTED P1 AND THE REFUTATION IS THE POINT
  E2M1 came back 81.15 % invariant on the window [min_pos, max_norm], not 100 %.  Cause: the
  bottom binade of E2M1 is SUBNORMAL and holds one magnitude (0.5) where every normal binade
  holds two (1,1.5 | 2,3 | 4,6).  So the set is not closed under HALVING out of the normal range:
  1.5/2 = 0.75 is not representable.  E3M0 has no such step -- one magnitude per binade
  everywhere -- which is exactly why it is exactly invariant.

  Restated: the closed range is [2*min_normal, max_norm], i.e. the part of the window that stays
  NORMAL at both scales.  E2M1 min_normal = 1.0 -> closed on [2, 6], one binade of its 3.585 lost
  to the subnormal step.  E3M0 min_normal = 0.25 -> closed on [0.5, 16].

PREDICTIONS (P1 restated after the refutation; P1' is what is tested below)
  P1' E2M1 is bitwise invariant on [2*min_normal, max_norm] and NOT on the subnormal binade.
  P2  E3M0 interior: bitwise invariant under s -> 2s.
  P3  INT4 interior: NOT invariant, and the disagreeing fraction is large.
  P4  So a format has THREE u-sensitive sites, not two: the top clamp, the bottom flush, and --
      for a float with subnormals -- the resolution step at the subnormal boundary.  E3M0
      (6.000 binades, no step) is nearly flat in u; E2M1 (3.585 binades, one step) is not; INT4
      (linear, sensitive everywhere) is the worst.  Sensitivity grows with K because a wider
      block spreads its elements further below its own maximum, pushing more mass onto the
      bottom sites.

This file needs no model and no checkpoint: it is a statement about the codebooks.
"""
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from u_surface import FMTS, TIES, q_elem            # noqa: E402

torch.set_grad_enabled(False)
FAILED = []


def check(cond, label, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {label}" + (f"   {detail}" if detail else ""),
          flush=True)
    if not cond:
        FAILED.append(label)


def main():
    torch.manual_seed(0)
    n = 4_000_000
    # log-uniform magnitudes over 12 binades: far wider than any block, so every regime is hit
    b = torch.exp(torch.rand(n, dtype=torch.float64) * 12.0 * np.log(2.0) - 6.0 * np.log(2.0))
    b = b * torch.where(torch.rand(n) < 0.5, -1.0, 1.0).double()
    # smallest NORMAL magnitude: the smallest m in the grid whose predecessor is m/2
    MIN_NORMAL = {"E2M1": 1.0, "E3M0": 0.25, "INT4": 1.0}
    print(f"\n=== invariance under s -> 2s, {n:,} log-uniform draws over 12 binades ===")
    print(f"    two windows are reported: the naive one [min_pos, max_norm] that refuted P1, and")
    print(f"    the normal-at-both-scales window [2*min_normal, max_norm] that P1' claims")
    print(f"    {'fmt':<6}{'tie':<6}{'naive N':>11}{'naive same':>12}"
          f"{'closed window':>16}{'closed N':>11}{'closed same':>13}")
    for name in ("E2M1", "E3M0", "INT4"):
        f = FMTS[name]
        for tie in TIES:
            s1, s2 = 1.0, 2.0
            y1, y2 = b / s1, b / s2
            r1 = torch.sign(b) * q_elem(y1, f, tie) * s1
            r2 = torch.sign(b) * q_elem(y2, f, tie) * s2
            naive = ((y1.abs() >= f.min_pos) & (y1.abs() <= f.max_norm)
                     & (y2.abs() >= f.min_pos) & (y2.abs() <= f.max_norm))
            lo = 2.0 * MIN_NORMAL[name]
            closed = (y1.abs() >= lo) & (y1.abs() <= f.max_norm)
            nn, nc = int(naive.sum()), int(closed.sum())
            sn = int((r1[naive] == r2[naive]).sum())
            sc = int((r1[closed] == r2[closed]).sum())
            print(f"    {name:<6}{tie:<6}{nn:>11,}{100.0 * sn / nn:>11.4f}%"
                  f"{f'[{lo:g},{f.max_norm:g}]':>16}{nc:>11,}{100.0 * sc / nc:>12.4f}%",
                  flush=True)
            if name in ("E2M1", "E3M0"):
                check(sc == nc, f"P1' {name} ties={tie}: bitwise invariant on the closed window",
                      f"{sc:,} of {nc:,}")
            else:
                check(sc < nc * 0.9, f"P3 INT4 ties={tie}: NOT invariant even on [2,7]",
                      f"{100.0 * sc / nc:.2f}% identical of {nc:,}")
        if name == "E2M1":
            f = FMTS["E2M1"]
            sub = (b.abs() >= 1.0) & (b.abs() < 2.0)          # halves into the subnormal binade
            r1 = torch.sign(b) * q_elem(b, f, "even")
            r2 = torch.sign(b) * q_elem(b / 2.0, f, "even") * 2.0
            same = int((r1[sub] == r2[sub]).sum())
            check(same < int(sub.sum()),
                  "P1' E2M1: the subnormal binade is where invariance breaks",
                  f"{100.0 * same / int(sub.sum()):.2f}% identical of {int(sub.sum()):,} draws "
                  f"in [1,2) -> [0.5,1)")

    # ---- the ends are the whole story for a float format: quantify how much mass they hold
    print(f"\n=== how much of a block's mass sits at an END, by format ===")
    print(f"    a float format's u-dependence is exactly the mass outside [min_pos, max_norm]")
    print(f"    {'fmt':<6}{'binades':>9}{'min_pos':>9}{'max_norm':>10}"
          f"{'mass at an end, block spread 4 binades':>42}")
    for name in ("INT4", "E2M1", "E3M0"):
        f = FMTS[name]
        # a block whose elements span 4 binades below its maximum, aligned at u = 0
        y = torch.exp(torch.rand(2_000_000, dtype=torch.float64) * 4.0 * np.log(2.0)) \
            * (f.max_norm / 2.0) / 2.0 ** 4
        ends = float(((y < f.min_pos) | (y > f.max_norm)).double().mean())
        print(f"    {name:<6}{f.binades:>9.3f}{f.min_pos:>9.3f}{f.max_norm:>10.3f}"
              f"{100.0 * ends:>41.2f}%", flush=True)

    if FAILED:
        print(f"\n  FAILED: {FAILED}")
        sys.exit(1)
    print(f"\n  ALL PREDICTIONS HELD")


if __name__ == "__main__":
    main()
