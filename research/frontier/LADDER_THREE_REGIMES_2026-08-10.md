# Three regimes, not one law — why the closed form gets 3 and 5 bits and misses 4

Follow-up to `LADDER_FORMULA_FAILS_4BIT_2026-08-10.md`. That note established the failure; this
one locates its cause and proposes a criterion that spans all three budgets.

## Sensitivity weighting cannot rescue it — and the reason is a theorem, not bad luck

`predict_weighted.py` reweights each layer's contribution by its measured perplexity damage per
unit of squared error, `s_l = Δppl_l / MSE_l`, taken from the per-block profiles measured on both
checkpoints. Sensitivity spans **39.5×** on SmolLM2 and **8.3×** on Qwen.

**It moves the score by less than 1 %** and does not flip a single ordering. SmolLM2 at 4 bits:
φ goes 1.5439e-03 → 1.5318e-03, supergolden 1.1989e-03 → 1.1932e-03. Supergolden still wins the
score; φ still wins perplexity.

The cause is already proved in the block-quantisation line: **`|w|/rowmax` has essentially the
same shape in every layer.** Reweighting which layers dominate cannot change an aggregate built
from identically-shaped contributions. There, reweighting changed a derived codebook by 0.0001;
here it changes a ladder score by <1 %. Same mechanism, same conclusion:

> **No reweighting of layers can rescue a predictor built on weight statistics, because the
> normalised weight distribution is layer-invariant.**

So the 4-bit cause lies outside weight statistics as usually written.

## What actually separates the ladders: reach versus resolution

At `b` bits the span (largest over smallest non-zero level) is `r^(n−1)`, `n = (2^b−1)/2`.
Weights below half the smallest level are **flushed to zero** — deleted, not rounded. Measured on
Qwen:

| bits | flushed range | which criterion orders perplexity correctly |
|---|---|---|
| 3 | **42 – 76 %** | **flush fraction — full order matches** |
| 4 | 3 – 33 % | **neither** |
| 5 | 0.01 – 3.8 % | **MSE — full order matches** |

**Three regimes.** At 3 bits almost everything is flushed and coverage decides. At 5 bits almost
nothing is flushed and resolution decides. At 4 bits the two are comparable, and an
energy-weighted criterion mis-ranks: on Qwen φ carries **20 % more** squared error than
supergolden yet deletes **8 points fewer** weights (10.6 % vs 18.8 %), and perplexity prefers the
deletion — winning by 10.7 %.

That is why the closed form predicts exactly two of three budgets. It is not arbitrary: **4 bits
is the crossover budget**, and the closed form has only the resolution term.

## A two-term criterion recovers all six winners

    score(r, b) = MSE(r, b) + λ · flush(r, b)

Sweeping λ (`two_term.py`, ~66 M and ~56 M sampled weights):

| λ | SmolLM2 | Qwen |
|---|---|---|
| 0 (the closed form) | 2/3 | 2/3 |
| 3e-3 | 2/3 | 3/3 |
| **5e-3 – 1e-2** | **3/3** | **3/3** |
| ≥ 2e-2 | 2/3 | 1/3 |

**A single λ in [0.005, 0.01] picks the correct winner in all six model×budget cases**, with the
full four-way ordering correct at 3 and 5 bits and the winner correct (3rd/4th swapped) at 4.

### The honest status of λ

**This is a fit, not a derivation.** One free parameter was tuned against six binary outcomes,
and λ has no theory behind it. Two things make it more than curve-fitting, and neither makes it a
law:

- the *same* λ works on both models, which were not pooled;
- the admissible window is a factor of two wide, not a knife edge.

**What would make it a law:** predict a budget or a model not used in fitting. Six bits has no
measured perplexity yet; a third checkpoint would serve equally. Until one of those is run, the
correct description is *"a two-term score with one fitted constant reproduces the six measured
winners"* — not *"the law extends to four bits"*.

## What stands and what does not

