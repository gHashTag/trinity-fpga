# The campaign deployed the arm with the biggest mean. The only arm that survives multiplicity is a different one

With the fifth checkpoint added, the nine placements can be ranked at the model
level over `n = 5`, with the Bonferroni family set to the nine the argmin was
actually taken from.

| placement | SmolLM2 | Qwen | Pythia | OPT | **GPT-2** | mean | 95 % CI | p | ×9 | verdict |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| `NEAR0` **(deployed)** | −4.99 | −3.14 | −8.07 | −2.73 | **−1.06** | **−4.03** | [−7.32, −0.63] | 0.031 | 0.279 | **TIE** |
| `NEAR0N` | −1.72 | −2.50 | −8.16 | −1.90 | −0.50 | −3.00 | [−6.72, +0.87] | 0.097 | 0.873 | TIE |
| `MIDN` | −5.04 | −2.07 | −2.22 | −1.41 | −1.97 | −2.55 | [−4.33, −0.74] | 0.018 | 0.162 | TIE |
| **`MID`** | −3.09 | −1.21 | −2.54 | −1.48 | −2.26 | −2.12 | **[−3.07, −1.16]** | **0.004** | **0.036** | **BEATS** |
| `G12` | −3.61 | −1.06 | −2.75 | −0.75 | −0.74 | −1.79 | [−3.42, −0.13] | 0.040 | 0.360 | TIE |
| `G68` | −2.80 | −1.22 | −1.98 | −0.55 | −0.94 | −1.50 | [−2.61, −0.38] | 0.020 | 0.180 | TIE |
| `MID2` | −0.12 | −1.35 | −5.18 | +0.50 | −0.23 | −1.30 | [−4.13, +1.62] | 0.280 | 1.000 | TIE |
| `G23` | +0.67 | −0.36 | −2.32 | +0.03 | −0.56 | −0.51 | [−1.90, +0.89] | 0.366 | 1.000 | TIE |
| `G34` | −1.03 | −0.10 | −0.88 | −0.06 | −0.19 | −0.45 | [−1.03, +0.13] | 0.096 | 0.864 | TIE |

**`MX-asym-MID` is the only placement that clears Bonferroni over the nine.** It
has a mean margin roughly *half* the deployed arm's, and it is the only one whose
claim survives the correction the pool size demands.

## Why: the deployed arm is the high-variance one

| | mean | range across checkpoints |
|---|---:|---:|
| `NEAR0` | **−4.03 %** | −1.06 to −8.07 — **7.01 pp** |
| `MID` | −2.12 % | −1.21 to −3.09 — **1.88 pp** |

`NEAR0`'s mean is carried by one checkpoint. Drop Pythia's −8.07 % and it is
−2.98 %; `MID` without Pythia is −2.01 %, essentially unmoved. A margin that
depends on which checkpoints are in the average is not a margin about codebooks.

**And the selection protocol cannot see this.** Leave one checkpoint out and pick
by mean margin on the other four: `NEAR0` is chosen **5 times out of 5**, because
the mean is exactly the statistic Pythia dominates. The protocol reliably selects
the arm whose advantage does not generalise, and reports −4.03 % [−7.32, −0.63],
p = 0.031 for doing so — which is `BEATS` only if you forget that the arm was
chosen from nine.

## The general statement

**Selecting on the mean and reporting with a multiplicity correction are
inconsistent objectives.** The mean rewards a large win anywhere; the correction
punishes exactly the variance that a large win anywhere implies. An arm that wins
by 8 % once and 1 % four times and an arm that wins by 2 % five times can have
the same mean, and only the second has a claim that survives being one of nine.

If the deliverable is *"a codebook that beats MXFP4 on a checkpoint you have not
seen"*, the selection statistic should be the one the claim is made in — the
worst case, or the mean penalised by its own spread — not the raw mean.

**Measured, and it is only a partial vindication.** Selecting by worst case
instead of by mean, leave-one-checkpoint-out:

| held out | mean-selected | worst-case-selected | held-out margin |
|---|---|---|---:|
| SmolLM2 | NEAR0 | `MIDN` | −5.04 % |
| Qwen | NEAR0 | `MID` | −1.21 % |
| Pythia | NEAR0 | `MIDN` | −2.22 % |
| OPT | NEAR0 | `MIDN` | −1.41 % |
| GPT-2 | NEAR0 | `NEAR0` | −1.06 % |

Worst-case selection **does** stop choosing one arm every time — it picks three
different ones — and its protocol figure is −2.20 % [−4.26, −0.10], p = 0.044
against mean-selection's −4.03 % [−7.32, −0.63], p = 0.031. Neither protocol
separates from the other at n = 5, and worst-case selection lands on `MID` only
once. So the rule *"select in the statistic you will report in"* is sound in
principle and is **not** demonstrated to help here; what is demonstrated is only
that mean-selection is degenerate, picking the same high-variance arm on every
rotation.

`MID` vs `NEAR0` head to head, model level, n = 5: **+1.99 % [−1.17, +5.25],
p = 0.157** — a tie, and `MID` is the *better* arm on GPT-2 alone (−1.22 %) while
losing on the other four.

## What this does not say

It does not say `MID` is better than `NEAR0`. They are a **tie** against each
other: paired at the model level over five checkpoints, the difference is inside
its own interval, and `n = 5` cannot separate arms that overlap this much. It
says something narrower and, for a deployment decision, more useful: **of the
nine, `MID` is the only one whose margin is still a claim after the pool it came
from is accounted for.**

Nor does it rescue the line as a whole. `NF4` — the 2023 reference — beats every
placement on GPT-2 at −3.03 %, and the standing note that our own KL criterion
prefers NF4 when the reference books are admitted to the pool is unaffected by
any of this.

---

*Five checkpoints, wikitext-2, block 32, E8M0, `lm_head` excluded. Model-level
statistics throughout — each checkpoint contributes one mean log-ratio, windows
are never pooled across checkpoints. Bonferroni family = 9, the placement pool
the argmin was taken from; `MX-asym-TOP` is a clipping arm and is not in it.*
