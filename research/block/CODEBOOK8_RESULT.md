# The 8-bit test broke my own corollary — result of the registered prediction

Scored against `PREREG_codebook8_2026-08-12.md`, committed before the run.

## Result

| codebook | width | D (counted) | N* (measured) | N*/D |
|---|---|---|---|---|
| E3M0 | 4 | 28.0 | 36.7 | 1.31 |
| E2M1 | 4 | 46.9 | 49.0 | 1.05 |
| int4 | 4 | 51.2 | 53.0 | 1.04 |
| NF4 | 4 | 53.1 | 54.3 | 1.02 |
| **E5M2** | 8 | 128.7 | 388 | **3.01** |
| **E4M3** | 8 | 256.5 | 530 | **2.07** |
| **int8** | 8 | 869.8 | 598† | **0.69** |

† extrapolation past the usable sweep, declared as such before the run.

**ORDINAL HELD** — across seven codebooks, two element widths, and a 31× range
of D.

**CARDINAL FAILED on all three 8-bit codebooks.** The registration named the
band 1.0–1.35. Measured 3.01, 2.07, 0.69.

## The failure is systematic, which makes it informative

D moves **6.8×** across the 8-bit row; N* moves **1.5×**. The crossover is far
less sensitive to corner density than `N* ≈ D` assumed.

**In hindsight the identification was a heuristic and never a derivation.**
`thm:latticeexp` puts the crossover where `g''h²/24` overtakes
`c₋c₊h/(8(c₋+c₊))` — a ratio of local *slopes* to *curvature*. Corner spacing
enters that ratio but does not determine it, and a codebook with many levels has
**small corner slopes as well as closely spaced corners**. The two effects pull
opposite ways. That is why the ratio falls as D rises, monotonically, across all
seven rows: 1.31, 1.05, 1.04, 1.02, 3.01→2.07→0.69 within each width class.

## One reading below the theorem's own floor

int8 gives **p = 0.490** on its coarsest doubling. The theorem admits nothing
below 1. Neither regime describes it: with 255 levels the error surface is nearly
flat in the scale, so at h = 1/16 the lattice minimum sits far from t* and what
is measured is the global bowl, not any local shape. Reported; nothing claimed
from it.

## Why this counts as the campaign working

The corollary was **mine**, published two iterations ago on four codebooks
spanning under 2× in D, and it was **broken by a test I registered in advance
specifically because a rule confirmed over so short a range is not yet a rule**.

> A confirmation range is part of a claim. Four points spanning 1.9× do not
> establish a law that will be read as covering 31×. State the lever, or go and
> widen it before someone else does.

The paper now carries the narrowed corollary, the falsifying table, and the
mechanism for why the strong form failed.

## Base rate, updated

| prediction | ordinal | cardinal |
|---|---|---|
| three-horn ordering | ✗ | ✗ |
| Bennett at N=2, N=4 | ✓ | ✗ |
| 4-bit codebook crossovers | ✓ | ✓ (3 of 4) |
| **8-bit width test** | **✓** | **✗ (0 of 3)** |
