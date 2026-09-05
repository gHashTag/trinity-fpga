# The control that was named and not run: seed or distance? Neither, yet — the far region is a trap the search does not leave

A fitting campaign claimed **the mechanism is the SEED, not the jointness**:
KL-opt (Lloyd-Max seed) and FIT-smollm2 (MXFP4 seed) are the same search, on the
same model, with the same budget; KL-opt has the *lower* in-sample KL and fails
out of sample (0/3), FIT-smollm2 generalises (3/3).

Adversarial verification proposed a competing reading of the same table: what
predicts held-out failure is the book's **distance from MXFP4** in level space,
`||delta||` = L2 over the six interior magnitudes, with perfect separation at
`d ~ 0.11` — and Lloyd-Max, which has no seed and no fit, is the worst arm of the
eight, which SEED cannot explain.

The two were confounded, because a coordinate descent stepping 0.06 → 0.004
cannot obviously cross back from 0.233 away. **This is the control that separates
them**: the same search (`onefit_kl.py`, `SEEDS=lloyd`, 120 evaluations, KL over
2 calibration windows, six free interior magnitudes) run from the **Lloyd-Max
seed** on all four checkpoints, each judged on the three it never saw.

Every ruler reproduces before any new number: fp32 and MXFP4 to `<2e-6` relative
on all four models, and per-window NLL identical to campaign B's to **0.00e+00**
on every model. Shared arms across every process that has measured them agree to
7.89e-05 nats.

## The result the control was designed to produce did not happen

No Lloyd-seeded fit walked back. All four landed **far**.

| fit | evals | KL start → end | vs MXFP4 KL | `\|\|delta\|\|` landed | walk-back | terminated by |
|---|---:|---|---:|---:|---:|---|
| LFIT-smollm2 | 120 | 0.389368 → 0.308924 | −20.18 % | 0.2117 | 0.0211 | budget |
| LFIT-qwen | 120 | 0.230137 → 0.192404 | −7.98 % | 0.2314 | 0.0014 | budget |
| LFIT-pythia | 96 | 0.627622 → 0.589359 | **+14.57 %** | 0.1711 | 0.0617 | step < 0.004 |
| LFIT-opt | 108 | 0.131098 → 0.104976 | −11.57 % | 0.2079 | 0.0249 | step < 0.004 |

Seed distance is 0.2328. The largest walk-back is **0.0617** of the **0.1228**
needed merely to reach the near group. Two of the four runs did not run out of
budget — they **converged**, step below 0.004, at d = 0.17 and 0.21. The far
region is a genuine local minimum of the fitting objective, not a budget
artefact.

So seed and distance remain perfectly collinear on every fitted book. **The
confound is not broken.** That is the honest headline.

## What it did establish

### 1. The seed hypothesis's decisive evidence does not replicate

The argument rested on KL-opt reaching a *lower* in-sample KL than the
MXFP4-seeded fit and still failing. Measured on all four rotations, that is
**1 of 4** — a SmolLM2 accident:

| fitting model | in-sample KL, MXFP4 seed | Lloyd seed | Lloyd better in-sample? |
|---|---:|---:|---|
| SmolLM2-135M | 0.327701 | **0.308924** | yes |
| Qwen2.5-0.5B | 0.161978 | 0.192404 | no |
| Pythia-160M | 0.434526 | 0.589359 | no |
| OPT-125M | 0.096418 | 0.104976 | no |

On Pythia the Lloyd-seeded search converged to a local minimum **worse than the
MXFP4 book it never saw** (+14.57 % KL): 96 evaluations of descent could not
reach the objective value MXFP4 has for free. The phenomenon is therefore not
"two equally good optima, one of which fails to transfer". Usually the far
region is simply worse — on the fitting objective as well.

### 2. The published KL-opt reproduces, independently

`LFIT-smollm2` = `[0, 0.077014, 0.188284, 0.313961, 0.465615, 0.611296,
0.768239, 1]` against published `KL-opt` = `[0, 0.07701, 0.18828, 0.31396,
0.46561, 0.6113, 0.79074, 1]`: five of six interior coordinates agree to
≤ 5e-6; only x6 differs (0.0225). Different script, different KL implementation
(memmapped log-softmax vs in-memory), same seed and step schedule, same landing
point. Perplexity on SmolLM2 20.2925 against the published 20.2587.

### 3. The full rotation, all twelve books

Negative = beats MXFP4. `(x)` = in-sample, excluded from the held-out summary.

| book | `\|\|delta\|\|` | SmolLM2 | Qwen2.5 | Pythia | OPT | held-out mean | worst | wins |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LFIT-smollm2 | 0.2117 | (−7.51) | +2.07 | +9.71 | +0.61 | **+4.13 %** | +9.71 | 0/3 |
| LFIT-qwen | 0.2314 | +3.98 | (+1.86) | +16.16 | +0.42 | **+6.85 %** | +16.16 | 0/3 |
| LFIT-pythia | 0.1711 | +4.80 | +4.71 | (+10.65) | +3.71 | **+4.41 %** | +4.80 | 0/3 |
| LFIT-opt | 0.2079 | −4.81 | +2.53 | +11.68 | (−0.95) | **+3.13 %** | +11.68 | 1/3 |
| KL-opt | 0.2233 | (−7.66) | +1.98 | +8.63 | +0.34 | +3.65 % | +8.63 | 0/3 |
| Lloyd-Max | 0.2328 | (+4.45) | +4.10 | +11.23 | +3.38 | +6.24 % | +11.23 | 0/3 |
| FIT-smollm2 | 0.0576 | (−4.69) | −2.01 | −4.62 | −1.58 | −2.74 % | −1.58 | 3/3 |
| FIT-qwen | 0.0757 | −6.08 | (−3.56) | −3.46 | −2.14 | −3.90 % | −2.14 | 3/3 |
| FIT-pythia | 0.0212 | −2.29 | −0.11 | (−6.48) | −1.50 | −1.30 % | −0.11 | 3/3 |
| FIT-opt | 0.1050 | −5.96 | −1.68 | +0.29 | (−0.93) | −2.45 % | +0.29 | 2/3 |
| JOINT-KL | 0.0270 | (−2.43) | (−0.21) | (−6.89) | −1.31 | −1.31 % | −1.31 | 1/1 |
| nSSE-equal | 0.1209 | (−5.24) | −0.10 | −0.19 | +3.71 | +1.14 % | +3.71 | 2/3 |

