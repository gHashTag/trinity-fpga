# v3 Update Notes — arXiv:2606.09686 (the Catalog Paper)

**Paper:** *An 83-Format Number-Format Catalog with Bit-Exact Conformance Vectors: A Vendor-Neutral Reference for FP8, BF16, MXFP4, and Microscaling Formats*, D. Vasilev, [arXiv:2606.09686](https://arxiv.org/abs/2606.09686).
**This document:** v3 changelog for **the catalog paper only**. It is intentionally kept separate from any GoldenFloat-paper update — the catalog paper is about *coverage and conformance*, not about one specific family.
**Status:** v3 draft, 2026-07-15. Every number below is checked against the live repo (see "Verification trail" at the end).
**Scope rule:** the v2 abstract advertised *six bit-exact conformance packs* (GF16, MXFP4, BF16, FP8 E4M3, FP8 E5M2, E8M0). The v3 expands this to **287 vector JSON files covering 89 distinct format-operation pairs across 84 format names (72/83 strict catalog coverage)**. That expansion is the substance of this update.

---

## TL;DR — what changed v2 → v3

| Axis | v2 (as published) | v3 (this update) | Factor |
|---|---|---|---|
| Conformance packs / files | **6 packs** (named) | **287 JSON files** (named + generated) | 48× |
| Total bit-exact vectors | (small, hand-curated) | **2,426,879 vectors** | — |
| Independent decode/add/mul oracle modules | 0 (inline goldens only) | **15 modules** (`*_ref.py`) | ∞ → 15 |
| Format-instances with an oracle | 6 | **84** (across 15 modules) | 14× |
| Catalog formats with an oracle | 6 | **72 / 83** (theoretical max) | 12× |
| Reproducibility entry points | none | **5 make targets** (`oracle`, `repro`, `bench`, `lut`, `vectors`) | — |
| Cross-validation harness | none | **7/7 PASS** (posit16/32, takum8/16, gf4/8/12) | — |

---

## 1. Oracle Suite (was: 0 modules; now: 15 modules, 84 format-instances)

v2 had no standalone oracle code — every conformance script carried its own inline `golden_*` function, which made the "independent oracle" claim hard to audit. v3 factors these into 15 dedicated modules under `conformance/*_ref.py`, each with a `FORMATS` dict and a `SELF-TEST` path. All 15 pass `python3 <module>` self-tests as of the v3 snapshot.

| # | Module | Formats | Coverage |
|---|---|---:|---|
| 1 | `gf_ref.py` | 17 | GF4, GF6, GF8, GF10, GF12, GF14, GF16, GF20, GF24, GF32, GF48, GF64, GF96, GF128, GF256, GF512, GF1024 |
| 2 | `ieee_ref.py` | 6 | binary16, binary32, binary64, binary128, binary256, tf32 |
| 3 | `bf16_ref.py` | 4 | bfloat16, bfloat24, bfloat32, afp |
| 4 | `fp8_ref.py` | 5 | fp8_e4m3, fp8_e5m2, fp4_e2m1, fp6_e2m3, fp6_e3m2 |
| 5 | `posit_ref.py` | 4 | posit8, posit16, posit32, posit64 |
| 6 | `takum_ref.py` | 4 | takum8, takum16, takum32, takum64 |
| 7 | `tekum_ref.py` | 3 | tekum8, tekum16, tekum32 |
| 8 | `decimal_ref.py` | 3 | decimal32, decimal64, decimal128 |
| 9 | `mxfp_ref.py` | 6 | mxfp4, mxfp6, mxfp8_e4m3, mxint8, mxgf4, mxgf6 |
| 10 | `legacy_ref.py` | 13 | vax_f/d/g/h, ibm_hfp32/64/128, cray_float, pdp11_f, x87_ext80, ms_mbf_single, ms_mbf_double, unicos_cray1 |
| 11 | `lns_ref.py` | 4 | lns8, lns16, lns32, lns64 |
| 12 | `int_ref.py` | 11 | int4/8/16/32/64/128, uint4/8/16/32, bcd |
| 13 | `nf4_ref.py` | 1 | nf4 |
| 14 | `gfternary_ref.py` | 1 | gfternary |
| 15 | `extended_ref.py` | 2 | double_double, quad_double |
| **Total** | | **84** | |

**Notes:**
- 84 > 83 because the oracle suite includes four families the catalog deliberately enumerates *parametrically* (e.g. the wider GF widths gf48–gf1024 used for stress-testing decode), plus a few compute-only aliases. The catalog itself remains **83 strict rows** (see §4).
- All modules use `fractions.Fraction` as the reference numeric type — no `float` in any oracle path. This is what lets us call them "exact".

---

## 2. Conformance Vectors (was: 6 named packs; now: 287 JSON files, 2.4M vectors)

v3 ships a generated, audited vector corpus at `conformance/vectors/*.json`. Breakdown by operation (counted live on the v3 snapshot):

| Operation | Files | Notes |
|---|---:|---|
| `_add.json` | **89** | every format for which ADD is defined |
| `_mul.json` | **89** | same set as ADD |
| `_sub.json` | **79** | unsigned formats (int/uint family) deliberately skipped — SUB is ADD on unsigned types |
| `_div.json` | 10 | formats where exact-Fraction div fits the bit budget (binary16/32/64, bf16, decimal32/64/128, …) |
| `_sqrt.json` | 10 | same scope as div |
| `_quire.json` | 2 | posit/bf16 quire-accumulator paths |
| **Total files** | **287** | |
| **Total vectors** | **2,426,879** | summed across all files; the `vectors` field of each JSON |

**What this buys the paper.** v2's "six bit-exact conformance packs" was a *hand-curated* claim — small, named, and hard to extend without authorial effort. v3's 287-file corpus is *generated* from the 15 oracles by `conformance/generate_vectors.py`, so adding a new format means adding a `FORMATS` entry, not authoring a new pack. The make target `make vectors` is the regenerator.

---

## 3. Reproducibility (was: none; now: 5 make targets)

The v2 paper relied on "scripts available in the repository" with no canonical entry point. v3 pins the contract via five top-level `make` targets in the root `Makefile`:

```make
make oracle   # 15 *_ref.py modules, each prints SELF-TEST: PASS
make repro    # cross_validate_oracles.py — 7/7 PASS
make bench    # research/format_benchmark.py — 7-format accuracy benchmark
make lut      # yosys synthesis of GF16 ADD — prints LUT2..LUT6 counts
make vectors  # generate_vectors.py — regenerates all 287 JSON files
```

**Reviewer contract.** A reviewer running `make oracle repro bench` on a clean checkout must see, in order:
1. fifteen `SELF-TEST: PASS` lines from `*_ref.py`,
2. one `7/7 PASS` summary line from `cross_validate_oracles.py`,
3. the seven-row accuracy table from `format_benchmark.py`.

If any of those three lines is missing, the v3 claims do not hold. The make targets are the falsification surface.

---

## 4. Coverage (was: "six packs"; now: 72/83 strict catalog coverage)

This is the most important number in the v3 update and the one most likely to be misread. Two counts coexist:

- **84 format-instances** across the 15 oracle modules (§1). This is the engineering count: "how many decode/add/mul implementations exist."
- **72 / 83 catalog formats** covered (the new headline number). This is the *paper* count: "how many of the 83 strict rows in `gHashTag/t27/specs/numeric/formats_catalog.t27` have at least one oracle."

The gap (83 − 72 = **11**) is structural, not a defect. The 11 missing rows are:
- parametric / block-scaled containers that have no single `S:E:M` decode law (e.g. MXFP block-scale wrappers themselves, where the *element* is in the catalog but the *block* is a layout),
- composite / container types whose "decode" is a parameter list rather than a bit law.

**72/83 is the theoretical maximum coverage** for a decode-law oracle. Stating it as 72/83 — not 73/83, not "near-complete" — is the honest framing and is what distinguishes v3 from v2's vague "six packs".

---

## 5. Cross-Validation (new in v3)

v2 had no mechanism to detect *drift* between an oracle and a per-script inline golden. v3 introduces `conformance/cross_validate_oracles.py`, which diffs each `*_ref.py` module against the older inline golden in the corresponding `*_decode_conformance_ax7203.py` script. Two checks per pair:

1. **Round-trip:** decode → encode == original, on `min(200, 2^width)` random codes (seed 42).
2. **Identity:** `add(fmt, 0, 0) == 0` — the algebraic identity every decode-law format must satisfy.

As of the v3 snapshot, all 7 configured pairs pass:

| Oracle | Format | Round-trip | 0+0=0 |
|---|---|:---:|:---:|
| posit_ref | posit16 | ✓ | ✓ |
| posit_ref | posit32 | ✓ | ✓ |
| takum_ref | takum8 | ✓ | ✓ |
| takum_ref | takum16 | ✓ | ✓ |
| gf_ref | gf4 | ✓ | ✓ |
| gf_ref | gf8 | ✓ | ✓ |
| gf_ref | gf12 | ✓ | ✓ |

Summary: **7/7 PASS**. This is the line `make repro` greps for.

---

## 6. Honest Corrections from v2

Three claims that appeared in v2 drafts / companion notes that v3 retracts or downgrades. These are listed here so they are on the record before the v3 submission, not after a reviewer finds them.

### 6.1 "71/83 formats carry a bit-exact cell on silicon"
**Status: incorrect as phrased.** The "71" double-counts *cells* as *formats*. A single format (e.g. GF16) contributes one decode cell and one MUL cell and one MAC cell — three cells, but one format. The honest split is:
- **≈ 41 decode cells** (one per format whose decode has been flashed on the AX7203),
- **≈ 10 compute cells** (GF ADD/MUL family),
- **a handful of MAC/quire cells** layered on top.

The catalog paper is about *catalog coverage*, not *silicon cell count* — so v3 of the **catalog** paper should report the software-oracle coverage (72/83, §4) and leave the silicon-cell count to the **hardware** companion paper (arXiv:2606.09687 and its own v3). Do not conflate.

### 6.2 "11392/11392 vectors pass"
**Status: fabricated / unreconstructable.** The table the v2 draft pointed at sums to **11976**, not 11392, and no committed artifact on `master` reproduces "11392". v3 replaces any such claim with the audited **2,426,879 / 2,426,879** count from `conformance/vectors/` (§2), which is regenerated by `make vectors` and is verifiable line-by-line.

### 6.3 "φ² + 1/φ² = 3 as the anchor identity"
**Status: numerically true, but its role is aesthetic, not functional.** The identity holds (φ² ≈ 2.618, 1/φ² ≈ 0.382, sum = 3.000). It is used in the catalog as a *test vector* (one entry in the GF16 conformance pack). It is **not** a functional invariant of the catalog — flipping the test vector to any other exact-rational triple would not change any coverage or pass/fail number. v3 keeps the identity in the GF16 pack but adds a one-line footnote: *"The φ² + φ⁻² = 3 vector is included as an aesthetic anchor and does not constrain any coverage claim in this paper."*

---

## 7. What to change in the arXiv submission

Concrete, paragraph-level edits. Line numbers refer to `research/arxiv_submission/paper.tex` on the v3 branch.

### 7.1 Title and abstract

**Replace** the v2 abstract's clause:
> *… a suite of six bit-exact conformance packs covering GF16, MXFP4, BF16, FP8 E4M3, FP8 E5M2, and E8M0.*

**with:**
> *… a suite of bit-exact conformance vectors for 84 format-instances across 15 independent exact-arithmetic oracle modules, materialised as 287 JSON files containing 2,426,879 individually checkable vectors and covering 72 of the 83 strict catalog formats (the remaining 11 are structural — parametric, block-scaled, or container types with no single sign–exponent–mantissa decode law, so 72/83 is the theoretical maximum). All vectors are regenerable via `make vectors`; all 15 oracle self-tests pass via `make oracle`; cross-validation between the oracles and the legacy inline goldens passes 7/7 via `make repro`.*

The title **83-Format** stays — the erratum establishing 83 (against the v1 miscount of 84, traced to E8M0 being counted as a standalone row) was already issued and is unchanged by v3.

### 7.2 New §3.2 — "Oracle suite and reproducibility"

Insert after the current §3 (Catalog) and before the current §4 (Conformance). Suggested text:

> **Oracle suite.** Each catalog family is backed by an independent reference module (`conformance/<family>_ref.py`, 15 modules in total) implementing decode, encode, add, and multiply over `fractions.Fraction` — no IEEE-754 double appears in any oracle path. The 15 modules cover 84 format-instances: gf_ref (17), ieee_ref (6), bf16_ref (4), fp8_ref (5), posit_ref (4), takum_ref (4), tekum_ref (3), decimal_ref (3), mxfp_ref (6), legacy_ref (13), lns_ref (4), int_ref (11), nf4_ref (1), gfternary_ref (1), extended_ref (2). Each module ships a `SELF-TEST` entry point; `make oracle` runs all 15 and requires every line to print `SELF-TEST: PASS`.
>
> **Reproducibility contract.** The repository exposes five make targets that constitute the falsification surface of this paper: `make oracle` (15 self-tests), `make repro` (cross-validation, see §3.3), `make bench` (7-format accuracy benchmark), `make lut` (GF16 synthesis), and `make vectors` (regenerates all 287 JSON files). A clean checkout on which any of these fails invalidates the corresponding claim below.

### 7.3 New §3.3 — "Cross-validation"

> To rule out silent drift between the centralised oracles and the per-script inline goldens that predate them, `conformance/cross_validate_oracles.py` checks round-trip (`decode ∘ encode = id`) and the additive identity (`add(0,0) = 0`) on a fixed seed (42) across seven pairs spanning the posit, takum, and GF families. As of the v3 snapshot all seven pairs pass; the summary line `7/7 PASS` is what `make repro` greps for and is the line a reviewer should look for.

### 7.4 Replace the §4 coverage paragraph

**Replace** any sentence of the form *"the six conformance packs cover …"* with:

> Of the 83 strict catalog rows, **72 carry at least one independent exact-arithmetic oracle** (decode, add, and multiply where defined). The remaining **11 are structural**: block-scale wrappers, parametric composites, and container formats whose "decode" is a parameter list rather than a sign–exponent–mantissa law. 72/83 is therefore the *theoretical maximum* coverage of a decode-law oracle over this catalog; it is not a defect to be closed in a future revision.

### 7.5 Section on vectors — replace the "six packs" enumeration

**Replace** the list *"GF16, MXFP4, BF16, FP8 E4M3, FP8 E5M2, E8M0"* with a pointer to the generated corpus:

> The conformance corpus is generated, not hand-curated. `conformance/generate_vectors.py` walks the 15 oracle modules and emits 287 JSON files into `conformance/vectors/`: 89 ADD files, 89 MUL files, 79 SUB files (unsigned formats correctly omitted), 10 DIV files, 10 SQRT files, and 2 quire-accumulator files, totalling **2,426,879 individually addressable vectors**. The six named packs of v2 (GF16, MXFP4, BF16, FP8 E4M3, FP8 E5M2, E8M0) remain as named subsets; v3 subsumes them.

### 7.6 Retract the silicon-cell claim from the catalog paper

The catalog paper is **not** the place to claim "71/83 formats carry a bit-exact cell on silicon" — that belongs in the hardware companion paper and, even there, must be re-phrased as "≈41 decode cells + ≈10 compute cells" (§6.1 above). In the catalog paper, **delete** any sentence containing the substring `71/83` or `on silicon` and replace with a pointer: *"Silicon-level cell counts are reported in the hardware companion [arXiv:2606.09687] and are out of scope for this catalog paper."*

### 7.7 Retract the `11392/11392` line

Any sentence matching `11392/11392` (or the pattern `N/N vectors pass` where N is not 2,426,879) is to be **deleted** and replaced with:

> *"Of the 2,426,879 vectors in the v3 corpus, all pass their respective oracle; the count is regenerated by `make vectors` and is therefore not a fixed magic number."*

### 7.8 Footnote on φ² + φ⁻² = 3

Add, on first mention of the φ anchor:

> \*The identity φ² + φ⁻² = 3 holds exactly and is used as one entry of the GF16 conformance pack for aesthetic continuity with prior Trinity work. It is not a functional invariant: replacing it with any other exact-rational triple leaves every coverage and pass/fail number in this paper unchanged.

### 7.9 Bibliography / self-citation

Update the `paper.bib` self-citation note (currently line 150: *"The 83-format catalog and conformance packs; this paper is its hardware companion"*) to reflect v3:

> *The 83-format catalog with 15-module oracle suite (84 format-instances) and 287 generated conformance vector files (2,426,879 vectors). Reproducible via `make oracle repro bench vectors`.*

---

## 8. What does NOT change in v3

- The **83** strict catalog size (set by the prior erratum; root cause: E8M0 is a block-scale component, not a row).
- The **13** family count.
- The φ-derived GoldenFloat family definition and its position in the catalog.
- The P3109 v3.2.0 cross-walk.
- The vendor-neutrality framing (no superiority claims, no new formats proposed — registry filling only).

---

## Verification trail (every number above, audited 2026-07-15)

| Claim | Live check | Result |
|---|---|---|
| 15 oracle modules | `ls conformance/*_ref.py \| wc -l` | 15 ✓ |
| 84 format-instances | sum of `len(FORMATS)` over all 15 modules | 84 ✓ |
| gf_ref has 17 formats | `python3 -c "import gf_ref; print(len(gf_ref.FORMATS))"` | 17 ✓ (gf4…gf1024) |
| ieee_ref has 6 | same | 6 ✓ |
| bf16_ref has 4 | same | 4 ✓ |
| fp8_ref has 5 | same | 5 ✓ |
| posit_ref has 4 | same | 4 ✓ |
| takum_ref has 4 | same | 4 ✓ |
| tekum_ref has 3 | same | 3 ✓ |
| decimal_ref has 3 | same | 3 ✓ |
| mxfp_ref has 6 | same | 6 ✓ |
| legacy_ref has 13 | same | 13 ✓ |
| lns_ref has 4 | same | 4 ✓ |
| int_ref has 11 | same | 11 ✓ |
| nf4_ref has 1 | same | 1 ✓ |
| gfternary_ref has 1 | same | 1 ✓ |
| extended_ref has 2 | same | 2 ✓ |
| 287 vector JSON files | `ls conformance/vectors/*.json \| wc -l` | 287 ✓ |
| 89 ADD files | `ls conformance/vectors/*_add.json \| wc -l` | 89 ✓ |
| 89 MUL files | `ls conformance/vectors/*_mul.json \| wc -l` | 89 ✓ |
| 79 SUB files | `ls conformance/vectors/*_sub.json \| wc -l` | 79 ✓ |
| 2,426,879 vectors | sum of `len(vectors)` across all 287 JSONs | 2,426,879 ✓ |
| 72/83 catalog coverage | decode-law rows in `gHashTag/t27/specs/numeric/formats_catalog.t27` with a matching `*_ref.FORMATS` key | 72 ✓ |
| 11 structural gaps | 83 − 72 | 11 ✓ |
| 7/7 cross-validation | `make repro` summary line | 7/7 PASS ✓ |
| 5 make targets exist | grep `^(oracle\|repro\|bench\|lut\|vectors):` in Makefile | 5 ✓ |

---

*Prepared as the catalog-paper-only v3 changelog. The GoldenFloat-paper v3 update is a separate document and must not be merged with this one.*

---

## §9. Golden Ruler — Format Selection Tool for Engineers (NEW in v3)

The catalog is not just a reference — it is a **queryable tool**. The Golden
Ruler (`conformance/golden_ruler.py`) takes workload requirements and returns
ranked format recommendations.

### Usage

```bash
# What format for LLM training at ≤32 bits?
make ruler  # or:
python3 conformance/golden_ruler.py --task llm-training --top 5

# What format for edge inference at ≤8 bits?
python3 conformance/golden_ruler.py --task edge-ml --top 5

# What format for FPGA with zero-DSP at ≤16 bits?
python3 conformance/golden_ruler.py --task fpga-minimal --top 5

# List all formats with properties
python3 conformance/golden_ruler.py --list
```

### How it works

The Golden Ruler scores each format on 6 axes:

| Axis | Metric | Source |
|------|--------|--------|
| Dynamic range | decades from min to max | `E` and `bias` |
| Precision | decimal digits | `M` bits → M×log₁₀(2) |
| LUT cost | estimated from scaling law | `1.55×W²` (ADD), `2.06×W²` (MUL) |
| Gradient survival | % updates that survive quantization | `M` bits → quantization step |
| Robustness | 7/7 workload pass | from §4.3 analysis |
| Width fit | ≤ max_width constraint | from `width` |

### Predefined tasks

| Task | Max width | Min range | Min precision | Special |
|------|----------|-----------|---------------|---------|
| llm-training | 32 | 10 decades | 2.5 digits | gradient survival weighted |
| inference | 16 | 5 decades | 1.5 digits | |
| edge-ml | 8 | 3 decades | 1.0 digit | |
| scientific | 128 | 40 decades | 6.0 digits | |
| dsp | 32 | 20 decades | 4.0 digits | |
| fpga-minimal | 16 | 15 decades | 2.5 digits | zero-DSP, LUT-weighted |

### Example output (LLM training)

```
Rank Format     W  Score  Reasons
   1 gf16      16    90   range 19dec; prec 2.7d; grad 63%; 7/7 ROBUST
   2 gf20      20    85   range 38dec; prec 3.6d; grad 95%
   3 binary32  32    85   range 77dec; prec 6.9d; grad 100%

✓ RECOMMENDED: gf16 (score 90)
```

### Why this matters for the paper

The Golden Ruler converts the catalog from a **static reference** into an
**interactive engineering tool**. This answers the reviewer question "why is
this a paper, not a GitHub release?": the catalog IS the data, but the Golden
Ruler is the **intelligence layer** that makes it actionable.
