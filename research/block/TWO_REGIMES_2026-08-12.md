# The two cost extremes are not in the same regime, and that is the first mechanistic difference found

MXFP4 costs +11.7 % on OPT-125M and +174.4 % on GPT-Neo-125M. The weight side is
closed — after the E8M0 scale the two checkpoints present the codebook with
distributions whose fourth moments differ by 6 % and whose mass in the altered
intervals differs by 13 %. So the difference is downstream of the weights, and
`seed_control.py` measures the only thing left: how the loss responds to a
perturbation of fixed relative size.

Five and three seeds respectively, four perturbation sizes, zero-eps control
bit-identical to the ruler on every run.

| | OPT-125M | GPT-Neo-125M |
|---|---:|---:|
| MXFP4 cost | +11.7 % | **+174.4 %** |
| **mean over seeds ~ eps^α** | **1.998** | **2.440** |
| **spread across seeds ~ eps^α** | **0.999** | **1.808** |

| eps | OPT mean | GPT-Neo mean | ratio |
|---:|---:|---:|---:|
| 0.005 | +0.037 % | +0.074 % | 2.0× |
| 0.010 | +0.145 % | +0.493 % | 3.4× |
| 0.020 | +0.576 % | +2.496 % | 4.3× |
| 0.040 | +2.350 % | +12.052 % | **5.1×** |

## The reading, and it is qualitative rather than a scale factor

**OPT sits in a locally quadratic basin over this whole range.** Its
seed-averaged response is `eps^1.998` against a theoretical 2.000, and its
across-seed spread is `eps^0.999` against a theoretical 1.000 — a smooth loss
with a realised first-order term that cancels in expectation. Both exponents are
within 0.1 % of what a second-order expansion predicts.

**GPT-Neo is not in that regime at these sizes.** Its mean grows as `eps^2.440`
— faster than quadratic — and its across-seed spread as `eps^1.808`, nearly
double the linear scaling a first-order term gives. Higher-order terms dominate
both statistics.

That is not "GPT-Neo is more sensitive by a constant". It is a different
functional form. And the ratio between the two grows with perturbation size —
2.0× at eps = 0.005, 5.1× at eps = 0.04 — because one response is quadratic and
the other is steeper.

## Why this is the shape a 21× cost difference needs

MXFP4 is a **fixed-size** perturbation. The same relative error applied to two
checkpoints costs what each checkpoint's response function says at that size. If
one checkpoint is inside its quadratic basin at MXFP4's effective perturbation
size and the other is past it, the costs diverge by far more than any ratio
measured at small eps would suggest — which is exactly the pattern: a 2.0× ratio
at eps = 0.005 and a 14.9× cost ratio at the size MXFP4 actually applies.

**This is not yet that claim.** Two checkpoints is not a relationship, MXFP4's
effective eps has not been measured on either, and the extrapolation from
eps = 0.04 to whatever MXFP4 corresponds to is unmade. What is established is
narrower and it is the first of its kind in this campaign: **the two extremes
differ in the character of their response, not only its size, and the difference
is in the direction the cost spread requires.**

## What would settle it

1. **Measure MXFP4's effective relative perturbation** per checkpoint — the RMS
   of `(quantised − original) / original` over the same tensors. That converts
   "eps = 0.04" into a point on the same axis as the cost, and it is cheap.
2. **The remaining six checkpoints**, seed-controlled. Two points cannot carry a
   relationship; eight can carry a model-level statistic with the checkpoint as
   the replicate unit, which is what every cross-model claim here requires.
3. **A registered prediction before those six are measured** — the exponent
   ordering, from the two known points, with a stated threshold. This campaign's
   two registered tests both came back informative and one of them refuted my own
   prediction; a third is worth more than another exploratory sweep.

---

*OPT-125M: 5 seeds. GPT-Neo-125M: 3 seeds. Both 40 × 2048 windows of wikitext-2,
isotropic Gaussian noise at fixed relative RMS per tensor applied to exactly the
tensors the campaign quantises, seeds from 20260812. The zero-eps control
reproduces the fp32 ruler bit-identically on every run; a run whose control fails
prints ABORT and returns 4 rather than a number. Exponents are fitted over four
sizes, not assumed.*
