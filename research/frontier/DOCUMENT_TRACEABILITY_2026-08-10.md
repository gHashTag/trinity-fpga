# The fourth defect class, found systematically rather than by accident

Three gates guard this tree. Each was found by tripping over it. Making the
search systematic means enumerating every pair of artefacts that must agree and
asking what checks each.

## The enumeration

| A | B | checked by |
|---|---|---|
| catalogue (SSOT) | Python oracle | `check_artefact_agreement` |
| oracle | RTL | `check_artefact_agreement` + conformance |
| RTL | build script | `check_script_rot` |
| design | measurement harness | `check_harness` |
| `cases.yaml` | `cases/` directory | **nothing** -- found by hand in iteration 36 |
| **the paper** | **the measurement files** | **nothing** |
| the skill file | repository state | **nothing** |
| `README` | code | **nothing** |
| `METHOD_2026-08-10.md` | what was actually done | **nothing** |

**All three existing gates are code-against-code, and they occupy one region of
the table. Every pair with a document on either side is unguarded.** That is why
the three finds felt accidental: the search had never left one corner.

## The class

**A document that quotes a measurement carries no link back to it.** Sixteen
claims were withdrawn during this work, and a withdrawn claim's number does not
remove itself from a paper.

## `tools/check_paper_numbers.py`

Extracts distinctive numeric literals from the paper -- three or more significant
digits, or two or more decimal places -- and asks whether each appears in any
file under `research/`, `fpga/` or `conformance/`.

Two classes of false positive are excluded rather than tolerated:

- **Derived constants.** A number stated beside the formula producing it is
  algebra, not measurement: `kappa(2) = 0.72135`, `log2(3) = 1.5850`,
  `(1/2)ln 2 = 0.3466`. **60 of them**, correctly absent from any data file.
- **Rounding.** A paper may print `0.181` where the data records `0.1807`. A
  data literal extending the paper's digits counts as its source.

## Result

Of **450** distinctive literals, **19** carry a unit, have no source, and are not
explained by rounding. Several are visibly from superseded tables:

| literal | context | why it is suspect |
|---|---|---|
| `774`, `36.30`, `3.77` | posit16 row | the combined-harness table, superseded by the isolated decoder at 302 LUT / 62.39 MHz |
| `53.26`, `33.23` | TNF64, TNF128 MHz | an earlier synthesis table |
| `12232`, `19980` | area-law fit points | an earlier ladder fit |
| `136.44`, `131.73` | a silicon comparison | no surviving source |
| `0.2497`, `0.2505` | posit slopes | superseded by the measured `0.261` and `0.260` |

## What the gate can and cannot say

It cannot prove a number is right. It finds numbers **with no source**, which is
strictly weaker and still enough: a figure nobody can trace to a file is one
nobody can re-check, and after sixteen withdrawals that is where a stale value
survives.

## Theorem

**T17 (a document is an artefact, and its pairs need guarding too).** Consistency
checks tend to be written between artefacts that a tool already reads together --
compiler, simulator, build script. Documents are read only by people, so the
pairs involving them go unchecked by construction, and they are precisely where
withdrawn numbers persist.

**Corollary.** Enumerating the pairs is what makes a search for defect classes
systematic. Three classes were found by accident in one region; enumerating found
five unguarded pairs in one pass, and the first one opened yielded 19 candidates.
