# WITHDRAWN -- the salience correction fails on the second model

**T34 as stated below is withdrawn.** It was verified on SmolLM2-135M and
refuted by Qwen2.5-0.5B within the hour, by the same replication step that has
caught eighteen earlier claims.

On Qwen the activation weighting scales all four candidates by very nearly the
same factor (1.09) and therefore cannot reorder them; supergolden stays ahead of
`phi` on the weighted error while perplexity still prefers `phi`. On SmolLM2 the
factors ranged 0.12--0.24 and the reordering was real.

So channel salience correlates with the quantisation error pattern in one model
and is close to independent of it in the other. An explanation that needs the
correlation is not a law, and the four-bit transposition stays open.

| model, bits | by MSE | by weighted error | by perplexity |
|---|---|---|---|
| SmolLM2, 4 | supergolden | **phi** | **phi** |
| SmolLM2, 5 | plastic | plastic | plastic |
| Qwen, 4 | supergolden | supergolden | **phi** |
| Qwen, 5 | plastic | plastic | plastic |

What survives: at four bits `phi` leads on perplexity on both models, by 2.7%
and 10.7%. The unweighted closed form remains the best available predictor at
three and five bits and is wrong at four on both.

The lesson is the one the night keeps repeating in a new costume. This
explanation was *more* attractive than the usual because it came with a
citation, a measured 28x channel spread, and a correct prediction on the first
dataset. None of that is replication.

---

## (withdrawn) Why the network prefers a coarser ladder than mean squared error does

The closed form of T33 ranked the ladders correctly at three and five bits and
transposed the top pair at four -- picking supergolden where perplexity picked
`phi`. The transposition reproduced on both models, in the same direction, which
makes it an effect rather than noise. This explains it.

## The mechanism

Plain MSE treats every weight alike. The output error of a linear layer is
`sum_j dw_ij x_j`, so a weight multiplying a large input channel costs more than
one multiplying a small channel, and the two are not close: measuring the RMS of
every input channel of every linear layer of SmolLM2-135M, the first attention
projection alone spans **28x** between its largest channel and its median.

This is the observation AWQ is built on -- weight salience follows the
*activation* distribution, not the weight distribution, and protecting roughly
1% of channels recovers most of the quantisation loss. AWQ uses it to choose a
per-channel scaling. The same observation chooses a ladder.

## The test

Rank the ladders by `sum_j a_j^2 dw_ij^2`, with `a_j` the RMS of input channel
`j`, instead of by `sum dw^2`. On SmolLM2-135M:

| bits | by MSE | by activation-weighted error | by perplexity |
|---|---|---|---|
| 4 | supergolden | **phi** | **phi** |
| 5 | plastic | plastic | plastic |

| bits | ladder | MSE | activation-weighted |
|---|---|---|---|
| 4 | shift | 3.0704e-03 | 3.3271e-04 |
| 4 | **phi** | 1.5439e-03 | **1.8241e-04** |
| 4 | supergolden | **1.1989e-03** | 1.9152e-04 |
| 4 | plastic | 1.9586e-03 | 4.6470e-04 |
| 5 | phi | 1.5026e-03 | 1.6214e-04 |
| 5 | supergolden | 9.5363e-04 | 1.0291e-04 |
| 5 | **plastic** | **5.2010e-04** | **5.7746e-05** |

The weighting reverses the four-bit pair and leaves five bits alone, which is
exactly the correction needed. The two ladders it separates differ by 5% in
activation-weighted error and by 22% in plain error -- the outlier channels are
what turns the second number into the first.

## Why it lands on the coarse side

A finer ladder spends its codes on resolution and loses span. The weights that
sit near the top of their channel's range are exactly the ones a coarse ladder
still represents and a fine ladder must clip, and those are disproportionately
the weights that multiply large activations. So the penalty for going fine is
concentrated precisely where the network is most sensitive, and plain MSE, which
spreads it evenly, understates it.

**T34 (the salience correction).** Among multiply-free ladders at a fixed code
budget, the minimiser of activation-weighted quantisation error
`sum_j a_j^2 dw_ij^2` predicts the perplexity ranking where plain mean squared
error does not. The correction always moves the choice toward the coarser
ladder, because span is what protects the salient weights.

## What this changes for the alphabet

`phi` is not merely tied at four bits and lucky. It is the predicted optimum
once weights are weighted by what they multiply, and the prediction now agrees
with the measurement on the budget this work targets.
