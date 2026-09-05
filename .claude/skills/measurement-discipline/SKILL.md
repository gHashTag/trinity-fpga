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
   all of them.** That possibility should be tested first, not last: it is cheap and it is the
   outcome that most changes the conclusion.

   **A second claim sat here and is withdrawn: "the best minimax value over the common grid was
   the spec's own."** True only of the candidate set it was computed on — and that set had **two
   elements**. SmolLM2 was swept on an 8-point grid and the others on a 13-point grid, so the
   intersection is `{0.0000, 0.4150}`: u = 0 (never clamp, trivially poor) and OCP itself. The spec
   won a contest against one alternative. Recomputed on the 13-point grid the three common-grid
   models were actually swept on, with excess relative to each model's own optimum:

   | | u | worst-case excess | binding model |
   |---|---|---|---|
   | minimax | **0.2042** (c = 3.456) | **1.488 %** | Pythia |
   | OCP / MX spec | 0.41504 (c = 4) | 5.025 % | OPT |

   **The spec costs 3.4× the worst-case degradation of the minimax constant at identical bit
   cost** — the scale field is unchanged, only `c` moves. Both criteria are right about different
   things: nothing on the grid beats OCP on all three at once, so OCP is Pareto-undominated, while
   the minimax constant loses to it on Pythia (1.488 % vs 0.551 %). **"No value beats the spec
   everywhere" and "the spec is the best worst case" are different claims that were stated as
   one.** n = 3; SmolLM2 and Qwen are not on this grid and either could move the point.

   **When you report an optimum over a candidate set, report the SIZE of the candidate set.** A
   minimax over two points is a coin toss in the vocabulary of an optimisation. This is §4c again:
   pooling arms swept on different grids silently shrank the candidate set to the intersection, and
   nothing printed the intersection.
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

### 4b. The tie floor is not set by the stored dtype. That law is withdrawn.

The campaign recorded that each checkpoint's tie-rule floor tracks its **release dtype** as `2^−m`
in the stored mantissa width, citing a predicted 8× against a measured 7.96×. Re-read from the raw
files, the law does not survive its own data:

| model | dtype | mantissa bits | u values probed | floor (max spread) |
|---|---|---|---|---|
| GPT-2 | fp32 | 23 | 4 | 0.000309 |
| Pythia | fp16 | 10 | 3 | 0.535782 |
| OPT | fp16 | 10 | 2 | 0.066723 |
| SmolLM2 | bf16 | 7 | — | 0.2398 (source not located) |
| Qwen | bf16 | 7 | — | 0.0932 (docstring, not a stored run) |

**Pythia and OPT are the same dtype and their floors differ by 8.03×**, where the law predicts
1.00. That 8.03 is almost certainly the "8× predicted, 7.96 measured" the law was recorded on — a
ratio between two models the law says should be identical, read as confirmation of it. The two
bf16 models differ by 2.57×, also predicted 1.00. Cross-dtype the ratios go the wrong way:
Pythia/SmolLM2 measures 2.23 where the law predicts 0.12.

What survives: **fp32 really is ~1000× below the rest**, which is the only part the mantissa-width
argument ever needed to explain and the only part it does. Within a dtype the floor varies by 8×,
so **the dtype sets an order of magnitude and nothing finer.**

Three provenance problems found in the same re-read, all worth checking for in any floor table:

* **The floors are a `max` over probed points, and the probe counts differ** — 4, 3, 2. A maximum
  grows with sample count, so the numbers are not commensurable as a cross-model quantity. They
  are defensible *per model at its own optimum*, which is how `depth/floor` used them, and not
  defensible as evidence for a law relating models.
* **A re-run overwrote a stored result with fewer rows than it had.** `align_u_tiefloor_pythia.json`
  holds one row; the two logs beside it show three (u = 0.30, 0.40, 0.41504, spreads 0.3972,
  0.5358, 0.5338). Everything downstream read the JSON. **Write results to a name that includes
  what varied**, or a narrower re-run silently truncates the record.
* **Two of the five floors have no stored run.** Qwen's 0.0932 is named in two script docstrings as
  a measured tie effect; SmolLM2's 0.2398 appears only as a hardcoded constant in scripts that
  consume it. Searched by content across the whole tree — the values, the filenames, and the JSON
  key — not by guessing a filename (§5). Not located is not the same as does not exist, but a
  number used as a denominator in a published table needs a file.

