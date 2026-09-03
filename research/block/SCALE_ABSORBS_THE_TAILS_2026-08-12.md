# The block scale absorbs the tails: every pre-registered prediction holds, and it is a negative result about a whole line of work

`PREREGISTRATION_SCALE_ABSORBS_2026-08-12.md` was written and committed with four
of eight checkpoints measured. All four remaining predictions hold, and so do
both correlation predictions.

| checkpoint | family | raw kurtosis | **block-normalised** | band | verdict |
|---|---|---:|---:|---|---|
| SmolLM2-135M | Llama-ish | 4.963 | 2.848 | — | measured before registration |
| Qwen2.5-0.5B | Qwen2 | 12.858 | 2.905 | — | measured before registration |
| OPT-125M | OPT | 13.211 | 2.985 | — | measured before registration |
| Pythia-160M | GPT-NeoX | 55.334 | 2.795 | — | measured before registration |
| **GPT-2 124M** | GPT-2, `Conv1D` | 32.882 | **2.841** | [2.75, 3.05] | **HOLDS** |
| **GPT-Neo-125M** | local+global attn | 12.982 | **2.916** | [2.75, 3.05] | **HOLDS** |
| **BLOOM-560M** | ALiBi, 250k vocab | 41.257 | **2.943** | [2.75, 3.05] | **HOLDS** |
| **Mamba-130M** | **no attention at all** | 3.786 | **2.837** | [2.6, 3.2] | **HOLDS** |

* **K5**: range over all eight = **0.190**, predicted ≤ 0.35. **HOLDS.**
* Raw kurtosis spans **14.6×** — 3.786 to 55.334.
* **K6**: Spearman(block-normalised kurtosis, MXFP4 cost) = **−0.500, p = 0.253**.
  Predicted |ρ| ≤ 0.5 and non-significant. **HOLDS.**
* **K7**: Spearman(raw kurtosis, MXFP4 cost) = **−0.250, p = 0.589**. Predicted
  non-significant. **HOLDS.**

**Mamba is the result.** A selective state-space model with no attention, whose
target tensors are trained under different pressure entirely, lands at 2.837 —
inside the *narrow* band written for the transformers, not the widened one it was
given. Whatever this is, it is not a property of attention.

## What it means

**C1 stands.** The E8M0 block scale `s = 2^⌈log₂ a⌉` absorbs essentially all
cross-checkpoint variation in tail weight. A raw distribution 14.6× heavier than
another produces a block-normalised distribution whose fourth moment differs by
6 %.

**C2 follows, and it is the useful part.** No statistic of the weight
distribution can predict how much a codebook's margin transfers between
checkpoints, because after the scale is applied the codebook is operating on the
same distribution everywhere. That explains a run of failures which had looked
like separate problems:

* **T41** predicted the clipping arm's sign from weight statistics and got two of
  four wrong;
* **T42**'s margin-from-occupancy conjecture;
* the **P1 / P2 / P3** bin predictors — none rotation-stable, and P2, the
  classical greedy criterion, anti-correlated;
* all four candidate explanations for the KL selector's uneven behaviour, each
  refuted by control;
* and the campaign's repeated surprise that a margin measured on four
  checkpoints does not appear on a fifth.

They were not five problems. They were one, and the answer is that **the
information those predictors were built to extract is destroyed by the format's
own scale rule before the codebook sees the data.** T38 said the scale rule
determines the headroom phase; this says it also determines the shape.

**C3 is now the open question and it is the only one left.** MXFP4's cost spans
**21×** across these checkpoints — +8.2 % on BLOOM to +174.4 % on GPT-Neo,
independently re-measured to 5.3e-07 relative — while the perturbation it applies
has the same shape everywhere. The difference must live in how sensitive each
checkpoint's *loss* is to a perturbation of fixed relative size, which is a
property of the trained function and not of the weights.

`sensitivity.py` measures exactly that: isotropic Gaussian noise of fixed
relative RMS applied to the same tensors the campaign quantises, on the same
windows, with the same seed on every checkpoint, and a zero-eps control that must
reproduce the fp32 ruler bit-identically before any figure counts. First
measurement, OPT-125M:

| eps | ppl | relative | ratio at 2× eps |
|---:|---:|---:|---:|
| 0 | 27.5678 | — | control bit-identical |
| 0.01 | 27.6489 | +0.29 % | |
| 0.02 | 27.8145 | +0.89 % | **3.042** |

**The response is sub-quadratic** — doubling the perturbation raises perplexity
by 3.04×, not the 4× a smooth second-order expansion predicts. That is reported
rather than divided away, and it means any `eps²`-normalised "sensitivity" is
itself an approximation whose error is measurable. The sweep across all eight
checkpoints is the next step and is not claimed here.

## What this does not say

Kurtosis is the fourth moment and nothing else. **C1 as tested says the fourth
moment is absorbed; it does not say every statistic is.** A predictor built on
block-normalised occupancy of the specific bins two codebooks differ in is not
excluded by this — it is what T42 attempted — and it needs its own registration
rather than being covered by this one. That limit was written into the
registration in advance, before the outcome was known, and it stands.

Eight checkpoints, one moment, one corpus.

---

*Block 32, E8M0 with `s = 2^⌈log₂ a⌉`, `lm_head` excluded, `block_tnf`'s own
target selector. GPT-2's `Conv1D` weights transposed to `[out, in]` so blocks run
along the contraction axis on every checkpoint, as in `lineC_fifth`'s G1 gate.
Kurtosis is `E[(x−μ)⁴]/E[(x−μ)²]²` over pooled target elements; block-normalised
kurtosis is the same statistic on `w/amax` per block of 32.*
