# The 4-bit advantage is a *post-training* advantage (W943)

Two experiments aimed at this project's own best result. Both were designed to
break it; one nearly did, and that is the finding.

## The gap, across training mode and architecture

Paired by seed, TNF4 − fp4 e2m1, five seeds each:

| setting | gap | SE | t (df=4) | seeds won |
|---|---:|---:|---:|---:|
| MLP, **PTQ**, MNIST | **+37.88** | 3.07 | 12.4 | 5/5 |
| MLP, **PTQ**, Fashion | **+64.42** | 2.61 | 24.7 | 5/5 |
| CNN, **PTQ**, MNIST | +12.98 | 6.11 | 2.1 | 5/5 |
| CNN, **PTQ**, Fashion | +24.90 | 5.10 | 4.9 | 5/5 |
| MLP, **QAT**, MNIST | **+0.19** | 0.03 | 6.5 | 5/5 |
| MLP, **QAT**, Fashion | **+0.89** | 0.20 | 4.6 | 5/5 |

**Quantisation-aware training closes the gap by a factor of 44 on MNIST and 31 on
Fashion.** Train the network *through* the quantiser and fp4 e2m1 recovers to
within a fifth of a point on MNIST and within nine tenths on Fashion; TNF4 under
QAT even beats its own fp32 baseline on Fashion by 0.09 pp.

The advantage does **not vanish** — it stays positive, 5/5 seeds, and remains
statistically significant (t = 6.5 and 4.6, because the variances collapse along
with the means). But its size changes category: **from "the only format that
works" to "a fraction of a point".**

## What the honest claim is now

> **TNF4's advantage is a post-training-quantisation advantage.** For a fixed model
> that cannot be retrained — the common deployment case — it is worth **13 to 65
> points** against fp4 e2m1. Where retraining is available, QAT recovers fp4 to
> within **0.19–0.89 pp**, and the remaining difference is real but small.

That sentence is more useful than the one it replaces, and it is the one the
evidence supports.

## Convolutions: the effect survives, smaller and unstable

A small CNN (conv16 → conv32 → fc10, two epochs, base 97.57 % MNIST / 85.53 %
Fashion) under the same PTQ protocol:

| format | MNIST | Fashion |
|---|---:|---:|
| TNF4 | −0.15 ± 0.09 | −0.31 ± 0.65 |
| fp4 e2m1 / GF4 | **−13.13 ± 13.66** | **−25.21 ± 11.31** |
| TNF8 / fp8 e4m3 / posit8 | −0.02…−0.03 | −0.01…−0.03 |

The fp4 collapse is **less severe on convolutions than on MLPs** (13/25 pp against
38/64) and **far more variable** (σ = 13.7 and 11.3 against 3–7 for the MLP). A
per-tensor scale over a convolution kernel spans fewer magnitudes per filter, so
fp4 underflows less often — and how often depends strongly on the draw.

**The 8-bit null survives convolutions too**: three formats within 0.03 pp on both
tasks. It has now held across MLP and CNN, weights-only and weights+activations,
two tasks, two network sizes, five seeds.

## Limits

Two epochs for the CNN against four for the MLP; QAT is straight-through with a
per-tensor max scale recomputed per step, no learned scale, no clipping schedule,
four epochs. A stronger QAT recipe would likely close the remaining gap further,
not widen it — which is the direction that matters for the claim above.

---

*φ² + φ⁻² = 3 | TRINITY*
