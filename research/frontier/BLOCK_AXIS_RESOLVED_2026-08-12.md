# The stop-rule as written is met. The stop-rule as intended is not.

The owner's rule, set 2026-08-09: *the paper does not publish until TNF beats
MXFP4 on the block axis by measurement.* Eleven agents, two independent
codebases, 14.9 million real blocks. Here is the answer, and it has two halves
that must be reported together.

## Half one: TNF beats MXFP4, measured

TNF-B32 — five-trit balanced-ternary scale field, step $2^{k/3}$, byte-identical
E2M1 elements, block 32, **exactly 4.25 bits/element**:

| source | blocks | MXFP4 RMSE | TNF RMSE | Δ | ΔSQNR | losing blocks |
|---|---|---|---|---|---|---|
| smollm2 (106.2 M weights) | 3,317,760 | 0.0225976709 | 0.0187310354 | **+17.11 %** | +1.63 dB | **0** |
| qwen (357.8 M weights) | 11,182,080 | 0.0023861225 | 0.0019942209 | **+16.42 %** | +1.56 dB | **0** |
| iid N(0,1) | 200,000 | 0.1150164117 | 0.0967254771 | +15.90 % | +1.50 dB | 0 |
| Student-t(3) | 200,000 | 0.2498330989 | 0.1915720973 | +23.32 % | +2.31 dB | 0 |

Downstream, smollm2 on wikitext2-test, 304,986 tokens, 210 Linear modules:

| arm, all 4.25 b/el | ppl | vs MXFP4 | fp32 gap closed |
|---|---|---|---|
| fp32 | 15.415 | — | 100 % |
| MXFP4 (Algorithm 1) | 25.056 | — | 0 % |
| **TNF 5-trit, step 1/3** | **20.034** | **+20.04 %** | **52.1 %** |

**Reproduced digit-for-digit to ten significant figures** by a re-implementation
written from the spec text that never imports the candidate's code. Zero losing
blocks in 14,899,840 real and 400,000 synthetic. Bits recomputed from scratch
four times: $1+2+1=4$; $32\times4=128$; scale $8$; $136/32 = 4.25$. No per-block
flag, no second scale, no side table.

**By the rule as written — beat MXFP4 on its own axis and its own workload with a
reproducible measurement — this is met.**

## Half two: ternary is not why, and a binary ladder does it better

**The ternary reading of the byte is a measured net negative.** At matched
dynamic range, 243 ternary codes against 255 binary ones, the binary field wins
on **six of six range settings across four sources, without exception**. And
against the natural binary ladders at the same eight bits:

| scale ladder, same 8-bit field | smollm2 | qwen |
|---|---|---|
| $2^{k}$ (MXFP4's own) | +3.50 % | +2.86 % |
| $\varphi^{k}$ | +8.51 % | +7.53 % |
| $2^{k/3}$ — **five trits, ours** | **+17.11 %** | **+16.42 %** |
| $2^{k/8}$ — plain binary | **+22.37 %** | **+21.79 %** |
| $2^{k/16}$ | +23.74 % | +23.23 % |

**A plain binary ladder beats the ternary one by five to six RMSE points and 1.1
perplexity.** Downstream the $2^{k/8}$ ladder closes 63.8 % of the fp32 gap where
TNF closes 52.1 %.

## What the gain actually is

**100 % scale axis, 0 % element axis** — every winning arm uses the byte-identical
E2M1 codebook. Within the scale axis the SSE decomposition isolates it:

| source | floor rule (a better *code*) | one-point-per-binade *grid* | irreducible codebook |
|---|---|---|---|
| smollm2 | 6.9 % | **35.8 %** | 57.3 % |
| qwen | 5.6 % | **36.3 %** | 58.1 % |

The floor rule is a ~6 % bug; the coarse grid is a ~36 % bug, six times larger.

**And the mechanism is resolution, not algebra.** Error is monotone in
points-per-binade and in nothing else: $\sqrt{\varphi}^{\,k}$ at 2.8808
points/binade lands next to $2^{k/3}$ at 3.0000. **$\varphi$ is not special
here** — it is a step size that happens to be finer than a binade.

## Two things this hands back to MXFP4

**About a fifth of the perplexity win is free to the baseline.** Replacing
Algorithm 1's floor with an SSE-argmin over the same 254 E8M0 codes emits a
**byte-legal MXFP4 bitstream** and buys +12.1 % ppl, 31.6 % of the fp32 gap.
That is an encoder change, not a format win, and belongs to MXFP4.

**"The element axis has at most 0.9 %" is false as stated.** The 0.9 % in this
paper is a *perplexity gap for the squared-error-optimal codebook* — evidence
that SSE is a bad proxy — not a bound. Measured element-axis headroom is
**+1.6 % to +8.5 %** depending on the scale ladder underneath it.

## The one hole in the 4.25 accounting

At $K=16$ the chosen absolute grid index over full tensors is
$m\in[-176,-27]$ for qwen — 150 codes, which fits in 255 but **does not fit
MXFP4's bias-127 origin**. Repairable by a re-biased origin constant at ~0 b/el,
but that constant is a new format parameter tuned on two sub-1 B models. Until
it is defined, the honest phrasing is **"4.25 b/el plus a format-level origin
constant MXFP4 does not have."**

## What to publish

The defensible claim: *at 4.25 bits per element, a finer scale ladder beats
MXFP4 by 17 % RMSE on two real models and 20 % perplexity, with zero losing
blocks in 14.9 million — and the gain is entirely the scale axis, entirely
resolution, and a binary ladder realises it better than a ternary one.*

That is a real result about **block scale resolution**, and it is publishable.
What is not publishable is "ternary wins the block axis": a referee needs one
afternoon and $2^{k/2}$ to refute it, and the paper does not need the claim.
