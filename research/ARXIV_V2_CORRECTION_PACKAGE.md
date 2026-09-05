# arXiv v2 correction package — 2606.05017 and 2606.09686

> Produced 2026-07-31 by a verification pass over the two published abstracts
> against the live artefacts. Every claim below carries how it was verified.
> Nothing here is asserted from memory or from a state file.
>
> **This is a prepared package, not a submission.** Replacing an arXiv entry
> needs the author's arXiv credentials — see §11.

## Executive summary (26 verification passes, 2026-07-31)

> **Read §13 first.** Both preprints have been revised since submission —
> 2606.05017 is at **v3**, 2606.09686 at **v2**, both updated 2026-06-22 — and the
> two headline problems below are present in those *current* versions, not in a
> stale v1. Everything in this package was checked against what arXiv serves today.

**Verdict: the science holds. The defects are in citations and in unstated
distinctions, not in the results.** Every central technical claim that could be
checked without hardware was recomputed independently and passed:

| claim | result |
|---|---|
| φ-rule `e = round((N-1)/φ²)` | **17/17** catalogued widths satisfy it (§10.1) |
| Lucas identity, 500 digits, n = 1…256 | **256/256**, worst residue at the representation floor (§10.4) |
| cross-validation vs ml_dtypes 0.5.4 | **66,224 codes, 0 divergences** — exhaustive, not sampled (`specs/numeric/ml_dtypes_crossval.t27`) |
| SHA-256 fingerprints exist | **yes**, 83 of them (§2.2) |
| Paper A's bibliography | **clean** — 24 IDs resolve, no misattribution (§9) |

### Do these first

| # | action | where | why now |
|---|---|---|---|
| 1 | Remove *"the fabricated TTSKY26b dies"* from Paper A's abstract | §1.1, **§13** | A factual claim about physical artefacts, live on a public preprint — and **it has survived two revisions**: arXiv:2606.05017 is at **v3** (updated 2026-06-22) and still contains it. Replacement wording already exists in trinity-papers-ru PR #17. |
| 2 | Fix Paper B ref **[3]** | §8.1 | Wholly misattributed: wrong authors, wrong title, wrong subject. One clicked link damages the whole bibliography's credibility. |
| 3 | Paper B: **six packs → 83** — but see §12 | §2.1, **§12** | Still the largest positive change, and **cheaper than pass 1 thought**: the manuscript's own v4→v5 changelog shows the submitted body already said *49 bit-exact / 34 structural*, and the local manuscript is already at **v5 (6 July)** saying "all 83". The abstract disagreed with its own body. The action is an **arXiv replacement**, not a rewrite. |
| 4 | Fix the remaining citation defects | §8.2, §8.3, §6.3 | Paper B [19] [20] [4] and Paper A `flops2026`. Corrected entries supplied verbatim. |
| 5 | Cite `arXiv:2607.13898` + add the DSP/soft-logic subsection | §5.1, §5.2 | Nearest FPGA neighbour, and it independently corroborates a finding Paper A never states. |
| 6 | Paper A: cite IEEE 754 and TestFloat | §7.2, §7.2a | TestFloat-3 is the **correctness gate of the pre-registered experiment** and is uncited — an uncited tool dependency, not a related-work nicety. |
| 7 | Restore three verbatim titles; add one sentence on rounding | §9.1, §10.3 | Cosmetic, near-zero cost, removes two referee questions. |

### Blocked on the author — nothing else can move these

Three passes in a row ended at the same wall. Each is one answer, not a project:

- **Which GF widths predate the φ-rule?** Until answered, the `9/9` figure cannot be corrected — it is off in *both* directions (§10.2). `open_question WIDTH_PROVENANCE`.
- **Is "13 families" the catalog's own taxonomy?** Not verified; a module-based grouping gives 15, which would not be a defect. `open_question FAMILY_TAXONOMY`.
- **Where is the accumulator implementation?** The identity verifies; the *path* the paper claims was not executed (§10.4). `open_question ACCUMULATOR_IMPLEMENTATION`.
- Plus one smaller one: which board the 323 MHz figure came from (§1.2). *(The P3109 draft version was listed here too, as "not publicly verifiable". It is settled — the Interim Report is public and simply carries no version number, so cite it by retrieval date. See §6.2.)*

### Blocked on one missing toolchain

`nextpnr-xilinx` (openXC7) is absent. That single gap blocks **three** things at once:
the GF16 `35/35 @ 323 MHz` check (§10.5), post-route P&R numbers that would close
`[method not pinned]` in both papers, and **the paper's own pre-registered FL-002
experiment** (§7.2a). Installing it is the highest-leverage infrastructure action
available.

### Closed — do not reopen

- The P3109 "version conflict" between the papers is **not an error**: they cite two different document series (§8.6).
- `ml_dtypes 0.5.4` is **current**; changing it would break reproducibility (§2.3).
- Tekum, takum and posit are **already cited** in Paper A (§5.4).
- The 11 pack-only structural formats have no decode oracle **by design** (`specs/numeric/catalog_coverage_delta.t27`).

### Artefacts produced

Five `.t27` SSOT specs under `specs/numeric/` (φ-rule, Lucas, coverage delta,
derived packs, ml_dtypes cross-validation) and four runnable checks under
`research/` (`verify_phi_rule.py`, `verify_lucas_exact.py`,
`crossval_ml_dtypes.py`, `gen_conformance_pack.py`), plus twelve candidate
conformance packs derived from existing oracles in
`conformance/vectors_generated/`.

---

## 0. Method

Abstracts were pulled verbatim from the arXiv API
(`https://export.arxiv.org/api/query?id_list=<id>`). Artefact state was read from
`gHashTag/t27` over the GitHub API (tree + file contents + commit history for
`conformance/vectors`). Third-party versions were checked against their own
registries. No claim below rests on a repo state file.

---

## 1. Paper A — arXiv:2606.05017 (GoldenFloat)

*"GoldenFloat: A Phi-Derived Static-Split Floating-Point Family from GF4 to GF1024
with a Lucas-Exact Integer Identity"*, submitted 2026-06-03.

### 1.1 CRITICAL — the abstract asserts fabricated dies exist

Published abstract, final sentence:

> An RTL-correctness erratum dated 2026-05-31 is reported in Section 5.5; **the
> fabricated TTSKY26b dies carry the defective multiplier portfolio**, and the
> corrected generator is the regeneration baseline.

This states that fabricated TTSKY26b dies exist. The binding project fact is that
the silicon track was **cancelled** — no dies were fabricated. The identical claim
has already been removed from the local paper sources in
`gHashTag/trinity-papers-ru` PR #17 (commit `925bdf6d`, *"убрать чипы/кремний из
ВСЕХ статей"*), whose replacement wording is reused verbatim below so the arXiv
entry and the repository agree.

**Proposed replacement:**

> An RTL-correctness erratum dated 2026-05-31 is reported in Section 5.5; **an
> early RTL multiplier generator carried a defect**, and the corrected generator
> is the **design** baseline.

Two substantive edits: `the fabricated TTSKY26b dies carry the defective
multiplier portfolio` → `an early RTL multiplier generator carried a defect`, and
`regeneration baseline` → `design baseline`. This is the highest-priority item in
this package: it is a factual claim about physical artefacts, live on a public
preprint.

> Section 5.5 of the paper body must be checked for the same wording — the
> abstract is the visible surface, not the only occurrence.

### 1.2 Board-part consistency check (verify, do not assume)

