# The selection table: what to use, at what width, and what it costs

Nine iterations narrowed the claims. This assembles the narrowing into the form a
practitioner can use: for each object being quantised, which format wins on
accuracy, at what threshold, and what its decode costs.

## Inputs, all measured

- **Crossovers** for eleven tapers against matched-width TNF (T9).
- **Decode cost**, isolated decoder, full observation, median of five seeds.
- **Workload spans** from real SmolLM2 weights.

## The table

| object | span | width | accuracy winner | threshold | decode LUT / MHz |
|---|---:|---:|---|---:|---|
| element inside an MX block | 3.04 | 8 | **TNF8** | 1 | — |
| | | 16 | posit16 | 8 | 302 / 62 |
| | | 32 | posit32 | 10 | 517 / 49 |
| | | 64 | posit64 | 54 | — |
| whole layer weight | 13.4 | 16 | **TNF16** | 8 | **101 / 408** |
| | | 32 | **TNF32** | 10 | — |
| | | 64 | posit64 | 54 | — |
| accumulator, fan-in 512 | 13.9 | 16 | **TNF16** | 8 | **101 / 408** |
| | | 32 | **TNF32** | 10 | — |
| training gradients | ~40 | 16 | **TNF16** | 8 | **101 / 408** |
| | | 64 | posit64 | 54 | — |

## Where the two axes agree

At 8 bits, and for whole weights, accumulators and gradients at 16 and 32 bits,
TNF wins on both accuracy and decode. Those rows are unambiguous.

## Where they disagree, and the honest price

For an element inside a block at 16 bits the taper is more accurate and much more
expensive to read:

| | accuracy at \|e\|≈1 | decode |
|---|---:|---|
| posit16 | **10.93 bits** | 302 LUT @ 62.39 MHz |
| TNF16 | 9.17 bits | **101 LUT @ 407.66 MHz** |
| difference | **1.76 bits to posit** | **3.0x area, 6.5x frequency to TNF** |

**The honest statement is both numbers, not a recommendation.** posit16 is 1.76
bits more accurate on this workload and costs three times the area and six and a
half times the delay to decode. Which matters depends on what is scarce in the
datapath, and this work does not know that for someone else's design.

## What is missing, named

- **64-bit decode was never measured.** posit64 leads on accuracy to 54 binades,
  which covers every workload here, and we have no decode figure to set against
  it. There is no recommendation at 64 bits.
- **TNF32 decode was never measured** either; only TNF16 appears in the isolated
  table.
- Gradient span is estimated from the literature rather than measured on a
  training run.

## Theorem

**T10 (a selection needs both axes and their exchange rate).** Choosing a format
requires the accuracy crossover *and* the decode cost, and the two can point
opposite ways. A recommendation is well-founded only when the design's scarce
resource is known; absent that, the honest output is the pair of costs, not a
winner.

This is the fourth time this session that a single-number answer turned out to be
the wrong shape for the question. The pattern is now explicit: **ratios hide
choices, crossovers name them, and pairs of costs name what is still unknown.**
