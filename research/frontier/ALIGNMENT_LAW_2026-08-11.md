# Alignment: not a law, a per-model knob — and the knob is prior art

**Verdict, stated plainly and first: `u*` is a MEASURED PER-MODEL QUANTITY. It is not a law, it is
not derivable from the block-maximum distribution without a metric mismatch, and it does not
transfer. The pre-registered leave-one-out test fails on Pythia under every rounding convention.
The best single alignment across the five families measured is `u = 0.415`, which IS the OCP MX
specification's own constant.**

Second verdict, which cost this wave its headline: the premise that alignment is *"fixed by every
specification and tuned by none"* is **false as literature**. Cook et al.'s **4/6**
(arXiv:2512.02010), **ScaleSweep** (arXiv:2606.07618) and **SOAR** (arXiv:2605.12245) all tune
exactly this constant, two of them by sweeping it. §6.

---

## 0. Instruments

Every number below carries the script that produced it. Nothing is quoted from memory.

| instrument | decides | sample | gates |
|---|---|---|---|
| `research/block/scale_settled.py` | the trusted quantiser + ppl; base×alignment sweep | 40 win × 2048 tok | **21 self-tests, abort before print** |
| `research/block/align_u.py` | the 5-family u-scan (Pythia, OPT, GPT-2) | 40 win × 2048 tok, 13 alignments | imports `scale_settled`; +7 own gates |
| `research/block/align_harden.py` | windows, second corpus, activations, ties | 120 win wikitext-2; 40 win docs-en | imports `scale_settled`; own gates |
| `research/block/u_surface.py` | u* vs block size K and element format | **4 win × 2048 = 8,192 tok** (some cells 20/40) | 12 gates, **G11 FAILED — see §5.5** |
| `research/block/u_theory.py` | is u* derivable? (squared error, no forward pass) | 4 M elements per cell | shares primitives with `u_surface` |
| `research/block/u_atoms.py` | the block-maximum atom lattice | 3,317,760 blocks (SmolLM2, K=32) | — |
| `research/block/scale_control.py` | base ladder incl. √2, 2^(1/4) | 40 win × 2048 tok | **no self-tests; ties resolve toward zero** |

Convention for every perplexity number unless stated: block K = 32, element **E2M1 with its
subnormal** (8 magnitudes), scale base `g = 2`, **4-bit scale field (16 levels)**, ties-to-even,
weight-only, all `nn.Linear` except the LM head, wikitext-2 test.

`u` is the alignment, reparameterised base-independently as the target clamp fraction under
log-uniform block maxima: `c(u,g) = max_norm / g^(1−u)`, so `amax/s ∈ [c, c·g)`. `u = 0` is
no-clamp for every base; `u = 0.4150375 = 1 − log₂(6/4)` is exactly OCP MX (`c = 4`, `emax = 2`).

---

## 1. Does `u*` replicate across families, block sizes and element formats?

### 1.1 Five families — no

`align_u.py`, 40 windows, ties-even (SmolLM2 and Qwen rows carried from the prior wave's
`scale_settled.py` run; the other three are this wave's and were re-verified against
`align_u_{pythia,opt,gpt2}.json`):

| model | store | fp32 | u\* | ppl(u\*) | ppl(OCP) | gain | tie floor | gain / floor |
|---|---|---|---|---|---|---|---|---|
| smollm2 | bf16 | 14.4874 | 0.35 | 20.6950 | 23.5224 | +2.8274 | 0.2398 | 11.8× |
| qwen | bf16 | 12.2277 | 0.30 | 14.5532 | 15.0632 | +0.5100 | 0.0932 | 5.5× |
| pythia | fp16 | 25.9561 | **0.40** | 44.5762 | 44.8219 | +0.2457 | **0.5358** | **0.5×** |
| opt | fp16 | 27.5678 | **0.25** | 31.0971 | 32.6597 | +1.5626 | 0.0667 | 23.4× |
| gpt2 | fp32 | 31.3254 | **0.25** | 35.6968 | 36.3248 | +0.6280 | 0.0003 | 2093× |

**`u*` spans 0.25–0.40 — three grid steps, six times the pre-registered stability threshold of
one.** The claimed `u* = 0.30–0.35` is reproduced by none of the three new families.

Full curves (ppl, ties-even, 40 windows; SmolLM2's column is the prior wave's):

|   u | pythia | opt | gpt2 | smollm2 |
|---|---|---|---|---|
| 0.00 | 46.9561 | 31.8092 | 36.7423 | 22.7120 |
| 0.05 | 46.1775 | 31.5720 | 36.7867 | 22.1478 |
| 0.10 | 46.0430 | 31.3658 | 36.6416 | 21.3716 |
| 0.15 | 46.1546 | 31.1570 | 36.4797 | 21.1493 |
| 0.20 | 45.2276 | 31.1058 | 36.2759 | 20.9775 |
| 0.25 | 45.3703 | **31.0971** | **35.6968** | 21.0100 |
| 0.30 | 46.0384 | 31.4082 | 36.2094 | 20.7384 |
| 0.35 | 45.0606 | 31.7738 | 36.2725 | **20.6950** |
| 0.40 | **44.5762** | 32.7237 | 36.3842 | — |
| 0.415 (OCP) | 44.8219 | 32.6597 | 36.3248 | 23.5224 |
| 0.45 | 45.3867 | 33.2249 | 36.5244 | — |
| 0.50 | 46.8273 | 34.2738 | 36.6759 | 27.7307 |
| 0.55 | 48.5139 | 35.3521 | 37.1971 | 31.8413 |

