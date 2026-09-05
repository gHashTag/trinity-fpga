# The closed form does not select the winner at 4 bits — on either model

**Status: the predictive claim is withdrawn. The measured replication is untouched.**

## What was claimed

> "Формула воспроизводит измеренную ошибку с точностью 1–9 % при 4 и 5 битах и **выбирает верную
> лестницу во всех трёх бюджетах**."

## What was run

`predict_any.py` — the same protocol as `predict2.py`, parameterised by model, scoring two
predictors separately against the recorded perplexities in `ladder_ppl_{smollm2,qwen}.json`:

- **EXACT** — quantise the real weights against the real codebook, sum squared error. No
  modelling assumption; asserts only that weight-MSE tracks perplexity.
- **CLOSED** — the analytic form `MSE(r,b) = c(r)²·E[x²|x>t] + E[x²|x<t]`, `t = r^-(n-1)/2`.
  Sees only the histogram.

Two implementation checks were done before drawing any conclusion:

1. `predict2.py` assigns levels with a full `|x − cb|` argmin; `predict_any.py` uses
   `searchsorted` on codebook midpoints. Verified identical on 200 000 random points at 3, 4 and
   5 bits for both ladders — **max difference 0.000e+00**. The rewrite is not the cause.
2. EXACT uses every weight, no subsampling. So subsampling in the CLOSED path is not the cause
   either, since **EXACT fails in exactly the same place**.

## Result

| bits | SmolLM2 predicted | SmolLM2 measured | Qwen predicted | Qwen measured | |
|---|---|---|---|---|---|
| 3 | shift | shift | shift | shift | ✅ full order matches |
| **4** | **supergold** | **phi** | **supergold** | **phi** | ❌ **wrong on both** |
| 5 | plastic | plastic | plastic | plastic | ✅ full order matches |

At 3 and 5 bits both predictors reproduce not just the winner but the **complete ordering of all
four ladders**, on both models. At 4 bits both pick supergolden and the measurement says φ.

The numbers at 4 bits:

    SmolLM2   supergold  MSE 1.1989e-03   ppl 25.098
              phi        MSE 1.5439e-03   ppl 24.428     <- higher MSE, LOWER perplexity
    Qwen      supergold  MSE 1.0713e-03   ppl 17.985
              phi        MSE 1.2902e-03   ppl 16.244     <- 20% higher MSE, 10.7% lower perplexity

**This is internally consistent with the closed form, not a bug in it.** The published optimum
table gives `r* = 1.4115` at 4 bits; the nearest named ladder to 1.4115 is supergolden (1.4656,
distance 0.054), not φ (1.618, distance 0.207). The formula points where it says it points — and
that is the wrong ladder.

## Why it fails, and why only here

Both predictors fail *identically*. That localises the error precisely: it is **not** in the
analytic approximation of the codebook error, because the exact codebook error makes the same
mistake. It is in the shared premise — **that weight-MSE ranks ladders the way perplexity does.**

At 3 and 5 bits the MSE gaps between ladders are large (2–6×), so any monotone proxy gets the
order right. At 4 bits the two leading ladders sit within 20 % of each other on MSE, and inside
that margin the proxy has no authority. φ carries 20 % more weight-MSE than supergolden on Qwen
and still wins perplexity by 10.7 %.

This matches, independently, what the block-quantisation line measured on the same two models:
per-layer weight-MSE correlates with perplexity damage at only **r = +0.13**, while damage itself
spans 42×. Weight-MSE is a usable proxy for coarse separations and unreliable for fine ones. The
4-bit case is a fine one.

## What survives, stated exactly

- **The measured replication stands.** φ wins at 4 bits on both models (2.7 % on SmolLM2, 10.7 %
  on Qwen); plastic wins at 5 bits; shift wins at 3 bits; the full ordering repeats across two
  architectures. That is measurement and is unaffected.
- **The closed form predicts 2 of 3 budgets**, with the complete ordering correct in those two.
  That is a real result and should be reported as "predicts the coarse regimes".
- **The closed form does not select the 4-bit winner**, which is precisely the budget carrying
  the headline claim. The sentence "выбирает верную лестницу во всех трёх бюджетах" is withdrawn.

## What would settle it

A predictor that respects the 4-bit case must weight the error by something other than uniform
squared error — the same conclusion the block line reached from the other direction. The cheapest
test: recompute both predictors with each layer's contribution weighted by its measured
perplexity sensitivity, and see whether φ then overtakes supergolden at 4 bits. If it does, the
law survives with a corrected objective; if it does not, the 4-bit ordering has a cause outside
weight statistics entirely.
