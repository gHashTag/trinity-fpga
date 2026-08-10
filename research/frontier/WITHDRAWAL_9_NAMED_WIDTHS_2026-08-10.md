# Withdrawal 9: the ternary rungs are wider than their names

Found by applying withdrawal 8's rule systematically -- carry a correction to
every claim resting on the same quantity -- rather than to the one place it
surfaced. It is the deepest of the nine.

## What the catalogue declares, and what the encoder produces

The SSOT specifies each ternary rung as `1 + Et + M = N` where `Et` counts
**trits** and `M` counts **bits**, with a `storage=uN` field. The oracle encodes
`sign | offset | mantissa` with the offset an integer in `[0, 3^Et - 1]`, stored
in binary. So the word is `1 + ceil(Et log2 3) + M` bits.

| name | Et | M | declared | offset bits | **actual** | over |
|---|---:|---:|---:|---:|---:|---:|
| GF-T4 | 1 | 2 | 4 | 2 | **5** | +1 |
| GF-T8 | 3 | 4 | 8 | 5 | **10** | +2 |
| GF-T16 | 6 | 9 | 16 | 10 | **20** | +4 |
| GF-T32 | 12 | 19 | 32 | 20 | **40** | +8 |
| GF-T64 | 24 | 39 | 64 | 39 | **79** | +15 |

Confirmed by running the encoder: `GF-T16` produces a 20-bit word. All nine
ternary rungs are affected. The `storage=u16` field is factually wrong.

The RTL agrees with the oracle: `tnet_tef #(MW=25, OW=10)` is `1 + 10 + 25 = 36`
bits for what is labelled TNF32. Oracle and RTL are mutually consistent and both
implement the position specification, so **the measurements are valid for the
formats that were built** -- those formats are simply wider than their names.

## Theorem

**T (the price of a position specification).** A format specified as
`1 + Et + M = N` in positions and stored in binary occupies
`1 + ceil(Et log2 3) + M` bits, exceeding its declared width by
`ceil(Et log2 3) - Et`, approximately `0.585 Et`. The excess grows linearly in
the trit count and reaches 15 bits at `Et = 24`.

**Corollary.** Any comparison "at equal N" where one side is specified in
positions and the other in bits hands the first side `0.585 Et` bits of
advantage.

## The honestly packed ladder, for comparison

Choosing `Et` by the golden rule and then the largest `M` with
`3^Et 2^M <= 2^(N-1)`:

| N | Et | M declared | M packed | lost | codes used |
|---:|---:|---:|---:|---:|---:|
| 4 | 1 | 2 | 1 | 1 | 75.0% |
| 8 | 3 | 4 | 2 | 2 | 84.4% |
| 16 | 6 | 9 | **5** | 4 | 71.2% |
| 32 | 12 | 19 | **11** | 8 | 50.7% |
| 64 | 24 | 39 | **24** | 15 | 51.4% |
| 128 | 49 | 78 | **49** | 29 | 79.2% |

**59 bits of mantissa across the ladder**, and at 32 and 64 bits nearly half the
code space is unreachable.

## What this invalidates

- Every "at equal N" comparison involving a ternary rung: 20 bits were compared
  against 16.
- The four-families table, including "GF-T carries 11.4x more binades than GF at
  N = 16".
- The `storage=` field for all nine ternary rows in the SSOT.
- Every silicon figure labelled TNF4/8/16/32 -- built and measured correctly, but
  mislabelled by width.

## What it leaves standing

- The measurements themselves, which are valid for what was built and need
  renaming rather than repeating.
- The binary GF and BNF families, specified in bits and fitting exactly.
- The machine-checked `phi` mathematics, which makes no claim about widths.
- The LNS comparison, where adders were matched on actual width rather than name.

## Method

Withdrawal 8 produced the rule: *a correction that invalidates a comparison must
be applied to every claim resting on the same quantity.* Applied once, on the
next iteration, it found this. The nine withdrawals arrived one at a time over
seven iterations because corrections were treated as local; applying one
systematically found the deepest of them immediately.
