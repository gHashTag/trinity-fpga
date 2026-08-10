# The block axis, attacked a second way, and still lost

The first attempt on the block axis put TNF4 there -- a ternary-exponent float,
which pays a packing remainder because `3^E` never divides `2^k`, using seven of
eight magnitudes. MXFP4 won, 21.94 against 36.72.

A geometric ladder pays no such remainder: eight magnitudes are eight
magnitudes, exactly as E2M1 has eight. And our own closed form made a prediction
for this axis: measuring the within-block distribution over 16,304,520 values
gave `r* = 1.3308` at eight magnitudes -- within 0.5% of the plastic number, a
degree-3 rung of our own hierarchy.

Protocol identical to the first attempt: K=32 along the contraction axis, E8M0
shared scale, SmolLM2-135M, 40 windows of 2048. Baseline 14.4874, reproducing
the earlier run's baseline exactly.

| element, 8 magnitudes | span | ppl |
|---|---|---|
| **MXFP4 (E2M1)** | 12.00x | **22.4998** |
| supergolden 1.4656 | 9.91x | 23.3582 |
| phi 1.6180 | 17.94x | 39.0928 |
| plastic 1.3247 | 5.40x | 39.6125 |
| **r\* = 1.3308, what the law predicts** | 5.56x | **37.0594** |
| degree 4, 1.1787 | 2.68x | 9779.34 |

**MXFP4 wins, and the law's own prediction is close to the worst choice.**

## Two findings, and the second is about us

**The block axis stays lost.** No rung of the hierarchy beats E2M1 there. The
best of them, supergolden, is 3.8% behind. The stop-rule on publication is not
lifted by this measurement; it is confirmed by it.

**The closed form does not transfer to the block axis.** T33 was validated on
per-channel scaling, where a channel holds thousands of weights, and it
transfers across models -- SmolLM2 and Qwen agree to four decimals at eight
bits. On blocks of 32 it fails, and not marginally: it selects `r*=1.3308`,
which measures 37.06 against the 23.36 of the ladder it ranks worse.

Perplexity is not even monotone in `r` here: 39.09, 23.36, 39.61 as the ratio
falls through phi, supergolden, plastic. A model whose predictions are smooth
cannot describe a response that is not.

The reason is structural. The form charges clipping at `E[x^2 1{x<t}]`, the
weight's own squared magnitude, which is right when a scale is shared by
thousands of weights and the clipped ones are a small tail. A block of 32 shares
one scale; killing its small elements removes a large fraction of that block's
contribution, and the loss is not the sum of their squares. **The scope of T33
is per-channel scaling, and it must be stated there rather than assumed
general.**

## What this changes

E2M1's levels are `0, 0.5, 1, 1.5, 2, 3, 4, 6`. It is not a geometric ladder at
all -- its successive ratios are `2, 1.5, 1.33, 1.5, 1.33, 1.5` -- and that
mixture is what beats every constant-ratio ladder here. On an axis where the
span within a block is short and the elements are few, a format that spends
fine steps at the top and coarse ones at the bottom does better than one that
spends the same ratio everywhere.

That is worth stating plainly because it is the strongest thing the competition
has and we have now confirmed it twice, by two different attacks of our own.