The three curves are not the same shape. OPT is a clean basin at 0.25. GPT-2 is a 0.47-deep,
0.05-wide **notch** at 0.25 (half-grid fill: 0.225 → 36.1641, 0.275 → 36.0684). Pythia is jagged
with its minimum essentially on the spec.

### 1.2 The pre-registered test, and it fails

Leave-one-out: take `u` from the other four (mean 0.287, grid 0.30), apply to the held-out one.

    ties=even   u=0.30  46.0385   vs OCP 44.8216   transfer costs +1.2169
    ties=zero   u=0.30  46.1012   vs OCP 44.8216   transfer costs +1.2796
    ties=away   u=0.30  45.7041   vs OCP 44.2878   transfer costs +1.4163

**Adopting the law makes Pythia 1.22–1.42 ppl worse than shipping the specification** — 2.3× its
own nuisance floor, under every rounding convention. This is the second constant in this campaign
killed by the third model at the budget it was invented for; the first was the ladder-criterion
`λ`. `measurement-discipline` §3b now records both.

### 1.3 The specification is the best worst-case choice

**No single `u` beats OCP on all four measured curves.** At every `u ≤ 0.35` Pythia loses to OCP
(ratio ≥ 1.0053); at `u = 0.40` both OPT (1.0020) and GPT-2 (1.0016) lose.

> **Minimax over the common grid lands on u = 0.415 — the OCP MX constant.**

And on Pythia the tuned gain is not worth having: **+0.2457 against a tie-rule spread of 0.5358**
at the same point. OCP with ties-away (44.2878) beats tuned `u*=0.40` with ties-even (44.5764) by
0.2886 — for Pythia the *rounding convention* is the bigger lever than the alignment.

### 1.4 Block size and element format — u\* moves with those too, and not enough to explain it

`u_surface.py` + `u_surface_verdict.py`, **24 cells** = 2 models × K ∈ {16,32,64,128} × format ∈
{INT4, E2M1, E3M0}, common grid {0, 0.125, 0.25, 0.375, 0.5}, **nw = 4 windows = 8,192 tokens**
(small; see §8).

Common-grid argmin, resolution 0.125:

| fmt | K | qwen | smollm2 | \|diff\| |
|---|---|---|---|---|
| INT4 | 16 / 32 / 64 / 128 | 0.250 / 0.375 / 0.375 / 0.375 | 0.250 / 0.250 / 0.250 / 0.375 | 0 / .125 / .125 / 0 |
| E2M1 | 16 / 32 / 64 / 128 | 0.250 / 0.250 / 0.250 / 0.375 | 0.125 / 0.250 / 0.125 / 0.125 | .125 / 0 / .125 / .250 |
| E3M0 | 16 / 32 / 64 / 128 | 0.500 / 0.375 / 0.500 / 0.500 | 0.250 / 0.250 / 0.250 / 0.375 | .250 / .125 / .250 / .125 |

- spread **between models** at fixed (K, fmt): mean |diff| **0.1250** over 12 pairs, max 0.250 —
  i.e. **one to two grid steps of pure model identity**;
- spread **across K** at fixed (model, fmt): 0.125 in all 6 series;
- total spread over all 24 cells: **0.125 … 0.500**.

So (K, format) does *not* absorb the variation: the between-model spread is the same size as the
across-K spread. `u*` is not a function of the format geometry.

What (K, format) *does* predict is **amplitude** — how much alignment is worth at all.
`A = (max−min)/min` over the common grid:

| model | INT4 | E2M1 | E3M0 |
|---|---|---|---|
| qwen K=16/32/64/128 | 11.1 / 17.2 / 27.3 / 49.6 % | 9.5 / 6.1 / 4.8 / 10.7 % | 0.4 / 0.7 / 0.5 / 0.7 % |
| smollm2 K=16/32/64/128 | 31.7 / 56.8 / 32.1 / 60.8 % | 41.0 / 39.4 / 32.5 / 35.6 % | 2.0 / 1.6 / 2.2 / 1.2 % |

Ordering `A(INT4) > A(E2M1) > A(E3M0)` holds in **6 of 8** (model, K) cells; it fails twice on
SmolLM2, where E2M1 edges INT4. `A` is monotone in K in **1 of 6** series; the sharper channel
`G_left = ppl(u=0)/ppl(u*) − 1` is monotone in K in **2 of 6**. Rank correlation of `A` with
end-mass at `u=0` (clamped + flushed weights) over all 24 cells: **ρ = +0.758**; for `G_left`,
**ρ = +0.905**. Held within one format (8 cells), `G_left` gives ρ = +0.524 (INT4), +0.738 (E2M1),
−0.190 (E3M0).

The mechanism behind the amplitude ordering is derived and checked in
`u_interior_invariance.py`: a scale change by a whole factor of `g = 2` maps a float codebook onto
itself except at its ends, so **all `u`-dependence of a float format is carried by three sites** —
the top clamp, the bottom flush, and (for a float with subnormals) the resolution step at the
subnormal boundary. E3M0 has one magnitude per binade and no step, so it is nearly flat in `u`
(A ≤ 2.2 % everywhere). E2M1 has the step (its bottom binade is subnormal — `1.5/2 = 0.75` is not
representable, so the first run came back 81.15 % invariant rather than 100 %, and the refutation
is what produced the corrected statement). INT4 is linear, is invariant nowhere, and is the most
`u`-sensitive of the three.

### 1.5 The curve is not smooth — there is a cliff, and it moves

