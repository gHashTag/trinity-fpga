# The alignment law is dead, and the OCP spec is the best worst-case choice

**Status: u\* is a measured per-model quantity, not a derivable constant. The pre-registered
leave-one-out test fails. This directly narrows the spine of `tnf_paper_v2.tex`, which was rebuilt
around alignment hours earlier.**

## Measured, five families

2^k base, 4-bit scale field, block 32, E2M1-with-subnormal, ties-to-even, weight-only, 40 windows:

| model | store | fp32 | u\* | ppl(u\*) | ppl(OCP) | gain | tie floor | gain/floor |
|---|---|---|---|---|---|---|---|---|
| smollm2 | bf16 | 14.4874 | 0.35 | 20.6950 | 23.5224 | +2.8274 | 0.2398 | 11.8× |
| qwen | bf16 | 12.2277 | 0.30 | 14.5532 | 15.0632 | +0.5100 | 0.0932 | 5.5× |
| **pythia** | fp16 | 25.9561 | **0.40** | 44.5762 | 44.8219 | **+0.2457** | **0.5358** | **0.5×** |
| **opt** | fp16 | 27.5678 | **0.25** | 31.0971 | 32.6597 | +1.5626 | 0.0667 | 23.4× |
| **gpt2** | fp32 | 31.3254 | **0.25** | 35.6968 | 36.3248 | +0.6280 | 0.0003 | 2093× |

**u\* spans 0.25–0.40 — three grid steps, six times the pre-registered stability threshold of one.
The claimed u\* = 0.30–0.35 is reproduced by none of the three new families:** two land at 0.25,
one at 0.40.

## The pre-registered test, and it fails

Leave-one-out: take `u` from the other four families (mean 0.287, grid 0.30) and apply it to the
held-out one.

    ties=even  u=0.30  46.0385  vs OCP 44.8216   transfer costs +1.2169
    ties=zero  u=0.30  46.1012  vs OCP 44.8216   transfer costs +1.2796
    ties=away  u=0.30  45.7041  vs OCP 44.2878   transfer costs +1.4163

**Adopting the law makes Pythia 1.22–1.42 perplexity WORSE than doing nothing and shipping the
spec** — 2.3× its own nuisance floor, under every rounding convention. This is the same failure
mode, on the third model, at the budget it was invented for, that killed the previous fitted
constant (λ). The campaign has now produced this exact shape twice.

## The finding that turns it around

**No single `u` beats OCP on all four measured curves.** At every `u ≤ 0.35` Pythia loses to OCP
(ratio ≥ 1.0053); at `u = 0.40` both OPT (1.0020) and GPT-2 (1.0016) lose.

> **The best worst-case alignment over the common grid is u = 0.415 — which IS the OCP spec.**

On Pythia the tuned gain is not even worth having: **+0.2452 against a tie-rule spread of 0.5358**
at the same point. Concretely, **OCP with ties-away (44.2878) beats the tuned u\*=0.40 with
ties-even (44.5764) by 0.2886.** For Pythia the spec alignment is already essentially optimal and
the *rounding convention* is the bigger lever.

## Reparameterising does not rescue it

The obvious repair — "the law is not a fixed `u` but a fixed clamp fraction" — fails too. Observed
clamp fraction at each model's own u\*: 40.57 % (pythia), 22.94 % (opt), 24.02 % (gpt2) — a
**17.6-point spread against u's own 15-point spread**. Not tighter, so "clamp a fixed fraction of
blocks" is not the hidden law either.

## What survives, stated at its real strength

Retuning `c` gives a **non-negative gain on 5 of 5 families**, but:

- the gain ranges **0.25 to 2.83 perplexity — a factor of 11**;
- it must be **measured per checkpoint**; nothing predicts it;
- on **1 of 5** it falls inside the model's own nuisance floor;
- and **no fixed value of it beats the specification across families**.

So the honest claim is: *alignment is a free per-model tuning knob worth up to 2.83 perplexity at
identical bit cost, which the specification fixes and which nobody varies — but the specification's
own choice is the best single value across the five families measured.*

That is a smaller claim than "the alignment is where the value is", and it partially **vindicates
OCP** rather than faulting it.

## Consequence for the paper

`tnf_paper_v2.tex` was rebuilt hours ago with alignment as its spine, titled *Base, Alignment,
Width*. The alignment section must now be narrowed from a law to a per-model tuning result, and the
finding that **OCP's constant is the best worst-case choice** must be stated — it is the more
interesting result and it is not what the rebuild claims.

The three-knob taxonomy survives intact; what changes is the *value* attached to the alignment
knob: not "2.83 for everyone" but "0.25–2.83, per model, unpredictable, and the spec is the best
fixed compromise".

## Two process notes from the run, both disclosed by the agent

1. **GPT-2 was not present** despite the task declaring it provisioned. The agent searched
   exhaustively, then downloaded it and **verified sha256 against the digest published by the HF
   API** (`248dfc39…`, 548,105,171 bytes) — explicitly because this campaign's own catalogue
   records a resumed download that spliced two byte streams and **passed a size check**. The first
   attempt did die mid-stream at 364 MB. The agent flagged the download as an action it would
   normally confirm with the owner first and had no channel to ask. **Recorded for review.**
2. The stated venv path did not exist; the agent used a different Python and said so rather than
   silently substituting.
