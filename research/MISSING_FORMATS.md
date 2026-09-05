# Missing formats — oracle coverage of the 83-format catalog

**AGENT F (conformance) finding.** Verified 2026-07-15 against:
- SSOT catalog `gHashTag/t27/specs/numeric/formats_catalog.t27` (repo `gHashTag/t27`, master — 83 `// CATALOG: id=` records, no dupes; family count 13).
- The 15 oracle modules in `conformance/`: `gf_ref`, `tekum_ref`, `posit_ref`, `bf16_ref`, `fp8_ref`, `mxfp_ref`, `takum_ref`, `decimal_ref`, `ieee_ref`, `legacy_ref`, `lns_ref`, `int_ref`, `nf4_ref`, `gfternary_ref`, `extended_ref` (84 `FORMATS` entries total).

> Companion to `conformance/generate_vectors.py` (now emits both `{format}_add.json` and `{format}_mul.json`). The generator's per-format seeds are op-independent, so ADD and MUL vectors exercise the **same** `(a, b)` input pairs.

---

## 1. TL;DR — the honest numbers

| Quantity | Count | Notes |
|---|---|---|
| Catalog rows (SSOT) | **83** | `gHashTag/t27/specs/numeric/formats_catalog.t27`, 13 families |
| Oracle format-names (15 modules) | **84** | what `generate_vectors.py` iterates |
| Catalog rows **covered** by an oracle | **72 / 83** | strict, by id (incl. `mxfp8` ← `mxfp8_e4m3`) — theoretical maximum |
| Catalog rows **without** an oracle | **11** | itemised in §3A — all structural |
| …of which are **structural / parametric / container** (no single S:E:M decode law) | **11** | §3A — correctly excluded, unreachable by design |
| …of which are **concrete, addable in principle** | **0** | all 12 former gaps closed (afp, gf512, gf1024 were the last 3) |
| Oracle format-names that are **NOT** catalog rows | **12** | §4 (tekum, unsigned ints, wider bfloats, …) |

