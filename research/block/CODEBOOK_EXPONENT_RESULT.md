# The corner-density diagnosis generalises — result of the registered prediction

Scored against `PREREG_codebook_exponent_2026-08-12.md`, committed before the run.

## Result

| codebook | D (counted, no error evaluated) | crossover (measured) | ratio |
|---|---|---|---|
| E3M0 — pure exponent, boundaries over 6.58 oct | 28.0 | 36.7 | 1.31 |
| E2M1 — MXFP4's own | 46.9 | **49.0** | **1.05** |
| int4 — linear, boundaries bunched in log | 51.2 | **53.0** | **1.04** |
| NF4 — asymmetric, 15 distinct magnitudes | 53.1 | **54.3** | **1.02** |

**Ordinal prediction HELD**: e3m0 < e2m1 < int4 < nf4 by D, and the same by
measured crossover, on values that are distinct rather than tied.

**Cardinal did better than registered**: the file said a cardinal hit "would be
luck at this level of modelling". Three of four land within 5%. E3M0 misses by
31%, and it has the sparsest boundaries of the four — with corners that sparse,
fewer fall inside the estimation window and the local-arc picture is weaker.
Reported, not dropped.

## Two ways this nearly reported a false confirmation

**1. The discrete crossover has no resolution.** Taking "first N in a doubling
sequence with p ≥ 1.9" returns **32 for three of the four codebooks**. The
script printed `СОВПАЛО` — but only because Python's sort is stable and the
insertion order happened to match D. **That was a tie being read as an
ordering.** The interpolated crossover is what the paper reports, and it
separates 49.0 / 53.0 / 54.3 properly.

**2. The last doubling is an instrument artefact.** At a reference ladder of 256
points per binade, the N=128 grid is only 2× the reference, so its excess is
biased low and its exponent high. **All four codebooks return p ≈ 2.29 there.**
Four independent codebooks agreeing to two decimals on a physical quantity would
be extraordinary; four instruments sharing a bias is ordinary. Discarded.

> **A confirmation that arrives through a tie, or through a number four
> independent systems agree on too precisely, is the instrument talking.** Both
> traps here pointed the same way as the hypothesis, which is exactly when they
> are hardest to see.

## What it buys

`cor:designrule`: refining the scale ladder past ≈ D points per binade moves from
the O(h) regime to the O(h²) tail, so the return per doubling falls from ~50% to
~25%. **D is computable from the codebook and the weight distribution alone.**
The operating point of the scale field is set by the element codebook and can be
read off before any quantisation is run.

## Registered-prediction base rate in this campaign

| prediction | ordinal | cardinal |
|---|---|---|
| three-horn ordering | ✗ | ✗ |
| Bennett at N=2, N=4 | ✓ | ✗ |
| codebook crossovers | ✓ | ✓ (3 of 4) |
