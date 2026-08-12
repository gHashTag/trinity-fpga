# Pre-registration: does the design rule survive a doubling of element width?

Committed **before** the measurement.

## Why this is the right next test

`cor:designrule` was derived and confirmed on four **four-bit** codebooks whose
corner densities span 28 to 53 per octave. That is a narrow lever — under 2×.
A rule that only holds across a 2× range of D is not obviously a rule.

Eight-bit codebooks give a 7× lever, and one that reaches 19× beyond the
four-bit range.

## Stage 1, measured first, by counting only

| codebook | levels | **D (counted)** | predicted crossover |
|---|---|---|---|
| **e5m2** — widest range, sparsest per octave | 249 | **124.7** | N ≈ 125 |
| **e4m3** — NVFP4's scale format, here as an element grid | 241 | **250.3** | N ≈ 250 |
| **int8** — densest boundaries per octave | 255 | **889.3** | N ≈ 889 |

For comparison the four-bit run gave 28.0, 46.9, 51.2, 53.1.

## The prediction

**Ordinal:** crossover must order **e5m2 < e4m3 < int8**.

**Cardinal:** the ratio crossover/D landed at 1.02–1.05 for three of four 4-bit
codebooks and 1.31 for the sparsest. If the rule is a rule, the 8-bit ratios
should sit in the same band, i.e. **roughly 1.0–1.35**.

**Falsified if** the ordering breaks, or if the ratios leave that band in a way
that tracks element width rather than D — which would say the rule is about
four-bit codebooks and `cor:designrule` needs its scope cut.

## Stated in advance, because it limits what can be claimed

**int8's crossover will be an EXTRAPOLATION, not an interpolation.** With a
reference ladder of 8192 points per binade the usable sweep tops out at the
512→1024 doubling, whose geometric midpoint is 724 — below the predicted 889.
The number for int8 is a fit extrapolated past the data and must be labelled
so wherever it appears.

**The last doubling of every sweep is discarded on principle**, not on
inspection. Iteration 106 learned this the expensive way: at a reference of 256
points/binade its N=128 grid was only 2× the reference, and all four codebooks
returned p ≈ 2.29 — four independent systems agreeing to two decimals, which is
an instrument sharing a bias and not four physical results.

## Base rate

| prediction | ordinal | cardinal |
|---|---|---|
| three-horn ordering | ✗ | ✗ |
| Bennett at N=2, N=4 | ✓ | ✗ |
| 4-bit codebook crossovers | ✓ | ✓ (3 of 4) |
