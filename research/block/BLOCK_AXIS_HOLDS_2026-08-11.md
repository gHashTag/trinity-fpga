# Two attempts to break the block axis, two failures, and one thing learned from the difference

`BLOCK_AXIS_CLOSED_2026-08-10.md` concludes: *no eight-level element format will
take the block axis from MXFP4.* Its **argument** was wrong — it rested on
Lloyd-Max being "the ceiling", and Lloyd-Max is the ceiling for squared error, not
for perplexity. Two codebooks were built to exploit that gap. Neither breaks the
conclusion, and the way they fail differs in a way worth recording.

## The two attempts

Both have **six free interior magnitudes**, both were found by the same
coordinate descent with the same 120-evaluation budget and the same step
schedule, and both were fitted on SmolLM2-135M. The only difference is *what they
were fitted against*.

| codebook | fitted against | SmolLM2 *(fitted)* | Qwen2.5-0.5B | Pythia-160M |
|---|---|---:|---:|---:|
| **KL-optimised** | the model's **logits** | **−7.66 %** | **+1.98 %** | **+8.63 %** |
| **nSSE-optimised** | the model's **weight statistics**, no forward pass | **−5.24 %** | −0.10 % | −0.19 % |

*Percentages are against MXFP4 under the top-normalised scale rule; negative is
better. Every codebook carries top = 1.0, so all sit at headroom phase φ = 0 —
see `SCALE_PHASE_THEOREM_2026-08-11.md`.*

Every reference figure was reproduced before anything new was quoted: all nine
rulers matched to ≤ 2.8e-06 relative, and `exp(mean per-window NLL)` matched the
whole-slice perplexity to **0.00e+00**, so the paired statistics and the headline
numbers are one measurement rather than two.

## Neither survives, and the second one fails silently

The KL codebook **loses** on both unseen models — the failure is loud and already
withdrawn (`KL_CODEBOOK_WITHDRAWN_2026-08-11.md`).

The nSSE codebook keeps its sign but loses its magnitude:

| model | mean ΔNLL | t | p | windows better/worse |
|---|---:|---:|---:|---:|
| SmolLM2 *(in-sample)* | −0.053826 | **−9.122** | 3.2e-11 | **38 / 2** |
| Qwen2.5-0.5B | −0.000959 | −0.178 | 0.861 | 10 / 10 |
| Pythia-160M | −0.001867 | −0.181 | 0.858 | 22 / 18 |
| **pooled out-of-sample** | **−0.001564** | **−0.221** | **0.826** | 32 / 28 |

Pooled 95 % CI in perplexity terms: **[−1.56 %, +1.27 %]** — it contains zero
comfortably. The margin collapses by a factor of 30 to 50, from decisive to
statistically indistinguishable from a tie. The point estimates (−0.10 %,
−0.19 %) are exact for these window sets, since the pipeline is deterministic,
but quoting either without `t = −0.18` beside it would be quoting noise.

## The conclusion holds, on better evidence than it had

To break "no eight-level element format takes the block axis from MXFP4" you need
an out-of-sample margin the data can distinguish from zero. Two independent
searches, against two different objectives, produced none. The conclusion now
rests on that rather than on the ceiling argument, which remains wrong.

## What the difference between the two failures teaches

This is the part worth keeping.

**A logit fit goes actively wrong off-model. A weight-statistics fit merely stops
helping.** The KL codebook inverts its ranking — first of three where fitted,
second of three on both unseen models. The nSSE codebook never inverts: nSSE <
MXFP4 < Lloyd-Max on all three. It keeps the *direction* and loses the *size*.

That is what you would expect if weight distributions are more alike across
checkpoints than logit distributions are, and it says something practical: when
fitting anything against a model, fitting against a *static* property of the
model degrades gracefully out of sample, while fitting against its *behaviour*
can reverse. The graceful failure is the safer one to build on, and it is also
the one that is easier to mistake for a result, because the sign never flips.

## Scope and one unverified inheritance

One model family per row, wikitext-2 only, K = 32, E8M0, `lm_head` excluded.
Coordinate descent is not a global search: a negative result bounds what *these*
searches found, not what exists.

Pythia-160M was not in the weights directory and was downloaded fresh; its three
ruler figures then reproduced to ≤ 1.2e-06, which is the evidence that it is the
same checkpoint the earlier figures came from.

The nSSE codebook's provenance was flagged as unverified by the agent that used
it and has since been confirmed: attack 5 ran the identical coordinate descent
against block-normalised squared error, a search that "never sees a single token
of text". The description "fitted to weight statistics, no forward pass" is
correct.
