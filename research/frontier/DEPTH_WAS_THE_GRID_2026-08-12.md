# The depth statistic measured the grid. Retracting a verdict, and what replaced it.

2026-08-12. Everything below comes from JSON already on disk — `align_u_{gpt2,pythia,opt}.json`
and `scale_settled_smollm2.json`. No model was loaded to find any of it.

## What was published

Four alignment optima, each scored by `depth` — the perplexity gap from the minimum to the
next-best point of the sweep — divided by that model's measured tie-rule floor:

| model | floor | depth | depth/floor | verdict as published |
|---|---|---|---|---|
| SmolLM2 | 0.2398 | 0.5104 | 2.13 | resolvable |
| GPT-2 | 0.0003 | 0.5127 | 1709 | resolvable |
| Pythia | 0.5358 | 0.2457 | 0.46 | **not identified** |
| OPT | 0.0667 | 0.0087 | 0.13 | **not identified** |

The conclusion drawn: *two of four optima are shallower than their own noise, so the reported
spread of u\* is partly models reporting an argmin they do not possess.*

**That conclusion is withdrawn.** Every number in the table is arithmetically correct. The
statistic is not.

## What was wrong

`depth` is the gap to *whatever sample happened to sit beside the minimum*. It therefore scales
with the grid spacing there — which I chose.

| model | source | u range | points | median Δu | Δu at the minimum | depth |
|---|---|---|---|---|---|---|
| SmolLM2 | `scale_settled` | [0.000, 0.900] | 8 | 0.1255 | −0.160 / +0.074 | 0.5104 |
| GPT-2 | `align_u` | [0.000, 0.550] | 13 | 0.0500 | −0.050 / +0.050 | 0.5127 |
| Pythia | `align_u` | [0.000, 0.550] | 13 | 0.0500 | −0.050 / **+0.015** | 0.2457 |
| OPT | `align_u` | [0.000, 0.550] | 13 | 0.0500 | −0.050 / +0.050 | 0.0087 |

Two faults, either sufficient on its own:

1. **Pythia's minimum was scored against a neighbour 3.3× closer in u than GPT-2's.** For a
   locally quadratic minimum the gap goes as Δu², so a 3.3× closer neighbour costs an order of
   magnitude of apparent depth before the model contributes anything.
2. **SmolLM2 was swept on a different grid entirely** — different range, different point count,
   irregular spacing — and sat in the same table as though the numbers were commensurable.

Ranking those four models by `depth` ranked their grids.

## What replaced it, and the reversal

Two grid-free readings of the same curves. Local curvature `d²ppl/du²` from the three-point
stencil at the minimum; and the interval where the **linearly interpolated** curve stays within
one measured floor of its minimum — no shape assumption, grid only limits resolution.

| model | depth (rank) | curvature (rank) | curvature/ppl | interval within one floor | width |
|---|---|---|---|---|---|
| GPT-2 | 0.5127 (1) | 437 (2) | 12.23 | [0.250, 0.250] | 0.000 |
| SmolLM2 | 0.5104 (2) | 348 (3) | 16.78 | [0.266, 0.347] | 0.082 |
| Pythia | 0.2457 (3) | **800 (1)** | 17.96 | [0.347, 0.433] | 0.086 |
| OPT | 0.0087 (4) | 128 (4) | 4.11 | [0.148, 0.261] | 0.112 |

Spearman between the two orderings is **+0.40**. Pythia moves from third-shallowest to sharpest.

Under the corrected statistic **all four optima are narrow, and the four intervals have an empty
intersection.** Four of the six pairs are outright disjoint:

    GPT-2 [0.250, 0.250]   vs  SmolLM2 [0.266, 0.347]   disjoint
    GPT-2 [0.250, 0.250]   vs  Pythia  [0.347, 0.433]   disjoint
    OPT   [0.148, 0.261]   vs  SmolLM2 [0.266, 0.347]   disjoint
    OPT   [0.148, 0.261]   vs  Pythia  [0.347, 0.433]   disjoint

This is the opposite of the withdrawn verdict, and it is a **stronger** refutation of a universal
alignment constant. Not "the curves are flat so the argmin wanders" but "each argmin is pinned and
they are mutually incompatible."

One row needs its own caveat, and it does not change the conclusion. GPT-2's interval has width
exactly 0.000 because its fp32 tie floor (0.0003) is finer than the sweep can resolve — that
interval is **grid-limited, not floor-limited**, and its true width is unknown but bounded below
by the local grid step. Widening it to a full step either way gives [0.235, 0.265], which is still
disjoint from Pythia's [0.347, 0.433] by 0.08. The empty intersection does not depend on the one
degenerate row.

It also places the MX specification precisely. OCP's own alignment is u = 0.41504. It lies inside
**Pythia's** interval and outside the other three.

