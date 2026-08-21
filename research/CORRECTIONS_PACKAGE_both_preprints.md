# Corrections package — arXiv:2606.05017 and arXiv:2606.09686

**Status: DRAFT IN REPOSITORY. Submitted nowhere.** Whether to file any of this is
the author's decision. The package exists so that decision can be made once, from
evidence, instead of four times from memory.

**Verified:** passes 248–254, by scripts in this directory, against the corpus and
against the 226 comments of gHashTag/trinity-fpga#199.

**As of pass 287 every one of the ten items has an executable check.** Items 5, 6,
4, 1 and 9 acquired theirs in passes 283–287; before that their numbers were
computed in a session and typed into markdown, which is the same defect several of
them complain about. The tools are named in each section and all of them exit
non-zero if the finding stops being true:

| item | tool |
|---|---|
| 1 GF64 chain | `research/audit_gf64_chain.py` |
| 2, 3 arithmetic claims | `research/audit_arithmetic_claims.py` |
| 4 DSP inference | `research/audit_dsp_inference.py` |
| 5 W² cost model | `research/audit_cost_model.py` |
| 6 additional cores | `research/audit_additional_cores.py` |
| 7, 10 workloads | `research/workload_suite.py`, `research/workload_matmul.py` |
| 8 E8M0 packs | `conformance/e8m0_ref.py` self-test |
| 9 cite keys | `research/audit_cite_keys.py` |

---

## Summary

Eighteen quantitative claims have been recomputed. **Nine reproduce cleanly**, one
is a sensitivity note rather than an error, and **eight need action** — one of
those (item 9) is a submission defect rather than a claim, and one (item 8) is
already closed by code in this repository.

**Still not attempted:** whether the cited competitor figures are represented fairly —
PERI's 3507 LUTs, the takum codec's −38% latency and −50% LUT. That needs the
publications themselves, and both web tools were unavailable in the session that
would have checked them. It stays open rather than being guessed at.

| # | claim | paper | verdict |
|---|---|---|---|
| 1 | GF64 reaches 70.1% (359/512) | 2606.05017, and repeated in the catalog draft | **evidential** — no complete chain |
| 2 | "5/11 values flushed to zero" | 2606.05017, abstract + contributions | **wording** — body is correct |
| 3 | "GF16 preserves 8.7× more gradient updates" | 2606.09686, abstract | **sensitivity note**, not an error |
| 4 | "DSP48E1 only when explicitly instantiated" | 2606.09686, abstract + §flags | **factual** — no wrapper uses it, and 915 targets infer it |
| 5 | LUT_ADD ≈ 1.63 W², R² ≥ 0.97 | 2606.05017, §cost | **no subset fits** — c is a window, not a constant |
| 6 | 505 / 587 / 580 LUT | 2606.05017, lines 56 and 132 | **traced** — 505 is takum16's, and the 75 does not reproduce |
| 7 | "seven formats across seven workloads" | 2606.05017, abstract | **reimplemented** — the cited script has four suites, one of them one of the seven; all seven now runnable here |
| 8 | "six conformance packs", including E8M0 | 2606.09686 abstract, and its erratum | **closed** — the E8M0 oracle and packs now exist |
| 9 | three `\cite` keys resolve to nothing | 2606.05017, §§ on RHT/LSQ and Parameter Golf | **submission defect** — `[?]` in the built PDF; confirmed from source, 21 cited / 18 defined |
| 10 | "no single format dominates" | 2606.05017 + 2606.09686, abstracts | **contradicted** — posit16 dominates GF16 on all seven |

What reproduces, for context: the 2.4M vector count (2,442,533), 41 decode cells,
10 GF compute formats, FP16 losing 5 of 11 dynamic-range values, GF16 losing 1,
the BF16 and GF16 noise floors (7.9% and 63.7% against 7.3% and 63.9%), and the
LUT table across twelve measurements with a largest deviation of 56 LUTs. Details
and tools in `research/PAPER_CLAIM_VERIFICATION.md`.

---

## 1. GF64 at 70.1% (359/512) — evidential

Full analysis: `research/ERRATUM_arXiv_2606.05017_gf64_claim.md`.

The figure is **not invented**. Seventeen comments investigate GF64 carefully, one
of them retracting an earlier theory. But no single GF64 comment carries all four
Tier-E links, and 359/512 is the highest of four silicon results spanning
19.2%–70.1%, from the build the next comment's own table labels "shift-reg
(buggy)". Every build with that path fixed scored lower.

