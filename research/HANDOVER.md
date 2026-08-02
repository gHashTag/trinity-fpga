# Handover — what to do with 174 passes of verification

One page. Everything below is either a change to make before submission, a claim the
papers under-state, a data fix that is ready, or a question only you can answer.

Nothing here is a suggestion about direction. Each item names what was measured, where
the measurement lives, and what it costs to act on.

> Read `research/SUBMISSION_CHECKLIST.md` for the full argument on any line. This page
> exists because that file is 600 lines and this is the part you act on.

---

## 1. Must change — a reviewer would catch these

| # | paper | change | why | cost |
|---|---|---|---|---|
| 1 | **B, abstract** | "a suite of **six** bit-exact conformance packs" → **83 packs (75 bit-exact, 8 structural)** | reports the central contribution at ~7 % of its actual coverage; the body already says otherwise | one sentence |
| 2 | **A, abstract** | delete "the fabricated TTSKY26b dies carry the defective multiplier portfolio" | the silicon track was cancelled — there are no fabricated dies | one clause |
| 3 | **B, hardware** | **remove the `takum32` row from the hardware-evidence table** | issue #199 records `takum64/32 synthesize but do NOT route … takum is NOT Tier E`, and the 65,536 figure it carries belongs to `gf16` | one row |
| 4 | **B, title + abstract** | "**84** numeric formats" → **83** | the SSOT holds 83 records, 83 distinct ids, 13 clusters — counted from the file, not quoted | one number |
| 5 | **B, references** | fix at least **11 of 20** bibitems | 9 of the 12 arXiv ids resolve to a different work; four are outright misattributions | replacements supplied in `BIBLIOGRAPHY_FIXES.md` |
| 6 | **B, abstract** | P3109 cross-walk maps **layout**, not values | every `binaryKpP` value is exactly twice its IEEE counterpart — confirmed at 252 configurations and 258,524 finite codes | one word |

---

## 2. Under-claims — these strengthen the paper and cost nothing but text

| what the papers say | what is true | where |
|---|---|---|
| 44 of 83 with board decode | **46 of 83**, after resolving `bf16`→`bf16_golden` and `mxfp8_e4m3`→`mxfp8` by pack metadata | `TIER_E_NUMBERS_READY_TO_PASTE.md` |
| 45 Tier-E cells | **72** format-operation cells over **49** distinct formats, from **75** four-link proofs | same |
| compute proofs across 12 formats | **10** — `gf4`–`gf32` only; `double_double` and `quad_double` carry *decode* proofs, not arithmetic | same (this one is an **over**-claim) |
| — | **13 more formats** the harness already covers, three of them the competitor | `THIRTEEN_MORE_FORMATS_READY_TO_PASTE.md` |
| — | GF16's layout **is IBM DLFloat**; the Russian manuscript says so and neither English paper mentions it | `SUBMISSION_CHECKLIST.md` §4b |

---

## 3. Ready to apply — one data fix

**`takum8` conformance pack: 124 of 255 vectors are wrong.**

The published pack sizes the takum field layout at the storage width. libtakum's own
`codec.c` sizes it at the reference width — `p = 16 − r − 5`, with no `n = 8` path at
all — and the rule tests true on every code:

```
takum_log8_to_float64(x) == takum_log16_to_float64(x << 8)     256 of 256, 0 differ
```

| | published | regenerated |
|---|---|---|
| codes worse than 1e−9 vs libtakum | **124** | **0** |
| worst relative error | 1.14e+26 | **6.895e−15** |

Produce it with `python3 research/regenerate_takum8_pack.py --out takum8_conformance_v0.json`
— 131 vectors unchanged, 124 changed, 1 NaR. **Open it as a pull request against `t27`,
not a push**: 124 changed vectors deserve a human before other tooling consumes them.
Full argument in `research/TAKUM8_HANDOVER.md`.

`takum16`, `takum32` and `posit8/16/32` were checked the same way and are **correct** —
takum16 on all 65,534 finite codes, posit8 exhaustively against SoftPosit.

---

## 4. Questions only you can answer

