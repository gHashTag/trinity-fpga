# The scale-cost frontier, and a strict win over MXFP4

Comparing scale formats in pairs hides what decides them. A scale is one value
per K weights, so it costs `scale_bits / K` bits per weight, and the deployed
choices sit at very different costs. Put perplexity against total bits per
weight and the axis settles in one table. Element is E2M1 throughout; only the
scale varies. 40 windows, wikitext-2.

| scheme | scale b/w | total b/w | SmolLM2 (fp32 14.4874) | Qwen (fp32 12.2277) |
|---|---|---|---|---|
| `phi^k` 4b/64 | 0.0625 | 4.0625 | 22.0978 | 15.0090 |
| **`phi^k` 4b/32** | **0.1250** | **4.1250** | **21.3545** | **14.8512** |
| `2^k` 4b/32 | 0.1250 | 4.1250 | 22.4998 | 14.9447 |
| `phi^k` 5b/32 | 0.1562 | 4.1562 | 21.3545 | 14.8512 |
| **MXFP4, E8M0 8b/32** | 0.2500 | 4.2500 | 22.4998 | 14.9447 |
| `phi^k` 4b/16 | 0.2500 | 4.2500 | 21.3112 | 14.5165 |
| E4M3 8b/32 | 0.2500 | 4.2500 | 19.8628 | 13.7636 |
| NVFP4-like E4M3 8b/16 | 0.5000 | 4.5000 | 18.5445 | 13.5340 |

The Pareto set is identical on both models: `phi^k` 4b/64, `phi^k` 4b/32,
E4M3 8b/32, E4M3 8b/16.

## Three findings

**1. MXFP4's scale field is four bits wider than it needs to be.** `2^k` at four
bits reproduces E8M0's perplexity *exactly* -- 22.4998 and 14.9447 on the two
models, to the last digit. The range actually occupied is 8.32 and 9.12 binades;
eight exponent bits buy nothing over four.

**2. At those four bits, `phi^k` beats `2^k`.** 21.3545 against 22.4998, and
14.8512 against 14.9447.

**3. Therefore `phi^k` 4b/32 strictly dominates MXFP4** -- cheaper by 0.125 bits
per weight and better on both models. Not a trade.

## What is not ours

E4M3 -- a scale with a mantissa, which is what NVFP4 uses -- dominates the upper
frontier on both models, 19.8628 and 13.7636 at the same 4.2500 bits per weight
where MXFP4 sits. A geometric grid, however fine, cannot match a scale that
carries significand bits. The direction NVFP4 took is stronger than the
direction MXFP4 took, and stronger than ours.

So the frontier has two regions: below 4.25 bits per weight it is ours, above it
is NVFP4's. That is the honest shape of the result.

## Against the stop-rule

The owner's condition is that the paper does not publish until TNF beats MXFP4
on the block axis by measurement. What is measured here is that **MXFP4's
scale, replaced by a phi-power grid, is beaten -- more cheaply and on two
models**. The element remains E2M1, so the composite is not TNF, and whether
that satisfies the condition is the owner's call rather than ours. It is stated
precisely so the call can be made on what was actually measured.

What makes the grid ours is not the measurement but the datapath: on a binary
machine `2^k` is a shift and `phi^k` is not, while on the datapath of this paper
`phi^k` is k Fibonacci steps and needs no multiplier. A scale grid that costs
everyone else a multiplier is free here.
