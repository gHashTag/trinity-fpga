# GF-T paper — build

Same pipeline as `research/arxiv_submission`: matplotlib for vector figures,
LaTeX for the paper. Built here with `tectonic` because `pdflatex` is not
installed on this machine; `latexmk -pdf` works equally.

```bash
python3 gen_figures.py     # → gft_accuracy.pdf, gft_ladder.pdf, gft_width.pdf
tectonic gft_paper.tex     # → gft_paper.pdf
```

## Every number, and where it came from

| Figure | Value | Produced by |
|---|---|---|
| Accuracy, GF-T16 vs tekum16 | tie / 2.84× / 5.53× | `conformance/gft16_ref.py`, `tekum_ref.py`, fixed seed, re-measured 2026-08-08 |
| Lineup area and frequency | 12 / 50 / 212 / 1,477 LUT at 161.11 / 153.23 / 131.73 / 83.27 MHz | Yosys 0.65 → nextpnr-xilinx 1743d0f, XC7A200T, `-nodsp`, one harness |
| Pipeline gain | 81.35 → 147.32 MHz | same, GF-T16 |
| Width cost | 1,179 → 219 LUT, 3 → 0 DSP48 | same, GF-T16 |
| Equivalence | 374 / 3,716 / 77,444 / 300,000 / 199,994, all 0 | `fpga/gft/tb_*.v` under Icarus 13.0 |
| The defect | 1,995,730 of 2,128,964 | original 32-bit module vs `gft_mul32.v` at GF-T32 |

## Checklist before submission

- [ ] Axis reads **powers of two** in the table, the figure and the caption
- [ ] Figure annotations match the table to the last digit — they disagreed once,
      because the annotation recomputed the ratio from the rounded plotted values
- [ ] The tekum-is-a-reconstruction limitation is in the body, not a footnote
- [ ] No "first / best / only / novel" claims, per the house honesty audit
- [ ] Generative-AI disclosure present (arXiv does not require it; it is there anyway)
- [ ] Category `cs.AR`, secondary `cs.ET`, matching the catalogue paper
