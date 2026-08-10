"""C: rebuild the silicon cost table around what survived, not around phi.

The published cost table compared phi (degree 2) against the plastic number (degree 3) and a
degree-4 ratio, on the premise that phi is the 4-bit winner. Three families later, phi is NOT the
4-bit winner in general -- Pythia picks supergolden -- while plastic at 5 bits and shift at 3 bits
hold on all three. So the cost question has changed: it is no longer "what does climbing to phi
cost" but "what does the SURVIVING ladder cost against the trivial one".

WHAT A MULTIPLY-FREE LADDER COSTS. A ratio r that is the root of a monic integer polynomial
    r^d = c_{d-1} r^(d-1) + ... + c_0
lets multiplication by r be a shift-and-add recurrence on the coefficient vector. The number of
ADDERS is the number of non-zero, non-power-of-two coefficients in that recurrence; the register
count scales with the degree d.

    shift     r = 2        r^1 = 2                 degree 1   0 adders
    phi       r = 1.618    r^2 = r + 1             degree 2   1 adder
    plastic   r = 1.3247   r^3 = r + 1             degree 3   1 adder
    supergold r = 1.4656   r^3 = r^2 + 1           degree 3   1 adder
    deg-4     r = 1.1787   r^4 = r^3 + 1           degree 4   3 adders  (measured earlier)

This script states the recurrences, verifies each one numerically against the actual root, and
counts the operations -- so the cost claim rests on the algebra rather than on a remembered table.
The FPGA numbers from the earlier synthesis are quoted where they exist and are labelled as
measured; nothing new is synthesised here.
"""
import numpy as np

# Coefficients are LOW-ORDER FIRST: r^d = sum_i poly[i] * r^i.
# The first version guessed these and two were wrong -- plastic had its coefficients reversed,
# and deg4's polynomial was invented outright (r^4 = r^3 + 1 has no root at 1.1787). The root
# check below caught both; these are now the minimal monic integer polynomials found by search.
LAD = {
    "shift":     dict(r=2.0,                poly=[2],              expr="r = 2"),
    "phi":       dict(r=(1 + 5 ** 0.5) / 2, poly=[1, 1],           expr="r^2 = 1 + r"),
    "supergold": dict(r=1.465571231876768,  poly=[1, 0, 1],        expr="r^3 = 1 + r^2"),
    "plastic":   dict(r=1.324717957244746,  poly=[1, 1, 0],        expr="r^3 = 1 + r"),
    "deg4":      dict(r=1.178724176,        poly=[1, 1, 1, -1],    expr="r^4 = 1 + r + r^2 - r^3"),
}

# Measured by nextpnr-xilinx on xc7a200t, median of five placement seeds. Logs on disk in
# fpga/phiscale/: 247.10 -> cs_phi32_4.log, 231.21 -> cs_plas32_3.log, 184.98 -> cs_d4_32_3.log.
# (I once labelled these unsourced after searching for the wrong filenames; that was wrong.)
FPGA = {"phi": (223, 192, 247.10), "plastic": (228, 200, 231.21), "deg4": (469, 320, 184.98)}

print("  ladder      recurrence                    deg  adders  root check      LUT   reg    Fmax")
for k, d in LAD.items():
    r, poly = d["r"], d["poly"]
    deg = len(poly)
    # verify: r^deg == sum poly[i] * r^i   (poly listed low-order first)
    lhs = r ** deg
    rhs = sum(c * r ** i for i, c in enumerate(poly))
    err = abs(lhs - rhs)
    adders = max(0, sum(1 for c in poly if c) - 1) if deg > 1 else 0
    f = FPGA.get(k)
    fs = f"{f[0]:>7}{f[1]:>6}{f[2]:>8.2f}" if f else f"{'-':>7}{'-':>6}{'-':>8}"
    print(f"  {k:11} {d['expr']:28} {deg:>3}{adders:>8}   {err:.2e}   {fs}")

print("\n  What the surviving result actually needs\n")
print("    3 bits -> shift      degree 1, ZERO adders  -- the trivial ladder wins outright")
print("    5 bits -> plastic    degree 3, ONE adder    -- 228 LUT / 200 reg / 231 MHz measured")
print("    4 bits -> model-dependent (phi or supergolden), both ONE adder")
print()
print("  Consequence for the node. The two budgets that hold across three families ask for")
print("  exactly two hardware modes: a bare shifter at 3 bits, and a one-adder degree-3")
print("  recurrence at 5 bits. Phi is NOT required by anything that survived -- it appears only")
print("  in the 4-bit case, which is model-dependent, and supergolden costs the same one adder")
print("  there. So a node that implements shift plus ONE degree-3 recurrence covers every")
print("  budget whose winner replicates, and phi's degree-2 rung buys nothing that is robust.")
print()
print("  The degree-4 rung remains the cliff: 3 adders, 469 LUT, 2.1x the area of degree 3 and")
print("  Fmax down to 185 MHz. Nothing in the surviving results asks for it.")

print("\n  Cost of the choice at 5 bits (the robust fine-budget winner), from measurement:")
p, s = FPGA["plastic"], FPGA["phi"]
print(f"    plastic vs phi:  LUT {p[0]}/{s[0]} = {p[0]/s[0]:.3f}x,  "
      f"reg {p[1]}/{s[1]} = {p[1]/s[1]:.3f}x,  Fmax {p[2]:.1f}/{s[2]:.1f} = {p[2]/s[2]:.3f}x")
print("    i.e. the ladder that wins at 5 bits costs 2.2% more area and 6.4% less Fmax than the")
print("    one that does not replicate. That is the whole price of using the surviving rung.")
