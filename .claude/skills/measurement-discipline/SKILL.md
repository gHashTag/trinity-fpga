---
name: measurement-discipline
description: How to make a quantisation/format measurement that survives its own audit. Self-test gates, competitor implementation from spec, confound control, provenance search, and the failure catalogue from the 2026-08 campaign. Use before writing any harness that will produce a number someone quotes.
---

# Measurement discipline

Distilled from a campaign that produced ~30 numbers and **withdrew 22 of its own claims**. Every
rule below is a specific failure that happened, not a principle someone liked.

---

## 1. A harness without self-tests produces mush, confidently

Two harnesses were written in one day. One carried 21 self-tests that **abort before any number
prints**; the other carried none. The one without printed `phi = 39.5555` against `2^k = 23.5380`
— sixteen points the wrong way — and reported the **same value under three different tie rules**,
which is impossible if the switch does anything. Two bugs:

* the tie switch was a no-op (`torch.bucketize(right=False)` already places a boundary value in
  the lower bin, so the `is_tie` branch never fired);
* the scale pointed the wrong way (`floor(log_phi(amax/6))` put `amax/s` in [6.85, 9.55], above
  `max_norm = 6`, so **every block maximum clamped**).

**Mandatory gates, run before the first number:**

```
1. baseline reproduces a known value                 (fp32 ppl == the number everyone else got)
2. every branch of every switch produces a DIFFERENT result on a hand-computed case
3. the derived quantity's RANGE is PRINTED, not assumed  (amax/s must land where you claim)
4. a NEGATIVE CONTROL reproduces a known-broken config   (the bug you already found)
5. a second, independent implementation agrees BITWISE on real data
```

Gate 3 is the one people skip and the one that catches scale-direction errors. Gate 4 is what
turns a fixed bug into a permanent tripwire.

## 2. Implement the competitor from its specification, never from memory

**Five competitor bugs in one campaign, all flattering us:**

| # | format | error | cost |
|---|---|---|---|
| 1 | MX shared scale | ceiling instead of `floor(log2 max) − emax` | overstated MXFP4's cost |
| 2 | **E2M1** | **missing its subnormal** — 7 magnitudes not 8 | **39 % of MXFP4's apparent error** |
| 3 | NF4 | our symmetric reconstruction, not the real 16-value table | beat a straw man |
| 4 | E4M3 | reserved NaN encoding ignored — max 480 not 448 | every UE4M3 row slightly wrong |
| 5 | E5M2 | reserved exponent ignored — 114688 not 57344 | — |

Bug 2 alone accounted for essentially the entire advantage claimed for several cycles. **Every
table was internally consistent throughout; consistency detected none of them.**

**Practice:** one `competitors.py` holding every reference format with a source citation and an
`assert` against a **published constant**, checked at import. It caught bugs 4 and 5 on its first
run. A format failing its check must stop the import, not be handed out.

```python
FP4_E2M1_MAGS = _mags(2, 1, emax_expected=2, maxnorm_expected=6.0)   # asserts at import
assert not np.allclose(NF4, -NF4[::-1]), "NF4 is ASYMMETRIC; a symmetric table is not NF4"
```

## 3. Control the confound, or you are measuring the confound

The campaign's central claim — "our scale ladder strictly dominates the standard" — was **the
alignment constant, not the ladder**. A geometric scale has two knobs,
`s = g^floor(log_g(amax/c))`: the base `g` (what we varied) and the alignment `c` (what the spec
fixes for one arm and leaves free for the other). Every comparison gave our arm its natural
alignment and the competitor the spec's. Reparameterised so each base sits at **its own best
alignment**, the competitor wins on both models.

**Before claiming A beats B: list every parameter that differs between the arms.** If a parameter
is free in one arm and fixed in the other, you are comparing tuning effort, not designs. Tune both
or fix both.

The replacement finding was larger than the original claim: retuning that one constant on the
plain competitor bought **2.83 perplexity at identical bit cost** — more than the ladder question
ever offered.

## 3b. Flat optima: a constant fitted on two checkpoints will not transfer. Twice now.

**This happened twice in one campaign, with the same shape, and the second time was after the
lesson had supposedly been learned.**

