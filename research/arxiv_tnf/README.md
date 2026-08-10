# Ternary Floats (TNF) — paper, figures, provenance

`tnf_paper.tex` builds with `tectonic tnf_paper.tex`. `pdflatex` is not installed
on this machine; figures come from `gen_figures.py` (matplotlib → vector PDF).

## What the paper claims, and what each claim rests on

| Claim | Evidence | Where |
|---|---|---|
| Error is `½·E[1/s]·2^−(M+1)`, exponent cancels | derived, then measured across 8 rungs to ±3% | Thm 1 |
| A regime codec costs 438 LUTs (unary) / 40 (length-prefixed) / 0 (fixed field) | synthesised under one harness, XC7A200T, harness of 24 LUTs subtracted | Thm 14, `fpga/regime/` |
| A mantissa bit costs `4.89·M` LUTs | `A(M) = 141 + 2.4455·M²`, 14 widths from M=7 to 90, R² = 0.99963 | Thm 18 |
| posit's regime = 9.95 mantissa bits at M=9; takum's = 0.91 | the two above, combined | Thm 19, Cor. break-even |
| No unbounded-range format tapers below 1 bit/doubling | Kraft's inequality | Thm 12 |
| 83 formats resolve into 4 staircase forms | `conformance/taper_classify.py`, bands placed inside each format's measured range | §Taxonomy |
| TNF16 is 2.83× / 5.46× more accurate than takum16 | round trip, 6000 values, **inside TNF's range only** | §Accuracy |

## Bounds that must travel with the claims

- **The accuracy result is range-bounded.** Theorem 12 forbids beating takum
  beyond TNF's own range; past `|e| = 40` TNF16 has no values and takum16 does.
- **The area argument separates the competitors.** Decisive against posit
  (9.95 bits at the 16-bit class), weak against takum (0.91, and below one bit at
  every rung above TNF8). Do not average the two into one number.
- **The competitor is takum, not tekum.** The oracle labelled `tekum_ref.py`
  decodes all 65,536 sixteen-bit codes identically to `takum_ref.py`.
- **The regime codecs are structural models**, not reproductions of the published
  posit or takum RTL. They compare a run-scanned regime against a
  length-prefixed one.
- **TNF128 is not claimed.** M=119 does not converge in routing on XC7A200T.

## Claims of ours the measurements falsified

Kept in the paper rather than deleted, because each was published before the
measurement that killed it.

1. *The TNF rungs do not fit their widths.* They do — the width counts positions,
   one per trit. We had measured the cost of a trit on a binary fabric.
2. *One trit per tripling is a new regime class.* It is takum's class; the two
   codeword-length functions differ by an additive 1 at every `|e|` to 4096.
3. *The gap between the arithmetic and geometric classes is empty because an
   intermediate regime is too expensive.* It costs 18% more than posit's, which
   ships. We have no explanation left and say so.
4. *TNF64 will cost 4,762 LUTs.* It costs 7,479 — the single power law was low by
   36%. The two-term structural model is right to 4.4%.

## Rebuilding

```
tectonic tnf_paper.tex
python3 gen_figures.py
python3 ../../conformance/taper_classify.py     # the 83-format taxonomy
python3 ../../conformance/regime_codes.py       # asserts radix invariance
```

Tool versions: Yosys 0.65, nextpnr-xilinx 1743d0f, Icarus 13.0, Python 3.14.3,
tectonic. Device XC7A200T-FBG484, chipdb from the openXC7 flow.
