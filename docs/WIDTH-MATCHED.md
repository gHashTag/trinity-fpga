# Against a same-width float, the advantage is stability — not accuracy (W945)

W944 reported an 83-point gap at 4-bit activations and called it an instability
with "some seeds diverging". The per-seed record says otherwise: fp4 e2m1 gave
**11.51, 10.28, 11.35, 25.17, 11.35** on MNIST — *all five seeds collapsed*, four of
them to chance. That was the first error. The second is larger.

## The comparison was not width-matched

| grid | values | positive values | smallest positive |
|---|---:|---:|---:|
| **TNF4** (physically **6 bits**) | **57** | 28 | **0.125** |
| fp4 e2m1 (4 bits) | 15 | 7 | 0.500 |

MNIST is **80.7 % zeros** with the rest sparse; quantising its activations to a
grid whose smallest positive value is 0.5 of the tensor max drives 84.2 % of them
to zero and the signal disappears. Fashion is 50 % zeros and survives. So the
83-point figure measured **a 57-level grid against a 15-level grid on a sparse
task** — a width effect and a dataset interaction, not a number system.

## Re-run against real 6-bit floats

`fp6 e2m3` and `fp6 e3m2` are shipped by the same oracle. Learned scale, three
epochs, five seeds, paired:

| configuration | TNF4 − fp6 e3m2 | TNF4 − fp6 e2m3 | TNF4 − fp4 e2m1 |
|---|---:|---:|---:|
| weights, MNIST | **+0.11** (t 2.2) | +0.82 (t 9.0) | +1.58 (t 8.2) |
| weights, Fashion | **+0.17 (t 1.2, 3/5 — not significant)** | +0.84 (t 4.2) | +0.91 (t 2.7) |
| weights+acts, MNIST | +23.13 (t 1.6, **σ 32.3**) | +51.75 (t 2.5, **σ 46.1**) | +82.83 (t 28.5) |
| weights+acts, Fashion | **−0.42 (t −1.9) — fp6 e3m2 WINS** | +0.12 (t 0.8) | +0.92 (t 4.5) |

**Against the fair peer, `fp6 e3m2`, TNF4's accuracy advantage is 0.11–0.17 pp and
is not significant on Fashion — and with quantised activations on Fashion, fp6 e3m2
beats TNF4 by 0.42 pp.**

## What actually survives

Stability. Across every configuration TNF4's standard deviation is **0.17–0.72 pp**.
With quantised activations on MNIST, `fp6 e2m3` has **σ = 46.09** and `fp6 e3m2`
**σ = 32.33** — training either one is a coin flip on that task, while TNF4 lands
at 96.76 ± 0.21 every time.

So the honest claim at matched width is:

> **TNF4 does not beat a same-width float on mean accuracy — it ties it (+0.11 to
> +0.17 pp, not significant on one task, and −0.42 pp in one configuration). What
> it does is train reliably where they do not: σ ≤ 0.72 against σ up to 46.**

## The correction chain, fourth link

| wave | claim | why it moved |
|---|---|---|
| W940 | TNF4 vs fp4: **+37.9 / +64.4 pp** | PTQ only |
| W943 | QAT closes it to **+0.19 / +0.89** | trained through the quantiser |
| W944 | learned scale re-opens it to **+1.58 / +0.91** | better recipe |
| **W945** | vs a **same-width** float: **+0.11 / +0.17**, n.s. on one task | fp4 was 4 bits, TNF4 is 6 |

Every step moved against the project's interest, and every one was forced by the
previous step's own principle. The surviving claim is smaller, matched, and
significance-tested — which is what makes it usable.

---

*φ² + φ⁻² = 3 | TRINITY*
