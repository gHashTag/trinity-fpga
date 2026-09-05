# Median of five seeds: the top of the table was never established

The first result in several iterations rather than a withdrawal, and it corrects
a claim in our own disfavour that we had been repeating.

## Method

Area is deterministic under placement-seed variation and timing is not --
measured at 0.0% against 11.4%. So frequency is reported as a median over five
seeds with the spread stated, and rows separated by less than the spread are not
ranked. Both reproduction scripts were repaired first (`mk8.sh`, `mkgf.sh`).

## Measured

| # | format | LUT | Fmax median | spread | MHz/LUT | published | shift |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | **GFTernary** | 466 | 84.22 | 16.1% | **0.1807** | 0.1771 | +2.1% |
| 2 | int8 | 448 | 80.67 | 11.4% | **0.1801** | 0.1894 | −4.9% |
| 3 | TNF16 | 514 | 74.34 | 10.8% | 0.1446 | 0.1447 | −0.0% |
| 4 | fp8 e4m3 | 490 | 69.23 | 11.6% | 0.1413 | 0.1468 | −3.8% |
| 5 | fp8 e5m2 | 481 | 65.13 | 7.8% | 0.1354 | 0.1358 | −0.3% |
| 6 | BNF16 | 519 | 70.16 | 14.0% | 0.1352 | 0.1369 | −1.3% |
| 7 | VAX F | 524 | 67.85 | 11.9% | 0.1295 | 0.1410 | −8.2% |
| 8 | GF10 | 538 | 69.27 | 6.0% | 0.1288 | 0.1359 | −5.3% |
| 9 | minifloat | 570 | 64.10 | 10.1% | 0.1125 | 0.1094 | +2.8% |
| 10 | GF14 | 590 | 65.83 | 9.5% | 0.1116 | 0.1239 | −10.0% |
| 11 | LNS16 | 659 | 43.85 | 13.3% | 0.0665 | 0.0654 | +1.7% |

LUT counts reproduce exactly in every case. Frequencies shift by up to 10% from
the published single-seed figures, in both directions -- which is what an 11.4%
median spread predicts.

## What changes

**`int8` does not lead GFTernary.** Published, the gap was 6.3% in `int8`'s
favour. At median of five it is **0.4%**, inside a 16.1% band. The two are
indistinguishable on this flow.

This corrects a statement repeated several times in this work, including in the
paper's own argument for excluding `int8` from the main table: "it scores 0.189,
7% above GFTernary." The exclusion argument stands on its own grounds -- `int8`
has no exponent field and borrows its range from outside the word -- but the 7%
does not, and the paper said it as though measured.

**`int8` does lead TNF16**, by 24.5% against an 11.4% noise floor. That gap is
real and is now the only resolvable one at the top.

## Theorem

**T (a ranking needs a resolution).** A ranking on a metric with measurement
spread `s` asserts an ordering only between rows separated by more than `s`.
Rows closer than `s` are unordered by the data regardless of how many decimal
places are printed. Measured here: three of the top four pairwise gaps are
smaller than the spread, so the published order of the first four rows carried
one real comparison and two that the data does not support.

**Corollary.** Reporting more digits than the spread justifies does not make a
ranking finer; it makes the absence of resolution harder to see. The published
table gave four significant figures on a quantity resolved to one.

## Note on direction

Every previous correction tonight moved against our claims. This one moves for
them -- our two-bit alphabet is not behind `int8`, it is level with it -- and it
came from the same procedure. That is the point of fixing a method rather than
defending a number: the correction goes wherever the measurement goes.