### 4c. A "distance to the nearest other sample" is a measurement of YOUR GRID

I scored four optima by `depth` = perplexity gap from the minimum **to the next-best point on the
sweep grid**, tabulated `depth/floor`, and published a verdict: *two of four optima are shallower
than their own noise and are not identified.* Every number in that table was real. The verdict was
an artefact.

`depth` is the gap to whatever sample happened to sit next to the minimum, so it scales with the
**grid spacing there** — a quantity I chose, not one the models have.

| model | grid | points | median Δu | Δu at the minimum | `depth` |
|---|---|---|---|---|---|
| SmolLM2 | [0, 0.90] | 8 | 0.1255 | −0.160 / +0.074 | 0.5104 |
| GPT-2 | [0, 0.55] | 13 | 0.0500 | ±0.050 | 0.5127 |
| Pythia | [0, 0.55] | 13 | 0.0500 | −0.050 / **+0.015** | 0.2457 |
| OPT | [0, 0.55] | 13 | 0.0500 | ±0.050 | 0.0087 |

Pythia's minimum was scored against a neighbour **3.3× closer in u** than GPT-2's — and for a
locally quadratic minimum the gap goes as Δu², so that is an order of magnitude of apparent depth
before the model contributes anything. And **SmolLM2 was swept on a different grid entirely**, yet
sat in the same table as if the numbers were commensurable. Ranking those four models by `depth`
ranked their grids.

**The correction, and the reversal.** The grid-free statements are the local curvature
`d²ppl/du²` and the interval where the *interpolated* curve stays within the floor of its minimum:

| model | `depth` order | curvature | curvature order | interval at the floor |
|---|---|---|---|---|
| GPT-2 | 1st (0.5127) | 437 | 2nd | [0.250, 0.250] |
| SmolLM2 | 2nd (0.5104) | 348 | 3rd | [0.266, 0.347] |
| Pythia | 3rd (0.2457) | **800** | **1st** | [0.347, 0.433] |
| OPT | 4th (0.0087) | 128 | 4th | [0.148, 0.261] |

Pythia moves from third-shallowest to **sharpest**; Spearman between the orderings is +0.40. Under
the corrected statistic **all four optima are narrow and their intervals have an empty
intersection**, four of six pairs outright disjoint — the opposite of the published verdict, and a
*stronger* refutation of a universal alignment constant: not "the curves are flat so u\* wanders",
but "each u\* is pinned and they are mutually incompatible."

**Rules that follow.**

1. **Never compare a nearest-neighbour gap across arms swept on different grids.**
2. **Print the grid alongside the argmin** — range, point count, and the spacing *at the minimum*.
   Had that column existed, the fault was visible without any new measurement.
3. **Prefer statistics that survive re-gridding**: curvature, an interpolated level-crossing
   interval, a fitted width. Each would have given the right ordering from the same data.
4. **Sweep every arm on the same grid, or say loudly that you did not.**
5. **A statistic can be arithmetically correct and still answer the wrong question.** Self-tests
   guard the harness computing the number; they say nothing about whether the number means what
   the conclusion needs. That check is separate and has to be done by hand.

### 4d. Paired arms need a paired floor. Common-mode noise cancels.

Having corrected the statistic, I asked how far the new conclusion was from collapsing: inflate
every floor by a factor `k` until the two furthest-apart models' intervals touch. **k = 5.** Not
500 — five. So I measured the missing nuisance instead of caveating it: the same u-sweep on three
disjoint folds of the corpus.

    GPT-2   fold 0: u* = 0.2500  ppl* = 35.6968
            fold 1: u* = 0.2500  ppl* = 30.7917
            fold 2: u* = 0.2500  ppl* = 37.2651

**The level moves 6.5 ppl between folds. The argmin does not move at all.**

| noise | what it is | median | vs GPT-2's tie floor |
|---|---|---|---|
| marginal | spread of the *level* across folds at fixed u | 6.7010 ppl | 22,337× |
| **differential** | spread of the *shape*, ppl(u) − ppl(u\*) | **0.2471 ppl** | 824× |

A harder fold lifts the whole curve and leaves its shape alone, because **every u is evaluated on
the same tokens with the same model — the arms are paired.** Inflating a floor as an absolute
offset models the noise as if each arm had its own independent sample. That is what `k` did, and
it is why `k = 5` looked alarming: it was 27× too pessimistic.

