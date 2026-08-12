# The crossover is not a local functional — a closed line, not future work

## What was attempted

Iteration 107 withdrew `N* ≈ D` as a heuristic that read a *spacing* off a
theorem about a *ratio*. The obvious repair: equate the theorem's two branches
directly.

    (1/24) g'' h²  =  (1/2) c₋c₊ h / (c₋+c₊)
    ⟹  N*_theory = g''(t*) (c₋+c₊) / (12 c₋c₊)

**No fitted constant anywhere**, and every term is *exact*, not estimated. On one
arc the rounding indices are frozen, so `g(t) = s²A − 2sB + C` with `s = 2^t`,
`A = ΣL²`, `B = ΣLv`. Hence `g'' = 2(ln2)²s(2sA−B)` and each one-sided slope is
`2(ln2)s(sA−B)` with its own arc's (A,B). No finite differences, so no inherited
lattice bias — the failure mode this programme keeps finding.

## It does not work

Seven codebooks, five aggregations of the per-block value:

| predictor | mean ratio | CV |
|---|---|---|
| 1/w*, arc containing the optimum | 0.27 | **32.1%** |
| N*_theory, median | 0.30 | 37.6% |
| N*_theory, corner-weighted | 0.21 | 37.8% |
| D, the withdrawn heuristic | 0.84 | 40.5% |
| N*_theory, mean | 1.15 | 47.5% |
| N*_theory, curvature-weighted | 1.22 | 51.4% |

A usable predictor sits near 10%. **The best here is 32%, and it is not the
derived one.**

## Why, and it is not the theorem's fault

The theorem concerns two asymptotic regimes and is exact in each. Equating
leading terms locates a crossover **only when every block is deep in one regime
or the other**, and near the crossover none is.

Measured N* is where the exponent of a **sum over millions of blocks** reaches 2.
That is a property of the whole distribution of per-block behaviours across a
range of h — not of any single block's slopes and curvature at its own minimum.
The diagnosis was aggregation, and the aggregation cannot be repaired by choosing
a better average: five were tried, spanning weight-by-corner to weight-by-
curvature to the 90th percentile, and the spread never fell below 32%.

## The honest status

`cor:designrule` stands in its **ordinal** form only — count corners, rank
codebooks, do not read a number off the count. That is now the strongest true
statement available, and this file records why the stronger one is not merely
unproven but **not derivable at this level of description**.

> Closing a line is worth as much as opening one. "Future work: derive the
> constant" would have been dishonest — the attempt was made, the formula is
> written down, and it fails for a stated reason. The next reader does not spend
> the afternoon we spent.
