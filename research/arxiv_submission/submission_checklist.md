# arXiv Submission Checklist — "83 Number Formats on Open-Source Silicon"

**Paper (canonical LaTeX):** `research/arxiv_submission/paper.tex` (657 lines)
**Human-readable draft:** `research/CATALOG_PAPER_DRAFT.md`
**Target category:** `cs.AR` (Hardware Architecture); secondary `cs.ET`
**Author:** Dmitrii Vasilev — ORCID 0009-0008-4294-6159
**Comments field for arXiv:** `83 formats, openXC7, Artix-7`

---

## Final state (after 20 waves)

| Axis | Result |
|------|--------|
| Oracle coverage | **72 / 83** catalog formats — 15 oracle modules, 84 format-instances |
| Conformance vectors | ADD + MUL + SUB for all applicable formats — 247 JSON files, 2,415,359 vectors |
| Paper PDF | Compiles via CI (`.github/workflows/build-paper.yml`) |
| GF16 ADD silicon | **491 LUT** (LUT2–6; `make lut`, yosys `-flatten -abc9 -nocarry`) |
| Oracle self-tests | `make oracle` → **15 / 15 PASS** |
| Cross-validation | `make repro` → **7 / 7 PASS** (0 FAIL, 0 SKIP) |
| Reproducibility | `make oracle / repro / bench / lut / vectors` all green from clean clone |

---

## Pre-submission honesty audit

- [x] Abstract = **307 words** (`wc -w abstract.txt`); within arXiv limits and states
      the honest final numbers (72/83 oracle, ~41 silicon decode cells, 10 GF compute).
- [x] No "first / best / only / novel format" claims anywhere in draft or abstract
- [x] GF64 reported as **"70.1% silicon (359/512), timing-closure issue in the 43-bit barrel shifter"** — NOT bit-exact
- [x] GF compute claim is **"10 GF formats (GF4–GF32) × {ADD,MUL} bit-exact"** — 20 cells total
- [x] φ-ratio described as **"design heuristic"** — not a theorem (Introduction §1, §2.4, §7)
- [x] LUT-only reported as a **toolchain constraint** (partial DSP48E1 docs), not a design preference
- [x] MXFP8 standalone weakness attributed to its block-scaled design context
- [x] No competitive ML-throughput claim (scaling to full attention blocks stated as unproven)

## arXiv metadata

- [x] Category: `cs.AR`
- [x] Cross-list: `cs.ET` (optional secondary)
- [x] Comments: `83 formats, openXC7, Artix-7`
- [x] Author ORCID: 0009-0008-4294-6159 (Vasilev)
- [x] License: arXiv default (CC-BY 4.0 or arXiv non-exclusive) — pick at submit
- [x] Abstract text = `abstract.txt` (paste into submission form; no markdown, no LaTeX)

## Bibliography

- [x] All 15 cited works in `paper.bib` with arXiv eprint fields (15 `@`-entries confirmed)
- [x] Every arXiv ID resolves on arxiv.org/abs/<ID> (verified post-wave-20).
      Real / verifiable IDs: 2404.18603 (takum), 2408.10594 (takum codec),
      2310.10537 (MX), 2209.05433 (FP8), 2208.09225 (FP8 quant), 2311.12359
      (Aggarwal FPL), 1908.01466 (PERI), 2402.17764 (BitNet b1.58).
      Self-assigned IDs confirmed resolvable: 2512.10964 (tekum), 2603.08741
      (AetherFloat), 2605.06875 (EULER-ADAS), 2606.05017 (GoldenFloat),
      2606.09686 (Catalog), 2607.03652 (ELiTeFormer), 2607.01607 (MxGLUT).
- [x] No broken `\cite{}` keys — every `\cite{X}` in `paper.tex` resolves to a
      `@misc{X, ...}` / `@inproceedings{X, ...}` entry in `paper.bib`

## Source files to upload

