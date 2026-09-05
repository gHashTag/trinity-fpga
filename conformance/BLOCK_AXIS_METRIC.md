# Why five of six MX formats fell out of taper_classify, and what it was not

`taper_classify.py` put five of the six MX entries in a bin labelled
"range < 6, not classifiable". That was read as a limit of the instrument, and
then as evidence that the taxonomy needed a fifth axis for block formats.

It is neither. It is two separate things, and both are worth writing down
because each looks like the other.

## 1. The classifier measured the wrong half of the format

It encodes one element with the block scale left at its default of `2^0`. An
MXFP4 element is E2M1 -- about four binades -- so the sweep runs out of range
before it has the six it needs.

In a block format the range does not live in the element. It lives in the shared
scale; the element only covers the spread *within* a block. Measuring the element
alone and concluding "no range" is like measuring a mantissa and concluding a
float cannot represent large numbers.

`block_axis_classify.py` fixes that by choosing the scale from the data, the way
a quantiser does. With that, all six classify: 139 binades, shape constant.

## 2. The metric does not transfer, and that is the deeper reason

Fixing the range exposes a second problem that no amount of instrument work will
fix. On a block of 32 with the spread real tensors actually have -- 7.72 binades,
measured, `research/block/block_ladder.json` -- MXFP4 gives:

| quarter of the block | mean relative error | share of total absolute error |
|---|---:|---:|
| smallest | **1.000** | 8.0% |
| largest | 0.078 | **52.4%** |

The smallest elements round to zero. Their relative error is 100% and they
account for 8% of the damage; the largest elements are thirteen times better
relatively and do half of it.

`M_eff` is derived from mean relative error, and that law assumes every value
matters equally. In a block format the small elements are noise-dominated **by
construction** -- letting them go is the design, not a defect. Averaging relative
error over a block therefore measures mostly the part the format was built to
discard.

**So the block axis does not need a wider map. It needs a metric that weights by
energy, and this repository already uses two: SQNR
(`research/block/scale_settled_sqnr_*.json`) and perplexity
(`research/block/oneadder_ppl_*.json`).**

## What this does not change

The block axis was decided on those metrics, and decided against us:
`research/block/BLOCK_AXIS_VERDICT_2026-08-10.md` -- MXFP4 21.94 ppl against
TNF4's 36.72 at four bits, MXFP6 14.73 against TNF6's 18.03 at six. Nothing here
reopens that. This note explains the mechanism behind a symptom; the verdict
stands.
