# The placement instability that drove three campaigns was one non-placement in the pool

`MX-asym-TOP` is not a placement of the sixteenth codeword. It extends E2M1's
ladder to 16/12, and normalising the result to the positive tail leaves the
negative extreme at **−0.75** — so it reconstructs the largest-magnitude negative
element of every block at 0.75× its scaled value. It buys a rung by clipping a
tail. Ranking it beside nine insertions compares a placement choice against a
clipping choice, and the comparison is what three campaigns were reading.

**The fact was never unknown.** It is written down in three places in this
directory, in the code, before any of the affected claims were made:

* `campaignA_books.py`'s module docstring — "TOP (extend the ladder to 16/12,
  which renormalisation pays for by clipping the negative extreme to −0.75)"
* `campaignD_spearman.py:86` — "TOP is not 'MXFP4 plus one level': adding 16/12
  forces a renormalisation", with an explicit `without TOP (n=4)` column
* `SIXTEENTH_CODEWORD_SPENT_2026-08-12.md` — "**TOP is a trap.** … reach bought
  on one side, paid for by clipping on the other"

What was missing was the one thing that could stop it propagating: the assertion.

```python
assert abs(max(pos, neg) - 1.0) < 1e-12          # what it did
```

The docstring above it read *"T38 on BOTH tails"*. `max(pos, neg)` is satisfied
by **either** tail reaching 1.0, so a book at +1.000 / −0.750 passes a check
whose stated purpose is to reject exactly that. Every downstream module took its
candidate list from `candidates()`, and `candidates()` returned the clipping arm
as `kind="sig"`.

## The fix

`check()` now asserts each tail separately, per kind. `MX-asym-TOP` is `kind
"clip"`, returned by a new `clipping_arms()` and **excluded from
`candidates()`**; `all_books()` still includes it, so it stays measured and
named — it is a real arm, just not a placement.

Blast radius, bounded by import as the run_synth lesson prescribes:
`campaignA_run.py`, `campaignA_stats.py`, `campaignB_selector.py` and
`onefit_klscore.py` take their pool from `candidates()`.

**🛑 And the sentence that stood here was wrong in the most useful way a
sentence can be.** It read: *"`campaignB_stats.py` hard-codes its own four-arm
list and never called `check()` at all."* Every word true, and used as an
exemption when it is the exact opposite — **because it never draws from
`candidates()`, it is the one campaign that did not inherit the fix.** A
blast-radius check bounded by imports tells you what an edit *reaches*; it does
not tell you what shares the defect through duplication rather than through
import. Two further things followed:

* **There is a second clipping arm, and this document did not name it.**
  `campaignB_books.py` asserts `top = max(abs(x) for x in lv)` under a docstring
  reading "T38 phase assert" — the same defect in different notation. It shipped
  **two** books at +1.000 / −0.750: `MX-asym-TOP` **and `JK-asym-TOP`**. Both are
  now `kind="clip"`, and `check()` verifies the label rather than trusting it: a
  `clip` that does not clip fails too.
* **The Bonferroni family counted a clipping choice as a placement.** Three
  placements, not four. The reclassification was made on structural grounds a
  day before anyone computed which way it moved a verdict — and at the model
  level it moves none.

## What moves

Every number below is this repo's own script, re-run unmodified except for the
candidate set.

### The selection protocol comparison inverts (`campaignA_stats.py`)

| protocol | with the clipping arm | placements only |
|---|---|---|
| select on one model **by perplexity** | 10 / 12, worst **+4.68 %** | **12 / 12, worst −1.41 %** |
| select on one model by KL | 12 / 12, worst −1.41 % | 12 / 12, worst −1.41 % |
| select jointly on three by KL | 4 / 4, worst −1.72 % | 4 / 4, worst −1.72 % |

One row of the rotation differs, and it is the whole published finding. With the
clipping arm in the pool, perplexity selects it on Pythia and loses on two
held-out models (+4.68 %, +2.33 %). Without it, perplexity selects `NEAR0N` and
wins on all three (−1.72 %, −2.50 %, −1.90 %).

