# What this campaign established, and what it only appeared to

Twenty-four hours produced eleven documents, six withdrawals and one result that
came in through a door nobody was watching. This is the consolidated reading, so
the next person does not have to reconstruct it from eleven files that each argue
one point.

## 1. The one positive result, and it is a negative one

**The E8M0 block scale absorbs the tails.** Across eight checkpoints and four
architecture families, raw weight kurtosis spans **14.6×** (3.786 to 55.334)
while block-normalised kurtosis — what the codebook actually sees — spans **0.190
absolute** (2.795 to 2.985).

Every prediction was pre-registered with four of eight checkpoints measured and
every one held, including Mamba-130M, a state-space model with **no attention at
all**, which landed inside the *narrow* band written for the transformers rather
than the widened one it was given.

**Consequence, and it is the campaign's most useful sentence:** no statistic of
the weight distribution can predict how much a codebook's margin transfers
between checkpoints, because after the scale rule the codebook operates on the
same distribution everywhere. That is not five failures, it is one:

| what failed | how |
|---|---|
| T41's clipping criterion | wrong sign on two of four |
| T42's occupancy conjecture | — |
| P1 / P2 / P3 bin predictors | none rotation-stable; the classical greedy one **anti**-correlated |
| four explanations for the KL selector | each refuted by control |
| "the margin from four checkpoints appears on a fifth" | it did not |

T38 established that the scale rule fixes the headroom phase. This adds that it
also fixes the *shape* — and therefore erases the inputs every one of those
predictors was reading.

**The registered caveat still stands:** kurtosis is the fourth moment and nothing
else. A predictor on block-normalised occupancy of the specific intervals two
books differ in is not excluded, has its own registration, and is being measured.

## 2. What was withdrawn, and the single shape it all had

| # | the claim | what it actually was |
|---|---|---|
| 1 | `MX-asym-TOP` ranked among the placements | a **clipping** arm at +1.000/−0.750; the T38 assert compared `max(pos,neg)` under a docstring saying "both tails" |
| 2 | "the objective was the fix, not the jointness" | one ineligible book in the pool. Remove it and perplexity-selection goes 10/12 → **12/12** |
| 3 | eleven of fourteen `BEATS`/`loses` verdicts | `np.concatenate` over four models' windows, handed to a t-test as n = 140 |
| 4 | `MX-asym-NEAR0` "−4.74 % held out, 4/4" | a **unanimous** rotation, therefore algebraically the in-sample mean |
| 5 | "the only arm clearing model-level significance" | four clear uncorrected; **none** clears Bonferroni over the nine the argmin came from |
| 6 | T41's "bit-exact" corollary | measured on `torch.randn`, where its own stated exception cannot occur |

**Six items, one shape: the harness asserted less than its prose claimed.** And
in every case the fact was already written down somewhere in the repository —
`campaignA_books.py`'s docstring named TOP's clipping, `campaignD_spearman.py`
carried a without-TOP column,
`gHashTag/trinity/.github/workflows/website-checks.yml`'s header said "the three
checks that exist and never run". Prose does not execute. Only the assertion is
load-bearing.

The sixth was found in a *script*, not a document, because the previous five were
caught by re-reading prose and this one lived inside a call to `np.concatenate` —
a shape-changing utility nobody reads as a claim about exchangeability.

## 3. The deployed codebook is a tie

With a genuinely held-out fifth checkpoint, at model level over n = 5, Bonferroni
family = the nine placements the argmin came from:

| placement | mean | 95 % CI | p | ×9 | |
|---|---:|---|---:|---:|---|
| `NEAR0` **(deployed)** | −4.03 % | [−7.32, −0.63] | 0.031 | 0.279 | **TIE** |
| **`MID`** | −2.12 % | [−3.07, −1.16] | 0.004 | **0.036** | **BEATS** |

