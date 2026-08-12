# Re-measuring the block axis in our own code, and the bug that nearly produced a false contradiction

The perplexity and RMSE figures behind the stop-rule answer came from a workflow
whose scratch directory was later wiped. The numbers survive in the run journal,
but **a number whose only witness is a log is a number with no instrument behind
it**. So the RMSE half was re-measured here, in code written for the purpose,
against the weights themselves.

## The baseline reproduces digit-for-digit

| model | blocks | MXFP4 Algorithm 1 RMSE, workflow | re-measured here |
|---|---|---|---|
| smollm2 | 3,317,760 | 0.0225976709 | **0.0225976709** |
| qwen | 11,182,080 | 0.0023861225 | **0.0023861225** |

Ten significant figures, independently coded. The baseline is not in doubt.

The encoder arm reproduces too: **+3.50%** on smollm2 against the workflow's
+3.50%, and +2.81% on qwen against its +2.86% — the small difference being the
bracket width of the search, which is the subject of the next section.

## The bug, and why it matters more than the numbers

The first version of this script searched a bracket of **±2 ladder steps** around
the floor point. That is ±0.67 octave at $2^{k/3}$ and only **±0.25 octave** at
$2^{k/8}$ — a narrower search for the finer ladder, in the direction that
handicaps it.

It produced: step3 +14.91%, step8 **+12.99%** on smollm2 — that is, **the finer
ladder losing to the coarser one, reversing the ordering the paper prints.**

Had that been trusted, this campaign would have "discovered" a contradiction in
its own central result that was entirely an artefact of the instrument built to
check it. The bracket now spans the same octave range for every ladder.

**The general form: when you re-implement a measurement to verify it, the
re-implementation is a new instrument and needs its own audit.** A verification
that disagrees is not evidence the original was wrong until the verifier has been
checked as hard as the thing verified. This work has withdrawn thirteen claims,
and at least four of them were comparisons whose two sides were not the same
quantity; a badly-bracketed search is that same error wearing different clothes.

## Status

The corrected sweep is running. Whatever it returns, the file
`research/block/verify_block_rmse.py` is now in the repository, so the block-axis
RMSE claim has an instrument behind it that can be re-run rather than a log entry
that cannot.