The abstract reports the GF16 FPGA codec as *"35-of-35 testbench at 323 MHz on
Artix-7 (Xilinx **XC7A35T**)"*. All current hardware work in `trinity-fpga`
targets **XC7A200T** (ALINX AX7203, IDCODE `0x13636093`). Both part numbers occur
in the repository, so **XC7A35T may well be correct for that original measurement**
— this is flagged for the author to confirm, not asserted as an error. If the
323 MHz figure was in fact measured on the AX7203, the abstract names the wrong
device; if it was measured on an XC7A35T board, no change is needed and the two
numbers simply belong to different substrates.

### 1.3 Unaffected claims (checked, no change)

- `e = round((N-1)/phi^2)` — the **arithmetic** verifies, 17/17 (§10.1).
  ~~and the 9/9 reproduction — internal, unchanged~~ **SUPERSEDED by pass 8**: the
  9/9 *count* is not established and is off in both directions (§10.2).
- "We make no per-rung accuracy or superiority claim" — correct and worth keeping
  verbatim; it is the honesty anchor of the abstract.
- Breadth/toolchain-coherence as an **open conjecture** with FL-002 falsification
  ledger — correct framing, keep.

---

## 2. Paper B — arXiv:2606.09686 (83-format catalog)

*"An 83-Format Numeric Catalog with Bit-Exact Conformance Vectors"*,
submitted 2026-06-08.

### 2.1 The pack count understates the artefact by 13.8x — because the artefact grew after submission

Published abstract:

> ... a catalog of 83 numeric formats spanning 13 families, **a suite of six
> bit-exact conformance packs** covering GF16, MXFP4 element, BF16, FP8 E4M3,
> FP8 E5M2, and E8M0 block scale ...

Live artefact, `gHashTag/t27/conformance/vectors/INDEX_all_formats.json`:

```json
"schema": "t27-conformance-index/v0.1",
"total_formats": 83,
"total_packs":   83,
"bitexact_packs": 75,
"selfconsistent_packs": 0,
"structural_packs": 8
```

83 `*_conformance_v0.json` packs are present in the tree — one per catalogued
format — carrying the schema, SSOT pointer, preprint link and the
`phi^2 + 1/phi^2 = 3` anchor check that the abstract describes.

**Provenance — the paper was accurate when submitted.** Commit history for
`conformance/vectors`:

| date | commit | what |
|---|---|---|
| 2026-06-07 | `00e92fe3` | add v0 vector packs (GF16, FP8 E4M3FN/E5M2, MXFP4 …) — **the original six** |
| *2026-06-08* | — | *paper submitted to arXiv* |
| 2026-06-14 | `16042f46` | **complete catalog-wide pack set for all 83 formats** |
| 2026-06-14 | `f58c298f` | promote 6 structural packs to bit-precise (IBM HFP, …) |
| 2026-06-18 | `3d925d68`, `a7bd4d3e` | `bitexact_selfconsistent` CI gate; promote 6 wide GF rungs |
| 2026-07-05 | `997d5b51`, `38efad6c`, `ea15cd54` | gf128 / gf512+gf1024 / gf256 → strict SW-bitexact |
| 2026-07-29 | `8c20cbd6` | instance packs, structural (q_format / minifloat) |

So "six packs" was **true on 2026-06-08** and became stale six days later. The v2
framing should therefore be *"the pack set was completed after v1"*, not *"v1
undersold"* — the former is what actually happened and is the stronger, more
defensible story.

**Proposed replacement:**

> ... a catalog of 83 numeric formats spanning 13 families, **a catalog-wide
> suite of 83 bit-exact conformance packs — one per format, of which 75 are
> bit-exact and 8 structural** — and an IEEE P3109 cross-walk ...

with a version note in the body:

> v1 (2026-06-08) described the initial six packs, which were the complete set at
> the time of submission. The catalog-wide set of 83 packs was completed on
> 2026-06-14 and strengthened through 2026-07-29; v2 reports the completed set.

This is the single largest improvement available to either paper: the central
contribution is currently reported at **7 % of its actual coverage**.

### 2.2 SHA-256 fingerprint claim — verified TRUE, phrasing could be tightened

The abstract says *"Each pack is a self-contained JSON document with a SHA-256
fingerprint"*. The fingerprints exist — 83 of them — but they live in
`gHashTag/t27/conformance/vectors/INDEX_all_formats.json`, one entry per pack:

```json
{ "id": "binary16", "file": "binary16_conformance_v0.json", "kind": "bitexact",
  "n_vectors": 8, "source": "generated by gen_all_formats.py",
  "sha256": "84fd7629430b06d761ac3b92fc85208c472a4582040b1ac2001cc87a6612f7b4" }
```

The claim is substantively correct; only the location is imprecise (the digest is
*of* the pack, recorded in the index, rather than *inside* the pack). Optional
tightening: *"each pack carries a SHA-256 fingerprint recorded in a signed index"*.
**No integrity problem here** — recorded so a reviewer's version of this question
is already answered.

### 2.3 ml_dtypes 0.5.4 — VERIFIED CURRENT, do not change

The abstract cross-validates against **ml_dtypes 0.5.4** (Google/JAX). Checked
against PyPI on 2026-07-31: **0.5.4 is the latest release**. This reference is not
stale and must not be "modernised" — changing it would be churn, and would break
the reproducibility of the reported cross-validation.

### 2.4 IEEE P3109 v3.2.0 — partly resolved, see §6.2 and §8.6

The abstract cites an *"IEEE P3109 v3.2.0 cross-walk"*. Project notes elsewhere
refer to a **P3109 v4.0** carrying a kappa-approximation in §4.4. That newer
version has **not been verified in this pass** — P3109 drafts are not exposed
through a machine-readable endpoint that was checked here. **Do not edit this
number on the strength of a note.** Before submitting v2, confirm the current
draft version from the P3109 working group directly; if it has moved, the
cross-walk section (not just the version string) needs re-checking, because a
changed draft can change the mapping itself.

---

## 3. Verified-unchanged summary

Items checked in this pass that need **no** edit — recorded so a later pass does
not re-litigate them:

| item | paper | verdict |
|---|---|---|
| ml_dtypes 0.5.4 | B | latest on PyPI 2026-07-31 — keep |
| SHA-256 fingerprints | B | present (83, in the index) — claim holds |
| 83 formats / 13 families | B | matches `total_formats: 83` — keep |
| anchor `phi^2 + 1/phi^2 = 3` | A, B | present in every pack + index — keep |
| "no per-rung superiority claim" | A | correct, load-bearing — keep verbatim |
| FL-002 open-conjecture framing | A | correct — keep |

## 4. Priority order — SUPERSEDED, see the executive summary

1. **A §1.1** — fabricated-dies claim. Factual claim about physical artefacts on a
   public preprint; the corrected wording already exists in trinity-papers-ru PR #17.
2. **B §2.1** — 6 → 83 packs. Largest understatement; pure upside; provenance clean.
3. **B §2.4** — P3109 version, *after* independent verification.
4. **A §1.2** — board-part consistency, *after* author confirms which substrate.
5. **B §2.2** — fingerprint phrasing, cosmetic.

Items 1 and 2 are independent and can ship in either order.

## 5. Related work published after v1 (added 2026-07-31, pass 2)

Competitor scan over arXiv (`export.arxiv.org` API, sorted by submission date).
Citation state was checked by fetching `paper1-goldenfloat/main_ru.tex` from the
**default branch** and grepping locally — see the method warning in §5.4.

### 5.1 Not cited, and it matters: arXiv:2607.13898

*"Jack of All Scales: A Versatile FPGA Tensor Block for MXFP Precisions"*,
submitted **2026-07-15** — six weeks after Paper A. Verified absent: paper1 cites
24 arXiv IDs in the 2601–2607 range (`2607.07964`, `2607.08095`, `2607.13511`,
`2607.14618`, `2607.21446`); `2607.13898` is **not** among them.

Why it belongs in v2 — two independent reasons:

**(a) It is the nearest FPGA-side neighbour.** They characterise MXFP dot products
on Altera Agilex-5 across soft logic and DSP fixed/float/tensor modes, then propose
DSP tensor-mode modifications for native MXFP support (preferred design point:
+36 % DSP tile area). Paper A's FPGA claim sits on Xilinx Artix-7 with a
soft-logic implementation. The axes are **complementary, not ranked** — different
vendor, different substrate strategy — and that is exactly how the citation should
read. No superiority claim in either direction.

**(b) It independently corroborates a finding Paper A currently does not state.**
From their abstract:

> the tensor mode … **cannot implement MXFP6 (E3M2) or any MXFP8 precisions,
> forcing designers to fall back to lower-density alternatives**

That is an external, different-vendor result showing hard DSP blocks are a poor
fit for narrow formats. It is the same wall the GF work hit from the other side.

### 5.2 Substantive gap: Paper A never discusses DSP vs soft logic

Grep over `main_ru.tex` for `nodsp` / `DSP48` / `DSP block` / `DSP-блок`:
**0 hits.** The paper reports an FPGA codec result without stating that the
implementation is soft-logic-only or why.

The project's own hardware record is that GF multiply synthesis **requires
`-nodsp`**, because DSP48E1 inference produces a routing failure. That is a
measured engineering constraint, currently invisible in the paper, and
arXiv:2607.13898 provides independent external support for the general claim.

Proposed v2 addition (short subsection, FPGA section): state that the GF codec is
implemented in soft logic with DSP inference disabled, give the routing-failure
reason, and cite 2607.13898 as an independent observation of the same
DSP/narrow-format mismatch on a different FPGA family. Status of the joint claim:
`[measured on our substrate]` + `[externally corroborated, different substrate]` —
**not** a general claim about all DSP architectures.

### 5.3 Lower-priority 2026 neighbours (log only, no action yet)

- `MXAttention` — data-free optimal scaling / pre-norm quantization for MXFP4
  attention (2026-07-27).
- *Stable FP4 Training via Transposition-Invariant Block Quantization* (2026-07-27).

Both are quantization-algorithm papers rather than format-family or FPGA work.
They matter for Paper B's relevance framing, not for its correctness. Revisit only
if the MXFP4 section is rewritten.

### 5.4 Verified NOT gaps, and one method warning

- **Tekum is already cited.** *"Tekum: Balanced Ternary Tapered Precision Real
  Arithmetic"* (2025-11-25) — `main_ru.tex` has 8 mentions and the bibitem
  `hunhold2025tekum`. Recorded here so a later pass does not "fix" a non-problem.
  takum (36 mentions) and posit (52) are likewise well covered.
- **METHOD WARNING — do not use GitHub code search for citation checks.**
  `search/code?q=…+repo:gHashTag/trinity-papers-ru` returned `total_count: 0` for
  `2607.17733` (MXSens), a **known positive** that is demonstrably present in
  PR #17's diff. Code search does not index non-default branches and gave a false
  negative on the control. Every citation claim in §5 was instead verified by
  fetching the file contents from the default branch and grepping locally. Any
  future pass must run the same known-positive control before trusting a search.

## 6. P3109 versions and a citation defect (added 2026-07-31, pass 3)

### 6.1 The two papers cite incompatible P3109 versions

| paper | what it cites | submitted |
|---|---|---|
| A — 2606.05017 | bibitem `p3109_v091`: *"IEEE P3109 Working Group … working draft **v0.9.1**, 2025. Reference implementation: `graphcore-research/gfloat`"* | 2026-06-03 |
| B — 2606.09686 | abstract: *"an IEEE P3109 **v3.2.0** cross-walk"* | 2026-06-08 |

The papers are **five days apart** and cite version numbers that cannot both
describe the same document at the same time; a v0.9.1 → v3.2.0 jump in five days
is not plausible. Either the two numbers refer to different artefacts (e.g. the
WG draft versus a versioned cross-walk table of our own), or one is wrong.

**Action:** reconcile before either v2 ships. This is the kind of discrepancy a
reviewer holding both papers finds immediately, and it costs nothing to fix once
the intended referent is known. Do **not** guess which one is right.

### 6.2 The P3109 draft version — ~~not publicly verifiable~~ **corrected, pass 81**

> ⚠️ **The paragraph below was wrong and is kept only to show what was corrected.**
> It said there is no `P3109/Public` repository. There is:
> `github.com/P3109/Public`, updated 2026-07-29, holding the *IEEE P3109 Interim
> Report* and **504 CSV value tables (154 MB)**. It was reached in pass 63 by
> following the very lead this section names — `graphcore-research/gfloat`, whose
> README links straight to it.
>
> **What is true, and settles the item:** the Interim Report carries **no version
> number anywhere in its text** — only "unapproved IEEE Standards Draft, subject to
> change" and a 2026 copyright. So the version cannot be confirmed, but for a
> different reason than stated: not because nothing is published, but because what
> is published is unversioned. **Cite the Interim Report by retrieval date.**
>
> This also disposes of §8.6's explanation that Paper A and Paper B "cite two
> different document series". Paper B's ref [18] names the Interim Report
> explicitly, and Paper A's [27] points at it through gfloat. One document, two
> different version strings attached to it.

~~Checked this pass: there is no `P3109/Public` repository, and no release/tag feed
for the working group.~~ The related public repositories —
`awf/p3109-cpp` (C++ implementation, WG participant), `imandra-ai/ieee-p3109`
(updated 2026-07-27), `rutgers-apl/FLoPS` — expose **no draft-version string**.
`graphcore-research/gfloat` is named by Paper A as the reference implementation
and is the best remaining lead. *(It was. Following it resolves the item.)*

### 6.3 Citation defect: `flops2026` has a placeholder author and a paraphrased title

Current bibitem in `main_ru.tex`:

> `\bibitem{flops2026}` **Authors of FLoPS**, *"FLoPS: a Lean~4 formalization of
> IEEE~P3109 low-precision floating-point,"* arXiv:2602.15965, 2026.

Both fields are wrong. Verified against the arXiv API for `2602.15965`:

- **Authors:** Tung-Che Chang, Sehyeok Park, Jay P. Lim, Santosh Nagarakatte
  (Rutgers — the `rutgers-apl/FLoPS` group).
- **Actual title:** *"FLoPS: Semantics, Operations, and Properties of P3109
  Floating-Point Representations in Lean"*.

A paraphrased title is not merely untidy — the reference cannot be found by title
search, which defeats the point of citing it.

**Corrected bibitem:**

```latex
\bibitem{flops2026} T.-C. Chang, S. Park, J. P. Lim, and S. Nagarakatte,
``FLoPS: Semantics, Operations, and Properties of P3109 Floating-Point
Representations in Lean,'' \texttt{arXiv:2602.15965}, 2026.
\url{https://arxiv.org/abs/2602.15965}.
```

**Verified NOT defects** (do not "fix" these): `\bibitem{positstd2022} Posit
Working Group` and `\bibitem{p3109_v091} IEEE P3109 Working Group` are legitimate
corporate authors. A scan of the whole bibliography found `flops2026` to be the
only placeholder-author entry.

### 6.4 Positioning note for Paper B: formal semantics is not implementation conformance

FLoPS is a **Lean 4 machine-checked formalization** of P3109 semantics, from an
active group (`rutgers-apl/FLoPS`, updated 2026-07-28); `imandra-ai/ieee-p3109`
is a second formal-methods effort in the same space. A reviewer of Paper B will
reasonably ask: *if the standard is being formalized in a theorem prover, why do
bit-exact test vectors add anything?*