`u_surface.py` at **nw = 20** (baseline 14.9563, so levels are not comparable with the 40-window
table), SmolLM2, K = 32, E2M1:

    u=0.340  21.5176      u=0.355  21.6456      u=0.360  21.7997
    u=0.365  23.9993   <- +2.20 ppl across Δu = 0.005
    u=0.370  24.1373

**A 0.5 % change in the alignment costs 2.20 perplexity.** The optimum is not an interior minimum
of a smooth basin; it sits immediately before a cliff. That is the strongest available explanation
of why a constant fitted on two checkpoints cannot transfer: a value chosen just below one model's
cliff can be just past another's, and nothing in the fitted value records where the cliff is.

The cliff is a property of the checkpoint's **block-maximum atom lattice**, not of the method.
`u_atoms.py` on SmolLM2 (bf16), K = 32, 3,317,760 blocks: the normalised block maximum takes
**exactly 128 distinct values** (bf16 carries 7 explicit mantissa bits), so the realised clamp
fraction is a 128-step staircase in `u` and the perplexity curve inherits its risers. An fp16
checkpoint has 1,024 atoms and an fp32 checkpoint 8.4 M — the same knob is smooth on GPT-2 and
staircased on SmolLM2 **purely because of the release format**.

---

## 2. Is there a derivation with no fitted constant?

**Yes for squared error. No for perplexity. That gap is the result.**

### 2.1 The derivable quantity exists and is remarkably stable

`u_theory.py`, no forward pass, no perplexity, `u` grid 0.000–1.000 step 0.025, minimising block
squared error.

**ARM S (synthetic, i.i.d. samples, 4,000,000 elements per cell — no model anywhere).** `u*` is
then a function of (K, format, source distribution) only, with no free parameter:

| dist | K=16 | K=32 | K=64 | K=128 | (E2M1) |
|---|---|---|---|---|---|
| gauss | 0.2440 | 0.2680 | 0.3223 | 0.4181 | |
| laplace | 0.2545 | 0.2870 | 0.3425 | 0.4332 | |
| t₅ | 0.2544 | 0.2911 | 0.3543 | 0.4515 | |

**ARM W (real `nn.Linear` weights, ~4,000,000 elements per cell by fixed stride, no forward
pass).** At K = 32, E2M1 — the configuration of the whole five-family table:

| model | tensors | weights | u\*(nSSE) | 1 % basin |
|---|---|---|---|---|
| smollm2 | 210 | 106,168,320 | **0.2709** | [0.225, 0.300] |
| qwen | 168 | 357,826,560 | **0.2761** | [0.225, 0.325] |
| pythia | 48 | 84,934,656 | **0.2704** | [0.225, 0.325] |

**Spread 0.0057 across three families — 4 % of one perplexity grid step.** The squared-error
optimum *is* a law, it needs no fitting, and it agrees with the synthetic Gaussian/Laplace
prediction to within 0.02.

### 2.2 And it is not the perplexity optimum

Measured `u*` by perplexity at the same K = 32, E2M1: **0.35 (smollm2), 0.30 (qwen), 0.40
(pythia)** — against a derived 0.2704–0.2761. The derivation is off by 1–3 grid steps, and it is
off in different directions.

This is not a surprise in this repository, it is a **measured law of it**.
`research/block/METRIC_DISAGREEMENT_2026-08-11.md`: one intervention, four instruments —
weight L2 −3.31 %, layer-output L2 −19.94 %, logit L2 **−46.11 %**, KL(fp32‖q) **+15.47 %**,
perplexity **+7.96 %**. Every Euclidean measure said the model got closer to fp32 and it got
worse; `exp(ΔKL) = 1.0678` against a measured ratio of 1.0796, so 85 % of the degradation is the
KL change alone. **Any alignment predictor built on squared error has a measured counterexample in
this repository**, and `u_theory.py` says so in its own docstring before it prints anything.

Does the derived value at least *work*? At `u = 0.275` (nearest measured grid points 0.25/0.30) it
beats OCP on smollm2, qwen, opt and gpt2 and **loses on pythia** (45.37 / 46.04 against 44.82) —
the same 4-of-5 pattern, the same held-out failure. Deriving the constant does not repair the
transfer problem; it only removes the fitting.

### 2.3 The obvious reparameterisation, tried and believed when it failed

"Not a fixed `u`, but a fixed *clamp fraction*" is the natural repair, since real block maxima are
not exactly log-uniform. Observed clamp fraction at each model's own `u*` (`align_u.py`,
denominator 2,654,208 blocks per model): **40.57 % (pythia), 22.94 % (opt), 24.02 % (gpt2)** — a
**17.6-point spread against `u`'s own 15-point spread**. Wider, not tighter. Not the hidden law
either.

The log-uniform model itself is good but not exact (`align_u.py`, pred vs observed clamp %):

|   u | predicted | pythia | opt | gpt2 |
|---|---|---|---|---|
| 0.10 | 10.00 | 9.83 | 9.16 | 9.71 |
| 0.25 | 25.00 | 25.01 | 22.94 | 24.02 |
| 0.415 | 41.50 | 42.23 | 37.58 | 40.15 |
| 0.55 | 55.00 | 56.02 | 53.54 | 53.91 |

Max departure **−3.92 points** (opt at OCP). Activations fit it far better: `align_harden.py`
records **41.55 %** of activation blocks clamping at the target 41.504 % — 0.05 points.

### 2.4 Why "measured per model" is still an acceptable result

Three reasons, all of which are load-bearing for the paper:

1. **It converts a free parameter into a stated cost.** "Alignment must be measured per
   checkpoint, and it is worth 0.25–2.83 ppl" is a deployable instruction. "Use u = 0.32" is a
   trap that costs Pythia 1.22.
