# The weight side is closed, and the registered prediction was wrong in the direction that closes it

`PREREGISTRATION_OCCUPANCY_2026-08-12.md` tested the one weight-side predictor
`SCALE_ABSORBS_THE_TAILS` did not exclude. Its registered expectation was that
**O1 would hold and O2–O4 would fail** — that occupancy carries real information
and is still not usable.

**O1 failed too.** The information is not there either.

## The measurement

The altered interval is derived from the books, not eyeballed: inserting level
`x` between neighbours `a < x < b` moves the decision boundaries from `(a+b)/2`
to `(a+x)/2` and `(x+b)/2`, so exactly the block-normalised magnitudes in
`[(a+x)/2, (x+b)/2]` are reconstructed differently.

| placement | altered interval | width |
|---|---|---:|
| `NEAR0` / `NEAR0N` | [0.02083, 0.06250] | 0.0417 |
| `G12` | [0.10417, 0.14583] | 0.0417 |
| `MID2` | [0.37500, 0.45833] | 0.0833 |
| `MID` / `MIDN` | [0.75000, 0.91667] | **0.1667** |

Mass in those intervals, eight checkpoints, four architecture families:

| checkpoint | `NEAR0` mass | `MID` mass | widest-two |
|---|---:|---:|---:|
| OPT-125M | 0.09124 | 0.04309 | 0.13543 |
| BLOOM-560M | 0.08957 | 0.04460 | 0.14004 |
| Qwen2.5-0.5B | 0.08512 | 0.04486 | 0.14011 |
| GPT-Neo-125M | 0.08444 | 0.04517 | 0.14106 |
| SmolLM2-135M | 0.08268 | 0.04643 | 0.14487 |
| **Mamba-130M** | 0.08258 | 0.04655 | 0.14613 |
| GPT-2 124M | 0.08255 | 0.04625 | 0.14543 |
| Pythia-160M | 0.08039 | 0.04774 | 0.14968 |

## Scored against the registration

| # | threshold, fixed in advance | measured | |
|---|---|---|---|
| **O1** | relative spread **> 20 %** | **12.8 %** (`MID`: 10.2 %) | **FAILS** |
| **O2** `NEAR0` | ρ ≤ −0.75, p < 0.05, sign **negative** | ρ = **+0.400**, p = 0.505 — **wrong sign** | **FAILS** |
| **O2** `MID` | same | ρ = −0.800, p = 0.104 | **FAILS** |
| **O4** | ρ ≥ +0.75, p < 0.05 | ρ = +0.607, p = 0.148 | **FAILS** |

**P1, my own registered number, predicted a 25–60 % spread. It is 12.8 %.** The
prediction was wrong, and it was wrong in the direction that strengthens the
conclusion it was written to hedge — which is the only reason writing it down in
advance was worth anything.

**The one thing pointing the right way**, recorded because a null deserves the
same scrutiny as a hit: `MID`'s ρ = −0.800 carries the predicted sign at n = 5.
It does not clear its threshold (p = 0.104, and ×4 for the registered family it
is 0.416), and `NEAR0` — the arm with the larger effect — points the *opposite*
way. One of four pointing correctly at n = 5 is what chance produces.

## What this closes

The registration fixed the meaning in advance: *"O1 fails → occupancy is absorbed
too, `SCALE_ABSORBS`'s C2 stands without its caveat, and the weight side is
closed."*

So, on eight checkpoints across four architecture families including a model with
no attention:

**Nothing about the weight distribution — not its fourth moment, not the local
mass in the exact intervals two codebooks differ in — varies enough between
checkpoints to explain why a codebook's margin does.** The E8M0 rule
`s = 2^⌈log₂ a⌉` normalises both away. A raw distribution 14.6× heavier than
another yields a block-normalised one whose fourth moment differs by 6 % and
whose mass in `NEAR0`'s interval differs by 13 %, while the margins those
checkpoints show differ by **8×** (−1.06 % on GPT-2 to −8.07 % on Pythia) and
MXFP4's own cost differs by **21×**.

**The inputs are the same and the outputs are not.** Everything that differs is
downstream of the weights.

## What is left, and it is one thing

How sensitive each trained function is to a perturbation of fixed relative size.
That is `sensitivity.py`, and its first result is under a control that has not
returned: OPT's response fits `eps^1.600` rather than `eps²`, which would be a
statement about the second-order assumption underlying the OBQ/GPTQ family — and
which a single noise draw could manufacture, because the first-order term has
zero expectation but a realised size scaling as `eps¹`. A five-seed control
decides it. Until then the exponent is not claimed.

## The honest limit

Eight checkpoints, all under 600M parameters, one corpus, one block size, one
scale rule. "The weight side is closed" is a statement about *these* statistics
on *this* configuration. A statistic nobody has thought of could still work; what
is established is that the two natural families — global moments and local
occupancy of the altered intervals — both fail, and they fail for the same
structural reason rather than by accident.

---

*Block 32, E8M0 with `s = 2^⌈log₂ a⌉`, `lm_head` excluded, `block_tnf`'s own
target selector, GPT-2's `Conv1D` transposed so blocks run along the contraction
axis. Occupancy is the fraction of `|w|/amax` per block of 32 falling in the
derived interval. Exact permutation p-values; replicate unit is the checkpoint.*
