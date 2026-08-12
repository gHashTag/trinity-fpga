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
