# Pre-registration: the block scale absorbs the tails, so weight statistics cannot predict transfer

**Written before the block-normalised kurtosis of `gpt2`, `gptneo`, `bloom` or
`mamba` was computed.** Four checkpoints are measured; four are not, and the
sweep that will produce them is running as this is committed. Every number below
for the unmeasured four is a prediction.

## The observation this comes from

Measuring raw weight kurtosis across the four checkpoints the campaign owns, to
explain why MXFP4's cost ranges from +8.2 % to +174.4 % — a **21× spread**:

| checkpoint | raw kurtosis | **block-normalised** | MXFP4 cost |
|---|---:|---:|---:|
| SmolLM2-135M | 4.963 | **2.848** | +51.4 % |
| Qwen2.5-0.5B | 12.858 | **2.905** | +21.6 % |
| OPT-125M | 13.211 | **2.985** | +11.7 % |
| Pythia-160M | 55.334 | **2.795** | +83.6 % |

Raw kurtosis spans **11×**. After dividing each block by its own maximum — which
is exactly what the codebook sees, since E8M0 supplies `s = 2^⌈log₂ a⌉` and the
book is applied to `w/s` — the spread is **6 %**.

## The claim

**C1. The E8M0 block scale absorbs essentially all cross-checkpoint variation in
tail weight.** Block-normalised kurtosis is a near-constant of trained
transformer weight matrices, independent of how heavy the raw distribution is.

**C2. Therefore no statistic of the weight distribution can predict how much a
codebook's margin transfers between checkpoints** — because after the scale is
applied, the distributions the codebook operates on are the same. This is a
*negative* result and it explains a run of failures: T41's prediction (refuted),
T42's margin-from-occupancy conjecture, the P1/P2/P3 bin predictors (none
rotation-stable), and the four candidate explanations for the KL selector's
uneven behaviour (all refuted).

**C3. The 21× cost spread must therefore live in the LOSS, not the weights** —
in how sensitive each checkpoint's output is to a perturbation of fixed relative
size, not in the size or shape of the perturbation.

## Predictions, as numbers, before the sweep finishes

| # | quantity | prediction |
|---|---|---|
| K1 | block-normalised kurtosis, `gpt2` | **2.75 – 3.05** |
| K2 | block-normalised kurtosis, `gptneo` | **2.75 – 3.05** |
| K3 | block-normalised kurtosis, `bloom` | **2.75 – 3.05** |
| K4 | block-normalised kurtosis, `mamba` | **2.6 – 3.2** — widened, and stated as widened: it is not a transformer, has no attention projections, and its target tensors are state-space matrices whose training pressure is different in kind |
| K5 | range across all eight | **≤ 0.35** absolute |
| K6 | Spearman(block-normalised kurtosis, MXFP4 cost) over all eight | **\|ρ\| ≤ 0.5, p > 0.05** — no relationship |
| K7 | Spearman(**raw** kurtosis, MXFP4 cost) over all eight | **also not significant** — the point is not that raw kurtosis is the right predictor and normalised is the wrong one; neither is |

**What each outcome means, agreed now:**

* K1–K5 hold → C1 stands on eight checkpoints across four architecture families
  including a non-transformer, and C2 follows.
* Any checkpoint lands outside its band → C1 is a property of the four it was
  found on, and the whole line is withdrawn to an observation.
* K6 fails, i.e. normalised kurtosis *does* track cost → C2 is wrong and there is
  a weight-distribution predictor after all, which would be a larger result than
  C1 and must be reported as overturning it.
* K7 fails → raw kurtosis predicts cost, C1 is beside the point, and the
  interesting question becomes why normalising destroys a real signal.

**A limit stated in advance.** Kurtosis is the fourth moment and nothing else. C1
as tested here says the fourth moment is absorbed; it does not say *every*
statistic is. A predictor built on block-normalised **occupancy of the specific
bins two codebooks differ in** is not excluded by this and is the natural next
candidate — it is what T42 attempted, and it deserves its own registration rather
than being covered by this one.

**And what this cannot become.** If K1–K5 hold, the honest statement is
"the fourth moment of the block-normalised distribution is near-constant across
these eight checkpoints", **not** "weight distributions are identical". Eight
checkpoints, one moment, one corpus.

---

*Block 32, E8M0 with `s = 2^⌈log₂ a⌉`, `lm_head` excluded, the same
`block_tnf.target_modules` selector every campaign measurement uses. Kurtosis is
`E[(x−μ)⁴]/E[(x−μ)²]²` over all target elements pooled, and block-normalised
kurtosis is the same statistic on `w/amax` per block of 32 along the contraction
axis. Records stay in-repo.*
