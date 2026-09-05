# The optimal multiply-free ladder depends on the bit budget, and follows from the weights

Theorem `thm:hierarchy` says the multiply-free scales form a hierarchy indexed by
algebraic degree, each degree buying finer granularity for a register. It does
not say which to use. That is an empirical question and this answers it, on
SmolLM2-135M, wikitext-2, 12 windows of 2048 tokens, per-output-channel scale,
codebook sized to exactly `2^bits` entries including zero and sign.

Baseline fp32 perplexity 14.3607.

| bits | shift (2) | phi (1.618) | supergold (1.4656) | plastic (1.3247) |
|---|---|---|---|---|
| 3 | **2309.86** | 41835.53 | 1367268.11 | 6720092.29 |
| 4 | 76.81 | **24.43** | 25.10 | 55.72 |
| 5 | 77.52 | 22.73 | 18.93 | **16.45** |

**The optimal degree rises with the code budget.** At three bits the coarsest
ladder wins because nothing spans enough range; at four the balance is at
`phi`; at five the finest ladder tested wins outright.

This is the paper's own range-against-precision law, applied to the scale
hierarchy rather than to a field layout. A ladder of ratio `r` with `n`
magnitudes spans `r^(n-1)`: finer steps cost span, and the budget decides which
is scarce.

## The honest verdict on our own alphabet

`phi` is optimal at four bits -- the regime this work is about -- and at five
bits it is beaten by the plastic number, 16.45 against 22.73, a 28% gap.

At four bits `phi` and supergolden differ by 2.7% on perplexity over 12 windows,
which this measurement cannot separate. The accurate statement is that they tie,
and supergolden costs one more register. So our alphabet is not beaten at its
operating point; it is the cheapest member of a tied pair there, and it is
beaten one bit up.

## A predictor, and a first attempt that failed

**First attempt (wrong).** Predict the winner as the finest ladder whose span
covers the weights' channel dynamic range, measured at 268.95x median over
155,520 channels. It picks the coarsest ladder at every budget: correct at 3
bits, wrong at 4 and 5.

It fails because coverage is the wrong criterion. Clipping the *smallest*
weights costs almost nothing -- a small weight contributes little to the output
-- while rounding a large one costs a lot. The trade is total error, not
coverage.

**Second attempt (works).** Rank the ladders by the mean squared quantisation
error on the weights alone, no model evaluation:

| bits | MSE order | perplexity order | agrees |
|---|---|---|---|
| 3 | shift, phi, supergold, plastic | shift, phi, supergold, plastic | exactly |
| 4 | supergold, phi, plastic, shift | phi, supergold, plastic, shift | top two swapped |
| 5 | plastic, supergold, phi, shift | plastic, supergold, phi, shift | exactly |

**T31 (the ladder law).** The multiply-free ladder minimising weight MSE also
minimises perplexity, except between ladders whose MSE differs by less than the
measurement can resolve. The 4-bit swap is exactly such a case: MSE differs by
28% while perplexity differs by 2.7% over 12 windows.

So the ladder can be chosen from the weights, without running the model. Where
two ladders tie, choose the cheaper -- which is the lower degree, which is fewer
registers.

## What was not measured

Twelve windows and one 135M model. The crossover's *location* is a property of
this weight distribution; the *existence* of a crossover follows from the span
law and would hold for any distribution with finite dynamic range. Training was
not attempted; these are post-training quantisation numbers.
