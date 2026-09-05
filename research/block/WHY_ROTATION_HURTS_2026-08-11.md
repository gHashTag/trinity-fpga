# The hypothesis was wrong, and the way it is wrong is the result

`ROTATION_VERDICT_2026-08-11.md` measured that a block-wise Hadamard makes block
quantisation worse in perplexity, and offered a mechanism, explicitly labelled a
hypothesis rather than a finding:

> a Hadamard mix within a 32-element block raises the typical magnitude relative
> to the block maximum that sets the shared scale, so more elements land in the
> coarse part of the codebook.

`why_rotation_hurts.py` tested it on 3,317,760 blocks across 210 layers of
SmolLM2-135M, MXFP4 E2M1 + E8M0, using the project's own quantiser. **It is
refuted, and refuted by sign.**

## The measurement

Three candidate mechanisms, each correlated against the per-block change in
relative quantisation error:

| predictor | r with Δerror | r with shuffled Δerror |
|---|---:|---:|
| H1 concentration, mean/max | **−0.4592** | −0.0006 |
| H2 E8M0 headroom, max / 2^⌈log₂max⌉ | −0.3069 | +0.0006 |
| H3 participation ratio | −0.3899 | −0.0005 |

The shuffled column is the check that the correlations are not the machinery
finding structure in noise; all three collapse to |r| < 0.001, so they are not.

Concentration does rise under rotation, by +0.0120 on average — that part of the
hypothesis holds. But its correlation with the error change is **negative**:
blocks whose concentration rises get *less* error, not more. The mechanism was
stated with the wrong sign.

The aggregate says the same thing more bluntly. Relative error rises in only
**48.0 %** of blocks — fewer than half — and the median block *improves*.

## What actually happened

| | value |
|---|---|
| total weight quantisation error, unrotated | 5.547835e+04 |
| total weight quantisation error, rotated | 5.364298e+04 |
| change | **−3.31 %** |
| perplexity, unrotated → rotated | 21.9397 → 23.7476, **+8.24 %** |

**Rotation makes the weights measurably more accurate and the model measurably
worse.** Not "nearly unrelated" — opposite in sign, on the same weights, in the
same run.

This is the strongest form of something the block line already recorded.
`BLOCK_AXIS_CLOSED_2026-08-10.md` observed that "squared error and perplexity are
nearly unrelated here", and `LADDER_FORMULA_FAILS_4BIT` found MSE ordering
inverting relative to perplexity. Those were orderings disagreeing. This is a
single intervention moving the two metrics in opposite directions by 3 % and 8 %
respectively, which is a cleaner demonstration than either.

## Consequences

**For the rotation result.** The verdict stands exactly as measured — the gap
widens — but the explanation attached to it was wrong and is withdrawn here
rather than quietly amended. The mechanism is not a weight-magnitude statistic,
because every weight-magnitude statistic says rotation helped.

**For the metric.** Any comparison on this axis reported in MSE is not merely
weakly informative, it can point the wrong way. `conformance/BLOCK_AXIS_METRIC.md`
argued that `M_eff` is the wrong instrument for block formats on general grounds;
this is the concrete case where following MSE would have produced the opposite
conclusion from the truth.

**For what to test next.** The remaining explanation is that rotation changes
*where* the error lands rather than how much there is. Unrotated, quantisation
error concentrates on the large weights in a block and leaves the small ones
nearly exact; a Hadamard mix spreads it evenly across all 32 coordinates. If a
model's sensitivity is concentrated on particular input channels — which is what
the activation-outlier literature behind AWQ and QuaRot asserts — then spreading
error onto sensitive channels costs more than the 3.31 % MSE reduction buys.

That is the next hypothesis and it is *not* established here. The test it
implies: correlate the per-input-channel change in quantisation error with the
per-channel activation magnitude measured by forward hooks, which
`sensitivity_profile.py` and `importance_diagnostic.py` already know how to
collect. If the correlation is absent, this explanation goes the way of the one
above it.

---

*Scope: one model, one codebook, weights only. The per-block analysis explains
the variation in the weight-error change; the perplexity consequence is measured
separately in `ROTATION_VERDICT_2026-08-11.md` and is not derived from it.*