2. **The negative result is sharper than the positive one would have been.** *No single value
   beats the specification across five families, and the minimax value is the specification's own*
   is a defence of OCP that OCP's own authors do not appear to have published. It is worth more
   than another tuned constant.
3. **It closes the question instead of leaving it open.** Both natural repairs — derive it from
   squared error (§2.1), or hold the clamp fraction fixed (§2.3) — were tried and both failed with
   measurements attached. There is no obvious third.

---

## 3. The three-knob taxonomy, with each knob's measured value

A block scale is `s = g^floor(log_g(amax/c))`, quantised into a field of `2^b` levels. That is
three parameters and exactly three:

| knob | what closes it | measured value | residual freedom |
|---|---|---|---|
| **BASE `g`** | a cost theorem | see below | none worth having at 4-bit fields |
| **WIDTH `b`** | `b_min = ceil(log₂ S(W,K))` | **4 bits, 0 clamps** | none |
| **ALIGNMENT `c`** | nothing — this document | **`u* = 0.25–0.40`, per model** | 0.25–2.83 ppl |

### BASE — closed by cost, and 2^k wins at equal tuning

Cost side (`frontier/ONE_ADDER_FAMILY_2026-08-10.md`, `frontier/LADDER_COST_AND_LAW_2026-08-10.md`,
silicon numbers isolated on xc7a200t, median of five placement seeds): `r^d = r + 1` has exactly
two non-zero coefficients at every degree, so its companion map costs **one addition** for every
`d`, verified exact over 3,000 random coordinate vectors at `d = 5` and `d = 8`; its roots
converge to `2^(1/d)` from above. φ (223 LUT, 247.10 MHz) and the plastic number (228 LUT,
231.21 MHz) both cost one adder and differ in area by 2.2 %. The earlier claim that "degree 4 is
where the hierarchy stops being cheap" was about the *minimal ratio at that degree* and was
**superseded** by the one-adder family — recorded here because both documents are on disk.

Accuracy side, and this is the confounded comparison the campaign already withdrew once. At the
**no-clamp alignment only** (`scale_control.py`, 40 windows, ties toward zero, ceil rule):

| base | adds | smollm2 | qwen |
|---|---|---|---|
| 2 (E8M0, MX spec) | 0 | 22.4998 | 14.9447 |
| φ = 1.6180 | 1 | **21.3545** | 14.8512 |
| √2 = 1.4142 | 0 | 21.8960 | 14.7456 |
| 2^(1/4) = 1.1892 | 0 | 24.0791 | **14.4328** |
| plastic = 1.3247 | 1 | 22.7625 | 15.0333 |

At **each base's own best alignment** (`scale_settled.py`, 21 gates, ties-even):

| base | smollm2 best | qwen best |
|---|---|---|
| 2 | **20.6950** (u = 0.35) | **14.5532** (u = 0.30) |
| φ | 21.3112 (u = 0.15) | 14.7850 (u = 0.15) |

**The base advantage was the alignment.** Tune both arms and the plain power-of-two ladder wins on
both models, at zero adders. (The two φ figures at their own best alignment are carried from the
prior wave's brief; `scale_settled_smollm2.json`'s own sweep records the φ no-clamp point at
21.3547/21.3545/21.1164 for ties even/zero/away, and its 2^k sweep bottoms at 20.7395 at `c = 3.8`,
i.e. `u = 0.341`. The write-up named in this wave's brief,
`frontier/PHI_SCALE_REFUTED_ALIGNMENT_2026-08-11.md`, **does not exist** — I searched the whole
repository by name and by value. Provenance gap, flagged.)

### WIDTH — 4 bits, and it is published

A 4-bit scale field is **bitwise identical to an unbounded E8M0 field** at K = 32: 0 of
**20,462,464** blocks clamped across five checkpoints, extended this wave to 3 families × 13
alignments × 2,654,208 blocks = **103,514,112 block-scale assignments, 0 clamped** (`nclip`
totals in `align_u_{pythia,opt,gpt2}.json`). The field is unclamped not only at the spec alignment
but across the whole `u` range. Prior art: **Chhugani et al., arXiv 2603.08713**, on larger
models, with the truncation explicitly proposed.

### ALIGNMENT — §1, §2. `u* = 0.25–0.40`, per model, gain 0.25–2.83 ppl, nuisance floor
0.0003–0.5358, minimax = the spec.

---

## 4. The zero-adder ladders, and whether step size matters at all

`√2` and `2^(1/4)` are rational powers of two, hence **zero-adder** scales *finer* than φ. If
fineness is what a scale ladder buys, they should beat φ, which costs an adder. Three things are
measured and one is not.

### 4.1 They do not order by fineness, and the two models disagree

From the table in §3, at `u = 0` (`scale_control.py`): on SmolLM2 the ordering is
φ < √2 < 2^k < plastic < 2^(1/4) — the **finest** ladder is the **worst**, by 2.7 ppl against φ.
On Qwen the ordering is 2^(1/4) < √2 < φ < 2^k < plastic — the finest ladder is the **best**.
**The two models order the bases oppositely.** Any "finer is better" law is dead on arrival at
n = 2.

### 4.2 The confound: those numbers are all at one alignment

`scale_control.py` uses `s = g^ceil(log_g(amax/6))`, which is `u = 0` for every base. §3 shows
what happens when the alignment is freed: 2^k moves 22.50 → 20.70 and φ moves 21.35 → 21.31.
**The measurement that would settle §4 — each zero-adder base at its own best alignment — was not
run this wave**, because no checkpoint was loadable (§8). It is the single most valuable missing
number in this document.