**All 12 concrete oracle gaps are now closed.** The last 3 — `afp` (bf16-layout + tensor shift, shift=0 ⟹ identical to bfloat16), `gf512` (`e=195, m=316`), and `gf1024` (`e=391, m=632`) — were added on 2026-07-15. Catalog coverage is at its theoretical maximum: the remaining 11 are structural-by-design (no decode law). The earlier "60/83 strict, 12 concrete gaps" figure (this file's prior revision) reflected the state before `nf4`, `bcd`, `ms_mbf32/64`, `gfternary`, `double/quad_double`, `gf48/96`, and finally `afp/gf512/gf1024` gained unified decode+add+mul oracles.

---

## 2. How the diff was computed

1. Pulled the 83 `// CATALOG: id=…` records from the SSOT `gHashTag/t27/specs/numeric/formats_catalog.t27` (the catalog matrix `fpga/CATALOG_MATRIX_83.md` and the catalog paper draft do **not** enumerate all 83 by name; only the `.t27` SSOT does).
2. Imported each of the 15 oracle modules and listed `FORMATS.keys()` → 84 names.
3. Set difference. One fuzzy merge applied: the catalog row `mxfp8` is covered by the oracle entry `mxfp8_e4m3` (same Microscaling family / same element encoding, OCP MX v1.0). Unsigned-int oracle entries (`uint4/8/16/32`) map to the catalog's combined `int4/8/16/32` rows (catalog uses one `INTn / UINTn` row per width), so they do **not** add catalog coverage — they are extra granularity.

Reproduce:
```python
# in conformance/
python3 -c "import ...diff..."   # see git log; the script is inline in the audit
```

---

## 3. The 11 catalog formats without a 15-module oracle (all structural)

### 3A. Structural / parametric / container / technique — 11 (cannot have a single uniform oracle)

These are correctly absent: they have no standalone `S:E:M` decode law. They are *applied atop a base format* or are *parametric frameworks*, so a bit-exact oracle is either undefined or parameter-dependent.

| # | Format | Cluster | Catalog `bits` | Why no oracle | Addable? |
|---|---|---|---|---|---|
| 1 | `block_fp` | CompressionTrick | 0 | Per-tile **shared exponent** applied atop a base int/float (Wilkinson 1963 / Darvish-Rouhani 2020). The block, not the element, is the unit. | No — container, not a format |
| 2 | `shared_exp` | CompressionTrick | 0 | Generalised BFP; same reason as `block_fp`. | No — container |
| 3 | `per_channel_scale` | CompressionTrick | 8 | INT8 + an fp32 **per-tensor/per-channel scale** (Jacob 2018 / TFLite). Decode requires the external scale. | No — container |
| 4 | `stochastic_rounding` | CompressionTrick | 0 | A **rounding technique**, not a format (`s=0 e=0 m=0`). Applied atop a base. | No — not a format |
| 5 | `minifloat` | Theoretical | 0 | **Parametric framework** "arbitrary E:M, ≤16 bits" (Higham 1996). It is the *design space* containing gf4/8/12/16, fp4/6/8 — not one format. | No — parametric |
| 6 | `tapered_fp` | Theoretical | 0 | **Parametric** tapered framework (Morris 1971); posit ancestor. No fixed layout. | No — parametric |
| 7 | `unum_i` | Theoretical | 0 | Gustafson 2015 — **tapered + ubound**, variable-length, interval-valued. | No — variable-length/interval |
| 8 | `unum_ii` | Theoretical | 0 | Gustafson 2016 — **SORN projective** lookup-table arithmetic; catalog itself flags "not GF-comparable". | No — LUT/set arithmetic |
| 9 | `q_format` | IntegerFixed | 0 | **Qm.n fixed-point parametric** (`bits=0`, `varies`). Needs `(m,n)` to instantiate. | No — parametric (instantiable, e.g. Q1.15) |
| 10 | `gf8_bfp` | GoldenFloat | 8 | GF8 element + **per-tile shared exponent** (§12.5 hybrid). Container atop GF8. | No — container atop GF8 |
| 11 | `gf_lns_hybrid` | GoldenFloat | 16 | **Dual-space** GF+LNS (mul in log-space, accumulate in linear). Two decode laws in one storage. | No — dual-space, not single-law |

These 11 explain the recurring "11" in the codebase's shorthand. They are **gaps by design**, not bugs to close (the catalog paper now reports these same 11 as "structural by design").

### 3B. Concrete formats — addable in principle — 0 remaining (all 12 closed)

Every concrete format that has a real bit layout and decode law now ships a
unified decode+add+mul oracle entry. The table below records the closure
history; the "Status today" column shows each is now covered.

| # | Format | Cluster | `bits` | Oracle module | Closed |
|---|---|---|---|---|---|
| 12 | `nf4` | QuantTuned | 4 | `nf4_ref` (16-entry quantile table) | 2026-07 |
| 13 | `bcd` | IntegerFixed | 0 | `int_ref` (bcd entry) | 2026-07 |
| 14 | `ms_mbf32` | HistoricalVendor | 32 | `legacy_ref` | 2026-07 |
| 15 | `ms_mbf64` | HistoricalVendor | 64 | `legacy_ref` | 2026-07 |
| 16 | `gfternary` | GoldenFloat | 2 | `gfternary_ref` ({-φ,0,+φ}) | 2026-07 |
| 17 | `afp` | QuantTuned | 16 | `bf16_ref` (afp entry; shift=0 ⟹ bfloat16, shift-aware `afp_*` helpers) | 2026-07-15 |
| 18 | `gf48` | GoldenFloat | 48 | `gf_ref` (`e=18, m=29`) | 2026-07 |
| 19 | `gf96` | GoldenFloat | 96 | `gf_ref` (`e=36, m=59`) | 2026-07 |
| 20 | `double_double` | ExtendedFloat | 128 | `extended_ref` | 2026-07 |
| 21 | `quad_double` | ExtendedFloat | 256 | `extended_ref` | 2026-07 |
| 22 | `gf512` | GoldenFloat | 512 | `gf_ref` (`e=195, m=316`) — edge-case self-test | 2026-07-15 |
| 23 | `gf1024` | GoldenFloat | 1024 | `gf_ref` (`e=391, m=632`) — edge-case self-test | 2026-07-15 |

> The final 3 (`afp`, `gf512`, `gf1024`) were the last concrete oracle gaps and
> are closed as of 2026-07-15. Catalog oracle coverage is now 72/83 — the
> theoretical maximum given the 11 structural formats in §3A.

---

## 4. The 12 oracle format-names that are NOT catalog rows

The 84 oracle names are **not** a subset of the 83 catalog ids. These 12 exist as oracles but have no matching catalog row:

| Oracle entry | Module | What it is | Catalog relation |
|---|---|---|---|
| `tekum8/16/32` | `tekum_ref` | Balanced-ternary tapered (Hunhold, arXiv:2512.10964) | **Not in catalog at all** — Trinity-internal study format |
| `bfloat24`, `bfloat32` | `bf16_ref` | Wider Brain-Float variants | Catalog lists only `bfloat16` |
| `mxfp8_e4m3` | `mxfp_ref` | The E4M3 element of MXFP8 | Maps to catalog row `mxfp8` (counted as covered) |
| `mxint8` | `mxfp_ref` | Microscaling INT8 element | Not a standalone catalog row (OCP MX int element) |
| `pdp11_float` | `legacy_ref` | PDP-11 float | Not in catalog (catalog has VAX/IBM/Cray/x87) |
| `x87_48bit` | `legacy_ref` | 48-bit x87 | Not in catalog (catalog has `x87_fp80`) |
| `uint4/8/16/32` | `int_ref` | Unsigned two's-complement | Fold into catalog's combined `INTn / UINTn` rows |

These are legitimate extra granularity (especially the unsigned ints and `tekum`); they just shouldn't be counted as catalog coverage.

---

## 5. The honest coverage claim (recommended wording)

For papers / READMEs, the recommended wording (updated 2026-07-15 after the last 3 concrete gaps were closed):

- **Oracle breadth (what `generate_vectors.py` actually produces):**
  > "Bit-exact ADD **and** MUL conformance vectors for **84** numeric format-instances across 15 oracle modules — covering **72 of the 83** catalog rows (the theoretical maximum), plus 12 non-catalog variants (unsigned ints, tekum, wider bfloats, OCP MX elements)."

- **Catalog coverage (strict):**
  > "**72/83** catalog formats have a unified decode+add+mul oracle; the remaining **11** are structural/parametric/container formats with no single S:E:M decode law (correctly excluded). There are **zero** concrete oracle gaps left."

- **One-line honesty:**
  > "72/83 strict (theoretical max); 11 structural-by-design; 0 concrete gaps."

---

## 6. Cross-references

- SSOT: `gHashTag/t27/specs/numeric/formats_catalog.t27` (gHashTag/t27 master).
- Count erratum: `research/ERRATUM_arXiv_2606.09686_catalog_count.md` (the 84→83 E8M0 correction; E8M0 is a Microscaling **component**, not a standalone row — so it is rightly absent from both the 83 and the oracle set).
- Generator: `conformance/generate_vectors.py` (emits `_add.json` + `_mul.json`).
- Oracle modules: `conformance/{gf,tekum,posit,bf16,fp8,mxfp,takum,decimal,ieee,legacy,lns,int,nf4,gfternary,extended}_ref.py` (15 modules, 84 `FORMATS`).
- HW matrix: `fpga/CATALOG_MATRIX_83.md` (decode-HW 41, compute-HW 30 = 71/83 Tier-E on AX7203 — a different, HW-oriented axis from this oracle-oriented audit).