Six, each recorded with `do_not_guess true` and an owner. None is a defect; each is a
decision about what a claim means.

1. **`posit8`: which format does the board proof describe?** The silicon core says
   `Posit8(es=0)`; the pack declares `es=2`, Posit Standard 2022. They disagree on 252 of
   255 values. Either re-synthesise the `es=2` core — `fpga/openxc7-synth/posit8_es2_decode.v`
   exists and matches SoftPosit on all 256 codes in simulation — or say in the row that
   the silicon is posit(8,0), taking board-verified decode from 46 to 45.
   **Measured 2026-08-03: re-synthesis costs 58 LUTs** — 103 against the legacy
   core's 45, which is 0.08 % of an XC7A200T. The whole board cell,
   `corona_decode_posit8_es2_ax7203.v`, synthesises at **187 LUTs against the
   existing cell's 130**, with an identical 139 flip-flops because the UART
   harness is byte-for-byte the same. There is no area argument for the second
   option, and everything short of place-and-route is done.
2. **`bcd`: should invalid nibbles decode?** 156 of 256 codes are invalid packed BCD
   (both nibbles must be 0–9, so 100 are valid). The oracle decodes them anyway as
   `sum(nibble·10ⁱ)`, and silicon agrees. The pack declares bit-exact BCD.
3. **`takum64` pack witness.** Its metadata records libtakum parity, but libtakum
   *stubs* takum64 decoding to NaN wherever `LDBL_MANT_DIG < 64` — every arm64 host.
   Either it ran on x86-64 and should say so, or it is void.
4. **`takum8`: below the standard's width threshold?** If yes, mark the width
   implementation-defined rather than bit-exact. If no, item 3 above applies.
5. **The Tier-E "cell" count.** The spec says 34; its own list has 33; measured from the
   issue by an explicit definition it is 72 cells over 49 formats. Which reading was
   pass 91 using?
6. **Which manuscript tree produced arXiv v3?** Five references appear in the published
   v3 and nowhere in `goldenfloat-preprint`, two of them postdating its last commit.
   Editing that file and submitting would **delete Paper A's citation of Paper B**.

---

## 5. Do not quote these — they were withdrawn

| withdrawn | replaced by |
|---|---|
| takum16 "negative half diverges, 32,766 of 32,768" | correct on **all 65,534** finite codes, both halves — the earlier figure compared against libtakum's *other* family |
| "60,485/60,485" | appears in no spec and matches neither half |
| the takum "negation defect" | the oracle is a documented linear structural model; sign-and-magnitude **by design** |
| takum8 "255/255 correctly rounded" | the witness shared the pack's own error; against libtakum it is 131/255 |
| "27 correction blocks in ten spec files" | **57 in 11** — the figure grows every pass |

`VERIFICATION_DOSSIER.md` used to instruct a reader to quote the first of these. It no
longer does.

---

## 6. What this campaign cannot tell you

Recorded so nobody re-derives them:

- **`decimal32/64/128` have no independent witness here.** libmpdec ships with CPython
  and implements decimal *values*, not the IEEE interchange encoding; writing the BID
  decoder ourselves would be single-source wearing a witness's clothes. A GCC toolchain,
  the decNumber source, or Intel DFP would close it.
- **`takum64` cannot be cross-validated on arm64**, for the reason in question 3.
- **The reference counts 28 / 33 / 56** need the three published manuscripts.
- **`posit64`** is out of SoftPosit's `positX` reach — 32-bit container.
- **60 of 70 bit-exact packs record no witness at all.** The campaign can supply three
  (`takum8`, `takum16`, `lns8`); the other 57 need a second implementation that, for the
  historical formats, does not exist. `WITNESS_RECORDS_READY_TO_PASTE.md` carries a
  record shape for saying so honestly.

---

## Reproducing any of it

```bash
python3 research/run_all_checks.py          # 47 checks, categorised
python3 research/audit_ci_health.py         # every workflow, queried individually
```

Checks needing large external artefacts resolve them through `$TRINITY_ARTEFACTS` and
**exit 2 with the command that produces them** when absent — verified by pointing that
variable at an empty directory. Eleven gates run in CI, all green.