The instrument gap must also be stated: `scale_control.py` carries **no self-tests** and resolves
element ties toward zero, where the trusted harness ties to even. Its 2^k `u=0` value is 22.4998
against `scale_settled.py`'s 22.7120 — a gap of 0.2122, of the same size as SmolLM2's measured
tie floor at `u = 0` (0.2398, `scale_settled_smollm2.json`, ties even/zero/away =
22.7120/22.5857/22.8255). Consistent with the tie rule, **not isolated by a direct A/B**.

### 4.3 Fineness is not free: it is paid for in scale-field width, and that is where the 4-bit
result stops

A field of 16 levels spans `15·log₂(g)` binades: **15.0 for 2^k, 10.4 for φ, 7.5 for √2, 3.75 for
2^(1/4)**. The measured "0 of 20,462,464 blocks clamped" is a statement about base 2 only. It
bounds each tensor's block-maximum span *above* by 15 binades and gives no lower bound, so **it
does not license the same claim for a finer base.** Two of the four ladders in §4.1 may be paying
one or two extra bits of scale field for their zero adders, at K = 32 that is 0.03–0.06
bits/weight, and nobody has checked.

The cost of getting this wrong is not gentle. On the *element* axis, where the same span/fineness
trade was measured (`frontier/ELEMENT_ONEADDER_2026-08-10.md`, SmolLM2, 12 windows, per-output-
channel scale, baseline 14.3607): at a 4-bit budget `r^8 = r+1` spans 1.7× and measures
**2,710,365 perplexity**. *Fineness without span is not precision, it is a very accurate
description of a narrow interval.*

**The missing measurement, named exactly so it can be run in one minute given weights:** per
tensor, `max(log₂ amax) − min(log₂ amax)` over its blocks, per checkpoint; then `nclip` at 16
levels for `g ∈ {2, φ, √2, 2^(1/4)}`. No forward pass required.

### 4.4 What this says about step size: base and alignment are one knob, not two

They are not independent, and the arithmetic says so without any model:

- The alignment window is `amax/s ∈ [c, c·g)`, whose **width is the base**. As `g → 1`, `c(u,g) =
  max_norm/g^(1−u) → max_norm` for every `u`: the scale converges to the real-valued absmax scale
  and **the alignment knob disappears**. A fine ladder is pinned near `u = 0`.
- `u = 0` is measurably the *worst* alignment in the whole family on 4 of 5 checkpoints — pythia
  46.9561, opt 31.8092, smollm2 22.7120, qwen (u=0 not measured this wave) — against optima 2.4,
  0.7 and 2.0 ppl below.
- So a zero-adder fine ladder buys resolution and **pays it back by surrendering the knob that
  §1 shows is worth 0.25–2.83 ppl**. On SmolLM2 that trade is visibly a loss (2^(1/4) at 24.08,
  worse than 2^k at *any* alignment in [0, 0.35]).

At 4 bits of scale field, the honest summary is: **step size is not where the value is.** The value
is in the alignment, the alignment is per-model, and the coarsest base — which costs zero adders
and zero extra field bits — is the one that leaves the most alignment freedom to spend.

---

## 5. Robustness of the surviving (per-model) gain

All of §5 is `align_harden.py` on SmolLM2, which imports every deciding primitive from
`scale_settled.py` rather than re-typing it.

### 5.1 More windows — survives, and grows slightly

Gain of `u = 0.30` over OCP against window count (wikitext-2):

    nw:  10     20     40     60     80    100    120
       2.958  2.789  2.784  2.903  3.022  3.165  3.144

At 120 windows: **+3.1436 ppl, 95 % CI [2.8085, 3.5193]**; at `u = 0.35`, +3.1267,
CI [2.8058, 3.4837]. The 40-window figure (2.83) is if anything conservative.

### 5.2 A second corpus — survives, at half the size

docs-en, **616,319 tokens**, 40 windows. fp32 10.1694, OCP 15.8280.

| u | ppl | gain over OCP | 95 % CI |
|---|---|---|---|
| 0.35 | 14.3683 | **+1.4596** | [1.2480, 1.6948] |
| 0.30 | 14.5723 | +1.2557 | [1.0490, 1.4820] |
| 0.25 | 14.3943 | +1.4337 | [1.2152, 1.6746] |
| 0.20 | 14.5848 | +1.2432 | [1.0022, 1.5117] |
| 0.00 | 15.7629 | +0.0650 | **[−0.1328, +0.2697]** |

The gain transfers across corpora — **at less than half the magnitude** (1.46 vs 3.14). The tuned
`u` is not corpus-specific, but its *value in perplexity* is. And `u = 0`'s interval covers zero,
which is the right sanity check: the no-clamp alignment is worth nothing.

### 5.3 Activations — the knob is larger there, and its optimum was not located

MX shares the scale encoding between weights and activations. Activation blocks quantised with an
unbounded (E8M0-class) field, `act_n` = 383,385,600 non-zero blocks:

| configuration | ppl |
|---|---|
| fp32 | 14.4874 |
| W fp32, A OCP | 28.7520 |
| W fp32, A u = 0.35 | **25.6646** (+3.09) |
| W OCP, A OCP — the MX spec, shared | 66.2715 |
| W u=0.35, A u=0.35 — shared, tuned | **43.7213** (+22.55) |
| W u=0.35, A OCP — split | 49.7034 |