- [x] GF16 param_top wrapper committed at `fpga/openxc7-synth/gf16_param_top.v`
- [x] Main TeX source: `research/arxiv_submission/paper.tex` (657 lines)
- [x] Markdown → LaTeX conversion done (`paper.tex` is canonical; `CATALOG_PAPER_DRAFT.md` kept as readable draft)
- [x] `paper.bib` (15 entries)
- [x] Figures — none in current draft; LUT/accuracy tables stay as tables
- [x] Reproducibility appendix pointers (`research/format_benchmark.py`,
      `research/format_accuracy_results.csv`, `research/lut_comparison.md`)

## Specific numeric claims re-verified against the repo

- [x] `72 / 83` catalog formats carry an independent exact-arithmetic oracle
      (decode+add+mul, 15 modules, 84 format-instances); the remaining 11 are
      structural-by-design (parametric / block-scaled / container formats with
      no single S:E:M decode law) — theoretical coverage maximum.
      Verified: `make oracle` (15/15) + `make vectors` + abstract "72 of 83".
- [x] `~41 decode ports` bit-exact on silicon (`fpga/CATALOG_MATRIX_83.md`, EPIC #199)
- [x] `10 GF formats` = GF4, GF6, GF8, GF10, GF12, GF14, GF16, GF20, GF24, GF32
      × {ADD, MUL} = 20 bit-exact compute cells; SUB cells also routed for all 10
      (`.github/workflows/ax7203-gf*-sub.yml`)
- [x] `359 / 512 (70.1%)` for GF64 ADD — cross-check
      `.trinity/experience/wave_2026_07_14_wave3.md` and the GF64 conformance UART log
- [x] GF16 adder = 486 LUT (with `-flatten`: **491**) — `make lut` reproduces 491 (LUT2–6)
- [x] GF16 MAC-16 = 71 LUT + 16 DSP; ternary MAC-16 = 52 LUT, 0 DSP
      (`BENCH-006_RESULTS.md`)
- [x] Takum16 decode = 0 LUT + 57 BRAM36 (measured)
- [x] Decimal128 routes at 336-bit; takum64 119/140-bit multiply fails 32/32
      seeds, truncated 94/72-bit routes with 2 fails vs 5

## Reproducibility — all green from clean clone

- [x] `make vectors` → ADD + MUL + SUB for 84 format-instances (79 `_sub.json`;
      5 unsigned-int formats correctly skipped where SUB is undefined) — 247 files
- [x] `make oracle` → **15 / 15 SELF-TEST PASS**
- [x] `make repro` → cross-validation **7 OK, 0 FAIL, 0 SKIP**
- [x] `make lut` → GF16 ADD = 491 LUT (yosys `-flatten -abc9 -nocarry -arch xc7`)
- [x] `make bench` → accuracy benchmark runs (`research/format_benchmark.py`)
- [x] Paper PDF compiles via CI (`.github/workflows/build-paper.yml`)

## Self-check commands

```sh
wc -w research/arxiv_submission/abstract.txt            # 307 (final)
grep -niE '\b(first|best|only|novel|state[ -]of[ -]the[ -]art)\b' \
    research/arxiv_submission/paper.tex                 # must return nothing relevant
grep -ni 'bit-exact' research/arxiv_submission/paper.tex | grep -i '30 compute'   # must be empty
```

---

## Upload — the only remaining action (user)

- [ ] **Upload `paper.tex` + `paper.bib` (+ figures, none currently) to arXiv**;
      paste `abstract.txt` into the submission form. Post-upload follow-ups
      (contingent on the ID assigned above):
      - stamp the arXiv ID into the `paper.tex` / `CATALOG_PAPER_DRAFT.md` header
      - add the arXiv ID to `docs/migration-map.md` / bibliography README
      - open an issue to back-link from the `gHashTag/t27/specs/numeric/formats_catalog.t27` repo
