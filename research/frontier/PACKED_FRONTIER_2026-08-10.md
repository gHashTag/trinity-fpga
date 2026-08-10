# Withdrawal 8: the headline result was a positions-versus-bits artefact

The largest withdrawal of the night, and it is the paper's headline.

## The claim

"A width-N format of effective mantissa `m` and range `b` binades is dominated by
the TNF family exactly when `m + ceil(log3(b+1)) <= N-1`, while any uniform
format obeys `m + log2(b+1) <= N-1`. The exchange rate is the result: every
uniform binary format is dominated with slack `0.3691 E`. Of 28 catalogued
formats from 8 to 128 bits, none escapes."

## The attack

The coverage condition counts **positions**. A format is stored in **bits**. A
family member with `Et` trits of exponent needs `Et log2(3)` bits to hold them,
so the realisable member obeys

```
3^Et * 2^M  <=  2^(N-1)
```

Substituting the minimum `Et = log3(b+1)`:

```
m + log2(3) * log3(b+1)  <=  N-1
m + log2(b+1)            <=  N-1        since log2(3) log3(x) = log2(x)
```

**That is identically the uniform binary budget.** The slack `0.3691 E` vanishes,
exactly and for every `E`. It was never a property of the format; it was the
difference between counting positions and counting codes.

## Measured against the catalogue, at equal storage

| verdict | count |
|---|---:|
| dominated | **6** of 17 sampled |
| tie or escape | 11 |

Every uniform binary format that spends all its bits ties exactly: binary16 at
15.06 against a budget of 15, binary32 at 31.10 against 31, binary64 at 63.27
against 63. The ones dominated are those wasting budget -- posit32 by 5.12
positions, posit64 by 14.24, takum32 by 0.82, tekum32 by 0.90, cray_float by
0.65, and our own gf8 by 0.70.

And several tapered formats **escape**: posit8 by 1.16, posit16 by 2.37, takum16
by 1.53, tekum16 by 1.49. That is consistent with our own corollary -- escape
requires non-uniformity, a taper is non-uniform, and a uniform family cannot
catch it at equal storage.

## The corrected statement

At equal storage the family **ties every uniform binary format that spends all
its bits, dominates those that waste budget, and is escaped by tapered formats
measured on the band where they concentrate precision.** Six of seventeen.

That is a different claim, and a much smaller one, than none of twenty-eight
escaping.

## Theorem

**T (packed coverage).** A family member realisable in `N` bits obeys
`3^Et 2^M <= 2^(N-1)`. Substituting the minimal `Et` gives
`m + log2(b+1) <= N-1`, identical to the uniform binary budget, since
`log2(3) log3(x) = log2(x)`.

**Corollary.** A ternary exponent encoding provides no budget slack at equal
storage. The `0.3691 E` slack exists only at equal **position** count -- that is,
on a fabric where a position is physically ternary.

## Why this went unseen for seven iterations

The same defect was already recorded twice tonight, as T6 and as the level-table
artefact where TNF4 with `Et=2` turned out not to exist in four bits because
`3^2 = 9 > 8`. Both were noted as local facts about packing. Neither was carried
back to the headline, which had been derived in positions months earlier and was
treated as settled.

**Rule adopted: a correction that invalidates a comparison must be applied to
every claim resting on the same quantity, not only to the one where it surfaced.**
The packing constraint was found on 2026-08-09 and applied to level tables the
same day; it took a further day to reach the result it most affected.
