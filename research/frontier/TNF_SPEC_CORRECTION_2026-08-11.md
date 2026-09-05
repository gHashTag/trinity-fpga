# All three TNF rungs were measured on modules that were not the format

TNF16's divergence turned out not to be isolated. Written from the paper's own
width table and checked against a reference derived from it, every rung moves.

| rung | specification | the module measured | agreement |
|---|---|---|---|
| TNF16 | $1+7+9 = 17$ bits | $1+7+8 = 16$ | **0 of 65,536** |
| TNF32 | $E_t{=}6$, $M{=}25$, 36 bits | 12 trits, $M{=}11$, 32 bits | no reference existed |
| TNF64 | $E_t{=}7$, $M{=}52$, 65 bits | 24 trits, $M{=}24$, 64 bits | no reference existed |

The specification is Table~11 of the paper, which we had already published: TNF32
is six trits and twenty-five mantissa bits. The module had twelve and eleven.
These are not readings of one format; they are different formats.

## What the correction costs

| rung | as measured before | at specification | places lost |
|---|---|---|---|
| TNF16 | $510$ LUT, $77.47$\,MHz, $0.1519$ | $565$, $66.28$, $0.1173$ | 6 to 13 |
| TNF32 | $492$, $75.57$, $0.1536$ | $569$, $66.91$, $0.1176$ | 3 to 12 |
| TNF64 | $494$, $75.16$, $0.1521$ | $572$, $65.38$, $0.1143$ | 4 to 14 |

All three leave the top of the table. What remains at rank 1 is **GFTernary,
the two-bit alphabet, which agrees with its reference on all four of its codes**
--- the only one of ours that was both checkable and correct from the start.

The corrected modules agree: TNF16 on all 131,072 codes, TNF32 on 9,997 sampled
values inside the fp32 window, TNF64 likewise. Zero mismatches each.

## Why it survived to be published

Neither TNF32 nor TNF64 had a reference. The check that found TNF16's divergence
could not run on them, and a format with no reference cannot diverge from
anything --- it can only be measured. Three of our own rungs sat in the table on
that basis, two of them at ranks three and four.

**A number whose correctness nothing can test is not a measurement of the thing
it is labelled with.** The table now prints, for every row, what was checked and
how much: five agree on every code, three disagree on some, and the ones with no
reference say so.

## The shape of the error, since it is the fourth of its kind here

Each time, an artefact and its specification drifted apart and nothing compared
them: a script instantiating a module no file defined, a figure carrying a name
two renames old, a harness observing a fraction of its output, and now a decoder
implementing a format the paper does not describe. The common cause is not
carelessness in any one place. It is that **a pair with no checker is a pair that
will diverge**, and the only defence that has worked is to enumerate the pairs
and build the checker before the number is quoted.
