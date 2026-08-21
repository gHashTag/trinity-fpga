# Erratum v2 — arXiv:2606.09686 (numeric format catalog)

**Article:** *An 84-Format Numeric Catalog with Bit-Exact Conformance Vectors: A Vendor-Neutral Reference for FP8, BF16, MXFP4, and Microscaling Formats*, D. Vasilev, [arXiv:2606.09686](https://arxiv.org/abs/2606.09686), submitted 2026-06-08.
**Type of correction:** correctness (format count) — blocks HW-replay reinforcement until release.
**SSOT:** `gHashTag/t27/specs/numeric/formats_catalog.t27` (repo gHashTag/t27, master branch).
**Verified:** 2026-07-04 — direct count `grep -c "// CATALOG: id="` = **83**, no duplicate ids; exactly **13** families (clusters).

---

## 1. The essence of the discrepancy

| What | Published (v1) | SSOT (fact) |
|---|---|---|
| Number of formats | **84** | **83** |
| Number of families | 13 | 13 ✓ (matches) |

The v1 title and abstract state "catalog of **84** numeric formats spanning 13 families". The current SSOT `gHashTag/t27/specs/numeric/formats_catalog.t27` contains **83** `// CATALOG:` records without duplicates. The families (clusters) match — the discrepancy is only in the number of formats, delta = 1.

## 2. Root of the delta 84 → 83 [established]

Of the 6 conformance packs listed in the abstract (GF16, MXFP4 element, BF16, FP8 E4M3, FP8 E5M2, **E8M0 block scale**), five have standalone rows in the SSOT catalog:

- `gf16`, `mxfp4`, `bfloat16`, `fp8_e4m3`, `fp8_e5m2` — present as separate catalog records;
- **`e8m0` (block scale) — is NOT a separate catalog row.** E8M0 is a scale component (shared exponent) of the microscale block, included in `mxfp4/mxfp6/mxfp8` (the Microscaling cluster), not a standalone numeric format.

The most likely reason for the number 84 in v1 is counting E8M0 block scale as a separate format on equal footing with the element formats. The canonical SSOT treats E8M0 as a component of microscaling, so the canonical number = **83**.

> Note: E8M0 has a conformance pack covering the block-scale component. Nothing here cancels it; this only clarifies that E8M0 is not counted as a separate catalog row.

**Correction to this erratum, pass 276.** The sentence above previously read "the presence of a conformance pack for E8M0 is correct and **remains in force**". It was not true when written: on the day this erratum was drafted no `e8m0` pack existed in `conformance/vectors/` and no oracle in `conformance/*_ref.py` carried an `e8m0` format key. Only a decode *host* existed, plus RTL wrappers and a Tier-E decode cell — which is why the hardware claim was never affected. Pass 266 built the missing pieces: `conformance/e8m0_ref.py`, and `e8m0_add.json` / `e8m0_mul.json` at 65,536 vectors each, exhaustive over all 256×256 operand pairs. There is deliberately no `e8m0_sub.json` — E8M0 has no sign bit and no zero, so negation is undefined for it. The sentence is now true; it is corrected here rather than quietly edited because it was written as a reassurance about something nobody had checked, and that is the kind of sentence worth leaving a mark on.

## 3. Corrections (v1 → v2)

1. **Title:** "An **84**-Format Numeric Catalog …" → "An **83**-Format Numeric Catalog …".
2. **Abstract:** "a catalog of **84** numeric formats spanning 13 families" → "a catalog of **83** numeric formats spanning 13 families".
3. **All occurrences of "84" in the body of the article** referring to the catalog size → **83**. The number of families (13) does not change.
4. Add a footnote: "E8M0 block scale is covered by a dedicated conformance pack but is enumerated as the shared-exponent component of the Microscaling family, not as a standalone catalog row; the canonical catalog size defined by `gHashTag/t27/specs/numeric/formats_catalog.t27` is 83."

## 4. What does NOT change

- 13 families — correct.
- Six conformance packs (including E8M0) — correct, remain.
- The identity φ² + φ⁻² = 3 as anchor vector — correct.
- P3109 v3.2.0 cross-walk — not affected.
- The claim "registry filling, no new formats, no superiority claims" — retained.

---

## EN version (for arXiv erratum / v2 comment)

**Erratum (v2).** The v1 title and abstract state a catalog of *84 numeric formats spanning 13 families*. The single source of truth `gHashTag/t27/specs/numeric/formats_catalog.t27` (repo gHashTag/t27, master) contains **83** catalog records with no duplicate ids; the family count (13) is unchanged. The discrepancy of one arises from counting the **E8M0 block scale** as a standalone format: E8M0 is the shared-exponent component of the Microscaling family (mxfp4/6/8), covered by its own conformance pack, but not enumerated as a standalone catalog row. The canonical catalog size is therefore **83**. All occurrences of "84" referring to the catalog size are corrected to **83**; the six conformance packs (including the E8M0 pack) and the φ²+φ⁻²=3 anchor identity are unchanged.

---

## Actions

- [ ] Update `docs/arxiv-submission/*` and the source of the catalog article: 84 → 83 (per item 3).
- [ ] Release v2 on arXiv with this erratum comment.
- [ ] Only AFTER v2 — attach the random-10 HW-replay to the second article (otherwise a reviewer will catch 84 vs replay-from-83).

*All claims verified against the live SSOT 2026-07-04. Delta established (E8M0), family count confirmed (13).*
