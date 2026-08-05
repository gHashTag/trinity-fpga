# Submission package — arXiv:2606.05017 + 2606.09686 (prepared 2026-08-05)

> Everything needed to publish updated versions, in one index. **Prepared material
> only — the arXiv replacement and PR merges require the author's credentials
> (ARXIV_V2_CORRECTION_PACKAGE §11).** Nothing here is a submission.

## Headline new result (strongest for the paper)
- **GF-T16 — a ternary-native GoldenFloat that beats tekum16** (measured ×3 mid-range,
  ×5.5 far-range; uniform 9-bit vs tekum's tapered 4-bit; no regime decode; exponent
  added natively in balanced ternary). Spec `t27/specs/numeric/gft16.t27`, oracle
  `conformance/gft16_ref.py`, RTL-sim conformance 30/30, adder 461 LC / 0 DSP.
  → `GFT16_BEATS_TEKUM16_2026-08-05.md`, `ARXIV_GFT16_SNIPPET.md` (ready LaTeX),
  full ladder GF-T4…GF-T1024 in `GF_T_GOLD_STANDARD_LADDER_2026-08-05.md`.

## Paper A — arXiv:2606.05017 (GoldenFloat), for v4
1. **Remove "fabricated TTSKY26b dies"** (false physical claim, alive through v3) —
   PR #17 / commit `925bdf6d` in trinity-papers-ru (**unmerged**). Replacement wording
   in `ARXIV_ABSTRACTS_READY_TO_PASTE.md`.
2. **Reconcile the board §1.2** (abstract XC7A35T / body XC7A100T-FGG676 / hardware
   XC7A200T-FBG484) + separate bare-core combinational Fmax (323 MHz) from routed
   Fmax (~27.55 MHz) — `XC7A200T_GF16_DATAPOINT_2026-08-05.md`.
3. **Add GF-T16** as a new §/table (the head-to-head win above) — `ARXIV_GFT16_SNIPPET.md`.
4. **GFTERNARY honesty**: it is a 2-bit φ-alphabet on a float mul (2 DSP/1191 LC), not
   ternary compute; the real ternary core is TF3/trinet_mac32 (0 DSP/398 LC) —
   `ARXIV_GFTERNARY_HW_SNIPPET.md`.
5. Citations: IEEE 754, TestFloat-3, FLoPS, Jack-of-All-Scales; `-nodsp` soft-logic
   subsection — `ARXIV_BODY_FIXES_READY_TO_PASTE.md`.

## Paper B — arXiv:2606.09686 (catalog), for v3
1. **84 → 83 formats** everywhere (E8M0 is a microscaling component) — `ERRATUM_arXiv_2606.09686_catalog_count.md`; still uncorrected in `paper3-methodology/main.tex`.
2. Abstract "6 packs" → "83 packs, 75 bit-exact + 8 structural"; "72/83 strict oracle,
   11 structural-by-design" — `MISSING_FORMATS.md`.
3. Fix the 12 bibliography defects (esp. [3] misattribution).
4. **Optional**: add the GF-T ternary-native ladder as a new format family + the
   full ternary-competitor comparison (tekum/takum/BitNet/posit) — strongest breadth result.

## Landing order (repo ⇄ preprint must agree before arXiv replacement)
1. Merge **trinity-papers-ru PR #17** (`925bdf6d`) — removes fabricated-dies, standardizes on AX7203/XC7A200T.
2. Land t27 codegen branches to master: `fix/gen-verilog-array-lowering` (`701d79b3`),
   `fix/r7-rust-wrapping-ops` (`377d9a27`), `fix/gf16-conformance-vectors` — so the cited SSOT matches.
3. Apply the erratum + abstract/body fixes to `goldenfloat-preprint` / `paper3-methodology`.
4. Author submits the new arXiv versions (their credentials).

## Science that HOLDS (recompute-verified, safe to keep)
φ-rule 17/17 · Lucas identity 256/256 (500-digit) · ml_dtypes cross-val 66,224/0 ·
83 SHA-256 conformance fingerprints · GF16 @322–323 MHz · GF8/GF16 add+mul bit-exact
on real AX7203 silicon (5/5, 529/529) · GF-T16 add RTL-sim 30/30.
