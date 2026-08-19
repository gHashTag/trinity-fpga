# The Pareto point, from oracles to cells to accuracy (W941)

Every earlier comparison here had one of two defects: the baselines were the
author's own RTL, or the widths came from module names. This closes both. **Every
decoder is generated from its own reference oracle by exhaustive enumeration** —
2^n codes through `conformance/*_ref.py`, emitted as a Verilog case statement — so
no implementation-quality difference can enter, and each width is read from the
format object (`sign_shift + 1`), never from a name.

Rigs: [`oracle_rtl.py`](oracle_rtl.py), [`activations.py`](activations.py).
Records: [`oracle_rtl_w941.json`](oracle_rtl_w941.json),
[`activations_w941.json`](activations_w941.json).

## Cost, all decoders generated identically

| format | physical bits | distinct values | decoder | **consumer** |
|---|---:|---:|---:|---:|
| fp4 e2m1 | 4 | 15 | 3.00 | **19.14** |
| GF4 | 4 | 15 | 5.00 | 21.14 |
| **TNF4** | **6** | 58 | 8.00 | **51.29** |
| GF8 | 8 | 255 | 12.00 | 145.57 |
| fp8 e5m2 | 8 | 247 | 18.00 | 151.57 |
| **fp8 e4m3** | 8 | 253 | 19.00 | **152.57** |
| posit8 | 8 | 255 | 33.00 | 165.14 |
| TNF8 | **11** | 2018 | 29.00 | 270.57 |

## Accuracy, with **weights and activations** both quantised

784-256-256-10, five seeds, per-tensor scale, both tasks. Quantising activations
was the standard suspicion about every null this project has reported; it does not
survive contact:

| format | MNIST W-only | MNIST W+A | Fashion W-only | Fashion W+A |
|---|---:|---:|---:|---:|
| TNF8 / fp8 ×2 / posit8 / GF8 | −0.02…+0.01 | **−0.01…+0.02** | −0.04…−0.01 | **−0.06…+0.04** |
| **TNF4** | +0.11 | **+0.33** | +0.33 | **+1.05** |
| fp4 e2m1 / GF4 | +37.99 | **+70.50** | +64.75 | **+71.32** |

**The 8-bit null survives activation quantisation entirely** — every one of five
formats stays inside 0.06 pp on both tasks. It was never an artefact of fp32
activations.

## The Pareto point

Putting the two tables together, with everything measured on one substrate by one
procedure:

| | consumer cells | MNIST (W+A) | Fashion (W+A) | verdict |
|---|---:|---:|---:|---|
| fp4 e2m1 | 19.14 | −70.50 | −71.32 | cheapest and **unusable** |
| **TNF4** | **51.29** | **−0.33** | **−1.05** | **2.97× cheaper than fp8** |
| fp8 e4m3 | 152.57 | −0.02 | −0.04 | the working baseline |

**TNF4 delivers fp8-class accuracy at one third of fp8's datapath cost** — 51.29
cells against 152.57, for a third of a point on MNIST and one point on
Fashion-MNIST, with weights *and* activations quantised. And it is the **only
sub-8-bit format measured that works at all**: fp4 and GF4 are 2.7× cheaper and
lose seventy points.

That is the paper's result, and it is not the one the manuscript currently leads
with.

## What it costs to believe this

- Truth-table decoders. Fair at these widths — every format gets the same
  treatment — and increasingly unfair to wide formats as n grows, which is why
  TNF16 (19 bits, 524,288 codes) is absent rather than estimated.
- Synthesis cells, `-nodsp`, one synthesiser, no place-and-route.
- The consumer is one 12×8 multiply; a wider accumulator moves the constant, not
  the ordering.
- Weights-only PTQ with max-scaling for the weights, per-tensor max for the
  activations, no retraining, MLPs only.
- `posit8`'s table disagrees with its oracle's own encoder on 5 of 200 samples —
  its encoder is not round-to-nearest. Its row inherits that.

---

*φ² + φ⁻² = 3 | TRINITY*