The answer is short and should be stated explicitly rather than left implicit: a
proof about the specification says nothing about whether a **particular decoder,
kernel or FPGA bitstream** emits the right bits. Formal semantics and executable
conformance vectors sit on different rungs — spec correctness versus
implementation conformance — and they compose rather than compete. Paper B
already cites FLoPS (`flops2026`); it does not yet make this distinction, and it
is the cheapest available strengthening of its contribution framing.

Status of that claim: `[positioning, not a result]` — it asserts complementarity,
not superiority over formal methods.

## 7. The conformance-testing lineage is missing (added 2026-07-31, pass 4)

### 7.1 Competitive scan on Paper B's axis returned nothing — and that is the problem

Targeted arXiv searches, sorted by submission date:

| query | hits |
|---|---|
| `abs:"conformance test vectors" AND abs:"floating-point"` | **0** |
| `abs:"numerical formats" AND abs:reference` | 3 — the top hit is **Paper B itself** |
| `all:"format catalog" AND all:precision` | **0** |

No competing published work was found on Paper B's axis. **This must not be
written up as uniqueness.** It is absence of evidence in one search space, and the
binding no-"first/only/best" rule applies with full force. Vendor test suites,
standards-body vectors and implementation test data exist; they are simply not
published as arXiv papers.

The actionable reading is the opposite of a victory lap: **Paper B has no
established category, so a reviewer has no reference frame for it.** A related-work
section cannot position against peers that do not exist — it has to build the frame
out of adjacent categories. Three of those are already known:

- **implementation test data** — `ml_dtypes` (cited), `graphcore-research/gfloat`;
- **formal formalizations** — FLoPS (Lean 4), `imandra-ai/ieee-p3109`;
- **conformance test suites** — Berkeley TestFloat / SoftFloat (see §7.2).

### 7.2 Paper A does not cite the canonical conformance prior art

> **CORRECTION (pass 5).** This subsection was originally headed *"Neither paper
> cites…"*. That was an overreach: it generalised from `main_ru.tex` (Paper A) to
> both papers without having read Paper B's bibliography. Paper B **does** cite
> IEEE Std 754-2019 (its ref [15]) and **does** cite conformance-testing prior art
> (Wintersteiger, *"Floating-point conformance testing in industrial practice"*,
> IEEE ARITH 2025, ref [11]). The findings below apply to **Paper A only**.
> TestFloat/Hauser remains uncited in both.

Verified over `main_ru.tex` (Paper A, 56 bibitems):

| term | occurrences |
|---|---|
| `TestFloat` | **1** (bare string; no bibitem) |
| `SoftFloat`, `Hauser`, `Berkeley` | **0** |
| a bibitem for **IEEE Std 754 itself** | **none** |

Two omissions, both conspicuous for papers in this area:

**(a) IEEE 754 is discussed in the body but never cited.** A paper proposing a
floating-point family, positioned explicitly against posit, takum, OCP-MX and
P3109, carries 56 references and none of them is the base standard. This is
trivially fixable and is the sort of thing a reviewer notices in the first pass.

**(b) Berkeley TestFloat / SoftFloat (Hauser) is the direct methodological
ancestor and is uncited.** It is *the* established prior art for floating-point
conformance testing. For Paper A this is a related-work hole; for **Paper B it is
the single most likely reviewer objection**, because Paper B's whole contribution
*is* conformance vectors: *"how does this relate to TestFloat?"* is the first
question any referee in this area asks, and the paper currently has no answer on
the page.

The honest answer exists and is strong — TestFloat targets IEEE 754 binary
arithmetic conformance of *operations*; the catalog targets *format decode/encode*
across 83 formats, most of which TestFloat does not cover at all (MXFP, NF4,
posit, takum, LNS, GF). Complementary scopes, different objects under test. It
just needs to be stated.

**Action:** add both citations plus one paragraph in each paper distinguishing
scope. Status: `[related work, no result claimed]`.

### 7.2a RESOLVED, and the finding is stronger: TestFloat-3 is a load-bearing instrument

The pass-4 caveat above (context not read) is now closed. `main_ru.tex` line 1728
sits inside the **pre-registration** block (`Дата предрегистрации: 2026-05-31`) —
i.e. the FL-002 falsification path the abstract promises. Its *Материалы*
paragraph reads:

- RTL GF16: corrected `gf16_mul.v` / `gf16_add.v` from `gHashTag/tt-trinity-gamma` PR #110
- RTL posit16: **PERCIVAL** (Mallasen et al., 2022, arXiv:2111.15286) — cited ✓
- driver: Rust `cli/dlc10` (`gHashTag/t27`)
- toolchain: **OpenXC7 (yosys + nextpnr-xilinx)** or Vivado 2023.2
- **correctness gate: an exhaustive TestFloat-3 run, 0 errors required over
  1 M random samples**, before any area/timing result is accepted

So TestFloat-3 is not mentioned in passing — it is the **correctness gate of the
pre-registered experiment**. That reclassifies the omission: this is an **uncited
tool dependency inside the falsification protocol**, which is a stricter failure
than a related-work gap. A protocol that gates its acceptance criterion on a tool
must cite that tool.

**Two things worth recording as strengths, not defects** (this package should not
only hunt faults):

1. The pre-registration is well formed — explicit thresholds (>15 % area, <85 % of
   posit16 `F_max`), an explicit commitment to report negative results prominently,
   no post-hoc threshold adjustment, and a date. That is a stronger design than
   most format papers carry.
2. The posit16 comparator (PERCIVAL) **is** properly cited.

**Practical blocker worth flagging to the author:** the pre-registered experiment
requires `nextpnr-xilinx` (OpenXC7). That toolchain is *not installed* on the
current workstation — the same gap that blocked the AX7203 P&R task this week. The
falsification experiment cannot run until either OpenXC7 or Vivado 2023.2 is
available. This is a scheduling fact, not a criticism of the paper.

### 7.3 Paper B's full text — RESOLVED in pass 5, see §8

`paper2-catalog/` holds `ARXIV_UPLOAD_EN_v2.md` (4 kB — arXiv upload metadata
only) and the actual manuscript as `statya2_ru.docx` / `.pdf`. The `.docx` is
binary and was not extracted, so **Paper B's bibliography has not been checked for
`flops2026`-class defects** (§6.3). That check is still open and needs the docx
unpacked locally.

## 8. Paper B bibliography audit — 4 of 20 references are defective (pass 5)

Paper B's manuscript (`paper2-catalog/statya2_ru.docx`) was unpacked and its
20-entry reference list extracted. Every arXiv ID was checked against the arXiv
API. **Four entries (20 %) do not match the work they point at.**

### 8.1 Ref [3] — wholly misattributed (most serious)

| | |
|---|---|
| **paper says** | C. Park, J.-H. Lim, S. Nagarakatte, *"ProofWright: Towards verified floating-point arithmetic"*, arXiv:2511.12294v2, 2025 |
| **arXiv:2511.12294 actually is** | *"ProofWright: Towards **Agentic Formal Verification of CUDA**"* — Bodhisatwa Chatterjee, Drew Zagieboylo, Sana Damani, Siva Hari, Christos Kozyrakis |

**All three listed authors are wrong** (none of Park, Lim or Nagarakatte is on the
paper), **the title is wrong**, and **the subject is wrong** — it is about agentic
formal verification of CUDA, not floating-point arithmetic. This is not a
formatting slip; the citation describes a different work than the ID resolves to.

This is the highest-risk item in this whole package after §1.1. A referee who
follows one link finds it immediately, and a misattributed citation reads as
*references that were generated rather than read* — which would cast doubt on the
rest of the bibliography by association, including the parts that are correct.

**Action:** decide what was actually meant. If the intended reference was the
Rutgers group's work, ProofWright is the wrong ID; if arXiv:2511.12294 was
intended, the authors and title must be replaced with the real ones. Do not patch
half of it.