## How far that is from collapsing: k = 5

The intersection is empty because of one pair — GPT-2 at 0.250 and Pythia at 0.400, 0.15 apart
while their intervals are at most 0.09 wide. Every other pair is decoration.

The floors used are **tie-rule** floors: they measure one nuisance source, the tie-breaking
convention at bin boundaries. Inflate every floor by a common factor `k` until those two intervals
touch:

| k | GPT-2 interval | Pythia interval | overlap |
|---|---|---|---|
| 1 | [0.250, 0.250] | [0.347, 0.433] | no |
| 2 | [0.250, 0.250] | [0.320, 0.459] | no |
| **5** | [0.250, 0.250] | **[0.000, 0.513]** | **yes** |

**k = 5.** At five times the tie floor, Pythia's interval spans the entire swept range and a
universal alignment survives untouched.

So the honest position is that **neither "flat" nor "sharp" is established.** The disjointness is
real at the tie-rule floor and dies at five times it, and nobody has measured the dominant
nuisance in a perplexity sweep: the evaluation sample.

## The measurement that settles it, now running

`research/block/u_eval_floor.py`. Split the corpus into disjoint folds of 40 windows and run the
whole u-sweep independently on each. Two outputs:

* the fold-to-fold spread of ppl at fixed u — the evaluation floor, measured rather than assumed;
* the fold-to-fold spread of **u\* itself** — which needs no floor, no curvature and no grid
  argument at all.

Pre-registered, both reported:

* **A** — u\* stable within a model, differing between models by more than that spread. The
  disagreement survives resampling; the alignment law is dead for the strong reason, and the tie
  floor was an adequate proxy after all.
* **B** — u\* moves within a model as much as it moves between models. Then the cross-family
  comparison was sampling noise, and the campaign's central negative result is unsupported. That
  would not make the law true; it would mean nothing has been shown either way.

GPT-2 and Pythia go first because that pair carries the whole claim.

## Unrelated to the fault, and unchanged by it

The refutation of the `frac(log2 blockmax)` hypothesis stands under **both** statistics. Pythia has
the lowest non-uniformity of the four (KS 0.0085) and, corrected, the highest curvature.
Spearman(KS, depth) = 0.000; Spearman(KS, curvature) = −0.800 — the wrong sign, no better. Fixing
the instrument did not rescue the hypothesis.

## The open gap this exposed

**SmolLM2 has never been swept on the common grid.** Its numbers come from `scale_settled`'s
8-point [0, 0.9] sweep and have been pooled with `align_u`'s 13-point [0, 0.55] sweeps throughout.
Nothing flagged the mismatch. Qwen has never been u-swept at all. Both are 2 of the 5 families,
and both need the common grid before any five-model statement is made.

---

# The evaluation floor, measured. And why `k = 5` asked the wrong question.

GPT-2, three disjoint folds of 40x1024 tokens each, full u-grid on every fold. Fold 0 reproduces
the stored sweep bitwise (gate F4), so the folds are the same experiment, not a re-implementation.

    fold 0:  u* = 0.2500   ppl* = 35.6968
    fold 1:  u* = 0.2500   ppl* = 30.7917
    fold 2:  u* = 0.2500   ppl* = 37.2651

**The level moves by 6.5 ppl between folds. The argmin does not move at all** — spread 0.0000,
against a grid step of 0.0150.

## The noise decomposes, and only one part matters

| noise | what it is | median | vs GPT-2's tie floor 0.0003 |
|---|---|---|---|
| **marginal** | spread of the *level* across folds at fixed u | 6.7010 ppl | 22,337x |
| **differential** | spread of the *shape*, ppl(u) − ppl(u\*), across folds | 0.2471 ppl | 824x |

Common mode cancels a factor of 27. A harder fold lifts the whole curve and leaves its shape
alone — which is exactly what should happen, because every u is evaluated on **the same tokens**
with the same model. The arms are paired.

**So `k = 5` was answered with the wrong statistic.** Inflating the floor as an absolute
perplexity offset models the noise as if each u were measured on an independent sample. They are
not. For an argmin over paired arms the floor is the **differential** spread, and the marginal
spread — the one that looks alarming — is 27x larger and irrelevant.

## What that does to the interval

At the differential floor, GPT-2's indistinguishable interval stops being degenerate:

    at the tie floor 0.0003            [0.2500, 0.2500]   width 0.000  (unresolvable, grid-limited)
    at the differential floor 0.2471   [0.2266, 0.2770]   width 0.050

and Pythia's interval was [0.347, 0.433]. **Still disjoint, by 0.070.**

So the tie-rule floor understated the correct noise for GPT-2 by 824x, and the disjointness
survived it anyway, because the interval widens only as the square root of the floor.