The deployed arm has nearly twice the mean and does not survive. The mechanism is
variance: `NEAR0` ranges 7.01 pp across checkpoints, `MID` ranges 1.88. And the
selection protocol cannot see it — pick by mean margin leave-one-out and `NEAR0`
is chosen **5 of 5**, because the mean is the statistic one checkpoint dominates.

**Selecting on the mean and reporting with a multiplicity correction are
inconsistent objectives.** They are also not separable at this n: `MID` vs
`NEAR0` head to head is +1.99 % [−1.17, +5.25], p = 0.157.

On GPT-2, the first checkpoint that took no part in any decision here, `NEAR0`'s
margin is **−1.06 %** against **−4.76 %** in-sample, it ranks **fourth** of nine,
and **NF4 — the 2023 reference — wins outright** at −3.03 %.

## 4. The open question, stated precisely

MXFP4's cost spans **21×**: +8.2 % on BLOOM-560M, +174.4 % on GPT-Neo-125M
(independently re-measured to 5.3e-07 relative). The perturbation has the same
shape everywhere — §1 establishes that. So the difference is in **how sensitive
each trained function is**, not in what its weights look like.

First measurement, OPT-125M, four perturbation sizes with a zero-eps control that
reproduces the ruler bit-identically: the response fits `rel ~ eps^1.600`, not the
`eps²` a smooth second-order expansion gives, with per-step ratios 2.691, 3.042,
3.399 rising toward the quadratic 4.0.

**That is not being claimed.** For isotropic noise the first-order term has zero
expectation, but a *single draw* realises one of size `|g|·eps·|w|`, which scales
as `eps¹` and would bend α below 2 at small eps — exactly the observed shape. A
five-seed control is running: if the seed-averaged mean recovers α ≈ 2 while the
across-seed spread scales as `eps¹`, the confound is demonstrated and every
single-seed number here must be re-read. Either outcome is reportable; neither is
reported yet.

## 5. The instruments built, because the findings were instrument failures

* `campaignA_books.check` — asserts **each tail per kind**, and verifies the
  `clip` label rather than trusting it: a `clip` that does not clip fails too.
* `campaignB_stats.row` — branches on the replicate unit **explicitly**, in prose
  at the site, instead of implying it through a reshape.
* `gate_status_ratchet.py` — 142 gate-shaped scripts in `research/`, CI invoked
  15, and the aggregator that would run them all was invoked **zero** times. Now
  per-script, direction-only, with a self-test that must fail. Its **first act
  was to disagree with itself** on an unchanged tree, which is how the
  load-dependence of a wall-clock limit got found and fixed.
* `provenance.py` — 70 of 70 records now pin the corpus **by content**, the
  checkpoint by revision, the harness by the source it executed. Written after
  the weights directory vanished mid-campaign and was recovered only because the
  ruler gate could prove the restored substrate was the same instrument.
* `sensitivity.py`, `seed_control.py`, `occupancy.py` — each with the control
  that decides whether its number means anything, run before the number.

## What a reader should take

**Established:** the scale rule absorbs the fourth moment of the weight
distribution across eight checkpoints and four families, and therefore
weight-side predictors of margin transfer cannot work. `MX-asym-NEAR0` beats
MXFP4 in 140 of 140 windows on the four checkpoints it was selected on — a
within-model claim, unaffected by any of the above.

**Not established:** that any codebook here beats MXFP4 on a checkpoint it has
not seen, at model level, after correcting for the pool it was chosen from. One
placement (`MID`) clears that bar and is a tie against the deployed one.

**Open:** why the same perturbation costs 21× more on one trained function than
another.

---

*Eight checkpoints — SmolLM2-135M, Qwen2.5-0.5B, Pythia-160M, OPT-125M, GPT-2
124M, GPT-Neo-125M, BLOOM-560M, Mamba-130M. wikitext-2, block 32, E8M0,
`lm_head` excluded, 4.25 b/elem. Cross-model claims carry model-level statistics
throughout; windows are replicates of the text and are never pooled across
checkpoints.*
