#!/usr/bin/env python3
"""device_fit.py — how many layers fit, and which resource runs out first.

Two claims for the golden lattice were withdrawn on 2026-08-18: the area
advantage does not survive giving the competitor its DSP blocks
(fpga/phiscale/ON_A_PART_WITH_DSP.md), and the exactness advantage does not
survive giving it round-to-nearest (conformance/lattice_accumulation.py).

What was left was a niche: "zero DSP is the whole product where DSPs are absent
or exhausted". This tests that sentence the way a device does -- by counting how
many layers fit before something runs out.

The answer is narrower than the sentence. On every part measured, LUTs run out
long before DSPs do, so the multiplier arm fits MORE layers, not fewer. The
niche exists only when something else has already taken most of the DSPs
without taking the LUTs.

Costs are measured with yosys 0.65, `synth_xilinx -family xc7`, N=16, ACC=16,
ROWS=16, reading only the LAST stat block. Change them here when the RTL
changes, and the conclusion recomputes.

Nothing here touched silicon. `synth_xilinx` targets a FAMILY, not a device --
it has no device option -- and no place-and-route ran, so these are
post-synthesis cell counts, not implemented ones.
"""

import sys

# arm -> (LUT, DSP48, FF) per layer
# Corrected 2026-08-18. The published figures here were inflated by exactly 3.0
# and the DSP count by 3: `synth_xilinx` prints its own statistics before the
# script's explicit `stat`, and the extraction summed LUT lines across every
# block in the log. Re-measured from the LAST block only:
#
#   published   5133 / 0 / 1767      true   1711 / 0 /  723
#   published   3825 / 3 / 1022      true   1275 / 1 /  346
#   published   5607 / 0 / 1022      true   1869 / 0 /  346
#
# `tern_layer_mem` contains exactly one 16x16 multiply, which fits ONE DSP48E1
# (25x18). Three was never obtainable from this RTL at any fan-in, and nothing
# in the original run questioned it.
#
# The exchange rate below survives the correction unchanged, because numerator
# and denominator were inflated by the same factor.
ARMS = {
    "phi": (1711, 0, 723),
    "multiplier": (1275, 1, 346),
    "multiplier, DSP denied": (1869, 0, 346),
}

# part -> (LUT, DSP48, FF)
PARTS = [
    ("XC7A35T", 20800, 90, 41600),
    ("XC7A100T", 63400, 240, 126800),
    ("XC7A200T", 134600, 740, 269200),
    ("XC7K325T", 203800, 840, 407600),
]


def fits(part, arm):
    _, L, D, F = part
    lut, dsp, ff = ARMS[arm]
    lut_bound = L // lut
    dsp_bound = (D // dsp) if dsp else None
    ff_bound = F // ff
    n = min(x for x in (lut_bound, dsp_bound, ff_bound) if x is not None)
    binding = "LUT" if n == lut_bound else ("DSP" if dsp_bound == n else "FF")
    return n, lut_bound, dsp_bound, ff_bound, binding


def main():
    print(__doc__.split("\n\n")[0])
    print()
    print(f"  {'part':<11} {'arm':<24} {'LUT':>5} {'DSP':>5} {'FF':>5} {'fits':>5}  binds")
    for part in PARTS:
        for arm in ARMS:
            n, lb, db, fb, binding = fits(part, arm)
            dbs = str(db) if db is not None else "-"
            print(f"  {part[0]:<11} {arm:<24} {lb:>5} {dbs:>5} {fb:>5} {n:>5}  {binding}")
        print()

    print("On every part here the multiplier arm is LUT-bound, never DSP-bound,")
    print("and fits MORE layers than the phi arm. The phi arm only beats a")
    print("multiplier that has been DENIED its DSPs.\n")

    print("So the remaining claim has a precise condition. For the multiplier to")
    print("become DSP-bound first, this share of the part's DSPs must already be")
    print("spent by something else -- and that something must use DSPs WITHOUT")
    print("using LUTs, or it would have taken the LUTs the layer needs:\n")
    print(f"  {'part':<11} {'phi fits':>9} {'DSPs that may remain':>22} {'already spent':>14}")
    for name, L, D, F in PARTS:
        phi_fit = L // ARMS["phi"][0]
        remain = (phi_fit - 1) * ARMS["multiplier"][1]
        print(f"  {name:<11} {phi_fit:>9} {remain:>22} {1 - remain / D:>13.1%}")
    print()
    print("86% to 90% of the DSPs already gone. That is a real configuration --")
    print("fixed-function filters, FFT, mixers -- and it is narrow, and it is the")
    print("only one left standing.")
    print()
    print("What this does NOT establish: one layer shape, one fan-in, one set of")
    print("measured costs. A different layer -- wider accumulator, more rows, a")
    print("different scale exponent -- moves every number here, which is why the")
    print("costs are constants at the top of this file rather than prose.")


if __name__ == "__main__":
    sys.exit(main())
