# MXFP4 applies the same perturbation to both extremes. The 21× is entirely in the response

The regime comparison in `TWO_REGIMES` was unfalsifiable while MXFP4's own
perturbation sat on a different axis from the noise ladder. It is now measured,
in the ladder's own units — `RMS(quantised − original) / RMS(original)`, per
tensor, over exactly the tensors the campaign quantises, which is the same
definition `seed_control.py` perturbs by:

| checkpoint | **eps_eff** | per-tensor range | error kurtosis | MXFP4 cost |
|---|---:|---|---:|---:|
| OPT-125M | **0.12248** | [0.11619, 0.13549] | 13.65 | +11.7 % |
| GPT-Neo-125M | **0.11991** | [0.11400, 0.15220] | 14.60 | **+174.4 %** |

**The two perturbations differ by 2 %. The costs differ by 14.9×.**

That closes the last route by which the input could have explained the spread.
The weight *distributions* were already shown to be interchangeable after the
scale — fourth moments within 6 %, altered-interval mass within 13 %. Now the
*perturbation* is interchangeable too. Everything that differs is the response.

## What extrapolation says, and why it is not the evidence

MXFP4 sits at **3× the largest point on the measured ladder**. Taking each
checkpoint's fitted exponent that far:

| | top ladder point | × 3.0^α | extrapolated | **measured** |
|---|---:|---|---:|---:|
| OPT | +2.350 % at eps 0.04 | 3.06^1.998 | 22.0 % | **11.7 %** |
| GPT-Neo | +12.052 % at eps 0.04 | 3.00^2.440 | 175.5 % | **174.4 %** |

GPT-Neo's extrapolation lands within **0.6 %** of the measured cost. OPT's
overshoots by **88 %**.

**This is not offered as a result.** It is a power law taken three times beyond
its fitted range, on a perturbation whose error kurtosis is ~14 rather than a
Gaussian's 3 — the quantisation error is deterministic, correlated with the
weights, and concentrated where the codebook is coarse. Isotropic noise of the
same RMS is not the same perturbation, and the whole point of measuring `eps_eff`
was to stop reasoning about a regime from outside it.

So the ladder is being extended to eps = 0.06, 0.09 and 0.12 on both checkpoints,
seed-controlled, and that measurement will say whether the power law holds where
MXFP4 actually operates.

## The asymmetry is the interesting part either way

If the direct measurement reproduces the pattern, the reading is sharp:
**MXFP4's structured error costs GPT-Neo what isotropic noise of the same size
would, and costs OPT about half.** That would make the structure of the error
benign on one checkpoint and not on the other — a statement about how the
codebook's error aligns with each loss surface, not about how big it is.

If the direct measurement contradicts the extrapolation on both, the power law
simply does not extend, and the regime comparison stands only over
eps ∈ [0.005, 0.04].

Either outcome is reportable and neither is claimed yet.

## What this already settles

Three explanations for the 21 × cost spread are now closed by measurement rather
than by argument:

1. **the weight distribution** — fourth moment absorbed by the scale, range 6 %
   across eight checkpoints and four families including a non-transformer;
2. **the local mass in the intervals the codebooks differ in** — range 13 %,
   the registered O1 threshold was 20 % and my own prediction was 25–60 %;
3. **the size of the perturbation** — 2 % apart on the two extremes.

What remains is the shape of each checkpoint's response, which is the one thing
that is not a property of the weights at all.

---

*`eps_eff` is pooled over all target tensors as `sqrt(Σd² / Σw²)` in float64,
with the per-tensor range reported so a pooled figure cannot hide a tensor that
behaves differently. Error kurtosis is `E[d⁴]/E[d²]²` over the same elements —
reported because two perturbations with equal RMS and different tails are not
the same perturbation, and RMS alone would assume they were.*
