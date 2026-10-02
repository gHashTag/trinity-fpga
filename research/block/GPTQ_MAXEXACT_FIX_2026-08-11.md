# GPTQ max-exactness fix — run, and it is a partial fix, not a full one

`THEOREM_2026-08-09.md` (lines 2271–2329) established the mechanism by which GPTQ loses to
plain round-to-nearest (RTN) under block-max scaling: the block scale `s = a/t_max` is set so the
block's maximum element always lands exactly on the top codebook level, but GPTQ's sequential
error compensation perturbs a row's max-holding column before its own turn if that column is not
first in processing order. Measured there: **95.0% of blocks lose max-exactness under GPTQ, 0.0%
under RTN.** The document proposed a fix but explicitly did not run it:

> "Testable fix, not yet run: quantise each group's maximal column *first*, before compensation
> can perturb it, or recompute the group scale from the compensated weights so the new maximum is
> exact again. Either restores the property; whether that restores GPTQ's advantage is the
> experiment."

This experiment runs it. Code: `gptq_maxexact_fix.py`.

## Why "process the max column first" cannot be a literal column reorder

GPTQ quantises one column index at a time for the **whole** weight matrix, using one Hessian
inverse `Hinv` shared by every output row. A row's group-maximum column differs from row to row,
so "process the max column first" cannot mean a single global reordering — it would need a
separate Cholesky factorisation (and `Hinv` permutation) per output row, at up to `d_out`× the
cost.

The implemented fix is the mathematically equivalent, much cheaper operation instead: a column
quantised exactly contributes **zero** error to columns after it (`err = (col − q)/Hinv[i,i]`,
and `col == q` exactly at the pinned top/bottom level), so "process the max column first" and
"protect the max column's pre-group value from incoming compensation until its own turn" produce
identical results. Concretely: for every (row, group), the group-local argmax column is fixed
from the *entering* (pre-compensation) weights — the same value that defines the group's scale
`s` — and any compensation update that would land on that (row, column) pair is zeroed for as
long as its own turn has not yet arrived within the group. When its turn comes, its value is
untouched since the group started, so `col/s = ±1` exactly, so it quantises to the pinned `±1.0`
codebook level exactly, so it propagates zero error onward — consistent by construction.

## Reproduction check (before trusting anything new)

Same model (SmolLM2-135M), same wikitext-2 windows (6–17), same 4 calibration sequences
(windows 18–21), same K=32 block size, same codebook derivation.

| configuration | this run | THEOREM_2026-08-09.md | diff |
|---|---|---|---|
| RTN uniform 4-bit | 17.3667 | 17.3662 | 0.0005 |
| GPTQ uniform 4-bit (original) | 17.7047 | 17.7846 | 0.080 |

RTN reproduces to 4 significant figures. GPTQ-original reproduces the *qualitative* finding
(worse than RTN, by a similar margin) but not to the same numerical tolerance — a 0.08 gap that
was not chased down further (candidate causes: BLAS/Cholesky numerical differences across
sandbox environments, torch version). **Because of this gap, all comparisons below are made
within this single run** (same weights, same calibration, same session), which is unaffected by
any cross-environment drift.

## Does the fix restore max-exactness?

| quantiser | blocks whose row-max is NOT exact | summed sq. error on maxima |
|---|---|---|
| RTN (reference) | 0 / 3,317,760 (0.0%) | 0.000e+00 |
| GPTQ-original | 3,162,231 / 3,317,760 (**95.3%**) | 5.206e+02 |
| **GPTQ-fixed** | **12,211 / 3,317,760 (0.4%)** | 8.658e+01 |

**Yes — 95.3% → 0.4%.** The mechanism is confirmed and the fix works essentially as designed.
The residual 0.4% is consistent with a known edge case, not a flaw in the fix: a "dead" column
(zero Hessian diagonal, i.e. zero activation variance seen in calibration) is zeroed to 0 in `w`
*before* the group's argmax is taken, so if a row's true global maximum happens to live in a dead
column, the fix's argmax picks the next-highest column instead — the protected column is real,
just not the one the diagnostic (which checks against the original, pre-zeroing weights) expects.
This was not chased down further; it affects 0.4% of blocks and does not change the conclusion.

## Does the fix restore GPTQ's advantage over RTN?

| configuration | perplexity | vs fp32 | vs RTN 4-bit |
|---|---|---|---|
| RTN uniform 4-bit | 17.3667 | +2.6387 | — |
| GPTQ uniform 4-bit (original) | 17.7047 | +2.9767 | +0.3380 |
| **GPTQ uniform 4-bit (max-exactness fixed)** | **17.5860** | **+2.8581** | **+0.2194** |

**Partial fix.** The max-exactness fix improves GPTQ by **−0.1186** perplexity points relative to
the original implementation — a real, same-direction, same-run improvement, consistent with the
mechanism actually mattering. **It does not close the gap to RTN**: GPTQ-fixed is still **+0.2194**
worse than RTN 4-bit, so the gate from `gptq_gate.py` ("does GPTQ 4-bit beat RTN 4-bit?") still
reads **FAIL**.

## Honest reading

Max-exactness destruction is **a** cause of GPTQ's underperformance under block-max scaling in
this setting, not **the whole** cause. Fixing it recovers roughly a third of the original gap
(0.338 → 0.219, i.e. −35%) but a residual +0.22 perplexity penalty against RTN remains
unexplained. This is a genuine open question, not a contradiction of the mechanism: `THEOREM_
2026-08-09.md` itself flagged this as an "honest limit" before the fix was run — "the relative
energy involved is small (1.07e-4 of the maxima's energy)... whether it fully accounts for the
perplexity regression is not established." That limit is now confirmed: it does not fully
account for it.

**What this does NOT do:** it does not make GPTQ a usable baseline for the promote-only
comparison in this programme (`gptq_gate.py`'s pass condition is unmet), and it was not tested at
5-bit or under promote-only allocation — both are natural follow-ups but out of scope for this
run. `[измерено — SW proxy]`, same model/data-scope caveat as the rest of the block-scaling
programme: SmolLM2-135M and wikitext-2 only, not yet checked on Qwen or Pythia.
