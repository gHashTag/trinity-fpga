# The accuracy coordinate, at last — and where the format stops mattering (W938)

`top-1`, `ImageNet`, `CIFAR`, `MNIST`: **0 hits across 7,858 lines** of the
manuscript. Every LUT-domain competitor prices area against a named accuracy on a
named dataset, so a reviewer cannot currently tell whether 28 LUT/weight is good.
This is the first task-level number in the project.

**Setup.** MNIST, a 784-32-10 MLP, 4 epochs of Adam, seed 20260820, fp32 baseline
**93.39 %**. Trained weights are then round-tripped through **the same shipped
conformance oracles** the paper's accuracy tables use (`conformance/*_ref.py`,
imported unchanged) and test accuracy is re-measured. Weights only; activations
stay fp32. Script [`accuracy_coordinate.py`](accuracy_coordinate.py), record
[`accuracy_coordinate_w938.json`](accuracy_coordinate_w938.json).

## With a per-tensor scale — the deployment-realistic path

| width | format | top-1 | Δ vs fp32 |
|---|---|---:|---:|
| **16** | TNF16 / posit16 / takum16 | 93.39 % | 0.00 pp |
| | GF16 / binary16 | 93.40 % | −0.01 pp |
| | bfloat16 | 93.38 % | +0.01 pp |
| **8** | GF8 | 93.48 % | −0.09 pp |
| | posit8 | 93.39 % | 0.00 pp |
| | TNF8 / fp8 e4m3 / fp8 e5m2 | 93.29 % | +0.10 pp |
| **4** | **TNF4** (E_t = 2, M = 1) | **93.38 %** | **−0.01 pp** |
| | GF4 | 87.90 % | +5.49 pp |
| | fp4 e2m1 | 87.90 % | +5.49 pp |

**At 16 bits the choice of number format is invisible to the task.** Six formats
whose representation errors differ by **16×** (8.5e-05 … 1.35e-03) land inside
0.02 pp of each other. At 8 bits the errors differ by 2× and the spread is
0.19 pp — still noise on this task.

**At 4 bits the format is worth 5.5 points, and TNF4 is the one that survives** —
0.01 pp from the fp32 baseline where fp4 e2m1 and GF4 lose 5.49. That is the width
where the field actually fights, and it is the only width in this experiment where
a number-system argument has anything to explain.

## Without a scale — an artefact, recorded so nobody quotes it

The same 4-bit run without a per-tensor scale gives TNF4 92.27 % against **21.72 %**
for both fp4 e2m1 and GF4 — a 70-point gap. **It is not an accuracy result.** Those
two formats flush **98.8 % of the weights to zero** (25,142 of 25,450): the median
trained weight is 0.056, far below their smallest representable magnitude, so what
the run measures is dynamic range, not the number system. No real sub-8-bit
deployment ships without a scale. The unscaled table is in the record only so the
70× is never quoted as a finding.

## The empirical prior, which was the open question

The trained tensors span **8.1 binades** between the 1st and 99th percentile of
|w| (15.9 binades end to end), with median |w| = 0.056. The paper's accuracy
regenerators draw uniformly over **77 binades** — roughly **9.5× wider than the
distribution the format will actually see**. W937 could only bound this; here it
is measured on real weights.

## The resolution floor — added after checking against the field

**The 16- and 8-bit rows resolve nothing, and that must be said before they are
read.** On a 10,000-image test set at p = 0.934 the binomial standard error is
**0.248 pp**, so the 95 % interval is about **±0.49 pp**. The observed spreads are
0.02 pp (16-bit) and 0.19 pp (8-bit) — both inside one standard error. The honest
label is **"not discriminative at this width"**, never "lossless, therefore
competitive". Only the 4-bit separation (5.49 pp, ~22σ) clears the floor.

Two corollaries. `bfloat16` and `binary16` at −0.01 pp did not "beat" fp32 — that
is **one test image**. And this is a **single seed on a single split**, which the
LUT-DNN literature does not accept: NeuraLUT reports 10-seed ablations, LUTNet
plots min/mean/max over five runs, SparseLUT retrains every baseline rather than
quoting it.

**The baseline is weak, and saying so costs nothing.** 93.39 % from four epochs on
784-32-10 sits *below* the field's quantised results: NeuraLUT-Assemble 98.6 % at
5,037 LUT, DWN 97.8 % at 2,092 LUT, TreeLUT 96.6 %, FINN's binarised SFC 95.83 %,
and even LogicNets-equivalent sparse networks at 93.76 %. FINN's own table has a
plain fp32 MLP at 97.3 %. So "preserves fp32 accuracy" here means preserving an
accuracy that the field's **fully binarised** networks already beat.

## Never compose these numbers with the area numbers

The accuracy above came from an **fp32 numerical simulation in which the format
never entered a datapath** — no multiplier, no accumulator and no activation ever
saw a TNF16 value; only the stored weights were round-tripped. The W936 figure is
a **decode block**. The literature's LUT counts (FINN 91,131; PolyLUT 70,673;
NeuraLUT 54,798) are complete placed-and-routed inference engines including
popcount trees, thresholding and stream plumbing.

So "our format: 93.4 % at N LUTs" is a category error of one to two orders of
magnitude, and it implies an end-to-end measurement that does not exist. The two
results belong in different sections. **The right peer group for a decode cost is
the codec literature** — Hunhold's takum codec paper reports no task accuracy at
all, only codec latency and CLB LUT swept over n = 8/16/32/64.

## How this should be positioned

- Weights-only PTQ, activations fp32, no retraining, no calibration beyond
  max-scaling. Better PTQ narrows every gap in the 4-bit row.
- MNIST with a 25 k-parameter MLP is the *easiest* task in this literature. A
  5.49 pp drop here would be substantially larger on a real network, and a 0.01 pp
  drop proves much less than it looks. **This is a lower bound on difficulty, not
  a competitive result.**
- `GF4` and `fp4 e2m1` agree to the digit in both runs, which suggests they are
  the same value lattice at four bits; that is worth a line in any table that
  prints both.
- Pairing with W936: TNF's decode is **2 cells** against fp8's 12 and posit16's
  125. Area and accuracy now exist in the same document for the first time.

---

*φ² + φ⁻² = 3 | TRINITY*