| # | the constant | fitted on | killed by | how |
|---|---|---|---|---|
| 1 | `lambda` in a two-term ladder criterion | SmolLM2, Qwen — 6 binary outcomes | Pythia | predicted the wrong ladder at exactly the budget lambda was invented to fix |
| 2 | `u*` = scale alignment | SmolLM2, Qwen — 2 optima | Pythia, OPT, GPT-2 | u\* spans 0.25–0.40 across five families; leave-one-out makes Pythia **1.22–1.42 ppl worse than shipping the spec** |

**The mechanism is the problem's, not the fitter's: 4-bit block quantisation has FLAT optima.**
The u-curve moves by ~0.3 perplexity across `u` in [0.20, 0.35] on one model and by 2.8 across the
whole range — so a grid search finds a confident-looking minimum whose location is set by noise
and whose transfer is worthless. Any parameter tuned on a pair of checkpoints inherits that.

**Practice:**

1. **Pre-register a stability threshold before measuring.** "u\* is a law if it varies by at most
   one grid step across families." Then the answer is binary and cannot be rationalised. Ours came
   back at six times the threshold.
2. **Leave-one-out is the only test that counts.** Take the constant from the other N−1 and apply
   it to the held-out model. If it does worse than *doing nothing*, the constant is not a law —
   and "doing nothing" means the published specification, not your own previous best.
3. **Compare the gain to the model's own nuisance floor, per model.** Ours ranged 0.5× (inside the
   noise) to 2093× across five checkpoints. A gain that is 11× on one model and 0.5× on another is
   not one phenomenon.
4. **Check whether the SPECIFICATION is the best worst-case choice.** We tuned a constant the spec
   fixes, beat it on 4 of 5 models, and then found that **no single value of ours beat the spec on
   all of them — and the best minimax value over the common grid was the spec's own.** That
   possibility should be tested first, not last: it is cheap and it is the outcome that most
   changes the conclusion.
5. **Try the obvious reparameterisation, and believe it when it fails.** "Not a fixed u but a fixed
   clamp fraction" was the natural repair; the clamp fraction spread 17.6 points against u's 15.
   Wider, not tighter. That closes the question instead of leaving it open.

**The tell, in advance:** if your parameter's curve is flat near the optimum *relative to the
spread between models*, you are fitting the gap between checkpoints, not a property of the method.
Measure the curvature before you claim the location.

## 4. Know your nuisance floor before you claim a margin

A claimed margin of **0.0935** sat next to a tie-rule effect of **0.0932** — and the tie rule
perturbed **only the comparator**. Mechanism: a power-of-two scale keeps binary float32 weights
exactly on the codebook's binary midpoint grid (1.08–1.34 % of elements are exact ties), while an
irrational scale essentially never lands on one (11 of 106 M). So one arm was tie-invariant and
the other moved by the size of the whole claim.

**Measure the nuisance first**: switch the rounding rule, the seed, the thread count, the window
count — and only claim differences larger than the spread you find. Here, thread count 1/2/4/8 was
bitwise identical (PyTorch CPU GEMM parallelises over output tiles, not the reduction axis), while
the tie rule was not.

## 5. A failed search is not a finding

I searched `fpga/phiscale/` for filenames containing `route`/`timing`/`report`, found none, and
**publicly withdrew a correct table** as unsourced. The evidence was 298 `.log` files in the
directory I was standing in. A later search for the decoder table failed the same way — the logs
were in `fpga/tnet/` with prefix `ws_`, not `cs_`.

**Before asserting a measurement does not exist:** `ls *.log`, `find`, and **grep by VALUE**, not
by guessed filename. `grep -rl '974\.66' .` finds it regardless of what the file is called.

## 6. Report the sample as a sample

"Max span 37 φ-steps → 40 bits" came from `sorted(lin)[:10]` — **ten of 210 tensors**, presented
as the model's. The full scan gave 43 steps and 46 bits. The caveat said "this model"; the numbers
were this model's *first ten tensors'*.

**Print the denominator next to every aggregate.** `over 210 tensors` costs nothing and makes the
error impossible.

## 7. Filters that show only success make failure look like silence

