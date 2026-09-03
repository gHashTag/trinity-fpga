# T42 — a codebook's margin over its parent is an integral against the checkpoint's block-normalised value distribution; that fixes the sign and most of the order, and misses the size by 2–3×

Every failure in this campaign is one question in different clothes. KL selection
worked on OPT and Qwen and not on SmolLM2 and Pythia. The placement order
disagrees between checkpoints at `rho = +0.083`. Eleven verdicts collapsed the
moment checkpoints rather than windows became the replicate unit. The question
underneath all of them: **what property of a checkpoint decides how much of a
codebook's measured margin transfers to it?**

T42 answers the first half of that exactly and the second half badly, and both
halves are reported.

---

## 🛑 Literature first, and it is not empty

Read on 2026-08-12, from the sources, not from memory.

| what is already established | where | what it covers |
|---|---|---|
| the values a block-scaled codebook actually sees are **absmax-normalised**, and their distribution is **not** the weight prior — it depends on block size and concentrates toward the origin as the block grows | **AF4 / "NF4 Isn't Information Theoretically Optimal"** ([arXiv:2306.06965](https://arxiv.org/abs/2306.06965)) | the *object* T42 integrates against — Yoshida derives `F_X(x;B)` explicitly and optimises a code against it |
| the same point, re-derived, with an EM/Lloyd estimator and a signed-absmax variant | **BOF4 / BOF4-S** ([arXiv:2505.06653](https://arxiv.org/abs/2505.06653)) | "absmax normalisation changes the blockwise source distribution and therefore the codebook favoured by a reconstruction objective" |
| quantisation damage scales predictably with model size and **training tokens**; post-training-quantisation degradation grows with data seen, to the point where more pretraining data is actively harmful | **Scaling Laws for Precision** ([arXiv:2411.04330](https://arxiv.org/abs/2411.04330)) | the only *quantitative* cross-model law for quantisation damage that exists — it predicts damage from a **parent** format, not the **margin between two** |
| PTQ robustness is set by the interplay of learning rate and other training hyperparameters, and decouples from validation loss once the LR decays | **Training Dynamics Impact PTQ Robustness** ([arXiv:2510.06213](https://arxiv.org/abs/2510.06213)) | a checkpoint-property answer that is about *training history*, not weight statistics |
| outlier-structure metrics — **kurtosis** and **max-to-mean ratio** — **fail** to predict PTQ degradation; Shampoo-trained nets have the *highest* MMR and the *best* PTQ robustness | **Beyond Outliers: Optimizers Under Quantization** ([arXiv:2509.23500](https://arxiv.org/abs/2509.23500)) | kills the obvious predictor class this record was told to search for, with a sign inversion |
| kurtosis as a *target to minimise* by rotation, and as a layer-selection signal | **KurTail** ([arXiv:2503.01483](https://arxiv.org/abs/2503.01483)) | kurtosis is useful as an objective; that is not the same as being a predictor |
| outlier features appear suddenly between 6B and 6.7B and that is where int8 breaks; the outlier count is **strictly monotonic in perplexity across models** | **LLM.int8()** ([arXiv:2208.07339](https://arxiv.org/abs/2208.07339)) | the closest published relative of T42's shape: a *checkpoint property* that orders a quantisation-relevant quantity across models |
| activation outlier magnitude migrated between weights and activations by a per-channel scale | **SmoothQuant** ([arXiv:2211.10438](https://arxiv.org/abs/2211.10438)) | the structure that makes activations, not weights, the usual difficulty axis |
| calibration objective and calibration set do not transfer; parameters are model- and data-specific | **generalisation-of-quantised-LLMs benchmark** ([arXiv:2406.12928](https://arxiv.org/abs/2406.12928)) | that transfer is a known problem — it does **not** offer a predictor, and states its own model coverage (two 7B models) as a limitation |

**So the honest position before deriving anything.** That the relevant density is
the block-normalised one, and that a codebook should be optimised against *it*
rather than against a Gaussian prior, is published and is AF4's whole point. That
quantisation damage from a single format has a cross-model scaling law is
published. That the obvious weight-statistic predictors of PTQ damage do not work
is published, with a sign inversion.

**What is not covered.** AF4 and BOF4 use the normalised density to *design a
code on one distributional assumption*; neither compares that density **between
checkpoints**, and — checked directly — AF4 "makes no statement about whether this
distribution differs between models, checkpoints, or other conditions" and has
"no discussion of predicting codebook advantage without direct measurement."
Scaling Laws for Precision predicts the damage of **one** format, not the
**difference between two**. Nothing found predicts, from weights alone, how much
of codebook A's advantage over codebook B on checkpoint 1 will survive on
checkpoint 2. That difference is the whole practical question of this campaign,
and it is what T42 is about.

---

## Setup

Two books, at the same alphabet cost, under the same scale rule.

* **MXFP4** — E2M1 magnitudes `{0, 1, 2, 3, 4, 6, 8, 12}/12`, applied with
  `sign(w)`; 15 distinct signed values.
* **MX-asym-NEAR0** — the sixteenth codeword spent on the **positive** side at
  the midpoint of the gap `0 → 1/12`, i.e. at `+1/24`; 16 distinct signed values.
  Negative side identical to MXFP4.

Both are normalised so `max|level| = 1.0` on both tails (T38), so the E8M0 block
scale `s = 2^⌈log₂ a⌉` (block absmax `a`) is **bit-identical between them**. The
two arms therefore differ in the level set and in nothing else — no scale
difference, no clipping, no phase difference. `campaignA_books.check` asserts
this rather than assuming it.

Write `y = w/s` for the block-normalised value. Since `s ≥ a ≥ |w|`, `y ∈ [−1, 1]`.

---

## Proposition 1 (the margin is a tent integral, exactly)

*Let the two books share the block scale. Then the difference in block squared
weight error is*

    ΔD = D_MXFP4 − D_NEAR0 = Σ_blocks s_b² Σ_j g(y_j)

*where `g` is a function of the two codebooks alone, supported on **positive**
`y ∈ [1/48, 1/16)` and there equal to*

    g(y) = (2y − 1/24)/24   on [1/48, 1/24)
    g(y) = (1/8 − 2y)/24    on [1/24, 1/16)

*a symmetric tent peaking at `y = 1/24` with height `(1/24)² = 1/576`. In
particular `g ≥ 0` pointwise, so this placement can never raise squared error.*

**Proof.** Per element the squared error is `(w − s·r(y))² = s²(y − r(y))²`, with
`r` the book's reconstruction of `y`; the scale factors out because it is shared.
`g(y) = e_MX(y)² − e_N0(y)²` is then a function of `y` and the two level sets
only. The two books have identical levels except for `+1/24`, so `r` differs only
between the decision boundaries that codeword creates: MXFP4's boundary in the
gap `0 → 1/12` is at `1/24`; NEAR0's are at `1/48` and `1/16`. Outside
`[1/48, 1/16)` both books return the same level and `g = 0`. Inside, substitute
the two reconstructions and expand as a difference of squares:
`y² − (1/24 − y)² = (2y − 1/24)/24` on the lower half and
`(1/12 − y)² − (y − 1/24)² = (1/8 − 2y)/24` on the upper. Both vanish at the
endpoints and meet at `(1/24)²`. ∎

**The band is derived, not asserted.** `campaignE_occupancy.band_and_g` locates
the disagreement region by scanning both reconstruction maps on a 2·10⁶-point
grid and recovers `[0.0208335, 0.0625]` against the exact `[1/48, 1/16]`; the
closed form matches the scanned `g` to `6.5e−19`.

**And it is checked against the real quantisers.** On the first four weight
tensors of every checkpoint, the analytic tent integral reproduces the difference
of `block_tnf.quant` and `campaignC_books.quant_signed` — the two instruments
actually used for the perplexity arms — to a worst relative error of

| checkpoint | worst relative error, analytic vs quantisers |
|---|---:|
| SmolLM2-135M | 1.37e−15 |
| Qwen2.5-0.5B | 3.89e−15 |
| Pythia-160M | 2.68e−15 |
| OPT-125M | 2.29e−15 |
| GPT-2 124M | 2.64e−15 |
| GPT-Neo-125M | 2.39e−15 |

That is double-precision round-off. Proposition 1 is not an approximation.

---

## Proposition 2 (the transfer statement)

*Define the checkpoint's `s²`-weighted block-normalised occupancy measure `ρ` by
`ρ(A) = Σ_b s_b² · #{j ∈ b : y_j ∈ A}`. Then*

    R  ≡  ΔD / D_MXFP4  =  ∫ g dρ / ∫ e_MXFP4² dρ

*so `R` depends on the checkpoint **only** through `ρ`. Two checkpoints with the
same normalised occupancy have the same `R`, whatever their architecture, size,
weight scale, tokenizer or training data.*

**Proof.** Both numerator and denominator are the same sum `Σ_b s_b² Σ_j f(y_j)`
for `f = g` and `f = e_MXFP4²`, which is by definition integration against `ρ`.
The block scales enter only as the weights of that measure and cancel from
neither. ∎

This is the sense in which a margin is "a property of the checkpoint": it is a
property of one measurable distribution, and the codebooks contribute two fixed
kernels. It is also where AF4's published observation is used rather than
rediscovered — AF4 derives that `ρ` is not the weight prior; T42 uses `ρ` as the
carrier of cross-model transfer, which AF4 does not.

---

## Theorem T42

*Let books A and B share a block scale rule and differ only in their level sets,
and let `L = log ppl_B − log ppl_fp32` be the log-perplexity excess the parent
already costs on that checkpoint. Assume*

* **(A1) local quadratic response** — the log-perplexity excess of an arm is
  proportional to its block squared weight error;
* **(A2) shared constant** — the proportionality constant is a property of the
  checkpoint, not of which of the two books produced the error.

*Then the constant cancels between the two arms and the margin is*

    log ppl_A − log ppl_B  =  −R · L,     R = ∫g dρ / ∫e_B² dρ,

*i.e. **the margin is the product of a codebook-and-occupancy term `R`, computable
from weights alone, and a term `L` that measures only how badly the parent
already damages that checkpoint.** With `g ≥ 0` the margin is non-positive on
every checkpoint.*

No free parameter appears. `R` is measured from the weights; `L` is read off two
rulers — `fp32` and `MXFP4` — that were measured in this repository long before
this theorem existed.

**Why the cancellation is the whole point, and why T41 does not apply.** T41
tried to rank *models* by a squared-error functional and failed at
`rho = −0.400`, then failed worse the more carefully the output error was
modelled. T42 uses squared error only to compare *two books on one checkpoint*;
the per-model curvature constant that T41 had to get right is exactly what
cancels here. Cross-model ordering then comes out of the **ratio**, not out of
the absolute error.

---

## The predictions, frozen before any NEAR0 perplexity was read

`campaignE_frozen.json`, timestamp `2026-08-12T15:37:09Z`. The occupancy run
(`campaignE_occupancy.py`) touches weights only and never loads the parquet.

| | claim | scoring rule, fixed in advance |
|---|---|---|
| **P1** | the ORDER of the measured fractional excess-loss reduction `R̂ = 1 − (log ppl_A − log ppl_fp32)/(log ppl_B − log ppl_fp32)` equals the order of `R` | Spearman over checkpoints, exact permutation p |
| **P2** | the MAGNITUDE: `Δppl% = 100(exp(−R·L) − 1)` | `|measured / predicted| ∈ [0.5, 2.0]` on **every** checkpoint — **the factor is 2 and it was written down before the numbers** |
| **P3** | the SIGN: `g ≥ 0` pointwise ⇒ NEAR0 never loses | one checkpoint where it loses refutes it |

Frozen values, all six checkpoints:

| checkpoint | `R` (weights only) | `s²`-weighted band occupancy | `L` | predicted `Δppl%` |
|---|---:|---:|---:|---:|
| OPT-125M | 0.075243 | 0.083480 | 0.11045 | **−0.828** |
| GPT-Neo-125M | 0.063365 | 0.074707 | (measured here) | (below) |
| GPT-2 124M | 0.060208 | 0.072006 | (measured here) | (below) |
| Qwen2.5-0.5B | 0.060149 | 0.073740 | 0.19520 | **−1.167** |
| SmolLM2-135M | 0.057554 | 0.071358 | 0.41502 | **−2.360** |
| Pythia-160M | 0.049347 | 0.063836 | 0.60748 | **−2.953** |

Note the two orders **disagree**, which is what makes P1 and P2 independent
tests: `R` is largest on OPT, but OPT has the smallest parent damage `L`, so
`R·L` ranks it last. A theory that only got the sign right would not produce
that.

---

## Widening `n` cost an instrument fix, and the fix is a false-green story

The campaign's replicate unit for a cross-model claim is the **model**, and it
has been stuck at `n = 4`. Two of the checkpoints added here are GPT-2 and
GPT-Neo. GPT-2 stores every projection as `transformers.pytorch_utils.Conv1D`,
whose weight is `(in_features, out_features)` — the **transpose** of
`nn.Linear`'s. `block_tnf.target_modules` filters on `torch.nn.Linear`, so on
GPT-2 it returns an **empty list**:

    Counter({'Conv1D': 48, ..., 'Linear': 1})     # the 1 is lm_head, excluded

Run unmodified, every arm would have quantised **nothing**, and the harness would
have reported `ppl(MXFP4) == ppl(fp32)` and a margin of exactly `0.00 %` — a
false green of precisely the kind this repository has shipped before. That is why
GPT-2 was never in this campaign.

The fix is a transpose adapter, not a second quantiser: the weight is handed to
the same `quant` / `quant_signed` in `nn.Linear` orientation, so a block is 32
consecutive **input** channels of one output row on every architecture, which is
what it already means for the four rulers. Two gates enforce it —
`assert_same_as_ruler` proves the adapter selects exactly what
`target_modules` selects on every `nn.Linear` checkpoint, and a no-op gate
asserts `max|w_quantised − w| > 0` before any perplexity is taken.

---

## Results

Every one of the four published rulers reproduced in this session's own process
before anything below was computed:

| checkpoint | fp32 published / here | MXFP4 published / here | rel. error |
|---|---|---|---:|
| SmolLM2-135M | 14.4874 / 14.4874 | 21.9397 / 21.9397 | 1.7e−06 |
| Qwen2.5-0.5B | 12.6999 / 12.6999 | 15.4374 / 15.4374 | 2.0e−06 |
| Pythia-160M | 25.9561 / 25.9561 | 47.6504 / 47.6504 | 2.2e−07 |
| OPT-125M | 27.5678 / 27.5678 | 30.7871 / 30.7871 | 1.4e−06 |

<!--RESULTS-->

---

<!--VERDICT-->
