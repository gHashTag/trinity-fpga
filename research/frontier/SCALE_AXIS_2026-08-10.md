# The scale axis: a phi-power block scale beats a power-of-two one at equal bits

The block axis was closed on the element format: the optimal eight-level
codebook beats E2M1 by 0.9%, so no element format takes it. The scale had never
been varied. It is one value per thirty-two weights, so its cost is amortised
thirty-twofold -- exactly the regime where a finer grid is affordable.

## The bit accounting comes first

E8M0 gives the scale eight exponent bits. The range actually needed is far
smaller: measured over 3,317,760 block scales, SmolLM2-135M spans 8.32 binades
and Qwen2.5-0.5B spans 9.12.

| grid | steps needed (SmolLM2 / Qwen) | bits |
|---|---|---|
| `2^k` | 8.3 / 9.1 | **4** |
| **`phi^k`** | 12.0 / 13.1 | **4** |
| `sqrt2^k` | 16.6 / 18.2 | 5 |
| `2^(k/4)` | 33.3 / 36.5 | 6 |

So at four exponent bits the choice is between `2^k` and `phi^k`, and `2^k`
wastes half its codes while `phi^k` uses twelve of sixteen with half the step.

## Measured, K=32, E2M1 elements, 40 windows

| scale grid | bits | SmolLM2 (fp32 14.4874) | Qwen (fp32 12.2277) |
|---|---|---|---|
| `2^k` (the MX spec's) | 4 | 22.4998 | 14.9447 |
| **`phi^k`** | **4** | **21.3545** (+5.09%) | **14.8512** (+0.63%) |
| `sqrt2^k` | 5 | 21.8960 | 14.7456 |
| `plastic^k` | 5 | 22.7625 | 15.0333 |
| `2^(k/4)` | 6 | 24.0791 | **14.4328** (+3.43%) |

**At equal bits `phi^k` beats `2^k` on both models.** That is the result, and it
is the first thing measured tonight that improves on the MX specification's own
choice without paying for it.

## What was refuted along the way

The first reading of the SmolLM2 column was that `phi` is the optimum of the
scale grid: the response there is non-monotone, worsening for grids finer than
`phi`, with `2^(k/4)` falling below plain `2^k`. Qwen refutes it. There the
response is monotone in granularity and the finest grid wins.

So `phi` is optimal on one model and merely better-than-two on the other, and
the magnitude differs eightfold between them. What replicates is the sign, not
the size, and not the claim of optimality. Stated as a law it would be the third
explanation tonight to die on the second model.

## What this is, and what it is not

It is **not** TNF beating MXFP4. It is MXFP4 improved by replacing its scale
with ours: the element format stays E2M1 and only the shared exponent's base
changes. The honest description is a contribution to the microscaling family
rather than a defeat of it, and the stop-rule's condition -- that our format beat
MXFP4 on this axis -- is still not met.

It is also the only place on the block axis where anything of ours has helped,
after four attempts on the element format that did not. That is worth knowing:
the axis has two halves and we had been attacking the closed one.

## Why a phi scale is ours specifically

On a binary datapath a `2^k` scale is a shift and a `phi^k` scale is not. On the
datapath this paper builds, `phi^k` is k Fibonacci steps and needs no
multiplier, while any non-dyadic scale would need one. The grid that helps here
is free for us and costs a multiplier for everyone else, which is the first
time that asymmetry has pointed our way in a measurement.
