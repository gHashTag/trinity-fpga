# Placement at fixed resolution is worth 0.7% of what resolution is worth

## The question

`tab:geoscale` asks whether scale points placed geometrically (2^(k/8)) beat the
same *number* of points placed linearly in a mantissa (E4M3 — NVFP4's grid). It
answers on perplexity over 40 windows, and reports geometric winning by 8.75%
on SmolLM2 at 8 bits.

The squared-error axis carries 14.9 million blocks and had no E4M3 row at all.

## The answer on the larger sample

| scale grid, 8 bits, K=32 | smollm2 | qwen |
|---|---|---|
| E4M3 — NVFP4's grid | +19.41% | +19.38% |
| 2^(k/8) — geometric | **+19.55%** | **+19.53%** |

Both against each model's own best E8M0 encoder.

**Geometric wins on both models — by 0.14 and 0.15 points.** The sign replicates.
The magnitude does not survive the larger sample: the placement of scale points
is worth **0.7% of what the resolution is worth**.

## Why this is a gain and not a loss

Two grids with the *same* point count and *different* point placement agreeing to
within 0.7% is the sharpest available confirmation of this paper's own law —
*error is monotone in points per binade and in nothing else*. Any pair of grids
with unequal point counts confounds the two. This pair does not.

So `thm:geoscale` keeps its sign and loses its practical significance, and the
central law gains its best test. That is a good trade and the paper now makes it
explicitly.

## Bookkeeping

The `e4m3` arm is in `verify_block_rmse.py`. Note it models the *grid*, not
E4M3's finite range; the index-span measurement already established these weights
fit. NVFP4 proper also differs in block size (16, not 32) and adds a per-tensor
FP32 scale, so it spends 4.5 bits per element against this comparison's 4.25 —
which is why this is a test of point placement and not a comparison against
NVFP4.