At the differential floor GPT-2's interval stops being degenerate — [0.2266, 0.2770] instead of a
grid-limited [0.250, 0.250] — and is **still disjoint from Pythia's [0.347, 0.433] by 0.070.** The
tie floor understated the correct noise by 824× and the conclusion survived, because an interval
widens as the **square root** of the floor.

- **When arms share a sample, the floor is the paired difference, not the marginal spread.**
- **After correcting an instrument, do not bank the new conclusion** — compute how large the
  remaining unmeasured nuisance would have to be to overturn it. If that factor is small, you have
  a hypothesis and a next measurement, not a result. Here it was 5, so I measured.
- **Report the argmin's own stability directly.** Fold-to-fold spread of u\* needs no floor, no
  curvature and no grid argument, and it is the statistic the conclusion actually rests on.

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

## 7c. A gate that tests one unit does not test the aggregation over units

Caught before it ran, and only because §4c had just made me suspicious of shortcuts.

I was about to replace a per-tensor computation with an algebraically equivalent closed form
evaluated once over the **concatenation** of every tensor's block maxima. The gate compared the
closed form against the real quantiser **on one tensor**, to double precision. It would have
passed, and the full computation would still have been wrong — the scale rule confines the
exponent to a field anchored at *the tensor's own minimum*:

```python
if nlev is not None:
    jlo = j.min()                                   # scale_settled.py:143
    jc = torch.clamp(j - jlo, 0, nlev - 1) + jlo
```

On one tensor `j.min()` is that tensor's minimum either way, so the fault cannot appear. On the
concatenation it becomes the **global** minimum and every tensor gets a different scale field than
the experiment it was meant to reproduce. The gate was blind to the exact axis the shortcut changed.

- **Gate the aggregation, not just the element.** If the replaced path runs per-unit and the
  replacement runs once over all units, compare *totals over all units*.
- **Grep for unit-scoped state before flattening anything**: `.min()`, `.max()`, `.mean()`, any
  normalisation, shared exponent or per-tensor anchor changes meaning under concatenation.
- **The cheapest fix is usually not to take the shortcut.** Doing it directly removed the closed
  form, the gate and the whole class of error, for about a minute of compute per model — which is
  what the shortcut existed to save.

## 7d. A withdrawal in your notes does not reach your documents

An FPGA frequency was withdrawn in research notes, in a memory file, and in two dated analysis
documents that each spelled out the mechanism and prescribed replacement wording. **The paper that
carries the number to readers still says it** — in the title, the abstract, the results table, the
throughput figure, and a sentence asserting all of it came "from actual FPGA hardware runs." A
later honesty pass over that same file did not catch it, because it was looking at a different
sentence.

The number was the toggle rate of a 20-inverter ring oscillator clocking a 23-bit counter. The
design's synthesised netlist holds 55 logic cells — 19 ring inverters, the counter, its carry
chain, a clock buffer and two LED drivers — and **zero cells of the arithmetic being claimed**,
which was constant-folded away because the wrapper feeds it literals. The tell was visible without
any of that: three designs whose claimed sizes differ by **62×** report 330 / 322 / 323 MHz, a
2.5 % spread. *A real critical path cannot be invariant to a 62× size change.*

- **When you withdraw a number, grep for the number** — the digits, across the whole tree,
  including papers, READMEs, CHANGELOGs and downstream docs. Not for the file you remember writing
  it in. Here it still lived in seven further files.
- **Record where it still lives**, and treat the withdrawal as incomplete until that list is empty.
- This is the debugging doctrine's *"distinguish runtime from persistent fixes — silent reverts
  create Sisyphus loops"*, applied to claims instead of configuration.

## 8. Blast radius is bounded by imports — check it before re-running anything

When a competitor bug is found, `grep -l` for the competitor's symbols. Scripts that never
reference it **cannot** be affected. This took seconds and exempted four load-bearing results from
re-measurement.

## 8b. Read what the assertion compares, not what the line above it claims

Four separate failures in this project have the same shape, and it is not "we didn't know".
In every one the fact was **already written down in the repository** and the harness quietly
contradicted it downstream:

| the harness | its docstring / comment said | its code did | what it cost |
|---|---|---|---|
| `campaignA_books.check` | "T38 on **BOTH** tails" | `assert max(pos, neg) == 1.0` | a clipping arm ranked as a placement for two campaigns; a published protocol finding withdrawn |
| `run_synth.py` | one Fmax per seed | appended **two** per run, sliced the last N | a median over three post-route and two post-placement figures |
| the decoder cost | "logic LUT" | counted `SLICE_LUTX` **BEL occupancy** | 1.00× reported where the truth was 1.67× |
| the render harness | "5 runs passed" | 5 × `exit=1` in 0 s with `dist` absent | a setup failure nearly reported as flakiness |

`max(a, b) == 1.0` is satisfied by *either* argument. `assert a == 1.0; assert b == 1.0` is the
claim. This is not a subtle distinction and it is not caught by reading the docstring — the
docstring is what lied.

**The check, and it is cheap.** For every assertion in a harness whose output you are about to
quote: read the *expression*, decide what set of inputs passes it, and ask whether that set is the
one the surrounding prose describes. Then feed it one input that should fail. In all four cases
above a single deliberate bad input would have caught it in under a minute.

**The corollary that costs the most.** When the fact is already recorded in the code — a docstring,
a comment, an `if name == ...: # careful` — that is *not* protection. Prose does not execute.
`campaignA_books.py` said TOP clips the negative tail to −0.75 in its module docstring, and
`campaignD_spearman.py` said the same thing at line 86 with an explicit without-TOP column, and
the arm was still in the ranked pool of every campaign for three days. Only the assertion is
load-bearing. See `research/block/CLIPPING_ARM_CORRECTION_2026-08-12.md`.

**And the class of bug this creates.** A too-permissive assertion does not produce an obviously
wrong number — it produces a *plausible* one, carrying an ineligible member through the whole
analysis. The symptom is not a crash; it is an unexplained instability that then gets its own
research campaign. Three campaigns here went into explaining an instability that was one
ineligible book in a pool of ten.

## 8c. Before writing a gate, search for the gate

Three times now the fix for "this is not checked" was **already in the repository, uninvoked**.
The render check, the ARIA check and the typecheck ratchet were each written the day their failure
was found, each then ran only when someone remembered, and a later session wrote a *second* gate
for the same thing. The second one is always weaker — it is written under time pressure, against a
symptom, without the first one's accumulated caveats:

| the duplicate | what already existed | how the duplicate was worse |
|---|---|---|
| `website-static-checks.yml` | `website-checks.yml`, green for six runs, already running the render check in CI | wired to raw `npm run typecheck` (184 pre-existing errors) instead of the repo's own `typecheck:ratchet` — red the moment it merged |

A permanently red gate is worse than no gate: it is a red X people learn to scroll past, and it sits
next to the real signal making that unreadable too.

**Do this first, it costs one command.** Before adding any check: `grep -rl` the repo for the thing
you are about to write, and `grep` CI config for whether the existing one is *invoked*. "Not run"
and "not written" look identical from the outside and have completely different fixes — the first
is one line of YAML.

**And when the debt is real, ratchet rather than demand zero.** A gate on the direction (no file may
gain errors) is green today, catches the regression tomorrow, and keeps the debt countable. Gate
**per unit, not on a total**: a scalar count passes when one file is fixed and another breaks by the
same amount, which is exactly the shape of a refactor trading one bug for another. That case belongs
in the gate's own self-test — `fixed one, broke another` must fail.

## 8d. The replicate unit is a claim — write it where claims are written

Six times. Five were caught by reading documents; the sixth was live in a script, three lines long,
and its statistical decision was made by `np.concatenate`:

```python
d = np.concatenate([dvec(D, m, arm, ref) for m in models])   # 4 models x 35 windows
r = paired(d)                                                # ...as n = 140
```

The section header said "POOLED OVER ALL FOUR MODELS" and the statistic said "n = 140 windows".
**Eleven of fourteen verdicts flipped** when each model contributed one mean log-ratio instead:
every "BEATS MXFP4" and every "loses to NF4" became a tie. The point estimates barely moved
(−4.99 % → −4.76 %); the intervals grew by roughly √35 and every one came to contain zero.

**Why this one hid for six rounds.** The declaration was implicit in a *shape-changing utility*.
`concatenate`'s job is to join arrays; nobody reads it as an assertion about exchangeability. The
five earlier instances were sentences in documents, which get re-read; this was a reshape, which
does not.

**The rule.** State the replicate unit in prose, at the site, and branch on it explicitly:

```python
if len(models) > 1:      # cross-model claim: n = models
    d = np.array([float(dvec(D, m, arm, ref).mean()) for m in models])
else:                    # within-model claim: windows are the right unit
    d = dvec(D, models[0], arm, ref)
```

**And the tell that it is a real correction rather than a motivated one: it should move claims in
both directions.** Here four rows moved toward our codebooks and seven away. An error that only
ever flattered us would be a different finding, and would deserve a harder look.

**Corollary — a unanimous rotation is not a rotation.** If every leave-one-out fold selects the
same arm, the "held-out" mean is *algebraically identical* to the in-sample mean. The label
transports no information and must not be quoted as though it does. Check that the folds disagree
before believing the rotation bought anything.

## 8e. A wall-clock limit measures the machine, not the code

The gate-status ratchet's first run against its own baseline, on an **unchanged tree**, reported
two scripts degraded `clean → TIMEOUT` and one improved `TIMEOUT → clean`. Nothing had changed
except how many workers were competing for cores.

A timeout is not a property of the script. It is a property of the script *and* the load, and any
status derived from it inherits that. Three consequences, all of which bit here:

* **The threshold is part of the measurement.** A script that is `TIMEOUT` at 90 s and `clean` at
  300 s has not changed; comparing across two thresholds reports a fix or a regression that did
  not happen. Record the threshold **in the baseline** and reuse it on every check, rather than
  passing it as a convenience flag.
* **Parallelism is part of the measurement too**, and it is the part people forget to record. Four
  workers on a machine already running a build is a different instrument from four workers on an
  idle one.
* **Re-run disagreements serially before believing them.** Any status change with a timing-derived
  status on either side gets one clean re-run with no contention. Only a script that exceeds the
  limit *alone* has actually regressed.

**The general rule.** Any gate whose verdict can move without the tree moving is a broken ruler,
and it will be muted within a week — correctly, because it is lying. Before wiring a gate into CI,
run it twice on an unchanged tree under *different* load and check it says the same thing. That
costs one command and it is the only evidence that the gate measures the code.

This one was caught because the ratchet was run against its own freshly-written baseline, which is
worth doing on purpose: **a new gate's first act should be to disagree with itself, so you find out
whether it can.**

## 8f. Pin the substrate, not just the harness

Every number in the 2026-08 block campaign was measured against a `weights/` directory in `/tmp`
belonging to **another session's scratchpad**. It vanished mid-campaign. Eleven documents quote
figures only that directory could produce, and nothing in the repository recorded how to rebuild it.

The recovery took twenty minutes and only because one file happened to carry the right gate:

1. corpus from the HuggingFace cache under `~` (which survived);
2. checkpoint re-downloaded from the Hub;
3. **and neither counts until the ruler reproduces** — a restored corpus differing by one row, or a
   re-uploaded checkpoint, produces numbers that look exactly like the old ones and are not
   comparable to them. Measured: fp32 14.4874 and MXFP4 21.9397 both to under 2e-06 relative. Gate
   passes, so pre-loss and post-loss numbers are comparable. Had it failed, the honest move was to
   say so, not to quote them together.

**What a measurement record needs and this one lacked:**

* **a provenance line per input** — Hub repo id *and revision* per checkpoint, repo/revision/file
  for the corpus. `gpt2` is not a version; `gpt2@<sha>` is;
* **a fingerprint checkable without the original** — row count, character count, content hash of
  the exact joined text, stored *in the measurement records*, so a restored copy is compared to
  what was used rather than to a description of it;
* **a ruler gate that runs on restore**, as the documented first step of any measuring session —
  not a gate that one file happens to carry.

The campaign spent a week finding harnesses that asserted less than their prose claimed. This is
that defect one level down: **the substrate was never asserted about at all.** A number is
comparable to another number only if something checkable says the instrument did not move — and the
instrument includes its inputs.

## 8g. Ask what the format destroys before building a predictor on it

Five separate predictor failures in this campaign turned out to be one failure. T41's clipping
criterion (wrong sign on two of four), T42's occupancy conjecture, the P1/P2/P3 bin predictors
(none rotation-stable, and the classical greedy one *anti*-correlated), the four refuted
explanations for a selector's uneven behaviour, and the standing surprise that a margin measured on
four checkpoints does not appear on a fifth.

All of them tried to predict a codebook's behaviour from the **weight distribution**. Measured
across eight checkpoints and four architecture families:

| | spread |
|---|---:|
| raw weight kurtosis | **14.6×** (3.786 → 55.334) |
| kurtosis **after the block scale** | **6 %** (2.795 → 2.985) |

The E8M0 rule `s = 2^⌈log₂ a⌉` absorbs essentially all of it. **The information those predictors
were built to extract is destroyed by the format's own scale rule before the codebook sees the
data.** Including on a non-transformer with no attention, which landed inside the band written for
the transformers.

**The rule.** Before building any predictor on an input statistic, measure that statistic *after*
every normalisation the pipeline applies, not before. If the pipeline flattens it, the predictor
cannot work and no amount of feature engineering on the raw side will save it. This costs one sweep
and it would have saved five.

**And the corollary for where to look next.** If a normalisation flattens the input differences
while the *outputs* still differ by 21×, the difference is downstream — in how sensitive the trained
function is, not in what it is made of. That is a different measurement (perturb by a fixed relative
size and watch the loss) and it needs its own control: a zero-perturbation run that must reproduce
the baseline bit-identically, or the harness is not measuring what it claims.

## 8h. Register the prediction you expect to fail, and score it when it does

The occupancy registration wrote down, in advance: *"the registered expectation is that O1 holds and
O2-O4 fail -- occupancy carries real information and is still not usable."* Uncomfortable to commit
to. Then **O1 failed too** -- 12.8 % spread against a registered threshold of 20 % and a registered
point prediction of 25-60 %.

Being wrong in the direction that *strengthens* the conclusion is the only evidence that the
conclusion was not steered. Had the spread come back at 30 %, the registration would have been the
thing stopping a post-hoc story about why 30 % is "meaningful". Because it came back at 12.8 %, the
registration is the thing that makes "the weight side is closed" a result rather than an assertion.

**The practice, and the order matters:**

1. write the threshold **and the predicted sign** before the data exists — a correlation with the
   right magnitude and the wrong sign is a failure of the stated mechanism, not a discovery, and
   only a pre-committed sign makes that call automatic;
2. write what each outcome will mean, including the one you do not want;
3. **score the prediction, not just the hypothesis.** "O1 failed" and "my P1 was wrong by half"
   are different admissions and the second is the one that calibrates you;
4. report the near-miss that pointed the right way — here `MID` at rho = -0.800 with the predicted
   sign, p = 0.104, x4 = 0.416 — because a null deserves the same scrutiny as a hit, and because
   one of four pointing correctly at n = 5 is what chance produces.

**The tell you are doing it wrong:** a registration whose predictions you would be happy with
either way is not constraining anything. If writing the number down does not feel like a risk, it
is not a prediction.

## 8i. A gate that stops finding things looks exactly like a corpus that got fixed

A cross-check was added to two yosys stat parsers, correctly diagnosed as missing. Wired as a gate,
it fired on **every** core -- the histogram exceeded yosys' declared total by a near-constant 6-9 --
so every core became "could not measure" and the script **exited 0 with nothing to report**. The
status ratchet recorded the change as `findings -> clean`: an *improvement*, in the severity order.

**Two lessons and the second is the sharper one.**

**(a) Severity orders are asymmetric in the wrong direction.** `clean` above `findings` encodes
"fewer problems is better", which is true of the corpus and false of the instrument. A gate that
stops reporting is not distinguishable from a corpus that got clean unless something separately
records **how much it examined**. `run_all_checks.py` in the same directory already makes exactly
this distinction -- HOLDS with a coverage of zero is "the shape that reads as assurance and is not"
-- and the ratchet did not. Record coverage alongside status, or a fix that silences a check reads
as progress.

**(b) The check was right and the population was wrong.** `logic_count.py` cross-checks its
histogram against the declared total and *raises*, correctly, because it locates an explicit
`=== top ===` block and reads the table beneath it. The two broken files take
`stdout.split("=== ")[-1]` -- the trailing text after the last marker, whose declared total and
whose matched lines are **not the same population**. Copying a check between two harnesses copies
its assumptions about what it is counting, and those assumptions are usually undocumented.

**The rule.** Before promoting a diagnostic to a gate, run it in advisory mode over the real corpus
and look at the hit rate. A check that fires on 100 % of inputs is measuring its own assumptions,
not the corpus -- and if you gate on it, you have replaced a partial instrument with a silent one.

This is instance nine, in a fix written for instances one through eight, by the person writing the
rules. The class is not something other people do.

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