Two things. **The weight-tuned alignment does not hurt activations — it helps them by 3.09 alone,
and 22.55 when shared.** And the activation clamp fraction at OCP is 159,296,972 / 383,385,600 =
**41.55 %** against the log-uniform target 41.504 % — activations are nearly exactly log-uniform,
better than any weight tensor measured.

**Caveat that must not be dropped:** the activation *optimum* was never located. `align_harden.py`
contains a `stage_actscan` for exactly that and its output key is **absent from
`align_harden_smollm2.json`** — it was not run. All that is shown is that the weight-tuned value
also helps activations, not that the two optima coincide.

### 5.4 The tie floor — measured, per model, and it spans three orders of magnitude

| model | store | tie spread at u\* | at OCP | exact E2M1 midpoints at OCP |
|---|---|---|---|---|
| smollm2 | bf16 | 0.0455 | 0.1005 | 1,230,740 / 106,168,320 = 1.1592 % |
| qwen | bf16 | 0.0932 | — | — |
| pythia | fp16 | 0.5358 | 0.5338 | 123,783 / 84,934,656 = 0.1457 % |
| opt | fp16 | 0.0667 | 0.0667 | 120,379 / 84,934,656 = 0.1417 % |
| gpt2 | fp32 | 0.0003 | 0.0003 | 14 / 84,934,656 = 0.0000165 % |

Predicted bf16 : fp16 midpoint ratio `2^(10−7) = 8`; measured **7.96**. The nuisance is set by the
checkpoint's **release dtype**, not by anything about the method — and it varies by three orders of
magnitude across the five models being compared. Worst-case gain for SmolLM2 (tuned at its worst
tie rule against OCP at its best): **+2.6970**, still far outside the floor.

Control: **dtype does not explain the `u*` spread.** `u* = 0.25` for fp16 OPT *and* fp32 GPT-2;
0.40 for fp16 Pythia; 0.30 and 0.35 for the two bf16 models. No pattern.

### 5.5 A cross-instrument gate FAILED, and the cause is a singularity at the specification

`gate_smollm2.log` (`u_surface.py` model gate 11) reproduces `scale_settled.py` **exactly** at
three alignments and fails at one:

    u=0.00000  ppl=22.7120  established=22.7120  diff=-0.0000   [ok]
    u=0.35000  ppl=20.6950  established=20.6950  diff=+0.0000   [ok]
    u=0.41504  ppl=24.1633  established=23.5224  diff=+0.6409   [FAIL]
    u=0.50000  ppl=27.7307  established=27.7307  diff=-0.0000   [ok]

The harness did the right thing — it refused to report the surface. **The cause is arithmetic and
is proved here without a model:**

`u_OCP = 1 − log₂(6/4) = 0.41503749927884381` gives `c = 6/2^(1−u) = 4.0` **bitwise** (IEEE-754
pattern `4010000000000000`). Rounding `u` to five decimals, `0.41504`, gives
`c = 4.0000069334772848`. Then for any block whose maximum is an **exact power of two**:

    c = 4.0            amax = 4 -> amax/c = 1.0            floor = 0  -> amax/s = 4   no clamp
    c = 4.0000069      amax = 4 -> amax/c = 0.99999826...  floor = -1 -> amax/s = 8   CLAMPS

The scale halves, and the block maximum clamps from 4 to `max_norm = 6` — a 25 % error on the
largest element in the block. On SmolLM2 at K = 32 that set is **29,746 of 3,317,760 blocks =
0.897 %** (`u_atoms_smollm2.json`, `n_t1`), which is 1/128 of the blocks because bf16 has 128
mantissa atoms per binade.

**The alignment axis has a singular set at `c` = a power of two, and the OCP specification sits
exactly on it.** A 2.5 × 10⁻⁶ rounding of `u` costs **0.6409 perplexity** — larger than the entire
tuned gain of three of the five models (pythia 0.2457, qwen 0.5100, gpt2 0.6280).

Status of that attribution: the mechanism is **proved** (exact arithmetic above); the assignment of
the whole 0.6409 to it is **corroborated but not isolated** — the two instruments agree bitwise at
all three non-singular `u` tested and disagree only at the singular one, but the direct A/B (rerun
`u_surface.py` at exact `U_OCP`) needs weights and could not be run (§8). Consequences:

