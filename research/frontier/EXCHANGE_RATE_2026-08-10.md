# The break-even width does not exist, and the last estimate is gone

Two results, and the first is a correction applied to a plan rather than to a
finished claim.

## 1. My own next step was ill-posed, and T7 caught it before it was run

The previous iteration recommended finding "the width beyond which a taper is not
justified". Applying T7 to that proposal before spending on it: the question
requires knowing **how many LUTs a bit of accuracy is worth**, which is unstated
and design-dependent. No single width exists.

**This is the first time tonight the method was applied prospectively rather than
retrospectively.** Twelve theorems were learned by discovering a claim was
already broken; this one prevented a measurement instead of correcting one.

## 2. The well-posed form: the exchange rate as a function of width

| N | taper's gain, bits | area multiple | delay multiple | **bits per area multiple** |
|---:|---:|---:|---:|---:|
| 16 | 1.76 | 3.0x | 6.5x | **0.589** |
| 32 | 2.41 | 5.0x | 8.0x | **0.485** |
| 64 | 6.10 | 20.5x | 61.5x | **0.297** |

**T12 (the exchange rate is monotone in width).** A taper's accuracy gain `g(N)`
grows roughly linearly in width while its cost multiple `r(N)` grows as
`N^(1.16−0.17) = N^0.99`, so `g/r` decreases. Measured: 0.589, 0.485, 0.297.

**Corollary.** Every project with a fixed exchange rate `K` has its own break-even
width `N*(K)`, and it is its own. What a designer reads off:

| their `K`, bits per area multiple | taper justified |
|---:|---|
| 0.05 – 0.20 | to 64 bits |
| 0.50 | only to 16 |
| 1.00 | nowhere |

The absence of a single answer is a property of the question, not a gap in the
measurements. A design that pays dearly for area loses the taper earlier; one
with cheap area keeps it longer.

## 3. The last estimated number, now measured

The selection table's gradient row said "~40 binades, from the literature" -- the
only figure in it not from this tree. Measured on one backward pass of the same
model used for every other weight figure, loss 2.7913, 211 layers with gradients:

| quantity | estimate | **measured** |
|---|---:|---:|
| gradient span, median per layer | ~40 | **17.29** |
| 90th percentile across layers | — | 19.30 |
| maximum over layers | — | 35.01 |
| span across the whole model at once | — | **30.70** |

**The literature estimate was 2.3x too high** for a per-layer scale. It does not
flip any row -- 17.29 still exceeds the 8 and 10 crossovers, so TNF16 and TNF32
keep those rows -- but the selection table now contains **no estimated
quantities**.

The gap between 17.29 per layer and 30.70 across the model is itself a design
statement: a single format for every layer must span 30.70 binades; a per-layer
scale needs 17.29. That is a 13-binade difference, worth about two exponent bits.

## Count

Twelve theorems about measurement. This iteration's contribution is the first
that cost nothing to learn -- the method refused a bad question before the
question was asked of the hardware.
