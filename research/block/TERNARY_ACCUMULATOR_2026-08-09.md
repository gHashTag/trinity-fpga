# The accumulator law for ternary networks

## Why nobody in the ternary-network field is a competitor

In a ternary layer `y_j = SUM_i s_ji * x_i` with `s in {-1,0,+1}` the weight
carries **no format at all**: 1.58 bits, no exponent, no mantissa, and no
multiply -- the datapath is add / subtract / skip. Every published ternary
method (BitNet, TWN, TernaryBERT, PTQTP, Sherry) quantises the **weight**.

So they were never competitors and we never beat them: a number format in a
ternary network describes the **activation and the accumulator**, which is a
different object. The niche that is actually empty is the accumulator.

## The law

Fan-in `K`, non-zero weight density `p`, activations `~N(0, sigma)`:

| quantity | scaling | consequence |
|---|---|---|
| range visited, `B(K)` | `log2(pK) + c` | logarithmic in fan-in |
| error after `pK` roundings | `sqrt(pK) * 2^-(M+1)` | square-root in fan-in |

Through the KKT solution (Theorem: optimal member):

```
E*(K) = ceil(log_3 B(K))        M*(K) = N - 1 - E*(K)
```

Demand for mantissa grows as `0.5 log2 K`; demand for exponent only as
`log_3 log2 K`. **The mantissa side outruns the exponent side.**

## Measured, on real ternarised weights (SmolLM2 `mlp.down_proj`, p = 0.543)

Fixed-field accumulator, rounding at every step, 40 trials per point:

| K | binades visited | TNF16 Et=2 (M=11) | TNF16 Et=3 (M=10) | TNF16 Et=4 (M=8) |
|---:|---:|---:|---:|---:|
| 64 | 6.0 | 2.871e-02 | **7.403e-04** | 3.351e-03 |
| 256 | 8.2 | 1.697e-02 | **1.224e-03** | 5.981e-03 |
| 1024 | 10.0 | 8.555e-03 | **2.746e-03** | 1.298e-02 |
| 4096 | 12.7 | 1.493e-02 | **5.039e-03** | 2.198e-02 |
| 16384 | 13.9 | 1.286e-01 | **9.863e-03** | 3.570e-02 |

Fitted exponent in `K`: **+0.476** (Et=3) and **+0.435** (Et=4) against a
predicted `+0.5`. The square-root law holds.

`Et=2` fits at `+0.207`, and that is **not** a refutation: 9 binades cannot
hold an accumulator that visits up to 13.9, so its curve is saturation-dominated
at small `K` and rounding-dominated at large `K` -- not a power law at all. It
is the range constraint of the KKT problem being active, visibly.

## The prediction was made before the measurement, and it held

Measured span `13.9` binades gives `E* = ceil(log_3 13.9) = 3`. The measurement
independently picks `Et=3` at **every** fan-in tested. Wider (`Et=4`) buys range
already covered and pays two mantissa bits for it; narrower (`Et=2`) saturates.

## What this does NOT say

The accumulator is one component. It says nothing about the weight quantiser,
which is where the published ternary work lives and where we have no result.
The two compose but neither subsumes the other.

## Self-caught defect #10: an instrument that never rounds

The first version normalised every value by its own magnitude before
quantising, which placed each sample exactly on a grid point and returned
error **identically zero at every fan-in and every format**. A real accumulator
has a fixed scale set by the hardware, not one per sample. Error that is exactly
zero everywhere is not a result; it is a broken instrument. Replaced with
significand rounding inside the value's own binade plus explicit saturation
and underflow at the exponent field's limits.

## Self-caught defect #11: positions are not codes on binary fabric

The width rule `1 + Et + M = N` counts **positions**. A binary-packed word can
only address `2^(N-1)` magnitudes, so the realisable format obeys
`3^Et * 2^M <= 2^(N-1)`. Building a level set from the position count alone
produced a truncated table whose top level sat at 0.25 instead of 1.0, and a
perplexity of 1482 against a baseline of 14.5 -- a 100x artefact that would have
read as "our own format is catastrophic". The gap between the two accountings is
the packing loss, which is the no-free-range theorem stated concretely.
