# The Appendix F alarm was false, and what was there instead

A literature review flagged MR-GPTQ (arXiv:2509.23202) Appendix~F as possibly
anticipating the fractional-exponent scale ladder — "a larger exposure than the
encoder claim, because it touches the $2^{k/3}$ ladder itself." Read it.

**Appendix F is "Standard deviation."** It estimates the variance of evaluation
scores across GPTQ calibration seeds and across scale-selection and ordering
strategies, on Llama-3.1-8B-Instruct, reporting means and standard deviations
over five random seeds. Appendix G is an ablation of linear transforms — DCT,
DST, Hadamard, GSR — at sizes 16 to 256. **Neither describes a fractional scale
ladder.** The alarm is withdrawn.

## What is actually there, and it matters more than the false alarm

MR-GPTQ names the same defect this paper names — its abstract says outright that
**MXFP4's power-of-two scale quantisation reduces accuracy** — and repairs it by
a *different* mechanism: **learned per-block scale shifts**, not a finer grid.

That is the closest published alternative to the mechanism measured here, and
the distinction is worth drawing precisely:

| | learned shift (MR-GPTQ) | finer ladder (this paper) |
|---|---|---|
| adapts | per block, independently | globally, fixed |
| costs | a trained parameter per block | a multiplier in the applier |
| priced in silicon | not by them | yes, here: 207 → 1,244 LUT |
| requires calibration | yes | no |

**We have not compared them.** A reader choosing between the two axes should know
that only one has been placed and routed. Stated in the paper.

## And a discipline worth borrowing

Their Appendix~F does what this campaign spent three iterations learning to do:
report a spread rather than a point, across seeds, for every configuration. They
vary *calibration* seeds where we vary *placement* seeds, and their standard
deviations on the Platinum benchmark run from 0.74 to 2.29 points — wide enough
that several of their own orderings are not separated either. **A paper that
prints its own spread is easier to trust than one that prints a rank.**
