# The prior art on learned 4-bit codebooks, and where our result sits in it

A codebook optimised against KL divergence reaches 20.2586 perplexity on
SmolLM2-135M against MXFP4's 21.9397 — 7.66 % in sample, 8.66 % on held-out
windows with `t(39) = −12.51`, better in 39 of 40 windows. Before that is called
new, the field has to be read. It was.

## What everyone else optimises

| work | objective | scale | baseline beaten | margin |
|---|---|---|---|---|
| **BOF4** ([arXiv:2505.06653](https://arxiv.org/abs/2505.06653)) | **MSE and MAE**, via EM on Lloyd's algorithm | real-valued block absmax | NF4 8.53 → **8.43** (Llama-3.1 8B, block 64) | ≈1.2 % |
| **any4** ([arXiv:2507.04610](https://arxiv.org/pdf/2507.04610)) | k-means, i.e. **squared error**, per row | per-row | learned vs fixed 4-bit | — |
| **QAM-W** ([arXiv:2605.26339](https://arxiv.org/abs/2605.26339)) | Lloyd-Max on a unit circular Gaussian, 2-D pairs + Hadamard + activation-aware scaling | per-channel | within ±0.4 % of BF16 | — |
| **TurboQuant** | residual Lloyd-Max + rotation | — | KL 0.002 nats at 4+4 bits | — |
| **LO-BCQ** ([arXiv:2502.05376](https://arxiv.org/pdf/2502.05376)) | block clustering, squared error | block | W4A4 | — |

**Every one of them minimises squared error**, in one estimator or another —
Lloyd's algorithm, k-means (which is Lloyd's), or an EM derivation of it. BOF4 is
the strongest of them and its contribution is a *better estimator of the same
objective*: an EM formulation, a signed-absmax normalisation, and an
outlier-preserving hybrid. The objective itself is never questioned.

## Which is the thing this repository measured to be wrong

`METRIC_DISAGREEMENT_2026-08-11.md`: one intervention, four instruments.

| instrument | change |
|---|---:|
| weight L2 | **−3.31 %** |
| layer-output L2 | **−19.94 %** |
| logit L2 | **−46.11 %** |
| KL(fp32 ‖ quantised) | **+15.47 %** |
| perplexity | **+7.96 %** |

Every Euclidean measure said the model got closer to fp32 — the logits by nearly
a factor of two — and it got worse. `exp(ΔKL) = 1.0678` against a measured
perplexity ratio of `1.0796`, so 85 % of the degradation is the KL change alone.

That is the gap in the literature stated as a measurement rather than an opinion:
**a better estimator of squared error is a better estimator of the wrong
quantity.** BOF4 improving NF4 by 1.2 % on MSE and our codebook improving MXFP4
by 7.66 % on KL are not the same kind of step, and the second is available to
anyone who changes the objective.

## What is honestly comparable, and what is not

**Not comparable as stated.** BOF4's 8.53 → 8.43 is Llama-3.1 8B at block 64
with a real-valued absmax scale. Ours is SmolLM2-135M at block 32 with an E8M0
power-of-two scale. Different model, different block, different scale *kind* —
and by `SCALE_PHASE_THEOREM_2026-08-11.md` a real-valued scale has no headroom
phase at all, so BOF4's setup is free of an effect ours has to control for.

**The right opponent for an element-codebook claim is NF4/BOF4, not MXFP4
alone.** MXFP4 is a deployed hardware format; NF4 and BOF4 are the state of the
art in *learned* element codebooks, which is the class our result belongs to.
Beating MXFP4 by 7.66 % says nothing about whether we beat BOF4, and that
comparison has not been run.

**The scale axis is a separate claim and stays separate.** `SCALE_FRONTIER`'s
φᵏ 4b/32 result is about the shared scale; nothing here touches it.

## What would make the claim complete

1. **Run BOF4 and NF4 in our harness**, same model, same block, same scale rule.
   Until then "a KL-optimised codebook beats the state of the art" is unearned —
   what is earned is "beats MXFP4 and the squared-error optimum, under one
   convention, on one model".
2. **Optimise BOF4's own codebook against KL** in the same harness. If the KL
   objective lifts BOF4 too, the contribution is the objective and it generalises;
   if it does not, the contribution is our particular codebook and is much
   narrower.
3. **A second model.** The transfer test is in flight and unreturned.

## The stop-rule is untouched

Nothing here argues for publication. It records that the closest prior art
optimises a quantity this repository has measured to point the wrong way, that
the comparison against that prior art has *not* been run, and that the honest
scope of the current result is one model, one block size, one scale convention.

---

*External figures are from the linked papers, read on 2026-08-11 rather than
cited from memory; BOF4's objective and baselines were confirmed from the full
text, not the abstract, after the abstract proved insufficient.*
