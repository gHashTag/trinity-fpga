# Pre-registration: what the three horns should cost

Written **before** the sweep finished. At the time of writing `horns54.txt`
contains one line — `extend|573|...` — and nothing for guard or assign.

## The three decoders

They differ only in what happens to the 13 out-of-specification offsets of
`TNF16c` (243..255, covering 3,328 of 65,536 codes):

| horn | logic | image of the surplus |
|---|---|---|
| **extend** | none | 3,328 distinct values the format does not define |
| **guard** | `off > 242` → NaN | 1 value |
| **assign** | `off > 242` → `off − 243` | aliased onto 13 canonical offsets |

## Two effects pull opposite ways

**Gate count.** Extend needs no comparison. Guard needs a magnitude compare
against 242 plus a mux to a constant. Assign needs the same compare, plus an
8-bit subtract, plus a mux. **On gates alone: extend < guard < assign.**

**Output image.** Guard collapses 3,328 codes onto a single NaN, so everything
downstream of the decoder sees a smaller image and observability-don't-care
minimisation shrinks it. Assign leaves the image the same size as extend's
in-specification image. **On downstream pruning: guard < assign ≈ extend.**

## Prediction

I expect **the image effect to lose to the gate count**, because the surplus is
only 5.1% of the code space and the accumulator behind the decoder is wide. So:

> **extend (573) < guard < assign, with guard around 585–595 and assign around
> 595–615 LUT.**

Confidence: moderate on the ordering, low on the magnitudes. The one measurement
that would surprise me is **assign cheaper than guard** — that would mean the
subtract is free in the mapper's packing while the constant-NaN mux is not, and
it would say the image effect is stronger than the surplus fraction suggests.

## What each outcome would mean

- **assign dearest, as predicted** — the third horn is bought for its correctness
  property (no code outside the format) and not for area. The paper recommends it
  on that basis and states the price.
- **assign cheapest** — the reservation proposition's dilemma dissolves entirely:
  the standardised option is both safer and smaller, and guarding was never
  worth doing. That would be the strongest possible outcome and I do not expect
  it.
- **all three within the 1.43% resolution threshold** — the dilemma is real but
  costless, which is itself worth stating: the paper spent three iterations on a
  choice the instrument cannot see.

---

# Outcome: the prediction failed on both axes

| horn | LUT | MHz | MHz/LUT | vs `extend` |
|---|---|---|---|---|
| **extend** | 573 | 67.87 | **0.1185** | — |
| **guard** | 591 | 68.14 | 0.1153 | −2.66%, p = 3.0e−05 |
| **assign** | 576 | 59.24 | 0.1029 | **−13.17%**, p = 2.1e−89 |

**Predicted `extend < guard < assign` on area. Measured `extend < assign <
guard`.** Assign came in *cheaper* than guard — 576 against 591 — which is the
one outcome recorded above as the surprise. The gate-count argument was wrong:
the conditional subtract packs into the same LUTs as the comparison it shares an
input with, while guard's mux to a 32-bit constant does not.

**And the axis that decided it was one the prediction never mentioned.** Assign
is $13.2\%$ worse per LUT not because of area but because of *frequency*:
59.24 MHz against 68.14. The subtract lands in the critical path between the
offset field and the exponent adder; the guard's mux does not, because a constant
NaN needs no arithmetic behind it.

So the pre-registration was wrong about the ordering it predicted and silent
about the mechanism that mattered. Recording both is the point of writing it
down first.

## What the paper should now say

The three horns are all real and none is free:

- **extend** — fastest per LUT, and 3,328 codes of the word decode to values the
  format does not define. A corrupted offset is undetectable.
- **guard** — costs $2.66\%$, and every code is either defined or flagged. The
  cheapest way to make the format total.
- **assign** — costs $13.17\%$, and every code *names a value the format
  defines*. Strictly the strongest correctness property, and strictly the most
  expensive here.

**The recommendation is `guard`**, and it is now a measurement rather than a
preference. The IEEE 754 answer is the safest of the three and it is the dearest
on this fabric, which is worth stating precisely because the decimal standard's
own reasoning is about interchange rather than about a critical path — a format
shipped for exchange between machines and a format shipped as a datapath do not
face the same cost.

## What was learned that no argument would have given

Both the gate-count argument and the observability-don't-care argument predicted
the wrong ordering, in opposite directions, and the true answer turned on
placement and timing rather than on either. **A cost argument about a decoder
that does not mention the critical path is not an argument about the decoder's
cost.**
