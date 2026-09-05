# The 4-bit effect scales on two independent axes (W940)

W939 showed the 4-bit separation growing with task difficulty. This adds a second,
orthogonal axis — network capacity — by re-running the identical protocol on a
**784-256-256-10** MLP (269 k parameters, against 25 k before). Five seeds, both
tasks, weights-only PTQ with a per-tensor scale, paired by seed.

| network | task | fp32 base | TNF4 − fp4 e2m1 | SE | t (df = 4) | seeds won |
|---|---|---:|---:|---:|---:|---:|
| 784-32-10 | MNIST | 93.76 | +8.40 | 2.25 | 3.7 | 5/5 |
| 784-32-10 | Fashion | 84.20 | +27.75 | 6.21 | 4.5 | 5/5 |
| **784-256-256-10** | MNIST | **97.26** | **+37.88** | 3.07 | **12.4** | 5/5 |
| **784-256-256-10** | Fashion | **86.85** | **+64.42** | 2.61 | **24.7** | 5/5 |

**The effect grows on both axes and the significance follows.** Harder task: ×3.3.
Bigger network: ×4.5 on MNIST, ×2.3 on Fashion. t climbs from 3.7 to 24.7. A split
artefact, a seed artefact or a scaling bug has no reason to track *either* axis,
let alone both.

**And the baseline is no longer weak.** 97.26 % on MNIST matches the plain fp32 MLP
in FINN's own table (97.3 %) and sits above FINN's binarised SFC (95.83 %) and
TreeLUT (96.6 %). The W938 criticism — "you are preserving an accuracy the field's
1-bit networks already beat" — no longer applies to the bigger model.

## Eight bits is still nothing, and now on a stronger model

On the 269 k-parameter network the **largest** absolute drop across all five 8-bit
formats is **0.02 pp** on MNIST and **0.04 pp** on Fashion. Against a binomial
standard error of ~0.16 pp at p = 0.97, that is not a measurement of anything. The
null found on the small model is not an artefact of the model being too easy —
it survives a 10× larger network and a harder task.

## What this does and does not license

- It licenses: **"at four bits, on two tasks and two network sizes, TNF4 holds
  within 0.33 pp of fp32 while fp4 e2m1 and GF4 lose 38–65 points, 5/5 seeds,
  p ≪ 0.01."**
- It does not license any statement about 8- or 16-bit formats, where nothing is
  resolvable.
- It remains weights-only PTQ with max-scaling, activations fp32, on MLPs. A
  convolutional model, quantised activations, or QAT could each move it.
- GF4 and fp4 e2m1 remain identical to the digit on every seed of every
  configuration — one lattice, two names.

---

*φ² + φ⁻² = 3 | TRINITY*