- ✅ The **measured** replication is untouched: φ at 4 bits on both models (2.7 %, 10.7 %),
  plastic at 5, shift at 3, full ordering repeating across two architectures.
- ✅ **Three regimes identified and quantified** by flush fraction, explaining precisely which
  budgets a single-term criterion can and cannot rank.
- ✅ Layer-sensitivity reweighting **provably cannot help**, for the same reason established
  independently in the block line.
- ⚠️ The two-term criterion is a **one-parameter fit to six outcomes**, pending an out-of-sample
  test.
- 🛑 Still withdrawn: *"формула выбирает верную лестницу во всех трёх бюджетах"* for the
  single-term closed form.

## B — synthetic shape: what moves the optimal rung

`shape_and_acts.py`, log-normal magnitudes of varying tail weight, scored with the two-term
criterion:

| σ | excess kurtosis | r\*(3b) | r\*(4b) | r\*(5b) | winners 3b / 4b / 5b |
|---|---|---|---|---|---|
| 0.2 | −1.8 | 1.654 | 1.234 | 1.103 | phi / plastic / plastic |
| 0.4 | −1.1 | 2.548 | 1.444 | 1.181 | shift / supergold / plastic |
| 0.6 | +1.2 | 2.600 | 1.838 | 1.313 | shift / shift / plastic |
| 1.0 | +30.4 | 2.600 | 2.600 | 1.681 | shift / shift / phi |
| 2.0 | +12553 | 2.600 | 2.600 | 2.600 | shift / shift / shift |

**Heavier tails demand a coarser ladder.** `r*` rises monotonically with kurtosis at every budget,
and the winning named rung climbs the hierarchy in step. That is the mechanism stated plainly:
tail weight buys reach, and reach costs resolution.

### An unforced agreement worth noting

On the real weights the continuous optimum lands essentially *on* the measured winners — and
nothing in the criterion knows the named constants exist:

    4 bits   r* = 1.6280   phi     = 1.6180    0.6% apart
    5 bits   r* = 1.3390   plastic = 1.3247    1.1% apart
    3 bits   r* = 2.4161   shift   = 2.0       nearest available rung

This is stronger than picking a winner from four candidates. λ was fitted to the *ranking* of
four discrete ladders; it was never fitted to a continuous position, and the continuous optimum
still coincides with the winner to about 1 %.

## C — activations want a different ladder from weights

Same criterion, real forward pass on SmolLM2:

| | samples | excess kurtosis |
|---|---|---|
| weights | 16.3 M | **+0.44** |
| activations | 10.6 M | **+25.06** |

| bits | r\* weights | r\* acts | winner weights / activations | flushed w / a |
|---|---|---|---|---|
| 3 | 2.416 | 2.600* | shift / shift | 37.1 % / 89.4 % |
| **4** | 1.628 | 2.600* | **phi / shift** | 8.9 % / 19.0 % |
| **5** | 1.339 | 1.786 | **plastic / shift** | 3.2 % / 0.1 % |

\* at the search-grid ceiling — the activation optimum may lie beyond 2.6 and is only bounded
below by these numbers.

**Prediction: activations want the coarsest rung at every budget, weights want φ then plastic.**
At 4 and 5 bits the two sides disagree outright. If it holds, a ternary node needs **two different
ladders on its two sides** — the weight side climbing the algebraic hierarchy, the activation side
staying on plain powers of two.

This follows from measured kurtosis (+25.06 against +0.44) and the same criterion, with no extra
assumption. It is nevertheless a **prediction**: no activation-quantised perplexity has been
measured, so the ordering is untested where it matters.

---

# Out-of-sample tests: one held weakly, one largely failed, one refinement found

## A — six bits: prediction held on both models, but the test is weaker than it looks

λ was fitted on {3,4,5} bits. Six bits is a budget the fit never saw.