**So the claim "the objective was the fix, not the jointness" does not survive.**
The published reasoning was that perplexity on a single checkpoint is a noisy
selector and KL is not. The entire difference between the two objectives was one
book that should not have been selectable by either. On the nine placements they
are indistinguishable: 12/12, worst −1.41 %, both.

### The mechanism Spearmans lose their zero-information rotations

Joint-KL score against held-out margin:

| held out | with the clipping arm | placements only |
|---|---:|---:|
| SmolLM2 | +0.188 | **+0.433** |
| Qwen | +0.758 | +0.817 |
| Pythia | **−0.030** | **+0.333** |
| OPT | +0.927 | +0.900 |

The published sentence — "the rotations that disagree are exactly those where the
objective carries no rank information about the judge" — described a pattern that
the clipping arm produced. No rotation carries zero rank information on the
placements.

### The models stop disagreeing about placement

| pair | with the clipping arm | placements only |
|---|---:|---:|
| SmolLM2 vs Pythia | **−0.212** | **+0.083** |
| Pythia vs OPT | +0.067 | +0.467 |
| Qwen vs Pythia | +0.430 | +0.650 |
| SmolLM2 vs OPT | +0.794 | +0.717 |
| Qwen vs OPT | +0.612 | +0.633 |
| SmolLM2 vs Qwen | +0.491 | +0.483 |

The single anti-correlated pair was the arm that wins on Pythia (−8.27 %) and
loses on SmolLM2 (+4.68 %). Its removal is worth 0.30 on the mean pair
agreement, and it takes with it the one pair used elsewhere to refute a
weight-distribution conjecture.

### The earlier document's headline failure disappears

`SIXTEENTH_CODEWORD_SPENT`'s rotation, on that document's own four-arm pool:

| picked on | with the clipping arm | placements only |
|---|---|---|
| SmolLM2 | NEAR0, −2.53 % vs NF4 | NEAR0, −2.53 % |
| Qwen | NEAR0, −0.85 % | NEAR0, −0.85 % |
| **Pythia** | **TOP, +5.35 % — "the protocol loses"** | **NEAR0, −0.51 %** |
| OPT | NEAR0, +0.44 % | NEAR0, +0.44 % |

"One rotation of four gives the headline" was one rotation reaching for a
non-placement. On the placements the rotation is unanimous — `NEAR0` 4/4 — and
every rotation beats MXFP4 held out (−4.65 %, −5.27 %, −3.62 %, −5.40 %).

### The classical criterion gets worse, not better

`campaignD_spearman.py`, its own `without TOP` column, against the pooled
measured order:

| predictor | n = 5 | n = 4, placements only |
|---|---:|---:|
| P1 bin mass | +0.700 | +0.400 |
| P2 mass × width² — the classical greedy step | +0.400 | **−0.200** |
| P3 KL share | +0.900 | **+1.000** |

At n = 4 only a perfect order is significant, so P3's `+1.000` (p = 0.0417) is
the floor of what the test can say, not a strong result. The direction of P2 is
the durable part: the greedy squared-error criterion is negative on the
placements, which is `METRIC_DISAGREEMENT` in the same direction the real-weight-
space measurement found (ρ = −0.800).

## What does not move

The `MX-asym-NEAR0` deployment claim is untouched: it beats MXFP4 in 140 of 140
windows across four models, and `NEAR0` is now selected by **more** rotations
than before, not fewer. The silicon results contain no placement ranking. The
T40 decomposition is about `NF4-sym` and never involved the clipping arm.

## The pattern, stated once

This is the same failure as the `run_synth` frequency collector three days ago
and as the `SLICE_LUTX` decoder cost before it: **the harness asserted less than
its docstring claimed, and every campaign downstream inherited the gap.** In all
three the underlying fact was already written down somewhere in the repository.
The instrument is not the thing that discovers the fact; it is the thing that
stops a known fact from being quietly contradicted 400 lines later.

The check that would have caught all three is the same one: *read what the
assertion actually compares, not what the line above it says it compares.*

---

*Re-analysis only — no model was re-run. Every per-window NLL is the one already
on disk from campaigns A and B; the candidate set changed and the statistics were
recomputed by `campaignA_stats.py` and `campaignD_spearman.py` unmodified. Four
models, wikitext-2, block 32, E8M0, `lm_head` excluded.*
