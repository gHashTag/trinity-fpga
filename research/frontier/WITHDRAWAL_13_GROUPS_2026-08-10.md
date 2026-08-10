# Withdrawal 13: the groups overlap, and the metric mostly restates area

The last claim to survive all sixteen previous iterations, measured on the
repaired rig at median of five seeds across eighteen formats.

## The full table

| # | format | kind | LUT | Fmax median | spread | MHz/LUT |
|---:|---|---|---:|---:|---:|---:|
| 1 | GFTernary | fixed | 466 | 84.22 | 16.1% | 0.1807 |
| 2 | int8 | fixed* | 448 | 80.67 | 11.4% | 0.1801 |
| 3 | binary32 | fixed | 479 | 75.94 | 8.3% | 0.1585 |
| 4 | GF+8 | fixed | 507 | 74.35 | 11.9% | 0.1466 |
| 5 | TNF16 | fixed | 514 | 74.34 | 10.8% | 0.1446 |
| ... | | | | | | |
| 13 | binary16 | fixed | 552 | 60.45 | 6.2% | 0.1095 |
| **14** | **posit8** | **TAPERED** | 560 | 44.96 | 9.7% | **0.0803** |
| **15** | **IBM hex32** | **fixed** | 683 | 47.39 | 8.4% | **0.0694** |
| 16 | LNS16 | log | 659 | 43.85 | 13.3% | 0.0665 |
| 17 | posit16 | TAPERED | 774 | 37.55 | 2.0% | 0.0485 |
| 18 | posit32 | TAPERED | 955 | 27.11 | 2.3% | 0.0284 |

## 1. The groups overlap

`posit8`, tapered, beats `IBM hex32`, fixed, by **15.7%** against a 9.7% noise
floor. The gap is resolvable, so this is not a tie.

The published claim reads "a fixed field beats a tapered one by 2.4x to 6.4x on a
ternary network". The 6.4x is real -- it is GFTernary against posit32 -- but it
is the **range between the extremes**, not a separation between groups. Stated as
a group claim it is false: a tapered format outranks a fixed one.

The corrected statement is narrower and still useful: **posit's scan cost grows
with width.** posit8 sits mid-table, posit16 near the bottom, posit32 last. That
is a claim about how a taper scales, which the data supports, rather than about
what a taper is.

## 2. The metric mostly restates area

| correlation | value |
|---|---:|
| LUT against Fmax | **−0.900** |
| LUT against MHz/LUT | −0.909 |
| 1/LUT against MHz/LUT | **+0.959** |
| Spearman rank, 1/LUT against MHz/LUT | **+0.961** |

Area and frequency are not independent on this flow: a larger design is also
slower, at −0.90. Throughput per area therefore does not separate two effects, it
compounds them, and its ranking reproduces the ranking by `1/LUT` at a rank
correlation of 0.961.

**T (a ratio metric over correlated factors restates the dominant one).** If
`F(A)` decreases monotonically in area `A`, then `F/A` decreases faster than
either factor, and a ranking on `F/A` approximates the ranking on `1/A`. Such a
metric measures size, not the property it was introduced to isolate.

This does not make the numbers wrong. It makes the phrase "throughput per area"
misleading: it sounds like two independent axes and carries about one and a half.
The honest report is LUT and Fmax side by side, with the correlation stated, and
no derived ratio presented as though it added information.

## What is left of the silicon argument

- **posit32 costs 6.4x what GFTernary costs.** True, resolvable, and the
  strongest single number in the table.
- **The scan cost scales with width.** Supported by three posit widths.
- **Nothing separates fixed from tapered as classes.** Withdrawn.
- **The ordering is largely an ordering by area.** Newly measured, and it means
  the table's headline metric was carrying less information than claimed.

## Count

Thirteen. This was the only claim to survive the whole night, and it survived
because nothing had measured it properly -- the group statement had never been
tested against the worst member of its own group.