| model | predicted | measured | ladder perplexities |
|---|---|---|---|
| SmolLM2 (fp32 13.73) | plastic | **plastic** ✅ | plastic 15.67, supergold 18.06, phi 21.94, shift 74.21 |
| Qwen (fp32 11.59) | plastic | **plastic** ✅ | plastic 12.37 |

**2 of 2 — but this does not test λ.** At six bits `n = 31`, so the span is `r^30` and the
smallest level for plastic is `1.3247^-30 ≈ 1.6e-4`. Essentially nothing is flushed, which is the
**resolution-dominated regime** where the single-term closed form already predicts correctly. The
test confirms the two-term criterion does not *break* outside its fitting range; it does not
confirm λ, because λ's term is negligible there.

**An out-of-sample test that would actually exercise λ has to sit near the crossover** — a third
model at 4 bits, not a wider budget on the same two.

## B — activations measured: the prediction was largely wrong

`shape_and_acts.py` predicted, from kurtosis alone, that activations want the coarsest rung at
every budget. Activations were then quantised in the forward pass (weights left fp32) and
perplexity measured on SmolLM2, fp32 = 13.7301:

| bits | predicted | measured | activation perplexities |
|---|---|---|---|
| 3 | shift | **phi** ❌ | phi 99 075, supergold 109 421, shift 320 142, plastic 330 488 |
| 4 | shift | **shift** ✅ | shift 28.79, phi 107.29, supergold 950.26, plastic 60 040 |
| 5 | shift | **plastic** ❌ | plastic 16.30, supergold 16.36, phi 18.27, shift 26.68 |

**1 of 3.** Predicting from a histogram statistic worked on weights and does not transfer to
activations. The criterion was validated only on weights and should not have been extrapolated
across surfaces without a check — which is exactly why the check was run.

**What survives, and it is the part that mattered:** weights and activations *do* want different
ladders.

    weights      3b shift   4b phi     5b plastic
    activations  3b phi     4b shift   5b plastic

At 3 and 4 bits the two surfaces disagree, and at 4 bits they swap outright — weights want φ
where activations want shift. **The "two ladders on two sides" consequence for a ternary node
holds; the specific claim "activations want shift everywhere" is withdrawn.**

Note also how brutal activation quantisation is: at 3 bits every ladder destroys the model
(perplexity ~10⁵), and even at 4 bits the best is 28.79 against fp32 13.73. Activations are a
far harsher surface than weights, where 4-bit costs only ~10 perplexity points.

## C — the second term should be energy, not count

`second_term.py` sweeps four candidates for the reach term, asking which admits the widest λ
window while still ranking all six measured winners:

| second term | λ values ranking all 6 | window |
|---|---|---|
| `flush_n` — fraction of **weights** below threshold | 4 / 62 | [5.0e-3, 1.0e-2] — **2×** |
| **`flush_e` — fraction of **energy** below threshold** | **11 / 62** | **[2.5e-1, 2.5e0] — 10×** |
| `dead_row` — fraction of channels entirely deleted | none | — |
| `span_log` — pure reach, data-independent | none | — |

**Energy below the threshold admits a five-times wider λ window than count.** That is a
refinement of the criterion, not a cosmetic one: it says the cost of losing reach is the *energy*
deleted, not the *number* of weights deleted — which is the physically sensible quantity and
makes the constant less finely tuned.

Both structural candidates fail outright. `dead_row` never fires (no channel is ever entirely
below threshold at these budgets), and `span_log` fails because a data-independent reach term
cannot know where a particular distribution's mass sits.

## Position after this round

- ✅ Two-term criterion survives a wider budget on both models (weakly — the regime does not
  exercise λ).
- ✅ Better second term found: **energy**, not count, with a 5× wider admissible window.
- ✅ Weights and activations demonstrably want different ladders at 3 and 4 bits.
- 🛑 Withdrawn: "activations want the coarsest rung at every budget" — 1 of 3.
- ⚠️ λ still has no derivation and still has not been tested near the crossover on a third model.