### 8.2 Refs [19] and [20] — no authors, paraphrased titles

| ref | paper says | reality (arXiv API) |
|---|---|---|
| [19] | *"Formal models of Tensor Core numerics for reproducible GEMM"*, arXiv:2512.07004 — **no authors** | *"Accurate Models of NVIDIA Tensor Cores"* — Faizan A. Khattak, Mantas Mikaitis |
| [20] | *"TAO: Tolerance-aware verification of numerical operators"*, arXiv:2510.16028 — **no authors** | *"TAO: Tolerance-Aware **Optimistic** Verification for **Floating-Point Neural Networks**"* — J. Yao, H. Su, T. Liao, Z. Cheng, H. Zhang, X. Wang, P. Viswanath |

Both entries omit the author list entirely and paraphrase the title. As in §6.3, a
paraphrased title cannot be found by title search.

### 8.3 Ref [4] — same defect class as Paper A's `flops2026`

| | |
|---|---|
| **paper says** | C. Chang, C. Park, J.-H. Lim, S. Nagarakatte, *"P3109 FLoPS: A Lean 4 formalization of IEEE P3109 floating-point semantics"* |
| **reality** | Tung-Che Chang, Sehyeok Park, Jay P Lim, Santosh Nagarakatte, *"FLoPS: Semantics, Operations, and Properties of P3109 Floating-Point Representations in Lean"* |

Three of four initials are wrong (`C. Chang` → `T.-C. Chang`; `C. Park` →
`S. Park`; `J.-H. Lim` → `J. P. Lim`; only Nagarakatte is right) and the title is
paraphrased. **The same work is mis-cited in both papers** (Paper A's `flops2026`,
§6.3) — so this is a systematic issue with one source, not two independent slips.

### 8.4 Corrected entries

```
[3]  B. Chatterjee, D. Zagieboylo, S. Damani, S. Hari, C. Kozyrakis,
     "ProofWright: Towards Agentic Formal Verification of CUDA,"
     arXiv:2511.12294, 2025.            [ONLY IF this ID was the intended source]

[4]  T.-C. Chang, S. Park, J. P. Lim, S. Nagarakatte, "FLoPS: Semantics,
     Operations, and Properties of P3109 Floating-Point Representations in Lean,"
     arXiv:2602.15965, 2026.

[19] F. A. Khattak, M. Mikaitis, "Accurate Models of NVIDIA Tensor Cores,"
     arXiv:2512.07004, 2025.

[20] J. Yao, H. Su, T. Liao, Z. Cheng, H. Zhang, X. Wang, P. Viswanath,
     "TAO: Tolerance-Aware Optimistic Verification for Floating-Point Neural
     Networks," arXiv:2510.16028, 2025.
```

### 8.5 Verified correct — do not touch

Checked and matching: [1] self-citation 2606.05017, [2] Hunhold takum 2412.20273,
[5] Rouhani MX 2310.10537, [15] **IEEE Std 754-2019** (so Paper A's omission,
§7.2, is Paper A's alone), [16] OCP MX v1.0, [17] ml_dtypes 0.5.4 (matches PyPI,
§2.3), [18] **IEEE SA P3109 Interim Report v3.2.0**.

### 8.6 The P3109 "version conflict" of pass 3 is RESOLVED — no error

Ref [18] reads *"IEEE SA P3109 **Interim Report** v3.2.0"*; Paper A's
`p3109_v091` reads *"working **draft** v0.9.1, 2025"*. These are **two different
documents in two different series**, not two versions of one document. §6.1's
hedge — *"either they name different artefacts or one is wrong"* — resolves to
**different artefacts**. No edit is required, and pass 6+ should not reopen it.

## 9. Paper A bibliography audit — clean (pass 6)

Pass 5 found a 20 % defect rate in Paper B, so Paper A could not be left on a
single spot-check (`flops2026`). All 24 arXiv IDs cited in `main_ru.tex` were
batch-queried against the arXiv API and every claimed title compared to the real
one.

**Headline: Paper A's bibliography is clean.** The defect concentration is in
Paper B, not across both papers.

| check | result |
|---|---|
| all 24 IDs resolve | **yes** — no fabricated identifiers |
| titles matching exactly | **21 of 23** (case style only: sentence vs title case — a style choice, not a defect) |
| misattributed works (Paper B [3] class) | **none** |
| wrong author attributions | **none** |

### 9.1 The three minor title restructurings

All three follow one pattern — the `Name: Subtitle` form inverted to
`Subtitle (Name)`:

| id | paper A writes | real title |
|---|---|---|
| 2603.02949 | *"A reference framework for LLM inference carbon estimation (SEAL)"* | *"**SEALing the Gap:** A Reference Framework for LLM Inference Carbon Estimation via …"* |
| 2603.18046 | *"NANOZK: layerwise zero-knowledge proofs for LLM inference"* | *"NanoZK: **Privacy-Preserving Verifiable Inference for Large Language Models via** Lay…"* |
| 2607.08095 | *"Decomposing proof construction to scale zero-knowledge machine learning (zkComposer)"* | *"**zkComposer:** Decomposing Proof Construction to Scale **zkML**"* |

Low severity — the ID is right and the work is identifiable — but the entries are
not findable by title search. Restore the published titles verbatim.

### 9.2 Two inline citations — attributions verified CORRECT

Neither is a bibitem; both are cited in body prose. Both first-author
attributions check out:

- `arXiv:2605.12464` — paper writes *"ScaleSearch (Gupta и др. 2026)"*. First
  author is **Tanmaey Gupta** ✓. But the real title is *"Search Your Block
  Floating Point Scales!"* — there is no "ScaleSearch" in it. The nickname is a
  reading aid, not a misattribution; still, a reader searching "ScaleSearch" finds
  nothing. Add the real title on first mention.
- `arXiv:2605.24391` — paper writes *"MX-SAFE / MXSF (Park и др. 2026)"*. First
  author is **Dahoon Park** ✓ and the real title does begin *"MX-SAFE: …"* ✓.
  **Fully correct, no action.**

### 9.3 What this changes about priorities

Before this pass the working assumption was that both bibliographies needed the
same treatment. They do not:

- **Paper B** — 4 of 20 refs defective (20 %), including one wholly misattributed
  work (§8.1). Its reference list needs a **full rebuild and re-verification**
  before v2 ships.
- **Paper A** — 1 real defect (`flops2026`, §6.3) plus 3 cosmetic title
  restorations and 1 nickname clarification. **Four targeted edits**, no rebuild.

The single shared defect is the FLoPS citation, wrong in both (§6.3, §8.3) — one
source of error, not two.

## 10. The φ-rule and the Lucas identity verify; the 9/9 count is unresolved (passes 7–9)

First pass to check a **numerical claim** rather than a citation. Artefact:
`research/verify_phi_rule.py` (added with this section, runnable, exit-coded).

It recomputes `e = round((N-1)/φ²)`, `f = N-1-e` from scratch at 60-digit decimal
precision and compares against the parameters the golden oracle actually uses
(`conformance/gf_ref.py::FORMATS`) — i.e. against the artefact, not against the
paper's restatement of itself.

### 10.1 Result: the rule holds for every catalogued GF format

```
catalogued GF formats satisfying the rule: 17/17
the abstract claims:                        9/9
```

All 17 — gf4, gf6, gf8, gf10, gf12, gf14, gf16, gf20, gf24, gf32, gf48, gf64,
gf96, gf128, gf256, gf512, gf1024 — satisfy both `e` and `m`. **The central rule
of Paper A independently verifies.**

### 10.2 But "reproduces" and "extends" are different claims — and the split is off

