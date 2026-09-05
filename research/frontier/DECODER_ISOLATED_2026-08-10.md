# Isolating the decoder: withdrawal 13 is itself withdrawn, and the result is larger

The metric was the problem, not the claim. Measuring what the comparison was
introduced to measure gives a cleaner separation than was ever published.

## What changed in the measurement

Every previous run synthesised `decoder + a common tef_add_w accumulator`. The
accumulator is identical across formats, so it is a constant in area and a
**confound in delay** -- it can sit on the critical path and mask what the
decoder costs. And because area and frequency correlated at **-0.90** on the
combined design, the derived ratio mostly restated size (withdrawal 13, part 2).

This run synthesises the decoder alone, feeding a single output register.

## Measured, median of five seeds

| format | kind | LUT | Fmax median | spread | LUT over a bare wire |
|---|---|---:|---:|---:|---:|
| **GFTernary** | fixed | **67** | **985.22** | 6.9% | **−21** |
| binary32 | fixed | 88 | 873.36 | 26.6% | 0 |
| int8 | fixed | 79 | 871.84 | 33.7% | −9 |
| *baseline, a wire* | — | 88 | 863.56 | 14.7% | — |
| BNF16 | fixed | 85 | 402.90 | 13.2% | −3 |
| TNF16 | fixed | 88 | 369.41 | 19.9% | 0 |
| binary16 | fixed | 136 | 228.57 | 17.6% | +48 |
| IBM hex32 | fixed | 165 | 125.63 | 23.6% | +77 |
| posit8 | TAPERED | 195 | 105.94 | 9.6% | +107 |
| LNS16 | log | 254 | 98.35 | 12.0% | +166 |
| posit16 | TAPERED | 251 | 75.87 | 9.6% | +163 |
| posit32 | TAPERED | 597 | 43.73 | 5.7% | +509 |

## 1. The groups separate, with no overlap

Worst fixed field: IBM hex32 at 165 LUT and 125.63 MHz.
Best tapered: posit8 at 195 LUT and 105.94 MHz.

**The worst fixed beats the best tapered on both axes** -- 1.18x on area and
1.19x on frequency. Withdrawal 13's overlap was an artefact of the shared
accumulator, and is withdrawn.

## 2. The axes are now substantially independent

Correlation between LUT and Fmax falls from **-0.900** on the combined design to
**-0.616** on the isolated decoder. Reporting them side by side now carries two
pieces of information rather than one and a half. The second half of withdrawal
13 is addressed rather than withdrawn: the fix was to measure differently, not to
argue the correlation away.

## 3. The result is larger than what was published

GFTernary against posit32: **8.9x on area and 22.5x on frequency**, against a
published 6.4x on the confounded ratio. Confounding had been *hiding* the
separation, not manufacturing it.

## 4. A detail worth keeping

**GFTernary costs 21 LUTs less than a bare wire**, and int8 nine less. Decoding a
two-bit alphabet lets the synthesiser simplify the register and XOR downstream
further than passing 32 raw bits does. The decode is not merely cheap -- at this
width it is *negative* against the trivial baseline, which is a fact about how
little information a two-bit symbol carries into the fabric.

## 5. TNF16 against BNF16 remains a tie

369.41 against 402.90 MHz, 88 against 85 LUT -- a 9% frequency difference inside
a 13-20% spread. Consistent with the no-free-range theorem: a ternary exponent
packed into bits buys nothing on binary fabric. This is the third independent
measurement agreeing.

## Theorems

**T (a shared component is a confound, not a constant).** Adding an identical
block to every design under comparison leaves area differences intact but does
not leave delay differences intact, because the shared block may hold the
critical path. Any conclusion about delay drawn from such a comparison bounds the
shared block's delay, not the varying part's.

**T (isolation restores independence).** Removing the shared block reduced the
area-frequency correlation from -0.90 to -0.62, which is what makes a
two-axis report meaningful. A metric combining correlated axes should be
replaced by a measurement that decorrelates them, rather than by a different
combination of the same numbers.

## Count

Thirteen withdrawals, one of them now withdrawn in turn. The pattern across the
night is that the measurements were rarely wrong and the **comparisons** usually
were -- wrong baseline, wrong units, wrong regime, wrong instrument, and here a
confounded harness. This is the first iteration where fixing the comparison made
a claim **stronger** rather than removing it.
