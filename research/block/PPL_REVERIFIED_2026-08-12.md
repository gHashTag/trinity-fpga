# The stop-rule's perplexity number now has a second witness

## Why this had to be done

The RMSE half of the block claim got an independent instrument last iteration.
The perplexity half — **the number the stop-rule actually turns on** — still had
exactly one, from a run whose working directory no longer exists. That asymmetry
was the worst place in the paper to be economical.

`research/block/verify_block_ppl.py` is written from the protocol, not from the
original script: different parquet reader, different text join, its own window
handling, its own layer selection, its own refusal gate on the fp32 ruler.

## Result, smollm2, 148 windows of 2048

| arm | ppl | vs MXFP4 floor | vs MXFP4's own best encoder |
|---|---|---|---|
| fp32 (the ruler) | 15.4148 | — | — |
| mxfp4_floor | 25.0798 | +0.00% | −13.47% |
| mxfp4_argmin | 22.1015 | +11.88% | +0.00% |
| **step3** (2^(k/3), ours) | 20.0022 | **+20.25%** | **+9.50%** |
| step8 (2^(k/8), binary) | 18.9053 | +24.62% | +14.46% |

**Against the published figures: +20.04% and +8.99%. Reproduced to 0.21 and 0.51
points by independently written code.**

## The interesting part is what did NOT reproduce

The **absolute** perplexities differ substantially — this instrument reads
fp32 = 15.41 and MXFP4 floor = 25.08 where the paper's frontier table prints
22.50 for MXFP4. Window count, layer set and tokenisation join all differ.

**The levels move and the comparisons do not.** That is the outcome to hope for
and it is worth stating explicitly, because it is the evidence that the claim is
a property of the formats rather than of one harness. A reproduction that
matched the absolute numbers too would have proven only that two scripts share a
protocol.

## Standing conclusions, unchanged

- The stop-rule as **written** is met on both metrics, now on two instruments each.
- The stop-rule as **intended** is not: `step8` — a *binary* ladder — beats
  `step3` on perplexity by 4.4 points against the floor and 5.0 against argmin,
  exactly as it does on RMSE. The paper says so and continues to.
- The encoder split still costs the headline dearly: **+11.88% of the +20.25%
  is MXFP4's own encoder**, and that arm emits a byte-legal MXFP4 stream.