## Pre-registered before Pythia's folds finish

The tie-rule floors span 1800x across models (GPT-2 0.0003 to Pythia 0.5358) and were shown to
track the checkpoint's stored mantissa width. The **differential evaluation floor should not**:
it is driven by which sentences are in the fold, not by how the weights were serialised. So:

> **Prediction.** Pythia's differential floor lands near GPT-2's in relative terms — GPT-2's is
> 0.2471 / 35.70 = 0.69% of its perplexity, so Pythia's should be about 0.0069 x 44.58 = 0.31 ppl.
> Registered interval **0.15 to 0.60 ppl**.

Consequences, stated in advance so neither can be chosen after the fact:

* **Inside 0.15–0.60.** Then Pythia's tie floor (0.5358) was an *over*estimate of the noise that
  matters, its interval narrows or holds, and the disjointness strengthens. The tie floor is then
  a bad proxy in **both directions** — 824x too small for an fp32 release, and too large for an
  fp16 one — and every interval in this campaign has to be recomputed against differential floors.
* **Above 0.60.** Then something model-specific inflates the shape noise, the interval widens, and
  the disjointness has to be re-checked before any of it is claimed.
* **u\* itself moves between Pythia's folds.** Then the argmin is not identified on that model at
  all, regardless of any floor, and Pythia cannot carry the disagreement.

---

# Result: OUTCOME A. And the prediction's range held while its direction did not.

Pythia, three disjoint folds, same protocol. Fold 0 reproduces the stored sweep bitwise.

    gpt2    u* per fold  [0.2500, 0.2500, 0.2500]    spread 0.0000
    pythia  u* per fold  [0.4000, 0.3500, 0.4000]    spread 0.0500

**Closest approach between the two models' fold sets is 0.10 — twice the largest within-model
spread.** That sentence uses no floor, no curvature and no grid argument. The cross-family
disagreement is not sampling noise. **OUTCOME A**, as pre-registered.

## The prediction, scored honestly

Registered before the folds ran: Pythia's differential floor in **[0.15, 0.60] ppl**, point
estimate 0.31 from scaling GPT-2's 0.69 % of perplexity.

| | GPT-2 | Pythia |
|---|---|---|
| marginal floor (level) | 6.7010 | 4.6044 |
| **differential floor (shape)** | **0.2471** | **0.5770** |
| as % of ppl at u\* | 0.714 % | 1.239 % |
| tie-rule floor | 0.0003 | 0.5358 |
| differential / tie | **800×** | **0.93×** |
| common mode cancels | 27× | 8× |

**0.5770 is inside the registered range** — but at its top edge, and the point estimate was off by
1.9×. The relative floor is 1.24 % against GPT-2's 0.71 %, so "corpus sampling makes it
model-independent in relative terms" is roughly right and not exactly right.

**The registered consequence was wrong in its direction.** I wrote that landing inside the range
would mean Pythia's tie floor was an *over*estimate and its interval would *narrow or hold*. In
fact the tie floor (0.5358) is within 7 % of the differential floor (0.5770) — it was neither over
nor under, it happened to be right — and the interval **widened**, 0.086 → 0.100.

The correct statement is narrower than the one I registered:

> The tie floor tracks the checkpoint dtype; the differential evaluation floor tracks the corpus
> and sits near 0.7–1.2 % of perplexity for both models. On an **fp32** release the tie term is
> negligible and the evaluation term dominates by 800×; on **fp16** the two are the same size and
> the tie floor is accidentally adequate. **The floor to use is max(tie, differential-eval)**, and
> the campaign used the tie term alone.

## Intervals at the correct floor

    gpt2    u* 0.2500   floor 0.2471   [0.2266, 0.2770]   width 0.0504
    pythia  u* 0.4000   floor 0.5770   [0.3297, 0.4298]   width 0.1001

**Still disjoint, gap 0.053.** OCP's u = 0.41504 remains inside Pythia's interval and outside
GPT-2's.

So the `k = 5` worry is resolved in the direction the corrected reasoning predicted: the floor was
indeed understated — by 800× on GPT-2 — and the disjointness survived it, because an interval
widens as the square root of the floor while `k` was applied as a linear offset.

## What is now established, and what is not

**Established.** Two models' alignment optima are individually stable under resampling to within
one grid step, and they differ by twice that. No single alignment constant is optimal for both.
The argument no longer depends on any floor.

**Not established.** This is n = 2. OPT and SmolLM2 have not been fold-resampled; SmolLM2 has
never been swept on the common grid; Qwen has never been swept at all. The three-model minimax
result (u = 0.2042 at 1.488 % worst case against OCP's 5.025 %) rests on single-fold curves for
OPT and should be re-derived once OPT is resampled.
