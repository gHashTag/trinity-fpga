# A better QAT recipe does *not* close the gap — my prediction was wrong (W944)

W943 measured the 4-bit gap under the weakest possible QAT (straight-through, a
per-tensor **max** scale, never learned) and closed it 44×, from +37.88 pp to
+0.19. Its Limits section then predicted: *"a stronger QAT recipe would likely
close the remaining gap further, not widen it."*

**That prediction is refuted.** Adding a learned scale — the LSQ gradient
`d(out)/ds = q(w/s) − w/s`, three epochs, five seeds, both tasks:

| configuration | TNF4 | fp4 e2m1 | paired gap | SE | t | seeds |
|---|---:|---:|---:|---:|---:|---:|
| **4-bit weights, learned scale**, MNIST | −0.03 | −1.61 | **+1.58** | 0.19 | **8.2** | 5/5 |
| **4-bit weights, learned scale**, Fashion | −0.02 | −0.93 | **+0.91** | 0.33 | 2.7 | 5/5 |
| **+ 4-bit activations**, MNIST | −0.26 | **−83.09** | +82.83 | 2.90 | 28.5 | 5/5 |
| **+ 4-bit activations**, Fashion | −0.55 | −1.47 | +0.92 | 0.20 | 4.5 | 5/5 |

On MNIST the learned scale made the gap **eight times larger** (0.19 → 1.58), not
smaller. The scale that a max-rule picks is not the scale training would choose,
and learning it helped TNF4 more than fp4.

**Caveat that bounds this:** W943 trained four epochs, this runs three, and the
fp32 baselines differ accordingly (97.26 vs 97.02 on MNIST). The cross-wave
comparison is therefore indicative; the **within-run paired tests are not**, and
they are what the table reports.

## Four-bit activations break fp4, unevenly

With activations also on the 4-bit grid, `fp4 e2m1` collapses to **13.93 % ± 6.30**
on MNIST — worse than chance-adjacent — while holding **84.58 %** on Fashion. The
σ of 6.30 says what the mean does not: this is an **instability**, not a clean
83-point defeat. Some seeds diverge and some do not.

TNF4 under the same treatment loses **0.26 pp** (MNIST) and **0.55 pp** (Fashion),
with σ ≤ 0.58 — stable on both.

So the defensible statement is about **robustness, not magnitude**: at four bits
with a trained scale and quantised activations, fp4 e2m1's outcome depends on the
seed, and TNF4's does not.

## What this does to the claim

W943 narrowed the headline to "a post-training advantage worth under a point where
retraining is available". W944 partially **un-narrows** it: with a real recipe the
weights-only gap is **0.9–1.6 pp**, not 0.19, and adding 4-bit activations makes
the competitor unstable. The honest range is now:

> **13–65 pp** without retraining · **0.9–1.6 pp** with a trained scale ·
> **and fp4 becomes seed-dependent once activations are quantised too.**

Three waves, three different numbers for one comparison, each from a better
experiment than the last. The range is the result; any single number in it is a
recipe, not a property.

---

*φ² + φ⁻² = 3 | TRINITY*
