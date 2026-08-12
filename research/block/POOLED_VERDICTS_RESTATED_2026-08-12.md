# Eleven of fourteen verdicts were windows pretending to be checkpoints

`campaignB_stats.py`'s `row()` did this:

```python
d = np.concatenate([dvec(D, m, arm, ref) for m in models])
r = paired(d)
```

Four models × 35 windows, concatenated, handed to a paired t-test as 140
replicates. They are replicates of **the text**, not of the model family. A
comparison that wants to say something about a fifth checkpoint has n = 4, and
the section header said so out loud — *"POOLED OVER ALL FOUR MODELS"* — while
computing as if the four models were one.

This is the **sixth** instance of this error in this campaign and the first one
found in a script rather than in prose. The previous five were caught in
documents after the fact; this one was still executing.

## What changes

`row()` now takes n = models when more than one model is involved, each
contributing its own mean log-ratio, and keeps windows only for the single-model
rows, which are within-model claims entitled to them.

| arm | vs | window-pooled, n = 140 | model-level, n = 4 | |
|---|---|---|---|---|
| MX-asym-MID | MXFP4 | −2.21 %, p = 9.6e-26 **BEATS** | −2.08 % [−3.48, −0.67], p = 0.019 | **TIE** |
| MX-asym-MID2 | MXFP4 | −1.59 %, p = 6.7e-09 **BEATS** | −1.56 % [−5.58, +2.62], p = 0.314 | **TIE** |
| MX-asym-NEAR0 | MXFP4 | −4.99 %, p = 1.6e-44 **BEATS** | −4.76 % [−8.58, −0.78], p = 0.032 | **TIE** |
| MX-asym-MIDN | MXFP4 | −2.78 %, p = 7.7e-32 **BEATS** | −2.70 % [−5.24, −0.08], p = 0.046 | **TIE** |
| MX-asym-TOP | NF4 | +3.59 %, p = 4.8e-06 **loses** | +3.28 % [−7.83, +15.73], p = 0.433 | **TIE** |
| MX-asym-MID | NF4 | +1.98 %, p = 9.0e-06 **loses** | +1.87 % [−4.68, +8.87], p = 0.440 | **TIE** |
| MX-asym-MID2 | NF4 | +2.62 %, p = 5.5e-08 **loses** | +2.41 % [−4.86, +10.24], p = 0.379 | **TIE** |
| MX-asym-NEAR0 | NF4 | −0.92 %, p = 1.6e-02 **BEATS** | −0.92 % [−6.62, +5.13], p = 0.655 | **TIE** |
| MX-asym-MIDN | NF4 | +1.38 %, p = 5.2e-04 **loses** | +1.23 % [−4.52, +7.33], p = 0.553 | **TIE** |
| JK-asym-MID | JOINT-KL | −2.32 %, p = 1.9e-22 **BEATS** | −2.18 % [−4.74, +0.45], p = 0.078 | **TIE** |
| JK-asym-MID2 | JOINT-KL | −1.93 %, p = 1.1e-25 **BEATS** | −1.86 % [−3.77, +0.10], p = 0.057 | **TIE** |

**Eleven flips. One verdict survives**: `JK-asym-NEAR0` vs `JOINT-KL`, −2.42 %
[−3.56, −1.26], p = 0.007 — and the script's own tag already says `3/4
in-sample`, so it is not a claim about a new checkpoint either.

**The point estimates barely move.** −4.99 % becomes −4.76 %; −2.21 % becomes
−2.08 %. Nothing about the codebooks changed. What changed is that the intervals
grew by roughly the square root of thirty-five, and every one of them now
contains zero.

**The correction is symmetric, which is how you know it is not motivated.** Four
rows moved *toward* our codebooks (a "loses to NF4" became a tie) and seven moved
*away* (a "BEATS MXFP4" became a tie). An error that only ever flattered us would
be a different kind of finding.

## The Bonferroni family was also wrong, and it does not matter

The section applied `nk = 4`, "Bonferroni ×4 over the placements", to a family
containing `MX-asym-TOP` — which is a clipping arm and not a placement
(`CLIPPING_ARM_CORRECTION_2026-08-12.md`). Three placements, not four. The
reclassification was made on structural grounds a day before anyone computed
which way it moved a verdict, which is the only reason it can be applied at all
without being a p-hack.

At the window level it mattered: `MX-asym-NEAR0` vs NF4 sat at p = 1.6e-02, so
`×4 = 0.065` was a TIE and `×3 = 0.048` a BEATS — a published verdict turning on
the third decimal of a multiplicity correction. **At the model level it changes
nothing**: p = 0.655, and no family size rescues that. The two defects were found
independently and the larger one dissolves the smaller.

## What survives

The per-model rows, which were always within-model claims and always kept their
windows. `MX-asym-NEAR0` still beats MXFP4 in **140 of 140 windows across four
models**, and that is a statement about text on a given checkpoint that no
pooling error inflates. What was never supported is the leap from there to a
checkpoint nobody measured.

Also unchanged: T40's decomposition. Restated at the model level in
`THE_SIXTEENTH_CODEWORD`, `(+0.464 %) × (−4.324 %) = −3.880 %` with residual
`6.94e-18` — the composition is arithmetic and holds at either level. What that
restatement withdraws is the *strength* of the surrounding margins: at four
checkpoints, "NF4 beats MXFP4" is a tie (−3.88 %, p = 0.208), and NF4's win is a
per-model result on 3 of 4 checkpoints.

## Why this one took six tries

The first five were caught by reading documents. This one was in a helper called
by every section of the script, named `row`, three lines long, and its one
statistical decision was made by `np.concatenate` — a function whose job is to
join arrays, not to declare a replicate unit. The declaration was implicit in a
call to a shape-changing utility.

**The rule this suggests:** the replicate unit is a claim, so it should be
written where claims are written, not implied by an array operation. `row()` now
states it in its docstring and branches on it explicitly, so the next reader sees
the decision instead of inferring it from a reshape.

---

*Re-analysis only — no model was re-run. Every per-window NLL is the one already
on disk from campaign B. Four models, wikitext-2, block 32, E8M0, `lm_head`
excluded.*