Three background runs produced **empty output files**, indistinguishable from "still running":
`sed -n '/PATTERN/,$p'` prints nothing when the pattern never appears; a module without an
`if __name__ == "__main__":` guard re-ran six full sweeps on import and then died; output
buffering hid everything until exit.

**Filter background output with `tail -N`** — it always shows something. **Guard every experiment**
behind `__main__`, or any future import becomes a silent, expensive failure.

Same class as: a truncated download whose **size check passed** (`curl -C -` spliced two byte
streams; only the parser caught it), and a `done 1` exit code reported after garbage arguments.
**A channel that reports only the happy path cannot distinguish failure from quiet.**

## 7b. Gate the setup, or the harness reports its own breakage as data

A stability run of a browser check produced this, and it was nearly written up as
a finding:

    run 1: exit=1  0s  popup-lines=0
    run 2: exit=1  0s  popup-lines=0
    ... five of five

That is not a flaky check. The check never ran: `dist/` and `node_modules` were
absent, so it exited immediately with "nothing to open". The setup step had
failed and the harness carried on measuring nothing, five times, and formatted
the result as a table.

Two tells were in the output and both were ignored: **every run took 0 seconds**,
and the setup's own `&& echo "built"` line was **missing from the log**. A
measurement that completes in no time did not happen.

- **Assert the preconditions and refuse to run.** Not "log a warning" — exit.
  The rewrite gates on `node_modules` existing and `dist/index.html` existing, and
  prints `SETUP FAILED: … — not measuring` instead of a table of zeros.
- **Never `>/dev/null` a setup step.** The build output was discarded, so the one
  place the real error appeared was thrown away before anyone could read it.
- **A borrowed dependency tree is a dependency.** The node_modules was a symlink
  into another worktree that had since been deleted. Symlinking to save four
  minutes of `npm ci` cost an entire measurement round.

The general form: **a harness must distinguish "the thing under test failed" from
"the harness failed", and when it cannot tell, it must say so rather than pick
one.** Five identical failures with no output is the signature of the second, and
it looks exactly like a decisive result for the first.

## 8. Blast radius is bounded by imports — check it before re-running anything

When a competitor bug is found, `grep -l` for the competitor's symbols. Scripts that never
reference it **cannot** be affected. This took seconds and exempted four load-bearing results from
re-measurement.

## 9. Adversarial verification finds what self-consistency cannot

Every theorem in the campaign was handed to a second agent instructed to **refute it, defaulting
to refuted when uncertain**. It worked:

* a "proved" width bound was shown **not necessary** — the datapath is Z-linear and reduction mod
  2^W is a ring homomorphism, so overflow self-cancels and the accumulator sizes to the *answer*;
  12/12 cases ran exact below the "necessary" width, 6 with genuine register overflow;
* an "optimal ratio law" was refuted on five counts, including that its central validation was
  **circular** (validated against the same approximation it derived) and that its own headline
  sub-claim failed in 20 of 25 of its own data cells.

**A theorem nobody tried to kill is a conjecture with good manners.**

## 10. Novelty is a literature question, not a memory question

Three claims died to searches that should have run first:

* the 4-bit scale-field result is **published** (Chhugani et al., arXiv 2603.08713) on larger
  models, with the truncation explicitly proposed;
* non-power-of-two logarithmic ladders for LLM weights are **published** (Log_b Quant,
  arXiv 2607.01127) and for CNNs are **8–10 years old** (Miyashita arXiv 1603.01025; Vogel
  ICCAD 2018);
* "every fixed-field format clocks faster than every tapered one" is **refuted** by published data
  — bounded-taper decoders (takum arXiv 2408.10594, b-posit arXiv 2603.01615) beat IEEE.

**Fetch the paper and read the sentence.** A search snippet is not a citation, and two
confabulations in this campaign came from trusting one.

---

## The stance that made the rest work

Withdrawals are the asset. A document that records "we claimed X, here is the measurement that
killed it, here is what replaced it" is worth more than one that never claimed X — because the
reader can see the instrument, and because the replacement is usually bigger. The alignment
finding exists **only** because the φ claim was audited to death.