The abstract says the rule *"reproduces the realised exponent widths of nine
formats … (9/9) and extends consistently to GF128, GF512, GF1024"*. That
distinction is the right one and the paper is correct to draw it: *reproducing* a
width chosen independently is evidence **for** the rule; *extending* to a width the
rule itself defines is not evidence at all.

`gf_ref.py` marks the boundary in its own comments — a block of formats, then
`# Canonical φ-rule family (arXiv:2606.05017) — wide formats`, then
`# — ultra-wide formats`. Reading the split by that marker:

> **CORRECTION (pass 8).** The table first published here placed gf64 and gf256
> in the pre-rule block. That was wrong. In `gf_ref.py` the marker
> `# Canonical φ-rule family (arXiv:2606.05017) — wide formats` sits **after
> gf32**, so gf48, gf64, gf96, gf128 and gf256 are all inside the rule-derived
> block. The corrected table and the two-sided consequence follow. The original
> one-sided reading ("the paper understates, 9/9 → 12/12") was premature.

| group | formats | claimed among the nine? |
|---|---|---|
| **pre-rule** (above the marker) | gf4, gf6, gf8, gf10, gf12, gf14, gf16, gf20, gf24, gf32 — **10** | 7 of them: gf4, gf8, gf12, gf16, gf20, gf24, gf32 |
| **rule-derived** (at/below the marker) | gf48, gf64, gf96, gf128, gf256, gf512, gf1024 — **7** | **2 of them: gf64, gf256** |

The count cuts **both ways**, which is why it cannot be "fixed" in one direction:

1. **Understated by 3.** gf6, gf10, gf14 are pre-rule, match the rule, and are
   *not* in the claimed nine. If they predate the rule, each is genuine evidence
   for it, discarded for free.
2. **Possibly overstated by 2.** gf64 and gf256 *are* in the claimed nine, but the
   artefact places them in the rule-derived family. If the rule generated those
   widths, matching it is circular and they cannot count as reproductions.

So the true reproduction count is **not established by this pass**. Plausible
values are **10/10** (if every pre-rule width counts) or **7/7** (claimed minus
the two derived) — but not 9/9 as it currently stands, and not the 12/12 this
section originally suggested.

**Do not guess.** The provenance split is inferred from comment placement in
`gf_ref.py`; only the author knows which widths were fixed before the rule
existed. This is recorded as `open_question WIDTH_PROVENANCE` in
`specs/numeric/phi_rule_verification.t27` with `do_not_guess true`.

**gf48 and gf96 remain a separate minor point:** both are rule-derived extensions
that the abstract's extension list (GF128, GF512, GF1024) omits. State the
extension set in full.

### 10.3 The unstated rounding convention is provably moot — say so

The paper writes `round(...)` without specifying half-even or half-up. A picky
referee can ask, since the two differ on an exact `.5`. The script checks: **no
GF width lands on an exact `.5`**, so both conventions agree on all 17 formats and
the ambiguity has no consequence.

That is worth one sentence in the paper — it converts a potential referee question
into a demonstrated robustness property, at zero cost.

### 10.4 Lucas-exactness — identity VERIFIED (pass 9)

SSOT: `specs/numeric/lucas_exact_verification.t27`.
Executable companion: `research/verify_lucas_exact.py`.

The abstract reports *"an integer-backed Lucas-exact accumulator path verified at
500-digit precision for n = 1 … 256"*. The identity underneath it is
`φ^(2n) + φ^(-2n) = L_(2n)`, an integer — and the project anchor
`φ² + 1/φ² = 3` is its n = 1 case, since `L_2 = 3`.

Recomputed independently: Lucas numbers from the **pure integer recurrence**
(no floating point on the target side at all), the φ-side in 500-digit decimal.

```
checked      : 256
mismatches   : 0
worst residue: 4.000E-392  at n = 256
```

`L_512` carries 108 integer digits, leaving ~392 fractional digits at 500-digit
precision — so the worst residue sits **exactly at the representation floor**
(relative error ~1e-499 against a magnitude of ~1e107). It is arithmetic noise,
not a failing identity. **The identity holds across the whole range.**

Worth telling the author: the choice of 500 digits is **well matched to n = 256**,
not arbitrary — enough headroom without extravagance. One sentence saying so
pre-empts the obvious referee question *"why 500?"*.

**What this does NOT establish, stated plainly.** The paper claims a verified
accumulator *path*, not merely a true identity. This pass verifies the
mathematics the path rests on; it does not execute the accumulator implementation,
which lives in the RTL/kernel. Recorded as
`open_question ACCUMULATOR_IMPLEMENTATION` with `do_not_guess true`.

### 10.5 Remaining unverified claim from Paper A

One numerical claim is still unchecked and is **not** asserted either way:

- the GF16 FPGA codec *"passing a 35-of-35 testbench at 323 MHz"* (and §1.2 on
  which board it ran on).

It needs the FPGA toolchain that §7.2a records as unavailable here — the same
`nextpnr-xilinx` gap that blocks the paper's own pre-registered experiment.

## 11. What this package cannot do

Replacing an arXiv entry requires the submitting author's arXiv account. This
document prepares the exact old → new text and the evidence for each edit; the
submission itself is the author's action. The repository carries an
`arxiv-replace-pipeline` skill that covers that workflow.

Nothing in `gHashTag/t27` or `gHashTag/trinity-papers-ru` was modified by this
pass — it was read-only apart from this file.

---

## 12. The arXiv entry is a version behind the manuscript (pass 25)

### 12.1 What the manuscript's own changelog says

`paper2-catalog/statya2_ru.docx` is **v5, dated 6 July 2026**, and carries a
version history. Its v4→v5 entry reads:

> v4→v5: в v4 (**8 июня 2026 г.**) набор пакетов делился как **49 битоточных /
> 34 структурных**. К v5 покрытие пересчитано по живому SSOT-индексу
> `gHashTag/t27/conformance/vectors/INDEX_all_formats.json` …

8 June 2026 is the arXiv submission date. So the **submitted body already
described 49 bit-exact + 34 structural = 83 packs**, while the **abstract of the
same submission** says *"a suite of six bit-exact conformance packs covering GF16,
MXFP4 element, BF16, FP8 E4M3, FP8 E5M2, and E8M0 block scale"*.

### 12.2 This corrects §2.1

Pass 1 framed the pack count as *"v1 was accurate at submission; the artefact grew
six days later"*. That is **not what happened**. The body and the abstract of the
same submission disagreed with each other: the abstract named six specific packs
where the body counted the whole corpus.

The correction matters because it changes the nature of the fix:

- **pass-1 reading** — the paper was right then and is stale now, so v2 must
  report new work;
- **actual situation** — the abstract understated the paper's own body from day
  one, and the local manuscript has *already* moved to v5 stating "all 83 packs".

So the fix is not authorship at all. It is **submitting the existing v5 to arXiv**.
No new text has to be written for this item.

### 12.3 What is NOT already fixed

The bibliography audit in §8 was performed against **this same v5 manuscript**, so
its four defective references — the wholly misattributed [3], the author-less [19]
and [20], and the mis-initialled [4] — are **present in v5** and still require
correction before any replacement is submitted.

Replacing the arXiv entry with v5 as it stands would fix the pack count and ship
the bibliography defects. Both must be done together.

### 12.4 Under-claimed: how wide values are serialised

Pass 24 established that the seven layout-B packs store values as **decimal
strings** with an explicit `value_encoding` field, because a gf1024 value carries
a 632-bit mantissa and cannot be held in binary64 at all.

Searching the v5 manuscript, `value_encoding` does not appear and serialisation of
out-of-double values is discussed once at most. The catalog therefore has a
working answer to a question the field genuinely has — *how do you publish
bit-exact conformance vectors for formats wider than a double?* — and does not
claim it.

This is the same shape as the pack count: a real contribution present in the
artefact and absent from the prose. Recommended as a short subsection rather than
a headline claim, since it is engineering, not a result.

