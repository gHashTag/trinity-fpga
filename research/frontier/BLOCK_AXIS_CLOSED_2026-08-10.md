# The block axis is closed, and not because we lost it

Three attacks have now failed on the block axis: TNF4 (a ternary-exponent float,
which pays a packing remainder), constant-ratio ladders from the multiply-free
hierarchy, and two-segment ladders built to imitate E2M1's non-constant spacing.
A fourth attempt is not warranted, and the reason is a measurement rather than
fatigue.

## The bound

Lloyd-Max on the within-block distribution (18,850,950 values, block of 32,
E8M0 shared scale) gives the eight-level codebook that minimises squared error.
It is not multiply-free and not a ladder. It is the ceiling.

| element, 8 magnitudes | squared error | x bound | ppl (40 windows) |
|---|---|---|---|
| **Lloyd-Max, the optimum** | 1.341e-03 | **1.00x** | **22.2976** |
| **MXFP4 (E2M1)** | 2.007e-02 | 14.97x | **22.4998** |
| supergolden/plastic top4 | 2.068e-03 | 1.54x | 27.3079 |
| supergolden/plastic top3 | 2.116e-03 | 1.58x | 30.8306 |
| supergolden/deg4 top4 | 2.355e-03 | 1.76x | 34.4941 |
| phi/supergolden top2 | 2.749e-03 | 2.05x | 38.6471 |
| shift/phi top2 | 5.695e-03 | 4.25x | 49.6820 |
| phi/plastic top2 | 2.823e-03 | 2.11x | 55.4495 |

Baseline fp32 14.4874, reproduced exactly across all three block runs.

## Two findings, and the second is the one that matters

**The optimum beats MXFP4 by 0.9%.** Not 20%, not 5% -- nine tenths of one
percent, and the optimum is not implementable. Whatever an element codebook can
contribute on this axis has already been contributed. **No eight-level element
format will take the block axis from MXFP4, because the best possible one does
not.**

> **WITHDRAWN 2026-08-11 — see `block/BLOCK_AXIS_NOT_CLOSED_2026-08-11.md`.**
> Both halves fail. "The best possible one" was the squared-error optimum, and
> squared error is the wrong optimum here — one intervention moved weight L2 by
> −3.31 %, logit L2 by −46.11 % and perplexity by +7.96 %
> (`block/METRIC_DISAGREEMENT_2026-08-11.md`). And a counterexample was published
> in 2023: **NF4**, the 4-bit NormalFloat from QLoRA, beats MXFP4 in this harness
> by **−6.50 % pooled out of sample** (95 % CI [−7.30, −5.70], t = −15.60,
> p = 2e-28, better in 95 of 100 windows) at strictly equal budget, fitted to a
> Gaussian prior rather than to any checkpoint here. It was never run until
> today. A three-model joint fit also beats MXFP4 on a held-out family by
> −1.31 % (p = 3.1e-07). **The measured table above is unaffected — only this
> conclusion is.**

**Squared error and perplexity are nearly unrelated here.** Lloyd-Max improves
squared error 14.97-fold and perplexity by 0.9%. Worse, the ranking inverts:
every two-segment ladder beats MXFP4 on squared error, by factors of 3 to 10,
and every one of them loses on perplexity, by 21% to 146%. The correlation is
not weak. It points the wrong way.

**T36 (the block axis is not an element-format problem).** On short blocks with
a shared scale, the element codebook minimising squared quantisation error is
not the one minimising perplexity, and the gap between the best achievable
codebook and a deployed one is a fraction of a percent. Effort spent designing
element formats for this axis cannot recover more than that fraction.

## Why squared error misleads here specifically

A block of 32 shares one scale. Squared error counts a clipped small weight at
its own magnitude, which is small -- so a codebook that packs its levels near
the top of the range scores well, having placed its resolution where the mass
is. But the network does not read a block's weights independently: they are
summed against activations, and a codebook that represents the top of every
block finely while collapsing its lower two-thirds destroys the block's ability
to represent a direction, not merely its magnitudes.

E2M1 spends `0, 0.5, 1, 1.5, 2, 3, 4, 6` -- a 12x span with levels at both ends.
It scores badly on squared error precisely because it refuses to concentrate,
and it wins on perplexity for the same reason.

## What this means for the stop-rule

The owner's condition is that the paper does not publish until TNF beats MXFP4
on the block axis by measurement. That condition cannot be met by element-format
work: the ceiling is 0.9% and it is not reachable by any ladder, closed ring or
multiply-free scale. If the condition is to be met at all it must be met on a
different axis -- the scale format, the block shape, or the datapath -- and if
it is not, the honest move is to state in the paper that the block axis belongs
to MXFP4 and say why, which the measurements above now support.
