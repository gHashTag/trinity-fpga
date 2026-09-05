# Withdrawal 16: the LNS comparison was never well-posed

The longest-running open number of the session, resolved -- not by removing
another confound, but by finding that it had no value to converge to.

## The trend, and why it never settled

| instrument | claimed advantage over LNS |
|---|---:|
| synthesis area only | 8.6x |
| post-route, 4-bit observation | 14x |
| post-route, 16-bit observation | 11.5x |
| post-route, 32-bit observation | 5.5x |
| post-route, harness invariant | 4.4x |
| **+ matched state width** | **5.8x** |

Five corrections moved it down; the sixth moved it back up. The trend theorem
said a monotone response signals remaining confounds. It stopped being monotone
because the last correction was not a confound removal -- it was a change of
*which property is held equal*.

## The two systems are not commensurable at equal storage

| system | bits | range | precision |
|---|---:|---|---|
| `Z[phi]`, 2x16 | 32 | `2^15`, **linear** in width | **exact** |
| `Z[phi]`, 2x32 | 64 | `2^31`, linear | exact |
| LNS-32 (1.8.23) | 32 | `2^±128`, **exponential** in the integer field | `~2^-23` relative |

**T (incommensurability at equal storage).** A system with exact arithmetic in a
ring and one with approximate arithmetic in a logarithm cannot be compared at
equal bit count. The first has range linear in width and absolute precision; the
second has range exponential in its integer field and relative precision. The
area ratio between them depends on which property is held equal, and moves in
both directions with that choice.

Measured: matching **bits** gives 5.8x in our favour. Matching **range** would
require `Z[phi]` components of 128 bits -- 256 bits of state against LNS-32's 32,
**8x the storage** -- and it would lose. Matching **precision** is impossible in
the other direction: the logarithm of a sum is irrational and the table always
rounds.

**Corollary.** A quantity whose value depends on an unstated choice has no limit.
It was never going to converge, and the five corrections that moved it were all
correct while the thing they were correcting did not exist.

## What is withdrawn and what replaces it

**Withdrawn:** every numerical form of "`Z[phi]` addition is N times cheaper than
an LNS adder". The ratio is not a property of the two systems.

**Retained**, because neither depends on a matched-storage assumption:

- `Z[phi]` is cheap under **both** operations -- multiplication by a power of
  `phi` is one integer addition, addition is componentwise -- where LNS is free
  on multiplication and pays a table on addition. That is a statement about
  operation counts, not about area at a chosen width.
- **LNS has no representation for zero**, since `log 0` is undefined, so it needs
  a flag and a special path. A ternary weight alphabet is about **46% zeros** on
  real weights. A system whose zero is a special case applied to an alphabet
  whose most frequent symbol is zero.

Both are structural, checkable, and independent of how the widths are matched.

## The lesson, stated generally

Six instrument corrections were made in pursuit of a number that did not exist.
Every one of them was a real defect and worth fixing -- three harness confounds
now have gates -- but none of them could have produced convergence.

**Before chasing a number's stability, check that the comparison producing it is
well-posed.** Ask what property is held equal, and whether the answer changes the
result. If it does, and no choice is principled, the ratio is not a measurement.
