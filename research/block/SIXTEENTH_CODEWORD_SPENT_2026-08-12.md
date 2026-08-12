# Spending the sixteenth codeword: a decisive win over MXFP4, and a tie with NF4

T40 established that a symmetric 8-magnitude book forfeits one of its sixteen
codewords on a second zero, and that the forfeit — not the shape of NF4's
quantile curve — is where NF4's margin comes from. This spends it.

> **Attribution, 2026-08-12.** The structural observation — that a
> symmetric few-bit alphabet wastes a representable value — is published:
> *Signed Symmetric Quantization for Few-Bit Integers*,
> [arXiv:2607.08779](https://arxiv.org/abs/2607.08779), from the integer
> side (int4's `−8 … +7` misallocated by symmetric scaling). What is ours
> is narrower and stated in `PRIOR_ART_SIXTEENTH_CODEWORD_2026-08-12.md`:
> the exact decomposition showing the codeword is the *entire* NF4 margin,
> the block-float setting under E8M0, the non-monotone placement, and the
> drop-in E2M1 variant.

## The construction, and it is not fitted to anything

**MX-asym-NEAR0** is E2M1's exact magnitudes plus **one extra positive level at
1/24**, half the smallest magnitude. In units of 1/24:

    positive  {1, 2, 4, 6, 8, 12, 16, 24}
    negative  {2, 4, 6, 8, 12, 16, 24}
    zero
    → 8 + 7 + 1 = 16 codewords

Integers throughout, so it is **the same 4-bit lookup as MXFP4 with a different
table** — no new hardware, no fitted parameters. The only data-driven decision
was *which of four placements*, made on SmolLM2 alone.

## What it beats, at the model level

| reference | per-model result | verdict |
|---|---|---|
| **MXFP4** | −4.99 % pooled, **140 of 140 windows**, 4 models of 4 | **beats** |
| **NF4-sym** | 4 models of 4 | **beats** |
| **JOINT-KL** | 4 models of 4 | **beats** |
| Lloyd-Max | −10.87 %, 100/100 held-out windows | beats |
| **NF4** | **+4.14 / −0.91 / −1.92 / −4.77 %** | **TIE** |

Against MXFP4 this is the largest and cleanest effect measured in this line: it
wins on **every window of every model**, including the three that took no part in
choosing the placement.

## The claim that did not survive, and why it is worth spelling out

The first draft of this result read *"an asymmetric variant beats NF4 out of
sample"*, on a held-out figure of **−2.87 %, p = 1.7e-13**. That statistic pools
**windows**. Windows are replicates of the *text*, not of the *model family*, and
the question "does this beat NF4 across models" has n = 3, not n = 100.

Pooled at the model level: **−2.55 % [−7.43, +2.59], p = 0.163** on the held-out
three, and −0.92 % [−6.62, +5.13], p = 0.655 across all four. **A tie.**

This repository has the precedent in its own files: `KL_CODEBOOK_WITHDRAWN`
records a window-pooled `t = −12.51` that certified an overfit. That is the third
time this campaign a window-pooled p-value has asserted something model-level
pooling does not support.

**And a leave-one-out rotation of the selection protocol settles it.** Choosing
the placement on each model in turn:

| placement chosen on | winner picked | result vs NF4 |
|---|---|---|
| SmolLM2 | NEAR0 | −2.87 % |
| Qwen | NEAR0 | −0.92 %, tie |
| OPT | NEAR0 | +0.67 %, tie |
| **Pythia** | **TOP** | **+5.97 %, and +2.55 % vs MXFP4 — the protocol loses** |

**One rotation of four gives the headline.** The NF4 comparison is not a property
of the codebook; it is a property of which model happened to be used to pick the
placement. The MXFP4 comparison is unaffected — NEAR0, MID, MID2 and MIDN all
beat MXFP4 regardless of which model selects.

## T40 confirmed constructively

Spending the codeword on E2M1's own shape recovers **121.9 %** of the
NF4-minus-MXFP4 gap over four models. The quantile curve was never the point.

## The control that carries the argument

Two **symmetric** books were built carrying the identical 1/24 level, but paying
for it by dropping an existing magnitude instead of spending the sixteenth
codeword. Both lose badly: **+4.12 %** and **+29.44 %** against MXFP4, better in
**0 of 140** windows against MX-asym-NEAR0.

So the win is not "a level near zero". It is **being able to add one without
giving anything up**. The codeword is doing the work.

**Mechanism**, on SmolLM2's 106.2 M weights: MXFP4's zero bin is its single
most-populated codeword at **11.79 %** of all elements. Adding +1/24 splits it —
zero falls to 8.86 % and the new level captures **5.83 %**, making it the sixth
most-used codeword of sixteen. It earns its place immediately.

## Placement is the whole question, and it is not monotone

| placement | vs MXFP4, pooled 4 models | windows |
|---|---:|---:|
| **NEAR0** (extra level near zero) | **−4.99 %** | 140/140 |
| MIDN (mirror control, negative side) | −2.78 % | 134/140 |
| MID (coarsest interior gap) | −2.21 % | 127/140 |
| MID2 (second-coarsest) | −1.59 % | 89/140 |
| TOP (beyond the top magnitude) | −0.67 % | 72/140, **tie** |

**TOP is a trap.** Extending the positive ladder forces a renormalisation that
clips the negative extreme to −0.75: reach bought on one side, paid for by
clipping on the other. It wins on Pythia (−8.27 %) and loses on SmolLM2 (+4.68 %)
and OPT (+2.33 %). Had one placement been guessed instead of four enumerated, the
conclusion could easily have been that the codeword is worthless.

**MIDN is not a control, it is a candidate.** It costs the same sixteen codewords
and is the *best* MX-asym arm on the selection model (20.8333 against NEAR0's
20.8440). The placement choice between them is inside the noise the rotation
above exposes.

## The instrument, which both auditors rebuilt rather than re-ran

An asymmetric book cannot go through `block_tnf.quant`, which applies a sign to a
magnitude list, so a signed quantiser was written and had to be proved equivalent.
Both auditors built their own adversarial tensors — rows containing *every*
decision boundary of every book on both signs, block max pinned so `E8M0` gives
`s = 1` and the boundaries survive the division — and got **0.000e+00** on all six
symmetric books. One went further and checked **indices** rather than values
against a brute-force nearest-level reference on all ten asymmetric books:
**0 differing indices out of 44,800 per book**. A naive signed bucketize differs
by up to 3.3e-01, so the test is not vacuous, and 189,406 weights in SmolLM2 land
exactly on an MXFP4 boundary — the tie rule is load-bearing, not hypothetical.

## What this is

A **deployable** improvement to MXFP4 at identical cost: same 4-bit index, same
E8M0 scale, same 4.250 bits per element, an integer lookup table, nothing fitted.
It beats the deployed format on every window of every model tested.

It is **not** a win over NF4, and the earlier draft saying so was wrong.

---

*Four models, wikitext-2, block 32, E8M0, `lm_head` excluded, published window
counts. Every book normalised to `max|level| = 1.0` — checked on **both** tails
for the asymmetric ones — so all sit at headroom phase φ = 0 (T38). Model-level
statistics are quoted for cross-model claims and window-level only for
within-model ones.*