It sits inside an item ending *"Each ships with a full evidence chain."*

**Proposed:** drop the aside, or restate it as an open timing-closure problem
rather than a cell. Suggested wording in the erratum file.

> **Mechanised in pass 285.** `research/audit_gf64_chain.py` replaces the reading
> with a check. It takes every comment mentioning GF64 by any spelling — **17**,
> matching the seventeen described above — and counts the four links in each one
> individually, rather than trusting the absence of `gf64` from
> `verify_tier_e.py`'s cell list, which groups by a parsed name and could have hidden
> a comment in its `?` bucket.
>
> **Zero of the 17 carry all four.** And the picture is sharper than that number:
>
> * The **359/512 figure and the evidence are in different comments.** It originates
>   in [#4965993162](https://github.com/gHashTag/trinity-fpga/issues/199#issuecomment-4965993162),
>   which records an IDCODE and a flash (`openocd 500kHz, 156s`) but carries **no CI
>   URL, no SHA-256 and no UART line at all**. Two later comments tabulate it and
>   both label its build *"shift-reg (buggy)"*.
> * The closest thing to a complete chain is
>   [#4958733671](https://github.com/gHashTag/trinity-fpga/issues/199#issuecomment-4958733671),
>   which has the CI URL, the SHA-256, the IDCODE **and a genuine board reading** —
>   `HW RESULT: GF64 ADD smoke 0+0=0x0000000000000000 @160000 IDCODE=0x13636093`.
>   That is a **one-vector smoke test**, not an N/N conformance count, and its score
>   is 4/4. Real silicon, not the 512-vector run the 70.1% describes.
>
> So the accurate statement is not that GF64 was never on the board. It was. What
> does not exist is a single comment tying the 359/512 number to a CI run, a
> bitstream hash and a conformance read — and the one comment with a board reading
> reports a different, much smaller test.

## 2. "5/11 values flushed to zero" — wording

Verified with `research/audit_arithmetic_claims.py` against `ieee_ref` and
`gf_ref`:

| value | FP16 (E=5) |
|---|---|
| 1e-10, 1e-8 | flush to zero |
| 1e-6 … 1e4 | representable |
| 1e6, 1e8, 1e10 | **overflow to infinity** |

Five of eleven are lost — the count is right in both places. Two flush to zero;
three fail at the **opposite end** of the range. The body's *"loses 5/11"* is
correct; only the abstract and the contributions list misstate the mechanism.

**Proposed:** in the abstract and contributions list, replace "flushed to zero"
with "lost" or "outside the representable range".

## 3. "8.7× more gradient updates" — sensitivity, not an error

63.9 / 7.3 = **8.75×**, which rounds to 8.7. The claim follows from the paper's
own numbers.

Recomputed from the oracles with the paper's own protocol — 2000 sequential steps
from w=0.5, updates from N(1e-4, 1e-3), re-quantised each step, five seeds — the
preserved fractions are 7.9% and 63.7%, giving **8.06×**.

Both are correct about their inputs. The ratio is sensitive to the BF16
denominator, which is the smaller and noisier of the two numbers.

**Proposed:** nothing is wrong. If a revision is being made anyway, "roughly 8×"
is more robust than "8.7×" to the seed and step count.

## 4. "DSP48E1 is used only when explicitly instantiated" — it is inferred, 915 times

Two separate problems with one sentence.

### 4a. The cited example does not use a DSP

`fpga/openxc7-synth/gf_mul_dsp_param.v` exists and does instantiate `DSP48E1`.
**No wrapper instantiates it.** The only two files referencing it are itself and a
comment in `gf_mul_param.v` saying the DSP mapping lives elsewhere.

`corona_compute_gf16_mul_ax7203.v` instantiates `gf_mul_param` — the LUT-only
version. That is consistent with `-nodsp` and with the 586/602 LUT measurement,
and inconsistent with GF16 MUL being *the example* of explicit DSP instantiation.

### 4b. The flag rule lets DSPs be inferred anyway

`.github/workflows/build-matrix.yml` adds `-nodsp` **only when the op is `mul`**.
Measured under those exact flags:

| target | LUT | DSP |
|---|---|---|
| gf16 **sqrt** | 334 | **8** |
| gf16 **fma** | 992 | **1** |
| gf16 **alu** | 952 | **1** |
| gf16 add / div / quire / mul | 625 / 430 / 107 / 742 | 0 |

The rule catches the one op that does not need it and misses three that do.
**915 of the 3,203 compute targets** have an op ending in sqrt, fma or alu, and
every one of them is synthesised with DSP inference left on — the block Project
X-Ray documents as only partially reverse-engineered, which is the stated reason
for `-nodsp` in the first place.

> **Softened in pass 285.** This sentence previously said every one of the 915
> *would infer* a DSP. That was generalised from three gf16 targets.
> `research/audit_dsp_inference.py` verifies the count exactly — 10 sqrt + 452 fma
> + 453 alu = 915 — and samples the inference across the width range rather than at
> one width, because DSP mapping depends on operand width. **13 of 15 sampled
> targets inferred one; two did not**, both `afp`, which is variable-width and
> whose ALU and FMA come out at 189 and 426 LUTs with zero DSPs. Every sampled
> `sqrt` took 8 DSPs regardless of width, down to `gf4`. So the defensible claim is
> that the rule leaves DSPs *possible* on 915 targets and most of them take one —
> which is enough to contradict "only when explicitly instantiated" without
> overstating the reach.

No Tier-E cell is affected: **zero** complete-chain cells carry op SQRT, FMA or
ALU.

### Why this is reported and not fixed

Extending `-nodsp` is a resource trade, not a bug fix:

| target | as CI builds it | with `-nodsp` |
|---|---|---|
| gf16 sqrt | 334 LUT, 8 DSP | **3,566 LUT**, 0 DSP |
| gf16 fma | 992 LUT, 1 DSP | 1,242 LUT, 0 DSP |
| gf16 alu | 952 LUT, 1 DSP | 1,238 LUT, 0 DSP |

Eight DSPs against three thousand LUTs on a part with 134,600 of them is a
judgement about which resource is scarce and which is trustworthy.

**Proposed:** say that DSP48E1 is disabled for MUL and inferred elsewhere, or
extend the rule and accept the LUT cost. As written the sentence describes neither
the code nor the flow.

## 5. The W² cost model — the coefficient is a window, not a constant

Fitted through the origin to the paper's own published tables:

| set | n | c | R² |
|---|---|---|---|
| ADD, GF4–GF24 (the stated range) | 9 | 1.588 | 0.9371 |
| ADD, GF4–GF32 | 10 | 1.350 | 0.9272 |
| **ADD, GF4–GF48** | **11** | 1.245 | 0.9815 |
| ADD, all measured | 14 | 0.928 | 0.9951 |
| MUL, GF4–GF24 | 9 | **2.089** | **0.9770** |

**No set reproduces c_ADD = 1.63 with R² ≥ 0.97.** The only set with exactly
eleven points — the count the paper cites — gives c = 1.245.

The reason is visible in the per-point ratio LUT/W², which falls monotonically
rather than holding constant:

| W | 4 | 6 | 8 | 12 | 16 | **20** | 24 | 32 | 64 | 128 |
|---|---|---|---|---|---|---|---|---|---|---|
| c | 0.94 | 2.78 | 2.67 | 1.97 | 1.90 | **1.61** | 1.42 | 1.21 | 1.05 | 0.91 |

**1.63 is approximately the value at W = 20**, not a property of the family.

With a free exponent, `LUT = a·W^b`:

| | a | b | R² (linear) | R² (log) |
|---|---|---|---|---|
| ADD, all 14 measured | 3.194 | **1.754** | 0.9913 | 0.9746 |
| MUL, GF4–GF32 | 0.791 | **2.361** | 0.6254 | 0.9044 |

ADD is **sub-quadratic** over the measured range and MUL is **super-quadratic**.
A shared W² model with a single coefficient is a compromise between them rather
than a fit to either.

> **Both R² conventions, corrected in pass 283.** This table previously showed one
> R² column, holding the log-space values, directly beneath the quadratic table
> whose R² is linear-space — two different statistics under one heading, in an
> argument whose entire subject is an R² threshold. The gap is wide: MUL reads
> 0.9044 in log space and 0.6254 against the raw counts. Neither is wrong. Fitting
> on logs weights the small formats far more heavily, which is often what one wants
> from a scaling law; measuring against the raw counts is what "R² ≥ 0.97" means
> when a paper says it about LUT counts. Reporting one under the other's heading
> was the error. **The conclusion is unaffected** — every quadratic fit above is
> linear-space and none reproduces c = 1.63 with R² ≥ 0.97.

All of the above regenerates from `research/audit_cost_model.py`, which reads the
measured rows of `research/COMPLETE_LUT_TABLE.md` and refits. The extrapolated
(`~`) rows are excluded: they were produced *by* the scaling law under test, and
feeding them back in would be circular.

**Proposed:** state the fitting window with the coefficient, or report the fitted
exponents. As written, "1.63 W², R² ≥ 0.97, 11 measured points" does not
correspond to any subset of the published table.

## 6. 505 / 587 / 580 LUT — traced, and one entry does not reproduce

The three numbers come from `research/COMPLETE_LUT_TABLE.md`'s "additional cores"
table, and tracing them there makes the problem precise rather than merely
inconsistent:

| core | table | measured here | |
|---|---|---|---|
| Ternary MAC-16 | 55 LUT | **55** | exact |
| GF Sqrt | 128 LUT, 8 DSP | **128 LUT, 8 DSP** | exact |
| GF Div | 207 LUT | **207** | exact |
| **GF Quire** | **75 LUT, 0 DSP** | **1063 LUT, 0 DSP** | **14×** |
| takum16 native MUL | 505 LUT | — | |
| GF16 | 485 ADD / 587 MUL | 490 / 602 | ordinary build drift |

Three of the four modules reproduce **exactly**, which is what makes the fourth
meaningful. The GF Sqrt row needed DSP inference left on — forcing `-nodsp` gives
4818 LUTs, and that was my error, not the table's.

So:

* **505 is takum16's multiply** in the source table, not GF16's. GF16's multiply
  is 587 there.
* Line 132's "580 LUT (505 multiply + 75 Quire)" therefore uses takum16's
  multiply figure for a GF16+ MAC, together with a Quire figure that does not
  reproduce.
* Line 56's "GF16 multiply-with-Quire (505 LUT) … plain GF16 multiply is 587 LUT"
  has a Quire with negative area under any reading.

**Proposed:** re-measure `gf_quire_param` and restate the MAC total. If the Quire
is genuinely 1063 LUTs, the GF16+ MAC is roughly 1650, not 580.

## 7. "Seven formats across seven workloads" — six of the workloads are not here

The abstract's central result is that GF16 is *the minimum-width IEEE-style format
that passes all seven tests*. The seven are named as four ML — matrix multiply,
gradient accumulation, dynamic range, attention softmax — and three hold-out —
convolution, polynomial evaluation, linear solve.

`research/format_benchmark.py`, which the paper cites as "the benchmark script",
implements **four suites**: `arithmetic`, `dynamic_range`, `cancellation`,
`edge_cases`. Only `dynamic_range` is one of the seven.

**Matrix multiply, gradient accumulation, attention softmax, convolution,
polynomial evaluation and linear solve appear in no script in the repository.**

### What implementing them showed

All seven are now runnable: `research/workload_matmul.py` (matrix multiply),
`research/workload_suite.py` (gradient accumulation, attention softmax,
convolution, polynomial evaluation, linear solve), and `dynamic_range` in
`format_benchmark.py`.

The first numbers I produced were wrong, and the correction matters more than the
original. Dividing the error by the exact **result** makes it explode wherever a
sum of products cancels — matrix multiply reported BF16 at 184%, and convolution
reported ≈54% for BF16, GF14 and GF16 *alike*, three formats sharing one number
that belonged to the inputs. Dividing instead by the **scale of the work**,
`Σ|a·b|`, is the standard normwise form and separates conditioning from precision.

Normwise, worst trial / median trial:

| workload | BF16 (M=7) | GF14 (M=8) | GF16 (M=9) | FP16 (M=10) |
|---|---|---|---|---|
| matmul, uniform[-1,1] | 0.71 / 0.49 | 0.31 / 0.26 | 0.14 / 0.12 | 0.06 / 0.06 |
| matmul, normal(0,1) | 1.16 / 0.52 | 0.43 / 0.27 | 0.25 / 0.14 | 0.09 / 0.06 |
| convolution | 0.84 / 0.54 | 0.30 / 0.24 | 0.17 / 0.12 | 0.07 / 0.06 |
| gradient accumulation | 2.68 / 1.93 | 1.98 / 0.79 | 1.15 / 0.44 | 0.74 / 0.19 |
| attention softmax | 2.57 / 1.46 | 0.92 / 0.59 | 0.44 / 0.30 | 0.30 / 0.16 |
| polynomial | 1.04 / 0.29 | 0.72 / 0.17 | 0.23 / 0.05 | 0.19 / 0.09 |
| linear solve | 14.76 / 1.11 | 8.31 / 0.68 | **0.93** / 0.45 | **1.10** / 0.26 |

**The error halves per mantissa bit** — 0.71, 0.31, 0.14, 0.06 across M = 7, 8, 9,
10. That is 2⁻ᴹ, and it is what precision looks like once conditioning is removed.

**There is no threshold at M ≥ 9.** The curve is smooth. A threshold exists only
once someone fixes an error budget, and none is published — so "M ≥ 9" is a choice
of budget presented as a property of the workload.

Two results survive as genuine, and both are about **range**, not mantissa:
GF14 scores 84.85% on mixed-scale matmul because E=5 lets products underflow; and
linear solve has GF16 beating FP16 on the worst case, 0.93 against 1.10, despite
one fewer mantissa bit, because E=6 beats E=5.

**Proposed:** commit the seven-workload harness, and state the error budget that
turns a smooth 2⁻ᴹ curve into the threshold M ≥ 9. The feasible corner (E=6, M=9),
and with it the φ-ratio result, rests on that budget being stated.

## 8. "Six conformance packs" — five of them are packs

The 2606.09686 abstract names six: GF16, MXFP4 element, BF16, FP8 E4M3, FP8 E5M2,
and E8M0 block scale. Five are present in `conformance/vectors/`. **E8M0 is not.**

No file matches `e8m0` there, and no oracle in `conformance/*_ref.py` carries an
`e8m0` format key.

What E8M0 *does* have is a conformance **host**,
`conformance/e8m0_decode_conformance_ax7203.py`, whose header states its golden is
*"re-implemented from the E8M0 spec, NOT copied from the RTL"* — plus RTL wrappers
and a complete-chain Tier-E decode cell.

**So the hardware claim stands.** What is missing is the pack and the oracle, not
the evidence.

This also touches the existing erratum,
`research/ERRATUM_arXiv_2606.09686_catalog_count.md`, which says:

> the presence of a conformance pack for E8M0 is correct and remains in force —
> the pack covers the block-scale component

There is no pack file to remain in force.

**Closed in pass 266.** `conformance/e8m0_ref.py` is the missing oracle and
`conformance/vectors/e8m0_add.json` and `e8m0_mul.json` are the missing packs,
65,536 vectors each — the format is 8 bits, so both are exhaustive over all
256×256 operand pairs. The oracle's self-test holds it to the host's independent
golden on all 256 codes and passes 10/10.

No `e8m0_sub.json`: E8M0 has no sign bit and no zero, so negation does not exist
and SUB is undefined. `negate_raw` now says so, the same way it already did for
unsigned integers. Without that it fell through to the default branch, flipped
bit 7 — which for E8M0 changes the *exponent* — and produced a 65,536-vector pack
of nonsense, which is what a first run actually wrote before it was caught.

**Amended in pass 276.** `research/ERRATUM_arXiv_2606.09686_catalog_count.md` no
longer says a pack "remains in force". The claim is dropped from the note and the
history recorded beneath it: the sentence was untrue when written, the hardware
claim was never affected, and pass 266 built what was missing. Item 8 is closed
in both directions — the gap and the sentence that papered over it.

## 9. Three citations resolve to nothing

`research/arxiv_submission/paper.tex` uses 21 distinct `\cite` keys.
`research/arxiv_submission/paper.bib` defines 18. Three are defined **nowhere in
the repository**:

| key | cited at | what it supports |
|---|---|---|
| `ufp4` | §Hadamard rotation | prior work whose technique the paper tests |
| `quest` | §Hadamard rotation | the same |
| `paramgolf2026` | §Cross-validation | the OpenAI Parameter Golf result used as external corroboration |

All three are load-bearing rather than decorative. The first two anchor a
**negative result** — *"Following UFP4 and QuEST, we tested Random Hadamard
Transform … neither technique improves results"* — and a reader cannot check what
was followed. The third anchors the claim that an outside competition
independently reached the same INT6 conclusion.

As it stands the built PDF would carry three `[?]` marks.

> **Mechanised in pass 287.** `research/audit_cite_keys.py` collects every `\cite`
> key from the source and every key defined by a `@entry` in the `.bib` *or* a
> `\bibitem` in the `.tex` — both, since a paper can carry a manual
> `thebibliography` and a `.bib` at once, and checking one alone would report keys
> as missing that resolve perfectly well. It confirms the count exactly: **21 cited,
> 18 defined, 3 unresolved**, and **zero defined-but-uncited**, so the bibliography
> has not drifted in the other direction.
>
> One of the three is different in kind. **`paramgolf2026` is a self-citation** —
> Parameter Golf is this project's own work, present here as
> `parameter_golf_gf8_ablation/`, `research/PARAMETER_GOLF_PLAN.md` and
> `research/PARAMETER_GOLF_RESULTS.md`. It is resolvable without leaving the
> repository, unlike `ufp4` and `quest`, which name external publications and need
> those publications to resolve — the same thing blocked for the competitor-figure
> check.
>
> The tool deliberately stops at naming the keys. Inventing a plausible-looking
> bibliography entry for a paper nobody has read would be a worse defect than the
> missing entry.

**Proposed:** add the three entries to `paper.bib`, or drop the sentences that
depend on them.

## 10. "No single format dominates" — posit16 does, on all seven

Both abstracts say a head-to-head comparison *"shows that no single format
dominates across arithmetic, dynamic-range, and cancellation suites"*.

With all seven of the paper's own formats run through all seven of its own named
workloads — median relative error, normwise where the workload is a sum of
products:

| workload | GF16 | GF12 | **posit16** | MXFP8 | BF16 | FP16 | takum16 |
|---|---|---|---|---|---|---|---|
| matmul u[-1,1] | 0.12 | 0.62 | **0.03** | 8.22 | 0.62 | 0.07 | 0.06 |
| matmul mixed | **0.12** | 99.67 | 0.21 | 99.71 | 0.59 | 0.07 | 0.33 |
| gradient accum | 0.27 | 5.33 | 0.17 | 78.95 | 1.93 | 0.20 | **0.13** |
| attention softmax | 0.29 | 48.02 | **0.13** | 100.00 | 1.34 | 0.15 | 0.27 |
| convolution | 0.11 | 0.53 | **0.03** | 8.26 | 0.53 | 0.06 | 0.04 |
| polynomial | 0.07 | 0.20 | **0.04** | 1.18 | 0.20 | 0.09 | 0.08 |
| linear solve | 0.65 | 1.18 | **0.09** | 17.86 | 1.18 | 0.33 | 0.30 |
| dynamic range, lost of 11 | 1 | 3 | **0** | 4 | **0** | 5 | **0** |

**posit16 has lower error than GF16 on all six error workloads and loses fewer
dynamic-range values.** takum16 beats GF16 on four of six.

### What this does not touch

The paper's *other* claim — that GF16 is the minimum-width **IEEE-style** format
passing all seven — survives, and its own wording is why. posit and takum are
tapered, outside that class by construction. Among the IEEE-style entrants GF16
does come out best: BF16 loses no range values but carries higher error
everywhere, FP16 loses five, GF12 and MXFP8 collapse.

So the correction is narrow: the dominance sentence is contradicted, the
minimum-width sentence is not.

**Caveats:** no pass/fail threshold is applied, because the paper's are not
published; and these are reimplementations of the workloads, since the paper's
harness is not in the repository (item 7).

**Proposed:** replace "no single format dominates" with a statement scoped to the
IEEE-style family, which is what the surrounding argument is actually about.

---

## Not checkable from this repository

**"72 of 83 formats carry an independent executable oracle."** The catalog
membership list is `gHashTag/t27/specs/numeric/formats_catalog.t27` in the **t27** repository, not present
here. The oracles carry **84** format keys, several of which are known not to be
catalog rows — `fp16_e6m9` and `fp24_7m16` exist only in the silicon-sprint packs,
`bf16`/`bfloat16` is an alias pair. **84 neither confirms nor refutes 72.**

## Two errors of mine, recorded rather than omitted

1. **LUT drift.** Pass 250 reported a +22% to +79% deviation from the published
   LUT table. That was a parser — yosys `stat` prints three blocks and my counter
   summed across a boundary. Retracted in pass 251; the corrected table shows the
   numbers reproduce.
2. **Noise-floor protocol.** My first run held the weight fixed instead of walking
   it, giving 17.2% and 71.6%.

Both are the same mistake: measuring a reasonable-sounding neighbour of the thing
the method describes. Neither reached a published claim.

## How to regenerate

```
python3 research/audit_paper_claims.py --comments <cached #199 json>
python3 research/audit_arithmetic_claims.py
python3 research/audit_lut_table.py
```
