# Pre-registration: the one weight-side predictor the scale-absorption result does not exclude

`SCALE_ABSORBS_THE_TAILS_2026-08-12.md` showed that block-normalised kurtosis is
near-constant across eight checkpoints — range 0.190 where the raw statistic
spans 14.6× — and concluded that **no statistic of the weight distribution can
predict how much a codebook margin transfers.**

That conclusion was over-stated in one specific way, and the registration behind
it said so in advance:

> Kurtosis is the fourth moment and nothing else. C1 as tested says the fourth
> moment is absorbed; it does not say *every* statistic is. A predictor built on
> block-normalised **occupancy of the specific bins two codebooks differ in** is
> not excluded by this […] and it needs its own registration.

This is that registration. **Written before the occupancy vectors were computed
on any checkpoint.**

## Why occupancy could survive where kurtosis did not

Two codebooks that differ by one level differ **only** on the interval where that
level changes the nearest-neighbour assignment. `MX-asym-NEAR0` inserts a level
at 1/24, so it changes reconstruction only for block-normalised magnitudes in
roughly `[0, 1/8]`; `MX-asym-MID` inserts at 10/12 and changes only
`[3/4, 11/12]`. The margin is a weighted sum of what happens in those intervals
and nowhere else.

A *moment* of the whole distribution is exactly the wrong instrument for that: it
integrates over the entire support and is dominated by the bulk. Two checkpoints
can have identical fourth moments and different mass in `[0, 1/8]`. **The fourth
moment being absorbed does not imply the local mass is.** So the conjecture is
not dead; it was never tested.

## The statistic

For each checkpoint, over the same target tensors and the same block-32 E8M0
normalisation every campaign measurement uses, the **signed block-normalised
occupancy vector**: the fraction of elements of `w/amax` falling in each of
MXFP4's 15 signed reconstruction cells, plus the fraction in the sub-cell each
candidate placement actually alters.

## Hypotheses, with directions and thresholds fixed now

| # | claim | test | threshold |
|---|---|---|---|
| **O1** | occupancy is *not* absorbed the way the fourth moment is | max–min across the eight checkpoints of the mass in `NEAR0`'s altered interval, relative to its mean | **> 20 %** relative spread ⇒ occupancy carries information kurtosis does not |
| **O2** | occupancy predicts the *per-checkpoint margin* of a placement | Spearman over eight checkpoints between altered-interval mass and that placement's measured margin vs MXFP4, for `NEAR0` and for `MID` separately | **ρ ≥ +0.75, exact p < 0.05** for at least one, and the sign must be as stated below |
| **O3** | occupancy predicts the *placement ORDER within* a checkpoint | Spearman over the nine placements, per checkpoint, between altered-interval mass and measured margin | positive on **≥ 6 of 8** checkpoints |
| **O4** | occupancy explains the 21× MXFP4 cost spread | Spearman(total mass in MXFP4's two widest cells, MXFP4 cost) over eight | **ρ ≥ +0.75, p < 0.05** |

**Predicted signs, written now.** More mass in the interval a placement alters
should mean a *larger* benefit from that placement, so the margin (negative =
better) should become **more negative** as mass rises: the Spearman against the
signed margin is **negative**, and against `|margin|` is **positive**. O2 and O3
are scored against that stated direction; a strong correlation with the opposite
sign is a **failure**, not a discovery, and will be reported as one.

**Predictions as numbers:**

| # | quantity | prediction |
|---|---|---|
| P1 | relative spread of `NEAR0`-interval mass across eight | **25 – 60 %** |
| P2 | O2 for `NEAR0` | ρ ≈ **−0.6**, *not* significant at n = 8 |
| P3 | O2 for `MID` | ρ ≈ **−0.5**, not significant |
| P4 | O3 | positive on **5 of 8** — below its own threshold |
| P5 | O4 | ρ ≈ **+0.3**, not significant |

**So the registered expectation is that occupancy carries real information (O1
holds) and still fails as a predictor (O2–O4 fail).** That is an uncomfortable
prediction to write down and it is the honest one: the campaign has produced
eleven predictors and none has survived a rotation. Writing "I expect this to
fail" in advance is the only way the eventual result means anything either way.

**What each outcome means, agreed now:**

* O1 fails → occupancy is absorbed too, `SCALE_ABSORBS`'s C2 stands without its
  caveat, and the weight side is closed.
* O1 holds and O2–O4 fail as predicted → the information exists and is not
  usable, which locates the problem precisely: it is not that the weights are
  identical, it is that the margin is not a function of them alone. C3 (the loss
  sensitivity) becomes the whole story.
* Any of O2–O4 clears its threshold **with the predicted sign** → the campaign
  has its first transferable predictor, and `SCALE_ABSORBS`'s C2 must be narrowed
  in the document itself, not in a footnote.
* Any clears with the **opposite** sign → reported as a failure of the stated
  mechanism, and the correlation treated as unexplained rather than as a finding.

## The statistics, fixed now

Replicate unit is the **checkpoint**, n = 8, for O1, O2 and O4. O3 is a
within-checkpoint rank test over nine placements, n = 9, reported per checkpoint
and summarised by a count, never pooled into a single p-value. Exact permutation
p-values throughout — at n = 8 the smallest achievable two-sided p is 1/2520 and
at n = 9 it is 1/181440, so the tests can refute and can only weakly confirm.
No Bonferroni over O1–O4: they are pre-registered as a set of four and the
correction is stated here — **any single one clearing at p < 0.05 uncorrected is
reported as p × 4.**

---

*Block 32, E8M0 with `s = 2^⌈log₂ a⌉`, `lm_head` excluded, `block_tnf`'s own
target selector, GPT-2's `Conv1D` transposed as in `lineC_fifth` G1. Eight
checkpoints: SmolLM2-135M, Qwen2.5-0.5B, Pythia-160M, OPT-125M, GPT-2 124M,
GPT-Neo-125M, BLOOM-560M, Mamba-130M. Margins are model-level as everywhere
else. Records stay in-repo.*