---

## 13. Both preprints are already revised — and the problems survived (pass 26)

### 13.1 Current versions

| preprint | current | submitted | last updated |
|---|---|---|---|
| 2606.05017 (GoldenFloat) | **v3** | 2026-06-03 | **2026-06-22** |
| 2606.09686 (catalog) | **v2** | 2026-06-08 | **2026-06-22** |

The arXiv API serves the latest version, so every abstract quoted in this package
is the **current** one. Verified directly against what arXiv returns today:

- `2606.05017v3` still contains **"fabricated TTSKY26b"**;
- `2606.09686v2` still contains **"six bit-exact conformance packs"**.

### 13.2 Why this changes the reading of item 1

The fabricated-dies claim is not an oversight left in an initial submission that
nobody revisited. The preprint has been **updated twice** since — v1 → v2 → v3 —
and the sentence asserting that fabricated dies exist is still there.

That makes it more urgent rather than less. A claim about physical artefacts that
persists through two rounds of revision reads, to anyone who later learns the
silicon was cancelled, as sustained rather than accidental. It is also the single
cheapest thing in this package to fix: two clauses, with replacement wording
already written and already applied in `trinity-papers-ru` PR #17.

### 13.3 Correction to §12: two version numberings, not one

§12 said "the arXiv entry is a version behind the manuscript". That is true in
substance but imprecise in detail, and the detail matters when someone goes to
submit.

The manuscript keeps its **own** version numbers (its changelog speaks of v4 and
v5) which do **not** correspond to arXiv's. Concretely:

- manuscript **v4** is dated 8 June 2026 = the date of **arXiv v1**;
- the local manuscript is **v5**, dated 6 July 2026;
- arXiv's latest is **v2**, from 22 June 2026 — a revision the manuscript's
  changelog does not obviously name.

So there is roughly a two-week gap between what arXiv serves and what the
repository holds, and the two numbering schemes must not be conflated when
preparing the replacement. Do not assume "manuscript v5" maps to "arXiv v3".

### 13.4 What this means for the package as a whole

Nothing here is an artefact of reading an outdated preprint. Every finding in
§§1-12 was derived from the abstracts arXiv serves today and from the v5
manuscript in the repository. The two headline items — the fabricated-dies claim
and the pack count — are live in the current public versions.

### 13.5 What the revisions actually changed (pass 27)

Fetched each version's abstract explicitly (`id_list=<id>v<n>`) and diffed them.

**Paper A — 2606.05017**

| step | abstract | change |
|---|---|---|
| v1 | 1350 chars | baseline; contains the fabricated-dies clause |
| v1 → v2 | 1810 chars | **added** a sentence: *"A format-conformance oracle (Corona) ships in the same repository and is used as the blackbox check in our continuous-integration audit."* |
| v2 → v3 | 1810 chars | **abstract unchanged — empty diff** |

The added Corona sentence is **accurate**: it describes Corona as an oracle
shipping in the repository and used as a CI check, and claims no silicon. It is
not part of the problem.

The erratum clause has therefore **never been edited since v1**, and v3 did not
touch the abstract at all.

**Paper B — 2606.09686**

| step | abstract | change |
|---|---|---|
| v1 → v2 | 1326 chars, unchanged length | **exactly one token: `84` → `83`** |

That is the entire v2 abstract revision. Notably it is the *same* 84-vs-83
discrepancy this campaign found independently in pass 10 — so the author noticed
it and corrected it. The pack count "six" was left untouched.

### 13.6 The mechanism, and why it matters for the fix

Neither revision was a re-read of the abstract. Both were **narrow targeted
patches** — one sentence added, one number corrected — and everything around them
was carried forward unexamined. That is why two rounds of revision left the
flagged claims in place: they were never in scope of either edit.

Two consequences:

1. **Encouraging.** The 84 → 83 edit shows count corrections do get made once
   noticed. The six → 83 fix is the same species of change, and the replacement
   text already exists in the v5 manuscript.
2. **Actionable.** The failure mode is not carelessness, it is the absence of a
   whole-abstract pass. A single read of each abstract against the item list in
   this package's executive summary would catch every remaining item at once —
   which is precisely what two rounds of patching did not do.

---

## 14. Paper B bibliography — RE-AUDIT: 8 of 20, not 4 (pass 34)

### 14.1 My pass-5 audit was not rigorous, and this corrects it

§8 reported four defective references and listed others as *"verified correct — do
not touch"*. That list was produced by checking that each arXiv ID **resolved**,
and sometimes the authors — **not the titles, systematically**. Re-running the
check properly against the arXiv API found **four more**, two of them on entries
§8.5 explicitly cleared.

**Do not rely on §8.5.** It is superseded by this section.

### 14.2 The four newly found

| ref | claimed title | actual title |
|---|---|---|
| **[1]** | *"GoldenFloat: A phi-anchored numeric format family and the identity φ²+1/φ²=3"* | *"GoldenFloat: A **Phi-Derived Static-Split** Floating-Point Family from GF4 to GF1024 with a Lucas-Exact Integer Identity"* |
| **[2]** | *"Takum arithmetic: A new paradigm for low-precision numerics"* | *"**Integer Representations** in IEEE 754, Posit, and Takum Arithmetics"* |
| **[8]** | *"M2XFP: A unified mixed-precision microscaling floating-point representation…"* | *"M2XFP: A **Metadata-Augmented** Microscaling Data Format for Efficient Low-bit…"* |
| **[13]** | *"Takum arithmetic in sparse iterative solvers: A precision-vs-storage study"* | *"**Evaluation of Bfloat16, Posit, and Takum** Arithmetics in Sparse Linear…"* |

**[1] is the companion paper, self-cited with the wrong title.** Anyone following
the reference reaches the right work, but a reader searching by the quoted title
finds nothing — including the authors' own future selves.

### 14.3 Verified correct on this stricter pass

[5] 2310.10537, [6] 2502.10517, [10] 2504.07835, [14] 2206.02915 — titles match.
Non-arXiv entries ([7] NVIDIA blog, [9] SIAM News, [11] ARITH 2025, [12] libtakum,
[15] IEEE 754, [16] OCP MX, [17] ml_dtypes, [18] P3109) were not re-checked here.

### 14.4 The count

**8 of 20 references (40 %) carry a wrong title, wrong authors, or both**:
[1], [2], [3], [4], [8], [13], [19], [20].

[3] remains the most serious — wrong authors, wrong title *and* wrong subject.

### 14.5 Paper B never cites the paper that defines takum

The takum-defining work is **arXiv:2404.18603, *"Beating Posits at Their Own Game:
Takum Arithmetic"* (Hunhold)**. Paper A cites it. Paper B does **not** — zero
occurrences — while cataloguing takum8/16/32/64 as four of its 83 formats.

Its [2] cites the *integer-representations* paper instead, under a title that
belongs to neither work and reads like the defining one. The likely intent was
2404.18603.

Worth noting: the project's own takum8 pack cites 2404.18603 correctly in its
`format_notes`. **The artefact cites the right paper; the paper describing the
artefact does not.**

### 14.6 Recommended correction

```
[2]  L. Hunhold, "Beating Posits at Their Own Game: Takum Arithmetic,"
     arXiv:2404.18603, 2024.                        [if the defining work was meant]

[1]  D. Vasilev, "GoldenFloat: A Phi-Derived Static-Split Floating-Point Family
     from GF4 to GF1024 with a Lucas-Exact Integer Identity,"
     arXiv:2606.05017, 2026.

[8]  M. Wang et al., "M2XFP: A Metadata-Augmented Microscaling Data Format for
     Efficient Low-bit Quantization," arXiv:2601.19213, 2026.

[13] L. Hunhold, "Evaluation of Bfloat16, Posit, and Takum Arithmetics in Sparse
     Linear Systems," arXiv:2412.20268, 2024.
```

