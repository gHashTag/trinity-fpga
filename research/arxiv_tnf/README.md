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
| TNF16 vs takum16 accuracy: WITHDRAWN — the takum oracle was wrong on every negative code (fixed in #606) and TNF16 stores 17 bits; at equal stored width the re-measurement (64-term accumulation, ±3 decades) is a three-way tie: tekum10 (15.85 b) 8.56e-3, takum16 5.70e-3, TNF(4,8) 5.32e-3 | re-measured 2026-08-18, corrected oracles | §Accuracy erratum |

## Bounds that must travel with the claims

- **The accuracy result is withdrawn, not merely range-bounded.** Theorem 12
  already forbade beating takum beyond TNF's range; the 2026-08-18
  re-measurement removed the advantage inside it too. With the takum oracle's
  negation defect fixed (#606) and stored widths equalised — TNF16 stores 17
  bits, the exact-width rung is TNF(4,8) — accumulation at equal width is a
  three-way tie (TNF(4,8) 5.32e-3 / takum16 5.70e-3 / tekum10 8.56e-3; 32-bit
  class 1.20/1.26/1.43e-7). No format wins by more than the width it gives up.
- **The area argument separates the competitors — and against takum it now has
  a measured axis.** On the regime-codec axis: decisive against posit (9.95
  bits at the 16-bit class), weak against takum (0.91, and below one bit at
  every rung above TNF8); do not average the two into one number. On the
  full-adder axis the fixed field is decisive against takum too: tef_add_full
  @ TNF(4,8) is 397 LUT / 45 CARRY4 against 1,182 LUT / 211 CARRY4 for the
  linear takum-model 16-bit adder (2.98×), and tekum8_decode.v (real base-3
  tekum) costs 542 LUT / 96 CARRY4 against 1 LUT for the TNF field slice —
  yosys 0.65 synth_xilinx, last stat block only, post-synthesis, no P&R, no
  board; on a ternary fabric trit extraction would be wiring.
- **The competitor was takum, not tekum — and real tekum is now in.**
  `tekum_ref.py` is a linear binary model of takum's layout (all 65,536
  sixteen-bit codes decode identically to `takum_ref.py`, which itself was
  wrong on every negative code until #606 — negation in takum flips the
  exponent sign; it now matches libtakum on 65,534/65,535 codes).
  `tekum_true_ref.py` implements the real base-3 tekum of arXiv:2512.10964
  Definitions 7–8 (worked example exact, monotone on all 6,559 tekum8 codes);
  tekum widths are in trits — tekum16 = 16 trits = 25.4 bits, 3^16 codes — so
  it never was a 16-bit competitor.
- **The regime codecs are structural models**, not reproductions of the published
  posit or takum RTL. They compare a run-scanned regime against a
  length-prefixed one.
- **TNF128 is not claimed.** M=119 does not converge in routing on XC7A200T.

## Claims of ours the measurements falsified

Kept in the paper rather than deleted, because each was published before the
measurement that killed it.

1. *The TNF rungs do not fit their widths.* On positions they do — one per
   trit. On stored bits they do not: TNF8 stores 10 bits, TNF16 17, TNF32 30,
   TNF64 65, TNF1024 1025 (measured 2026-08-18). TRUE_LADDER in
   conformance/tnf_ref.py now holds the exact-width rungs — TNF(2,3) at 8
   bits, TNF(4,8) at 16, TNF(4,24) at 32 — and every equal-width comparison
   must use those.
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