1. **The trusted number for OCP is 23.5224** (`scale_settled.py`, `c = 4.0` literal, which is the
   specification's own rule `X = 2^(floor(log₂ amax) − emax)`). 24.1633 is an artefact.
2. Every `u_surface.py` cell **at a power-of-two `c` reached through a rounded `u`** is suspect.
   The 24-cell surface in §1.4 uses the grid {0, 0.125, 0.25, 0.375, 0.5}, on which E2M1 gives
   `c` = 3, 3.2716, 3.5676, 3.8905, 4.2426 — none a power of two. E3M0 at `u = 0` does give
   `c = 8` and INT4 at `u = 0` gives `c = 3.5`, but `u = 0` is exact in binary, so `c` is computed
   exactly and the singularity cannot fire; the gate log confirms 0.00 % block-max clamp there over
   3,317,760 blocks. **§1.4 stands.** The trap is specific to an irrational `u` written to finite
   decimals, which is what the OCP constant is.
3. Prediction, unmeasured: the same rounding costs GPT-2 essentially nothing (1 block in 8.4 M
   rather than 1 in 128).

---

## 6. Prior art, named honestly

**The premise this wave was handed — "alignment is fixed by every specification and tuned by none"
— is false, and the correction is the most important paragraph in this document.**

### 6.1 The knob has a name in the FP4 literature: 4/6

> "In terms of scale initialization, **4/6 (Cook et al., 2026) extends AbsMax scaling by
> additionally evaluating a scale that maps the block maximum to 4 instead of 6 and selecting the
> lower-error quantization.**" — ScaleSweep, arXiv:2606.07618, §2

> "**4over6 (Cook et al., 2025) adaptively chooses the scaling range of NVFP4 blocks between 6 and
> 4** to reduce quantization error." — SOAR, arXiv:2605.12245, §2

Primary: **Jack Cook, Junxian Guo, Guangxuan Xiao, Yujun Lin, Keith Wyss, Mahdi Nazemi, Asit
Mishra, Carlo del Mundo, Tijmen Blankevoort, Song Han. "Four over six: More accurate NVFP4
quantization with adaptive block scaling." arXiv:2512.02010.** Its abstract states it addresses
"non-uniform step sizes" by "adaptively scaling some blocks to smaller FP4 values, making the
distribution of representable values more uniform and reducing quantization error for near-maximal
values", evaluated on a Nemotron-3 Nano 30B-A3B training recipe.

"4" and "6" **are our alignment constant `c`.** The difference is the base, and it matters: NVFP4's
scale is an FP8 E4M3 value, fine enough to hit a target ratio nearly exactly, so "map to 4" there
means `amax/s = 4` — *less* clamping. With a power-of-two scale, `c = 4` means `amax/s ∈ [4, 8)` —
46.57 % of SmolLM2's blocks clamp. **Same constant, opposite clamp behaviour, because of the base**
— which is §4.4's point arriving from the literature side.

### 6.2 And it is swept, not just switched

- **ScaleSweep** (Li Lin, Xiaojun Wan, Peking University; arXiv:2606.07618): "sweeps over feasible
  block scale candidates and selects the candidate that minimizes a target objective", with derived
  lower/upper bounds on the sweep range under **MSE and weighted MSE**; NVFP4, Llama-3.1/3.2 and
  Qwen3; reports >93 % of full-precision performance under end-to-end W/A/KV/Q quantisation.
- **SOAR** (arXiv:2605.12245): Decoupled Scale Search — discrete search over FP8-representable
  neighbours for the dequantisation scale, continuous multiplicative search for the quantisation
  scale, alternating with a closed-form analytical update, 15 iterations, calibration-free,
  MSE objective. It explicitly criticises 4/6 as "restricted to a simple binary choice between
  predefined ranges, which lacks the sufficient resolution".

### 6.3 The general clipping-threshold literature is older and larger

- **ACIQ** (Banner et al., openreview `B1x33sC9KQ`): finds the optimal clipping threshold
  **analytically** from the tensor's distribution by minimising MSE, avoiding a candidate search.
- **OCTAV** — Optimally Clipped Tensors And Vectors (Sakr et al., ICML 2022, arXiv:2206.06501): a
  recursive **Newton-Raphson** algorithm for MSE-optimal clipping scalars, per tensor, per
  iteration, during QAT.
- **Chhugani et al., arXiv 2603.08713**: Overflow-Aware Scaling and Macro Block Scaling for MXFP4
  — and the 4-bit scale-field truncation that this campaign's WIDTH knob re-measured.

### 6.4 What is left that is ours

Honestly, and it is less than the brief assumed:

1. **A base-independent reparameterisation** (`u` = target clamp fraction under log-uniform block
   maxima) that makes "the alignment" comparable across bases and formats and gives the spec
   constants closed forms: OCP MX = 0.41504, RNE-on-the-exponent = 0.5, floor-on-`amax/max_norm` =
   1.0, absmax/no-clamp = 0. I found no prior source stating it this way; absence of evidence.
2. **The judge.** Every work above optimises squared error. §2.2 is a measurement, in this
   repository, that squared error moves opposite to perplexity on a real intervention. Our `u*` is
   measured by perplexity, and it disagrees with the MSE optimum by 1–3 grid steps on 3 of 3
   models where both are known.
3. **The transfer failure and the minimax result.** None of the works above reports a leave-one-out
   test of a single global alignment across model families, nor the finding that the specification
   is the best worst-case choice. §1.2, §1.3.
4. **The singularity at `c` = a power of two.** §5.5. Directly relevant to anyone implementing a
   swept alignment on a power-of-two scale — which is MXFP4, not NVFP4.

---

## 7. What this wave refutes or narrows — ours included

| # | claim | status | killed by |
|---|---|---|---|
| 1 | "`u* ≈ 0.30–0.35` is the alignment" | **REFUTED** | 3 new families land at 0.25, 0.25, 0.40 (§1.1) |
| 2 | "retuning `c` buys 2.83 ppl" | **NARROWED** to 0.25–2.83, per model, inside the nuisance on 1 of 5 (§1.1) |
| 3 | "alignment is fixed by every spec and tuned by none" | **REFUTED as literature** | 4/6, ScaleSweep, SOAR, ACIQ, OCTAV (§6) |
| 4 | "u\* is a property of (K, element format)" | **REFUTED** | between-model spread equals across-K spread (§1.4) |
| 5 | "the hidden law is a fixed clamp fraction" | **REFUTED** | 17.6-point spread vs `u`'s 15 (§2.3) |
| 6 | "φ beats 2^k as a scale ladder" | **REFUTED** (prior wave, re-stated) | at equal tuning 2^k wins on both models (§3) |
| 7 | "finer ladders are better" | **REFUTED** | the two models order the bases oppositely (§4.1) |
| 8 | "4-bit scale field is enough" | **NARROWED to base 2** | 15·log₂(g) binades; unmeasured for √2, 2^(1/4) (§4.3) |
| 9 | "MXFP4's alignment is a mistake" | **INVERTED** | minimax over five families is the spec's own constant (§1.3) |
| 10 | `u_surface.py`'s OCP cell = 24.1633 | **WITHDRAWN** | 5-decimal rounding of `u` off a power-of-two `c` (§5.5) |
| 11 | "degree 4 is where the ladder stops being cheap" | **SUPERSEDED** (earlier wave, recorded) | `r^d = r+1` is one adder at every `d` (§3) |

**What survives, at its real strength:** *alignment is a free per-model tuning knob worth
0.25–2.83 perplexity at identical bit cost; it must be measured per checkpoint; on one of five
models it is inside that model's own nuisance floor; and no fixed value of it beats the
specification across families.* That is a smaller claim than the one this wave was asked to harden,
and it partially **vindicates OCP** rather than faulting it.

**Consequence for the paper.** `tnf_paper_v2.tex` was rebuilt around alignment and titled *Base,
Alignment, Width*. The three-knob taxonomy survives; the **value attached to the alignment knob does
not**. It must be restated as per-model tuning, the minimax-is-the-spec finding must be stated
because it is the more interesting result, and §6 must be added — the knob is not virgin ground.

---

## 8. What could not be measured this wave, and why

**No new perplexity was measured. No new weight statistic was measured. This document is a
synthesis of measurements already on disk plus a literature search that was run.** The reason is
environmental and is stated in full because it bounds everything above:

1. **The checkpoints are gone.** The brief names five at
   `…/0e868af8-…/scratchpad/weights/`. That directory now contains `wikitext2-test.parquet` and a
   `smollm2/` holding **only** `config.json`, `generation_config.json`, the tokenizer files and
   `vocab.json` — **no weight file at all**. Qwen, Pythia, OPT and GPT-2 are absent entirely.
2. **The one other copy on the machine is truncated.** A sibling session's scratchpad
   (`…/4ee033a3-…/scratchpad/w/smollm2/model.safetensors`) holds **15,863,808 bytes**; a 135 M
   parameter bf16 checkpoint is ≈ 270 MB. It is an in-progress or dead download. Per this
   campaign's own catalogue — a resumed download that spliced two byte streams and **passed a size
   check** — I did not use it. `~/.cache/huggingface/hub` holds only empty stubs for all five.
3. **The stated venv does not exist.** No `ppl-venv` at the given path. Read-only analysis used
   `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3` (torch 2.11.0,
   transformers 5.14.1, pyarrow 25.0.0), not the torch 2.13 the brief names.
4. **Shared machine.** Load average 4.9–17 throughout; sibling agents were running `u_surface.py`,
   `u_theory.py`, `align_harden.py` and a place-and-route concurrently. A run-to-run difference of
   1 × 10⁻⁴ ppl from thread count is on record (pythia fp32: 25.9560 at 5 threads, 25.9561 at 4).
   Treat 0.0003 as the instrument floor — below every effect reported here, and exactly the size of
   GPT-2's entire tie-rule spread.

**Consequently unrun, in priority order:**

1. **§4.2 — each zero-adder base (√2, 2^(1/4)) at its own best alignment.** The single most
   valuable missing number; without it §4 rests on a no-self-test instrument at one alignment.
2. **§4.3 — per-tensor block-maximum span, and `nclip` at 16 levels for g ∈ {2, φ, √2, 2^(1/4)}.**
   No forward pass needed; ≈ 1 minute given weights.
3. **§5.5 — `u_surface.py` rerun at exact `U_OCP`**, to isolate the 0.6409 rather than attribute it.
4. **§5.3 — `align_harden.py actscan`**, to locate the activation optimum instead of assuming it
   coincides with the weight one.
5. A Qwen `u`-curve at 40 windows in this wave's instrument; Qwen contributes only `u*` and its
   gain to §1.1, and SmolLM2 has no measurement at `u = 0.40`/`0.45` — the region where Pythia's
   optimum sits. The "no single `u` beats OCP on all four" statement in §1.3 is therefore carried
   by OPT and GPT-2 losing at `u = 0.40`, not by SmolLM2.

**Scope of everything above:** five checkpoints, all 125 M–500 M parameters; wikitext-2 test plus
one 616 k-token second corpus on one model; block sizes 16/32/64/128 on two models at 8,192 tokens
and 32 elsewhere; element formats E2M1/E3M0/INT4 on two models, E2M1 on five; base 2 for the
five-family result; weight-only except §5.3. GPT-2 alone runs at seqlen 1024
(`max_position_embeddings = 1024`), so its perplexity *level* is not comparable with the others —
only its own `u`-curve is.

---

*Sources for §6, fetched and read on 2026-08-12 rather than cited from memory:*
[arXiv:2512.02010](https://arxiv.org/abs/2512.02010) ·
[arXiv:2606.07618](https://arxiv.org/pdf/2606.07618) ·
[arXiv:2605.12245](https://arxiv.org/pdf/2605.12245) ·
[arXiv:2206.06501](https://arxiv.org/abs/2206.06501) ·
[ACIQ](https://openreview.net/pdf?id=B1x33sC9KQ) ·
[arXiv:2509.23202](https://arxiv.org/html/2509.23202v2).
*The ScaleSweep and SOAR quotations are from `pdftotext` extractions of the fetched PDFs, lines 239
and 294 respectively; the 4/6 abstract was read through an automated fetch, and its verbatim text
beyond the first sentence was not retrieved — flagged rather than paraphrased as if it had been.*
