# Every Euclidean instrument said the model got better. It got worse.

This closes a chain that ran for three passes:

- `ROTATION_VERDICT_2026-08-11.md` — a block-wise Hadamard makes perplexity
  **8.24 % worse**.
- `WHY_ROTATION_HURTS_2026-08-11.md` — …while **reducing** total weight
  quantisation error by 3.31 %, and no weight-magnitude statistic explains it.
  The proposed mechanism was refuted by sign.

Two further mechanisms were proposed and measured, and both failed:

**The error lands on channels that matter** (`where_error_lands.py`). Weighting
the per-input-channel error by AWQ's own importance — mean activation magnitude
from forward hooks, spread 21.7× between the top channel and the median — the
weighted error still *falls*, by 2.72 % against the plain 3.31 %. Directionally
there is a hint (the reduction is smaller when importance is respected), but a
smaller reduction cannot produce an increase. Both controls held: uniform
weighting reproduced the plain number exactly, and a shuffled importance vector
stayed at −3.29 %.

**The logits shrink.** Both arms shrink almost identically against fp32 — logit
standard deviation ratio 0.9320 unrotated against 0.9273 rotated. Not it either.

## What it actually is

Four instruments on the same intervention, same model, same inputs
(`metric_disagreement.py`):

| instrument | unrotated | rotated | change |
|---|---:|---:|---:|
| weight L2 | 5.5478e+04 | 5.3643e+04 | **−3.31 %** |
| layer-output L2 | 8.7916e+06 | 7.0388e+06 | **−19.94 %** |
| logit L2 | 5.7523e+09 | 3.0997e+09 | **−46.11 %** |
| KL(fp32 ‖ quantised) | 0.42415 | 0.48975 | **+15.47 %** |
| perplexity | 26.333 | 28.429 | **+7.96 %** |

**Every Euclidean measure says the rotated model is closer to fp32 — the logits
by nearly a factor of two — and KL says it is further away.** Perplexity follows
KL, which is not a coincidence: cross-entropy against the true tokens is the fp32
cross-entropy plus KL(fp32 ‖ quantised) up to a term that does not depend on the
approximation. So the check is arithmetic rather than rhetorical:

    exp(ΔKL) = 1.0678     measured perplexity ratio = 1.0796

85 % of the perplexity change is accounted for by the KL change alone.

The disagreement is not inside the network. It is between two ways of measuring
distance between distributions, and only one of them is what a language model's
quality is made of. An L2 error of a given size costs nothing if it sits on
tokens that already had no probability, and costs a great deal if it sits on the
few that did. Rotation makes the error smaller and moves it onto the probability
mass.

## Why this matters beyond one rotation

`conformance/BLOCK_AXIS_METRIC.md` argued on general grounds that `M_eff` — a
mean-relative-error statistic — is the wrong instrument for block formats.
`BLOCK_AXIS_CLOSED_2026-08-10.md` observed that squared error and perplexity are
"nearly unrelated". `LADDER_FORMULA_FAILS_4BIT` found MSE orderings inverting.

This is the same fact in its sharpest available form. Not a loose proxy, not a
disagreeing ordering: **one intervention, four instruments, three of them wrong
by sign, and the errors are large** — a 46 % improvement in logit L2 accompanying
an 8 % degradation. Any comparison of quantisation schemes reported in squared
error has a measured counterexample in this repository.

It also explains, without needing a new theory, why the block line kept finding
MSE-optimal codebooks that lost on perplexity. Lloyd-Max minimises squared error.
That is the wrong objective, and it was the wrong objective every time.

## What is still not known

Why a Hadamard mix moves error onto the probability mass is not established here.
The natural next question is whether it is the *correlation* the transform
induces: quantising in the rotated basis makes the errors on the 32 coordinates
of a block dependent, and dependent errors do not average away across a
contraction the way independent ones do. That predicts the effect should scale
with block width and vanish at K = 1. Measurable, unmeasured, written down as a
hypothesis — the third one in this chain, and the previous two were wrong.

---

*Scope: one model (SmolLM2-135M), one codebook (MXFP4 E2M1 + E8M0), one rotation.
The four-instrument table uses 4 windows so that all instruments read identical
inputs; the perplexity direction matches the 40-window measurement in
`ROTATION_VERDICT_2026-08-11.md` (+8.24 % there, +7.96 % here).*