At the model level (n = 3 held-out checkpoints) every book is a **TIE** except
`LFIT-pythia`, which **loses**: +4.41 %, 95 % CI [+2.92, +5.93], t = +12.88,
p = 0.006. Individual books cannot be separated at n = 3; the signal is in the
sign pattern — **11/12 held-out wins for the MXFP4-seeded fits, 1/15 for the
Lloyd-seeded ones**.

### 4. The one test the design does support at the model level

The two seeds are **paired**: same fitting model, same budget, same held-out
triple. n = 4 fitting models.

| comparison | Lloyd seed vs MXFP4 seed | 95 % CI | t | p | direction |
|---|---:|---|---:|---:|---|
| held out | **+7.30 %** | [+3.40, +11.35] | +6.06 | **0.0090** | worse in 4/4 |
| in-sample | +4.93 % | [−8.69, +20.59] | +1.10 | 0.351 | worse in 2/4 |

Starting the same search from Lloyd-Max costs **7.30 % perplexity on checkpoints
it never saw**, and the in-sample comparison is inconclusive — a CI that wide is
not evidence of equality, only absence of evidence of difference.

### 5. Distance is a band, not a monotone

With twelve books the separation at 0.11 still holds — all five books with
d < 0.11 have a negative held-out mean, all seven with d ≥ 0.11 a positive one.
Under exchangeability that arrangement has probability 1/C(12,5) = 1.3e-3, but
the books are **not** exchangeable (four pairs share a fitting model, four share
a seed), so it is a description, not a test.

Within the two groups the relation is not the same:

* d ≥ 0.11 (n = 7): Spearman(`||delta||`, held-out) = **+0.714** (p = 0.071)
* d < 0.11 (n = 5): Spearman = **−0.700** (p = 0.188) — *farther is better*

And MXFP4 itself is at d = 0 and is beaten by all five near books. So "closer to
MXFP4 is better" is wrong as stated. What the data shows is a **band of good
books at small but non-zero distance** (0.02–0.11) and failure beyond ≈ 0.12.
Across all twelve books Spearman = +0.825 (p = 0.001), Pearson = +0.890 — driven
by the between-group split, not by ordering inside either group.

## The mechanism the data supports

**Which basin the book is in decides whether it transfers.** In this data basin
membership is labelled equally well by "started at Lloyd-Max" and by "ended
beyond d ≈ 0.11", and this control did not break the tie between those two
labels, because the barrier is real: two of four searches converged inside the
far region and the best walk-back covered half the distance to the near group.

What did change is the *character* of the far basin. It is not a rival optimum
that overfits; on three of four models it is worse on the fitting objective
itself, and on one it is worse than the untouched MXFP4 book. The earlier claim
that a lower in-sample KL coexists with held-out failure is a single-model
observation that does not replicate.

Only two books in the whole record are far without being Lloyd-seeded —
Lloyd-Max (d = 0.2328, +6.24 %) and nSSE-equal (d = 0.1209, +1.14 %, sitting
just past the boundary and just past neutral). **n = 2 on the axis that
discriminates the two hypotheses.** Twelve non-independent books are a surviving
hypothesis, not a settled law.

## The control that would separate them, and was not run

Vary distance while holding the seed fixed: run the MXFP4-seeded search with a
step schedule or budget large enough to reach d > 0.11, and judge the far books
*it* finds. If MXFP4-seeded far books also fail, distance survives without the
seed. Alternatively, seed from a far book that is not Lloyd-Max (nSSE-equal at
0.1209, or a random book at d ≈ 0.23) — if the failure follows the distance and
not the identity of the seed, the same conclusion holds with the seed varied.

## Apparatus

* `onefit_kl.py` gained `SEEDS=lloyd` and a `TAG` output suffix; `onefit_measure.py`
  gained `FITS="name=file"` and the same `TAG`. Defaults are unchanged, so no
  published file name or result is touched.
* `lineB_seed_vs_distance.py` — the analysis; `lineB_stats.json` — its output.
* `onefit_kl_lloyd_<model>.json` — the four fits; `onefit_ppl_lloyd_<model>.json`
  — the four perplexity rotations.
* Nothing on the measurement path was reimplemented: `quant` / `perplexity` /
  `target_modules` / `load_wikitext` come out of `block_tnf.py`, per-window NLL
  through `onefit_stats.load`, statistics through `campaignC_stats.paired`.

**Scope.** Four checkpoints, one text (wikitext-2), block 32, E8M0, lm_head
excluded, eight magnitudes with the top pinned to 1.0. Held-out unit is the
checkpoint; window-level numbers appear only inside a single model. Coordinate
descent is a local search: every statement above about "the far region" is about
what this search reaches from these two seeds, not about what exists.