Verify [8] and [13] author lists against the API before pasting — this pass
checked their titles, not their author lists, and that is exactly the shortcut
that produced §8.5.

---

## 15. RETRACTION — the takum "fix" was not a fix (pass 34)

PR #281 is **closed unmerged and retracted by me**. It changed
`conformance/takum_ref.py` from sign-and-magnitude negation to two's complement,
on the strength of three converging measurements, and shipped with exhaustive
verification against libtakum.

It was still wrong, because I never read the module's own docstring. It opens, in
capitals:

> **СТАТУС КОДИРОВКИ — ВАЖНО**: Настоящий takum — ЛОГАРИФМИЧЕСКИЙ … значения в
> общем случае ИРРАЦИОНАЛЬНЫ и не допускают точной Fraction-арифметики … поэтому
> здесь реализована **РАБОЧАЯ СТРУКТУРНАЯ МОДЕЛЬ** … интерпретированная
> **ЛИНЕЙНО** … а НЕ логарифмически.

and states the decode explicitly as `value = (-1)^S · (1 + M_u/2^p) · 2^c` —
**sign-and-magnitude by design**, reverse-engineered from
`fpga/openxc7-synth/takum64_decode.v` and validated against named LUT codes.

The reason is principled and is the same one recorded for LNS in
`intrinsic_invariant_sweep.t27`: an exact-`Fraction` oracle cannot represent
logarithmic takum values, which are irrational.

### What was true, and what was not

| claim | status |
|---|---|
| the oracle disagrees with libtakum on the negative half | **true**, and now explained — a different model on purpose |
| posit satisfies the negation invariant, takum does not | **true**, but the invariant does not apply to a deliberate linear structural model |
| the change makes it match libtakum-linear 65536/65536 | **true, and irrelevant** — matching libtakum was never this file's goal |
| **it was a defect** | **false** |

The selftest kept passing throughout because the documented check vectors
(`0x40`/`0xC0` = ±1) are exactly the symmetric case where the two negation rules
coincide — the same blind spot §14's published-pack audit found in curated packs.

### Also retracted

The pass-32 framing *"SW and HW paths implement different variants under one name"*
is withdrawn as a finding. The split is **documented in that same docstring**, with
its reason. It is a design decision, not an undiscovered inconsistency.

### What survives

`research/libtakum_bridge.c` and the comparison scripts stand: they established
that the HW conformance golden is an exact implementation of logarithmic takum
(60485/60485 at takum16). That is a real, useful measurement independent of the
retracted interpretation.

### The lesson, recorded in the skill

**Read the artefact's own documentation before calling anything a defect.** Three
converging measurements and an exhaustive verification did not save me from it,
because all of them were answering the wrong question. Now in
`.claude/skills/t27-spec/SKILL.md`.

---

## 16. The paper's own title — a gap in this package, found in pass 58

Fifty-seven passes audited the *references'* titles and found 8 of 20 defective.
None of them looked at **the title of Paper B itself**.

The repository's own erratum quotes it:

> **Paper:** "An **84**-Format Numeric Catalog with Bit-Exact Conformance Vectors:
> A Vendor-Neutral Reference for FP8, BF16, MXFP4, and Microscaling Formats"
> (arXiv:2606.09686v1, 8 Jun 2026)

and then states plainly:

> **Canonical count going forward: 83.** The number 84 in the paper is superseded.

Four artefacts now agree on 83 — the SSOT `gHashTag/t27/specs/numeric/formats_catalog.t27`, a fresh codegen
re-run, `gHashTag/t27/conformance/vectors/INDEX_all_formats.json`, and the **v2 abstract**, whose only change from v1
was the single token `84` → `83` (§14 of this package). If the title still reads
*84-Format*, the paper's most visible number contradicts its own abstract, its own
repository, and its own erratum.

**This is not asserted as fact.** Network access was unavailable when this section
was written, so the *current* title of v2 was not re-fetched. What is established:
the v1 title said 84, the erratum supersedes 84, and the abstract was corrected. The
title is simply the one place nobody in this campaign checked.

**Action:** fetch `export.arxiv.org/api/query?id_list=2606.09686` and read the
`<title>` element. If it still contains *84-Format*, this belongs at the top of the
ordered fix list — a title is the one thing every reader sees, and arXiv permits a
title change on replacement.

### 16.1 A related standing warning in CI

`gHashTag/t27/tools/check_catalog_count.py` hardcodes

```python
# The count claimed in arXiv:2606.09686 Table 1 abstract ("exactly 84").
PAPER_DECLARED_COUNT = 84
```

so every CI run prints

```
WARN: SSOT (83) != paper count (84). An erratum to arXiv:2606.09686 is required
```

The comment attributes 84 to the **abstract**, which v2 corrected. Whether the
constant should become 83 depends on the title question above, so it is reported
rather than patched — changing a number to match an expectation that has not been
re-verified is the error this package exists to document.

What is unambiguous either way: a gate that warns on every run about an erratum
that has already been written is a gate people stop reading, and it will not be
believed on the day the divergence is real.

### 16.2 Resolved, 2026-08-01 — the title is fine

Fetched `export.arxiv.org/api/query?id_list=2606.09686` directly (the earlier
failure was WebFetch's summarising model, not the network):

```
TITLE    : An 83-Format Numeric Catalog with Bit-Exact Conformance Vectors:
           A Vendor-Neutral Reference for FP8, BF16, MXFP4, and Microscaling Formats
ID       : http://arxiv.org/abs/2606.09686v2
UPDATED  : 2026-06-22T12:28:45Z
```

**The v2 replacement corrected the title as well as the abstract.** Both read 83.
The concern raised in §16 was unfounded, which is why it was recorded as an open
question rather than a finding.

Two consequences.

**The CI constant is now unambiguously stale.** With title and abstract both at 83,
`PAPER_DECLARED_COUNT = 84` in `gHashTag/t27/tools/check_catalog_count.py` describes only the
withdrawn v1, and its permanent `WARN: an erratum is required` refers to work the v2
replacement already performed.

**The abstract's real defect is confirmed to survive v2.** Verbatim from the fetch:

> "a suite of **six** bit-exact conformance packs covering GF16, MXFP4 element,
> BF16, FP8 E4M3, FP8 E5M2, and E8M0 block scale"

against 83 packs in the artefact — 75 bit-exact and 8 structural. This remains the
single highest-value correction in this package, and it is now verified present in
the current published version, not inferred from an older one.

Also re-confirmed in the current text: "83 numeric formats spanning **13 families**"
(unverified — §5), and "IEEE P3109 **v3.2.0**" (not publicly checkable — §5).

### 16.3 Paper A, v3 — the flagged sentence is still there

```
ID     : http://arxiv.org/abs/2606.05017v3
UPDATED: 2026-06-22T12:03:17Z
```

> "An RTL-correctness erratum dated 2026-05-31 is reported in Section 5.5; **the
> fabricated TTSKY26b dies** carry the defective multiplier portfolio, and the
> corrected generator is the regeneration baseline."

Present verbatim in v3, having now survived two revisions. This is the only claim
in either paper that measurement contradicts, and §2 of this package gives the
replacement sentence.

One correction to this package's own framing while here: Paper A's abstract *does*
position the work against related families — "posit (2022 Posit Standard), takum
(Hunhold 2024, 2025), OCP-MX (Rouhani et al. 2023), and the IEEE P3109 multi-width
float draft". The related-work gap identified in pass 50 is narrower than stated: it
concerns published *conformance vector sets*, not format families, and the
ready-to-paste subsection should be introduced on those terms.
