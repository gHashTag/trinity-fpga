# α = 1.600 was one noise draw. The loss is quadratic, and the claim was correctly withheld

`sensitivity.py` fitted OPT-125M's response to a fixed-relative perturbation at
`rel ~ eps^1.600`, with per-step ratios 2.691, 3.042, 3.399 against the 4.000 a
smooth second-order expansion gives. The tempting reading was that the quadratic
form does not govern at these sizes — a statement about the standing assumption
underneath the OBQ/GPTQ family.

**It was not claimed**, because the confound was identifiable before the data:
for isotropic noise the first-order term `g·n` has expectation **zero**, but a
*single draw* realises one of typical size `|g|·eps·|w|`, which scales as `eps¹`
and would bend α below 2 at small eps — exactly the observed shape.

`seed_control.py` separates the two. Five seeds per eps on OPT-125M, same
perturbation path, zero-eps control bit-identical to the ruler:

| eps | **mean over 5 seeds** | ratio | **spread across seeds** | ratio |
|---:|---:|---:|---:|---:|
| 0.005 | +0.037 % | — | 0.0657 pp | — |
| 0.010 | +0.145 % | **3.92** | 0.1312 pp | **2.00** |
| 0.020 | +0.576 % | **3.97** | 0.2624 pp | **2.00** |
| 0.040 | +2.350 % | **4.08** | 0.5240 pp | **2.00** |

Fitted over all four:

| | exponent | theory |
|---|---:|---:|
| **mean over seeds** | **1.998** | 2.000 — a locally quadratic loss |
| **spread across seeds** | **0.999** | 1.000 — a realised first-order term |

**Both within 0.1 % of their theoretical values over four perturbation sizes.**
That is the confound demonstrated rather than argued: the linear term is present,
it cancels in expectation, and a single draw does not cancel it. There is no
room left for an alternative reading.

## Consequences

**1. α = 1.600 is withdrawn.** The loss is locally quadratic in these weights on
this data, as a smooth expansion predicts. No claim about the second-order
assumption in the quantisation literature follows, and none is made.

**2. Every single-seed sensitivity figure in this directory must be re-read.**
That is `sensitivity_opt.json` and `sensitivity_gptneo.json`. They are not wrong
about *magnitude* — at eps = 0.02 the single-seed OPT figure is +0.895 % against
the 5-seed mean of +0.576 %, the same order — but their **exponents** are
one-draw artefacts and must not be quoted. `sensitivity.py` should be run with
seeds or not at all; a multi-seed run on the two cost extremes is in progress.

**3. The single-seed contamination is worst exactly where the measurement is
most interesting.** The spread/mean ratio falls as eps grows — 1.8 at
eps = 0.005, 0.9 at 0.010, 0.46 at 0.020 — so a single draw is *dominated* by
noise precisely in the small-perturbation regime a quantisation study cares
about.

## What survives, and it is the interesting part

GPT-Neo-125M, the +174.4 % cost extreme, measured on the same four-eps ladder
(single seed, so its **exponent** 2.305 is subject to the same caveat, but its
**magnitudes** are not the thing in doubt):

| eps | OPT-125M | GPT-Neo-125M | ratio |
|---:|---:|---:|---:|
| 0.01 | +0.294 % | +0.600 % | **2.04×** |
| 0.02 | +0.895 % | +2.959 % | **3.31×** |
| 0.04 | +3.04 % | +13.65 % | **4.49×** |

**GPT-Neo is measurably more sensitive to the same perturbation**, in the
direction the 21× MXFP4 cost spread requires — and it is the first quantity in
this campaign that differs between checkpoints in the right direction after the
weight side was closed. The sensitivity ratio at eps = 0.02 is 3.3× against an
MXFP4 cost ratio of 14.9×, so it does **not** account for the whole spread on
these two points, and nothing is claimed about the eight-checkpoint relationship
until the multi-seed sweep exists.

**Nothing here is a result yet.** It is the first place the campaign has looked
where the numbers differ in the right direction, and the instrument that measures
them has just been shown to need seeds.

---

*OPT-125M and GPT-Neo-125M, 40 × 2048 windows of wikitext-2, the same target
tensors every campaign measurement quantises, isotropic Gaussian noise at fixed
relative RMS per tensor, seeds 20260812…+4. Zero-eps control reproduces the fp32
ruler bit-identically on every run; a run whose control fails prints ABORT and
returns 4 rather than a number.*
