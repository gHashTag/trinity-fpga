# The 4-bit landscape in August 2026, and where our results actually sit

`LITERATURE_SCAN_2024_2026.md` carries 32 mentions of posit and 21 of takum
against 2 of MXFP4 and none of NVFP4. That is the opposition we win against, not
the opposition that threatens us. This note records the second kind, from
sources outside the project, and states plainly which of our results survive
contact with it.

## The deployed formats

| | element | block | scale | scale cost |
|---|---|---|---|---|
| **MXFP4** (OCP) | E2M1 | 32 | E8M0, power of two | 0.25 b/w |
| **NVFP4** (NVIDIA) | E2M1 | 16 | E8M0→FP8 E4M3, carries a mantissa | 0.50 b/w |

Both use the same four-bit element. They differ on the axis we have been
measuring: the width and the *kind* of the shared scale.

Reported externally: MXFP4 relative error ≈2.5 % against ≈1.5 % for NVFP4, the
latter bought with twice the scale overhead. On B200, MXFP4 runs up to ≈15 %
faster than NVFP4 despite the closely related numerics.

## The result that matters to us, and it is not ours

**MR-GPTQ** (*Bridging the Gap Between Promise and Performance for Microscaling
FP4 Quantization*, ICLR 2026, [arXiv:2509.23202](https://arxiv.org/abs/2509.23202))
applies block-wise Hadamard rotation with rotation fused into the weights, and
brings MXFP4 "near the accuracy of NVFP4". Measured speedups over FP16: 3.6×
layer-wise and 2.2× end-to-end on B200, 6× and 4× on RTX 5090.

Two things in that paper bear directly on our claims.

**1. It names MXFP4's weakness as power-of-two scale quantisation error.** That
is E8M0, and it is the same diagnosis our scale-axis line reached independently
and by measurement. `SCALE_FRONTIER_2026-08-10.md` puts perplexity against total
bits per weight and finds a strict domination:

| scheme | scale b/w | total b/w | SmolLM2 (fp32 14.4874) | Qwen (fp32 12.2277) |
|---|---|---|---|---|
| **`phi^k` 4b/32** | **0.1250** | **4.1250** | **21.3545** | **14.8512** |
| MXFP4, E8M0 8b/32 | 0.2500 | 4.2500 | 22.4998 | 14.9447 |

Cheaper by 0.125 bits per weight *and* better perplexity on both models. That is
domination in both coordinates, not a trade.

`GEOMETRIC_SCALE_2026-08-10.md` then replaced the loose version of this with an
inequality (T37): for scales read as multipliers, a geometric grid beats a float
grid at every width, the advantage rising monotonically to `1/ln 2 = 1.442695`.
Measured, geometric beats E4M3 by 5.3 % at seven bits and 8.8 % at eight. The
earlier, weaker claim — that a scale carrying a mantissa always wins — had
compared E4M3 at eight bits against a phi grid at four, and was withdrawn.

So: the field's own ICLR 2026 paper names the defect, and our measurement both
locates it on the cost frontier and explains it with an inequality. That
convergence is worth more than either result alone, and neither party knew of
the other.

**2. It rotates, and our block-axis verdict does not.**
`BLOCK_AXIS_VERDICT_2026-08-10.md` measured MXFP4 at 21.9397 and TNF4 at 36.7214
on unrotated weights. The 2026 state of the art rotates first. Our own
`block/heavy_tail_test.py` measures what rotation does — median excess-kurtosis
change **−1.601**, i.e. it makes weights lighter-tailed, exactly as QuaRot and
QuIP intend — so the distribution the verdict's Lloyd-Max bound was computed on
is not the distribution a 2026 deployment quantises.

**This does not overturn the verdict, and it is not a way back in.** Rotation is
format-agnostic preprocessing; it helps whatever is quantised afterwards.

**Measured 2026-08-11, and it is worse than that.** `ROTATION_VERDICT_2026-08-11.md`
ran the comparison under a block-wise Hadamard of the quantisation block size,
on the verdict's own setup and quantiser. Rotation alone makes every arm worse
and ours worse by more: MXFP4 21.9397 → 23.7476 against TNF4 36.7214 → 42.3269,
so the 4-bit gap goes from **+14.78 to +18.58** and the 6-bit gap from **+3.30 to
+6.09**. The scope objection is therefore answered in the direction least
convenient for us — the element axis is decided against us on both
distributions.

That measurement isolates the *rotation*. MR-GPTQ is rotation plus GPTQ error
compensation, and the compensation is the part that repairs what the transform
costs, so nothing above contradicts that paper or should be quoted as if it did.

## Also on the board

- **HiFloat4** ([arXiv:2604.08826](https://arxiv.org/pdf/2604.08826)) — Huawei,
  4-bit pre-training on Ascend NPUs. A vendor format on a non-NVIDIA stack.
- **SharQ** ([arXiv:2606.26587](https://arxiv.org/pdf/2606.26587)) — couples
  activation sparsity to FP4.
- **SOAR** ([arXiv:2605.12245](https://arxiv.org/pdf/2605.12245)) — scale
  optimisation for NVFP4 specifically, i.e. the scale axis is being worked by
  others now.

That last one is the competitive risk worth naming: our strongest surviving
result is on the scale axis, and the scale axis has stopped being empty.

## What this changes about positioning

The site leads on the range axis against tekum16 (2.84× mid, 5.53× far). That
claim is measured and reproduced, and it is scoped correctly since 2026-08-11.
But tekum16 is not what a reader deciding between formats in 2026 is choosing
between, and the range axis is not where the money is.

The strongest defensible claim we hold is the scale one: **a four-bit geometric
scale grid strictly dominates MXFP4's eight-bit E8M0 — cheaper and more accurate
on two models — and there is an inequality saying why.** It is stronger than the
tekum16 claim, it is against an opponent people have heard of, and an ICLR 2026
paper independently names the defect it exploits.

It is not, however, a claim that we beat MXFP4 overall. On the element axis we
lose, measured and recorded. The two statements are about different fields of
the same format and both must be carried together.

## Not a publication recommendation

The owner's stop-rule holds: nothing goes to arXiv until the format is first on
its own axis by reproducible measurement. This note does not argue that the
condition is met. It records that a strict-domination result over MXFP4 exists
on the *scale* axis while the *element* axis is lost, and that the two together
are what a reviewer would see. Whether that constitutes the condition is the
owner's call, not this file's.

---

*Sources for the external figures are the papers linked above; the internal
figures are from `SCALE_FRONTIER_2026-08-10.md`, `GEOMETRIC_SCALE_2026-08-10.md`,
`block/BLOCK_AXIS_VERDICT_2026-08-10.md` and `block/heavy_tail_test.py`, all
re-read on 2026-08-11 rather than cited from memory.*
