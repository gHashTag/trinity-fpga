# The fifth checkpoint: NEAR0's margin falls to a quarter, and it is no longer the best arm

**Status: the pre-registered test is INCOMPLETE.** `PREREGISTRATION_FIFTH_2026-08-12.md`
fixes an `n = 4` model-level test on four new checkpoints. Two were measured
before the run hit a weekly usage limit; `bloom-560m` and `mamba-130m` were not.
**The registered statistic cannot be computed and is not computed here.** What
follows is the per-checkpoint evidence that exists, reported as such, so that the
remaining two can be added without anyone having chosen a threshold in between.

## GPT-2 124M — the first checkpoint that took no part in any codebook decision

80 × 1024 = 81,920 tokens, the same span as 40 × 2048 elsewhere. New rulers,
nothing published to reproduce against: **fp32 29.0797, MXFP4 33.8114**, so MXFP4
costs +16.27 % — gate G5 holds.

| arm | margin vs MXFP4 | rank on the old four |
|---|---:|---:|
| **NF4** | **−3.03 %** | — |
| `MX-asym-MID` | **−2.26 %** | 4th |
| `MX-asym-MIDN` | −1.97 % | 3rd |
| **`MX-asym-NEAR0`** | **−1.06 %** | **1st** |
| `MX-asym-G68` | −0.94 % | 6th |
| `MX-asym-G12` | −0.74 % | 5th |
| `MX-asym-G23` | −0.56 % | 9th |
| `MX-asym-NEAR0N` | −0.50 % | 2nd |
| `MX-asym-MID2` | −0.23 % | 7th |
| `MX-asym-G34` | −0.19 % | 8th |

Three things, and none of them is what the campaign expected.

**1. The margin falls to roughly a quarter.** `MX-asym-NEAR0` measures **−4.76 %**
on the four checkpoints it was selected on and **−1.06 %** here. The selection
optimism measured from pool size predicted 2.30 pp of the 4.76 pp headline; the
observed gap on a genuinely held-out checkpoint is **3.70 pp**. The optimism
estimate was itself optimistic.

**2. `NEAR0` is not the best placement here — it is fourth.** `MID` and `MIDN`
both beat it, and `MID` is the arm with the *smallest* uncorrected p on the old
four (0.019) that nobody deploys. The deployed choice loses to an arm the
campaign has been treating as a runner-up.

**3. NF4 wins outright**, by more than any placement. That is the third time in
this line that the 2023 reference book has come out ahead when a genuinely new
condition is introduced.

**H3, the ranking-transport hypothesis, is not supported at this n.** Spearman
between the old-four order and the GPT-2 order over the nine placements is
**ρ = +0.550, p = 0.125**. The registered prediction was ρ = +0.75 with exact
p < 0.05. The rank information is *positive* — the order is not random — but it
does not clear the threshold fixed in advance.

**P7 fails on both halves.** It predicted `NEAR0` would stay rank 1 or 2 (it is
4th) and `G23`/`G34` would stay the two worst (the two worst are `G34` and
`MID2`).

## GPT-Neo-125M — one arm only

Measured under a different line before the limit, so only `MX-asym-NEAR0` was
run: **fp32 24.4877, MXFP4 67.1914** — MXFP4 costs **+174.4 %** here, five times
its cost on any other checkpoint in the pool, which is itself worth recording.
`MX-asym-NEAR0` is **−1.90 %**, rulers reproduced.

So on both new checkpoints `NEAR0` still beats MXFP4, and on both it does so by
**about a third to a quarter of its in-sample margin**:

| | in-sample four | GPT-2 | GPT-Neo |
|---|---:|---:|---:|
| `MX-asym-NEAR0` vs MXFP4 | −4.76 % | −1.06 % | −1.90 % |

## What can and cannot be said now

**Can:** the *sign* survives on two architecturally distant checkpoints, and the
*magnitude* does not. Whatever is real here is roughly a quarter of what was
reported, and the campaign's chosen placement is not the best one on the first
checkpoint that never voted for it.

**Cannot:** anything with a p-value. `n = 2` of a registered `n = 4`, and scoring
a pre-registered test on half its sample is precisely the freedom the
registration exists to remove. `bloom-560m` (ALiBi, 250,880-token vocabulary) and
`mamba-130m` (no attention at all) are the two that would say whether this is a
transformer property, and they are the two that are missing.

**The registration stands unamended.** No threshold, direction, checkpoint or
statistic in it has been changed after seeing these two. The remaining two
checkpoints can be measured against it as written.

---

*wikitext-2, block 32, E8M0, `lm_head` excluded, 4.25 b/elem. GPT-2's `Conv1D`
weights transposed to `[out, in]` so the block axis is the contraction axis on
every checkpoint. Cross-model claims would take model-level statistics; none is
computed here because the registered n is not reached.*
