# Pre-registration: is the sensitivity ratio a model property or an interaction?

Committed **before** the run.

## Why

`prop:sensitivity` was measured on ONE encoder (MXFP4's reference rule). It says
the perturbation is constant to 1.02× across four models while the damage spans
3.77×, so the spread is sensitivity. That statement has no scope yet: the ratio
might be a stable property of each model, or an interaction between model and
format that happens to look stable at one point.

Four models × four arms (floor, argmin, 2^(k/3), 2^(k/8)) settles it.

## The theory's own prediction, which contradicts how I printed it yesterday

If the damage is second order in the perturbation —
`Δppl ≈ ½ vec(ΔW)ᵀ H vec(ΔW)` — then damage grows as the **square** of
‖ΔW‖, so the model invariant is

    S₂ = Δppl / (‖ΔW‖/‖W‖)²

and **not** the ratio `Δppl / (‖ΔW‖/‖W‖)` printed in iteration 111. That ratio
was a diagnostic of anti-correlation, not a candidate invariant, and stating it
as though it were one would be a units error of exactly the kind this campaign
keeps finding.

## Registered predictions

1. **S₂ is more nearly constant per model across the four arms than S₁.** If the
   second-order picture holds, S₂'s within-model spread should be materially
   tighter.
2. **The within-model spread of S₂ should be smaller than the between-model
   spread**, otherwise "sensitivity is a model property" is not a statement.
3. **Ordinal**: the between-model ordering of S₂ must be
   `gpt2 < qwen < smollm2 < pythia`, matching the damage ordering, on every arm.

**Falsified if** S₂ varies as much within a model as between models — in which
case `prop:sensitivity` describes a model-format interaction and must be narrowed
to the encoder it was measured on.

## A caution stated in advance

MXFP4 at 4.25 bits is not a small perturbation: ‖ΔW‖/‖W‖ ≈ 11.7%, and
perplexity rises by up to 76%. A second-order expansion has no right to hold at
that amplitude, so **prediction 1 may fail for a reason that has nothing to do
with the model-versus-interaction question.** If S₂ is no better than S₁, the
honest reading is that the quadratic regime does not reach this far, not that
sensitivity is unreal.

## Base rate

| prediction | ordinal | cardinal |
|---|---|---|
| three-horn ordering | ✗ | ✗ |
| Bennett at N=2, N=4 | ✓ | ✗ |
| 4-bit codebook crossovers | ✓ | ✓ (3 of 4) |
| 8-bit width test | ✓ | ✗ |
| block-outlier explanation | ✗ (reversed) | ✗ |
