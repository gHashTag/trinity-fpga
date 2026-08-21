# What in arXiv:2606.05017 has been checked, and what it came to

Passes 231–247 changed goldens, rebuilt every vector pack, corrected oracles and
edited 4,776 sites of RTL. Passes 248–251 asked the obvious follow-up: do the
paper's own numbers still describe the corpus they describe?

Eighteen claims have now been recomputed from the repository. **Nine reproduce
cleanly**, one is a sensitivity note rather than an error, and eight need action --
collected with proposed wordings in
`research/CORRECTIONS_PACKAGE_both_preprints.md`.

The sixth is the largest: six of the paper's seven named workloads exist in no
script here, so the constraint fixing the feasible corner had never been
checkable. `research/workload_matmul.py` now implements one of them.
One is a wording error, and one figure is placed inside a promise the evidence
behind it does not keep.

Every row below is produced by a script in this directory, so the table can be
regenerated rather than trusted.

---

## Reproduce

| claim | paper | recomputed | tool |
|---|---|---|---|
| conformance vectors | 2.4M | **2,442,533** | `audit_paper_claims.py` |
| decode cells on silicon | ~41 of 83, 41 ports | **41** distinct formats | `audit_paper_claims.py` |
| GF formats with compute cells | 10 (GF4–GF32) | **10** distinct widths | `audit_paper_claims.py` |
| dynamic range, FP16 | loses 5 of 11 | **5** | `audit_arithmetic_claims.py` |
| dynamic range, GF16 | loses 1 of 11 | **1** | `audit_arithmetic_claims.py` |
| noise floor, BF16 | preserves 7.3% | **7.9%** | `audit_arithmetic_claims.py` |
| noise floor, GF16 | preserves 63.9% | **63.7%** | `audit_arithmetic_claims.py` |
| LUT table, 12 measurements | see below | largest deviation **56 LUTs** | `audit_lut_table.py` |

The LUT table in detail, against `research/CI_LUT_REPORT.md`:

| fmt | ADD pub | ADD here | MUL pub | MUL here |
|---|---|---|---|---|
| GF4 | 18 | 15 | 7 | **7** |
| GF8 | 172 | 171 | 157 | 159 |
| GF12 | 296 | 283 | 407 | 365 |
| GF14 | 398 | 382 | 470 | 451 |
| GF16 | 434 | 490 | 586 | 602 |
| GF20 | 627 | 647 | 877 | 852 |

Measured on a Homebrew yosys 0.63 rather than the pinned `regymm/openxc7`
container, with the flags the report documents. Differences of this size are
ordinary between yosys/abc builds.

---

## Does not reproduce

### 1. GF64 at 70.1% (359/512)

Full analysis: `research/ERRATUM_arXiv_2606.05017_gf64_claim.md`.

The number is **not invented** — seventeen comments in issue #199 investigate GF64
carefully, one of them a retraction of an earlier theory. But:

* no single GF64 comment carries all four Tier-E links, and the one carrying this
  figure has a truncated SHA and a build number rather than a CI URL;
* 359/512 is the highest of four silicon results spanning 19.2%–70.1%, from the
  build that the next comment's own table labels "shift-reg (buggy)". Every build
  with that path fixed scored lower.

It sits inside an item ending *"Each ships with a full evidence chain."*

### 2. "5/11 values flushed to zero"

The abstract and the contributions list say *flushed to zero*. The body says
*loses 5/11*, and the body is right:

| value | FP16 |
|---|---|
| 1e-10, 1e-8 | flush to zero |
| 1e-6 … 1e4 | representable |
| 1e6, 1e8, 1e10 | **overflow to infinity** |

Two of the five flush to zero. Three fail at the opposite end of the range. The
count is correct in both places; only the mechanism is misstated, and only in the
abstract and contributions list.

---

## arXiv:2606.09686 — the catalog paper

Checked from `research/CATALOG_PAPER_DRAFT.md`.

### Follows from the paper's own numbers

> GF16 preserves **8.7×** more gradient updates than BF16

63.9 / 7.3 = **8.75×**, which rounds to 8.7. With the numbers pass 251 measured
from the oracles, 63.7 / 7.9 = **8.06×**. Both are true statements about their
own inputs; the ratio is sensitive to the BF16 denominator, which is the smaller
and noisier of the two.

### Does not hold

> MUL designs add `-nodsp` (DSP48E1 is used only when explicitly instantiated,
> **as in GF16 MUL's single-DSP multiplier**)

`fpga/openxc7-synth/gf_mul_dsp_param.v` exists and does instantiate `DSP48E1`.
**No wrapper instantiates it.** The only two files that reference it are itself
and a comment in `gf_mul_param.v` saying the DSP mapping lives elsewhere.

`corona_compute_gf16_mul_ax7203.v` instantiates `gf_mul_param` — the LUT-only
version. That is consistent with `-nodsp` and with the 586/602 LUT measurement,
and inconsistent with GF16 MUL being the example of explicit DSP instantiation.

### Not checkable this way

> reached through **four parameterized decode templates** (algebraic, table-2^x,
> transcendental-exp-via-tables, truncated-multiply)

Only two files are named `*_decode_param.v`. That is not evidence against the
claim: the templates are described by technique, not by filename, and the takum16
cell is documented as a BRAM LUT rather than a `_param` module. Counting files
would be measuring a neighbour of the claim rather than the claim.

---

## Not checkable from this repository

**"72 of 83 formats carry an independent executable oracle."** The catalog
membership list is `gHashTag/t27/specs/numeric/formats_catalog.t27` in the **t27** repository, which is not
present here. The oracles carry **84** format keys, and several are known not to
be catalog rows — `fp16_e6m9` and `fp24_7m16` exist only in the silicon-sprint
packs, `bf16`/`bfloat16` is an alias pair. **84 neither confirms nor refutes 72.**

---

## Two errors of my own, both caught before publication of a wrong number

1. **LUT drift.** Pass 250 reported a systematic +22% to +79% deviation from the
   published LUT table. That was a parser: yosys `stat` prints three blocks after
   a synth run and my counter summed across a block boundary. Retracted in pass
   251; the corrected table is above. Before that, I nearly compared the UART
   *wrappers* (1281 LUTs) against *core* numbers — the wrappers carry STARTUPE2,
   the UART state machines and the framing.
2. **Noise floor protocol.** My first run held the weight fixed at 0.5 and drew
   independent updates, giving 17.2% and 71.6%. The paper walks the weight for
   2000 steps, re-quantising each time; the walk drifts upward, the ulp grows
   with it, and later updates survive less often. Measured as described: 7.9% and
   63.7%.

Both are the same mistake in different clothes — measuring a reasonable-sounding
neighbour of the thing the method describes.

---

## How to regenerate this

```
python3 research/audit_paper_claims.py
python3 research/audit_arithmetic_claims.py
python3 research/audit_lut_table.py
```

`audit_paper_claims.py` reads issue #199 through `gh` by default, or a cached
JSON via `--comments FILE`.
