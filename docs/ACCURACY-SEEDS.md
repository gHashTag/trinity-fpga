# Five seeds, two tasks — the 4-bit result becomes admissible (W939)

W938 gave one seed on one split, which this literature does not accept: NeuraLUT
reports 10-seed ablations, LUTNet plots min/mean/max over five, SparseLUT retrains
every baseline rather than quoting it. Here are **five seeds** on **two tasks**,
same architecture (784-32-10), same weights-only PTQ with a per-tensor max scale,
activations fp32. Record [`accuracy_seeds_w939.json`](accuracy_seeds_w939.json),
script [`accuracy_seeds.py`](accuracy_seeds.py).

## MNIST — fp32 baseline 93.76 ± 0.36 pp

| width | format | top-1 | drop |
|---|---|---:|---:|
| 16 | TNF16 / posit16 / takum16 / GF16 / bfloat16 / binary16 | 93.76 ± 0.36 | ±0.01 |
| 8 | GF8 · posit8 · TNF8 · fp8 e4m3 | 93.70–93.75 | +0.01 … +0.05 |
| 8 | fp8 e5m2 | 93.63 ± 0.31 | +0.13 ± 0.10 |
| **4** | **TNF4** | **93.44 ± 0.27** | **+0.32 ± 0.23** |
| **4** | GF4 · fp4 e2m1 | 85.04 ± **5.10** | +8.72 ± 5.00 |

## Fashion-MNIST — fp32 baseline 84.20 ± 0.29 pp

| width | format | top-1 | drop |
|---|---|---:|---:|
| 16 | all six | 84.18–84.20 | ±0.02 |
| 8 | GF8 · posit8 · TNF8 · fp8 e4m3 | 84.18–84.20 | +0.00 … +0.02 |
| 8 | fp8 e5m2 | 83.83 ± 0.36 | +0.37 ± 0.34 |
| **4** | **TNF4** | **83.34 ± 0.51** | **+0.85 ± 0.64** |
| **4** | GF4 · fp4 e2m1 | 55.60 ± **13.95** | +28.60 ± 13.94 |

## The paired test, which is the one that matters

Same seeds, same trained networks, so the comparison is paired:

| task | TNF4 − fp4 e2m1, per seed | mean | SE | t (df = 4) | verdict |
|---|---|---:|---:|---:|---|
| MNIST | +5.48, +5.81, +5.10, +8.55, +17.08 | **+8.40** | 2.25 | **3.7** | significant, p < 0.05 |
| Fashion | +20.17, +49.23, +13.23, +23.46, +32.64 | **+27.75** | 6.21 | **4.5** | significant, p < 0.05 |

TNF4 wins **5 of 5 seeds on both tasks**, and the effect is **3.3× larger on the
harder task**. That direction is the strongest evidence in the table: an artefact
of one split would not scale with task difficulty.

## What is still not a result

- **16 and 8 bits resolve nothing of practical size.** The one 8-bit difference
  that passes a paired test — GF8 over fp8 e5m2, +0.12 pp on MNIST (t = 3.8) and
  +0.37 pp on Fashion (t = 2.8) — is statistically real and practically
  irrelevant. Saying both halves is the honest form.
- **GF4 and fp4 e2m1 agree to the digit on every seed of both tasks.** They are
  one value lattice; any table printing both is printing a column twice.
- **The competitors are unstable, not merely worse:** GF4/fp4 carry σ = 5.10 pp on
  MNIST and **13.95 pp** on Fashion, against TNF4's 0.27 and 0.51. A format whose
  accuracy depends that strongly on the seed is a deployment hazard independent of
  its mean.
- **Still weights-only PTQ on a small MLP**, and the fp32 baselines (93.76, 84.20)
  remain below the LUT-DNN field's *quantised* MNIST results (NeuraLUT-Assemble
  98.6 %, DWN 97.8 %, FINN's binarised SFC 95.83 %). This measures formats against
  each other, not this project against the field.
- **Never compose these with the decode-area numbers** (T781): no circuit produced
  both.

---

*φ² + φ⁻² = 3 | TRINITY*
