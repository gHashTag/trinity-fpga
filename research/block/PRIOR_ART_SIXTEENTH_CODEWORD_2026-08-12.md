# The extra codeword is published prior art. What is ours is narrower, and worth stating exactly

T40 found that a symmetric 8-magnitude book plus a sign bit spends two of its
sixteen codewords on `+0` and `−0`, leaving fifteen distinct values, and that
spending the sixteenth is worth more than any codebook-shape effect measured in
this line. Before that gets called new, the field was checked. It is not new.

## The published work

**Signed Symmetric Quantization for Few-Bit Integers**
([arXiv:2607.08779](https://arxiv.org/abs/2607.08779)) makes the same structural
observation from the integer side:

> the alphabet contains one more negative representable value than positive.
> Standard symmetric quantizers fix the scale as positive, assigning this extra
> value to the negative tail and forcing clipping of positive outliers.

Their method places the extra representable value on the **dominant-outlier
tail**, by a sign-selection rule, keeping the zero point at zero. Evaluated on
Qwen3, Qwen3.5 and Llama3; they report 88–99 % of weight groups satisfying their
optimality condition, and improvement at no extra inference cost.

## How it differs from ours, precisely

| | arXiv:2607.08779 | this work |
|---|---|---|
| alphabet | int4 two's complement, **−8 … +7** — already asymmetric | magnitude + sign, **made** symmetric by construction |
| the wasted value | the extra *negative* value, misallocated by symmetric scaling | the *duplicate zero*, `+0 = −0` |
| what is chosen | which **tail** the extra value serves | where in the ladder the extra **level** goes |
| format | integer quantisation | **block float** with a shared E8M0 scale (MXFP4/E2M1) |
| block formats | not discussed | the entire setting |

The two are the same idea seen from opposite sides: theirs is *an asymmetric
alphabet wasted by symmetric use*, ours is *a symmetric construction that
discards one codeword outright*. Neither subsumes the other, and theirs is
published first.

## What survives as ours

1. **The exact decomposition.** `NF4-sym` — the same Gaussian-quantile
   construction with the sixteenth value switched off — is a **tie** with MXFP4
   (+0.33 %, p = 0.46), and `(+0.335 %) × (−4.429 %) = −4.109 %` reproduces the
   full NF4-vs-MXFP4 margin with residual `0.00e+00`. That the *entire* margin of
   the field's reference 4-bit codebook is the codeword and not the curve is a
   measurement, and it is ours.
2. **The block-float setting.** Their work is integer quantisation and does not
   discuss a shared scale. Ours is MXFP4's own element format under E8M0.
3. **Placement is not the tail, and is not monotone.** Their choice is binary —
   which tail. Ours is a position in the ladder, and the measured spread across
   five placements is 3.13× at a fixed alphabet ratio, with `TOP` a trap that
   clips the opposite extreme.
4. **A deployable artefact.** `MX-asym-NEAR0` is E2M1's magnitudes plus one level
   at 1/24 — integers in units of 1/24, so the same 4-bit lookup as MXFP4 — that
   beats MXFP4 in 140 of 140 windows across four models.

## What this changes about how the result should be written

The sentence *"a symmetric codebook wastes a codeword"* must be attributed, not
claimed. The sentence *"that waste is the entire NF4 margin, and here is a
drop-in E2M1 variant that recovers it"* is ours and is what should lead.

This is the second time in three days that checking the literature moved a claim
from ours to theirs — the first being NF4 itself, which had beaten MXFP4 in this
harness since 2023 while three sessions went into building alternatives. Both
checks cost under an hour. Both were done after the work rather than before it.

---

*External claims are from the linked abstract, read 2026-08-12, not cited from
memory. Their specific margins are not quoted here because the abstract does not
give them and the full text was not read; the comparison above is structural, not
numerical, and should not be read as a performance comparison against them.*
