# The block axis is not closed, and the counterexample was published in 2023

> **Corrected 2026-08-12 — see `THE_SIXTEENTH_CODEWORD_2026-08-12.md`.** Two
> things below are wrong. NF4's **−6.50 %** was pooled over three families; over
> four it is **−4.11 %**, because on OPT-125M — never run at the time — **NF4
> loses to MXFP4 by +2.14 %** (p = 4.7e-10). And the margin is not the
> Gaussian-quantile shape at all: a symmetric 8-magnitude book spends one of its
> sixteen codewords on a second zero, and `NF4-sym`, the same construction with
> the extra value switched off, is a **tie** with MXFP4 (+0.46 %, p = 0.795 at
> n = 4 checkpoints; the window-pooled +0.33 %, p = 0.46 was restated
> 2026-08-12). The
> decomposition is exact to a residual of 0.00e+00. The conclusion that the block
> axis is not closed stands; the reason given for it does not.

`BLOCK_AXIS_CLOSED_2026-08-10.md` concludes: *no eight-level element format will
take the block axis from MXFP4.* Today that conclusion was attacked four times.
Three of the attacks were ours and two of those failed. The fourth was not an
attack at all — it was running a baseline nobody in this repository had ever run.

**NF4, the 4-bit NormalFloat from QLoRA (2023), beats MXFP4 in this harness by
6.50 % out of sample**, at strictly equal budget, fitted to nothing here.

| arm | b/elem | fitted on | SmolLM2 | Qwen | Pythia | pooled OOS |
|---|---:|---|---:|---:|---:|---:|
| MXFP4 (E2M1) | 4.250 | hand-designed | ruler | ruler | ruler | — |
| **NF4** | **4.250** | **an N(0,1) prior** | **−8.77 %** | **−2.26 %** | **−6.28 %** | **−6.50 %** |
| BOF4, our implementation of their method | 4.250 | SmolLM2 | −6.43 % | +0.86 % | +0.78 % | +0.81 % |
| Lloyd-Max | 4.250 | SmolLM2 | +4.45 % | +4.10 % | +11.23 % | +8.80 % |

NF4's pooled out-of-sample figure: **95 % CI [−7.30 %, −5.70 %], t = −15.60,
p = 2e-28, better in 95 of 100 windows.** It is out of sample on all three models
by construction — it was fitted to a Gaussian prior, not to any checkpoint.

All nine rulers reproduced before anything new was quoted, worst relative error
2.8e-06, and a second agent re-ran every configuration in a fresh process and got
the numbers digit for digit.

## So the conclusion is false, and it has been since before it was written

The sentence to withdraw is *"no eight-level element format will take the block
axis from MXFP4, because the best possible one does not."* Both halves fail. The
"best possible one" was the squared-error optimum, which is the wrong optimum
(`METRIC_DISAGREEMENT_2026-08-11.md`). And a format that takes the axis has been
sitting in `bitsandbytes` since 2023.

**Every "beats MXFP4 by X %" claim in this repository has to be read against
−6.50 %, not against zero.** That includes ours.

## Our own attempts, in that light

Three codebooks were fitted here today. Corrected pooling — over only the models
each arm never saw — gives:

| codebook | fitted against | pooled out-of-sample | verdict |
|---|---|---|---|
| KL-optimised, one model | SmolLM2 logits | +3.91 %, t = +7.11, p = 1.9e-10 | **loses** |
| nSSE-optimised, one model | SmolLM2 weight statistics | **+1.37 %**, t = +2.85, p = 0.0053, CI [+0.42, +2.34] | **loses** |
| **JOINT-KL, three models** | SmolLM2 + Qwen + Pythia logits | **−1.31 % on a held-out family**, t = −6.17, p = 3.1e-07 | **beats** |

**The joint fit is the first codebook in this line to beat MXFP4 on a family it
never saw with a confidence interval excluding zero** — OPT-125M, CI
[−1.73 %, −0.88 %], 33 of 40 windows, and −1.17 % again on a disjoint window set.
Its held-out margin is *larger and more significant* than its weakest in-sample
one (Qwen, −0.21 %, p = 0.61), which is not the shape of a fitted artefact.

Two of its six free magnitudes moved. Requiring one codebook to serve three
models spent about two effective degrees of freedom instead of six, and appears
to have been the regulariser the single-model fits lacked.

But −1.31 % against NF4's −6.50 % is the honest ranking. **We built, over a day,
something five times weaker than a 2023 baseline we had never measured.**

## Two of today's own records need correcting

**`BLOCK_AXIS_HOLDS_2026-08-11.md` overstated nSSE.** It recorded the
weight-statistics codebook as an out-of-sample *tie* that "degrades gracefully".
On a third unseen family, OPT-125M, it **loses** by +3.71 % (t = +12.56,
p = 2.8e-15, better in 1 of 40 windows). Pooled correctly over all three unseen
families it is +1.37 % worse than MXFP4, with a CI excluding zero. The graceful
reading held for two models and broke on the third. The "logit fits reverse,
weight fits degrade gracefully" contrast is weakened to "both lose, the logit fit
by more".

**The sensitivity scepticism was itself wrong.** A campaign proposed that the
optimised codebooks "earned their margins by moving far, not by moving well". A
matched-distance control refutes it: 15 random codebooks at nSSE's own 13.577 %
RMS distance give a mean of +20.98 %, only 1 of 15 beats MXFP4, none beats the KL
codebook, and nSSE's exact mirror at the same distance is +15.94 % against nSSE's
−5.24 %. nSSE ranks 14 of 15 among undirected draws at its own radius
(one-sided p ≈ 0.07). **Direction does matter**; the earlier claim extrapolated
an extreme order statistic from a 2 % radius across a surface it had itself shown
to be non-linear.

## What BOF4 does here, and what that suggests

BOF4 is the current MSE-optimal leader in the literature. Implemented from its
published method and fitted to SmolLM2's own weights, it is **indistinguishable
from MXFP4 out of sample** (+0.81 %, CI [−0.53, +2.16], p = 0.235). Refitting per
model does not rescue it: −6.43 % in-sample on SmolLM2, −0.18 % on Qwen, +4.01 %
on Pythia.

That is consistent with this repository's measured finding that squared error
points the wrong way — but it is *consistency*, not proof. Their published result
uses a different model, block size and a real-valued absmax scale, which by T39
has no headroom phase at all. BOF4-S beats MXFP4 here (−6.42 % with their
Gaussian artefact) but is **not at equal budget**: its signed block maximum needs
a sign bit E8M0 does not have, costing 4.28125 b/elem.

## The lesson, which is larger than the result

The strongest opponent was free, published, and one import away. Three sessions
of this repository's work went into beating a hardware format while the research
leader in the same class went unmeasured. A day of searching produced a codebook
five times weaker than an off-the-shelf baseline.

**Run the baselines before building the alternative.** Not after.

---

*Method reused from `block_tnf.py` by source split, never reimplemented. Every
codebook normalised to top = 1.0 so all sit at headroom phase φ = 0 (T38),
asserted in code. Block 32, E8M0, `lm_head` excluded, published window counts.
NF4's 16 levels are `bitsandbytes`'; BOF4 is our implementation of their
described EM method and is labelled as such, not as their artefact. A second
agent reproduced Campaign A's four models digit for digit in a fresh process and
supplied the corrected out-of-sample pooling used above.*
