# Twelve of nineteen adjacent pairs in the ranking are not distinguishable

The throughput table stored a median and a spread per row. **A median with a
spread cannot say whether two rows differ**, so no ranking in this paper had ever
been tested. Every row was re-swept keeping all five per-seed frequencies.

## First: the table was not measured on one harness

Seventeen of twenty-one rows reproduced their LUT count exactly. Four did not,
and all four fell. The cause for two of them is exact:

`f_tnf32s.v` drives its decoder from a **128-bit** LFSR; every other harness uses
a **64-bit** one. Measuring `GFTernary` — which reproduces exactly at 463 LUT —
on the wide harness gives **527**. The difference is **64 LUT, exactly**, and it
matches TNF32 (569 → 505, −64) and TNF64 (572 → 506, −66).

**Two rows of the table were measured on a harness 64 LUT more expensive than
the one the other nineteen used, and then ranked against them.** TNF32's true
figure on the common harness is **0.1274, not 0.1176** — it moves from rank 10 to
rank 6.

`TNF64` needs 65 independent input bits and therefore *cannot* use the 64-bit
harness at all; the 506 measured here drove it with a repeated bit, which is its
own defect. It is excluded until the common-harness sweep completes.

The two `fp8` rows also moved (516 → 485, 529 → 480) and that is **not**
explained by the LFSR. Unresolved.

## Then: the ranking itself

Twenty formats on one 64-bit harness, five seeds each, adjacent pairs tested by
whether their seed ranges overlap:

**Distinguishable: 7 of 19.**

| pair | median gap | verdict |
|---|---|---|
| GFTernary > binary32 | +10.1% | **distinguishable** |
| binary32 > fp8 e5m2 | +16.8% | distinguishable |
| fp8 e5m2 … VAX F — **eleven formats** | — | **one indistinguishable block** |
| VAX F > GF+8 | +9.2% | distinguishable |
| GF+8 > posit8 | +23.6% | distinguishable |
| takum16 > LNS16 | +14.2% | distinguishable |
| LNS16 > posit16 | +18.7% | distinguishable |
| posit16 > IBM hex32 | +80.2% | distinguishable |
| IBM hex32 vs posit32 | +0.1% | not distinguishable |

`binary16` and `GF14` differ by **0.0%**. `IBM hex32` and `posit32` by **0.1%**.

## What this does to the paper's claims

**The headline survives.** `GFTernary` beats `binary32` by 10.1% and the seed
ranges do not overlap — 0.1770–0.1913 against 0.1560–0.1695. That comparison is
real.

**Almost nothing else in the middle is.** Eleven consecutive formats — including
`binary16`, `TNF16`, `BNF16`, `GF10`, `GF14`, `TNF32`, `TNF8` and both `fp8`
variants — form a single block whose members cannot be ordered by this
instrument. **Every same-width claim made against `binary16` sits inside that
block** and must be restated with the range, or dropped.

The table must carry per-seed ranges, and the ranking must be drawn as bands
rather than positions. A rank order the instrument cannot resolve is not a
result; it is a sorting artefact of the median.
