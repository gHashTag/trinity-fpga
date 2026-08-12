# The held-out label on −4.74 % carries no information, and it is provable rather than arguable

`MX-asym-NEAR0` has been quoted as **"−4.74 % held-out mean, 4/4 models, the only
arm clearing model-level significance (−4.76 %, CI [−8.58, −0.78], p = 0.032)"**.
Both halves are in-sample, and the first is in-sample in a way that can be shown
by algebra rather than argued about.

## (a) The −4.76 % is not a protocol result at all

It is `MX-asym-NEAR0`'s plain four-model mean margin against MXFP4. Reproduced
exactly: −4.7599 %, [−8.5808, −0.7793], p = 0.0322. No model is held out of it,
because no selection happens in it.

## (b) The −4.74 % reconstructs, and the reconstruction is the disproof

Select on one model by perplexity from the pool {NEAR0, MID, MID2}, judge on the
other three: −4.65 / −5.27 / −3.62 / −5.40, mean **−4.736 %**.

**The rotation is unanimous — NEAR0 is picked 4 of 4 — so that mean is
algebraically identical to NEAR0's plain four-model mean.** A leave-one-out
rotation whose folds all return the same arm computes the same number the
in-sample estimate does. The held-out label transports nothing; it is a
relabelling of (a).

And the pool it rotates over is **3 of the 7 possible insertions**, reduced to 3
by deleting the clipping arm *after* all four checkpoints had been seen. The same
protocol with the clipping arm still in the pool gives **−3.343 %**.

## The rotation-honest counterpart, in full

Complete nine-placement pool, selected by joint KL on three checkpoints and
judged on the fourth — the objective campaign A actually used:

| held out | fitted on | arm picked | runner-up (joint-KL gap) | held-out margin |
|---|---|---|---|---:|
| SmolLM2-135M | qwen+pythia+opt | `MX-asym-NEAR0N` | NEAR0 +2.018 % | −1.72 % |
| Qwen2.5-0.5B | smollm2+pythia+opt | `MX-asym-NEAR0` | NEAR0N +1.510 % | −3.14 % |
| Pythia-160M | smollm2+qwen+opt | `MX-asym-MIDN` | NEAR0 +0.202 % | −2.22 % |
| OPT-125M | smollm2+qwen+pythia | `MX-asym-NEAR0` | NEAR0N +1.195 % | −2.73 % |

Three distinct arms, so **there is no codebook to attach this to** — it is a
statement about the protocol. The point estimate is **−2.46 %**, better on 4 of 4
held-out checkpoints, against the in-sample **−4.76 %** of the same protocol.

**No interval is quoted, deliberately.** The four folds share three of four
models with each other and land on near-identical arms, so a t-interval over them
has no coverage guarantee. Its nominal `p = 0.0043` is *smaller* than the
in-sample `p = 0.032` only because selection shrinks the between-model spread
fourfold (sd 0.00633 against 0.02573 nats) by replacing Pythia's −8.07 % with
−2.22 %. That is a variance effect, not more evidence, and quoting the interval
would invert the reader's conclusion.

## "The only arm clearing model-level significance" is false

The nine-placement matrix, model-level, n = 4:

| placement | SmolLM2 | Qwen | Pythia | OPT | mean | 95 % CI | p | p × 9 |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| NEAR0 | −4.99 | −3.14 | −8.07 | −2.73 | **−4.76** | [−8.58, −0.78] | 0.032 | 0.290 |
| NEAR0N | −1.72 | −2.50 | −8.16 | −1.90 | −3.61 | [−8.46, +1.50] | 0.108 | 0.974 |
| MIDN | −5.04 | −2.07 | −2.22 | −1.41 | −2.70 | [−5.24, −0.08] | 0.046 | 0.418 |
| MID | −3.09 | −1.21 | −2.54 | −1.48 | −2.08 | [−3.48, −0.67] | 0.019 | 0.167 |
| G12 | −3.61 | −1.06 | −2.75 | −0.75 | −2.05 | [−4.20, +0.15] | 0.059 | 0.533 |
| G68 | −2.80 | −1.22 | −1.98 | −0.55 | −1.64 | [−3.17, −0.09] | 0.044 | 0.393 |
| MID2 | −0.12 | −1.35 | −5.18 | +0.50 | −1.56 | [−5.58, +2.62] | 0.314 | 1.000 |
| G34 | −1.03 | −0.10 | −0.88 | −0.06 | −0.52 | [−1.33, +0.30] | 0.135 | 1.000 |
| G23 | +0.67 | −0.36 | −2.32 | +0.03 | −0.50 | [−2.54, +1.58] | 0.496 | 1.000 |

**Four arms clear p < 0.05 uncorrected, not one** — and correcting over the nine
placements the argmin was taken from, **none does.** `MID` has the smallest
uncorrected p (0.019) and it is not the arm anyone deploys.

## What survives, and it is not nothing

`MX-asym-NEAR0` beats MXFP4 in **140 of 140 windows across four models**. That is
a within-model claim on each checkpoint, and no selection protocol inflates it:
the arm was not chosen per model, and the windows are the replicate unit the
claim is entitled to. What was never supported is the step from there to a fifth
checkpoint, and that step is what the held-out label was doing.

## The rule this does not license

An earlier draft proposed "subtract about 6 % of the margin per candidate beyond
the first" as a portable correction for selection optimism. **Withdrawn.** The
optimism curve measured here (0.23 / 0.48 / 1.03 / 1.64 / 2.30 pp at pools of
2/3/5/7/9) is a property of this nine-arm pool's particular correlation
structure, and the measurement it would correct — optimism −2.36 pp [−6.89,
+2.39], p = 0.208 — is itself a tie at n = 4. A rule of thumb derived from a tie
is a rule of thumb about noise.

The portable part is the classical one and belongs to the literature, not here:
the expected maximum of `K` correlated statistics exceeds the population maximum,
by roughly `σ√(2 ln K)` in the independent Gaussian case. Selection optimism is
textbook; what is ours is only the measurement that it accounts for **2.30 pp of
a 4.76 pp headline** in this specific pool.

---

*Rulers reproduced in the measuring process on all four checkpoints before any
number here was quoted (worst relative 2.0e-06; per-window NLL identical to
campaigns A and B at 0.00e+00; instrument `block_tnf.quant` against
`campaignC_books.make_quant_signed` bit-exact at 0.000e+00). Four models,
wikitext-2, block 32, E8M0, `lm_head` excluded. Cross-model claims carry
model-level statistics.*
