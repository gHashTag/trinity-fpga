# There is no gap in the multiply-free spectrum -- the enumeration stopped early

Earlier this session we reported that the multiply-free ratios have a gap at the
eight-bit block-scale optimum: target `1.026159`, nearest available `1.049852`,
an error of 88%. **That is withdrawn.** The gap was the edge of our enumeration,
which stopped at degree 8.

Extending it:

| coefficients | max degree | roots found | nearest to 1.026159 | error |
|---|---|---|---|---|
| {0,±1} | 8 | 1568 | 1.049852 | 88% |
| {0,±1} | 9 | 4302 | 1.036380 | 0.99% |
| {0,±1} | 10 | 13501 | 1.027738 | 0.15% |
| **{0,±1,±2}** | **9** | **734533** | **1.026129** | **0.003%** |

The polynomial reaching 0.003% is
`r^9 = -r^8 - r^7 + r^6 + r^5 + r^4 + 2r^3 - r^2 - r` with coefficients
`[-2,-1,1,1,1,1,2,-1,-1]`; a coefficient of ±2 is a shift, so the map remains
addition and wiring with no multiplier.

## What is a real limit, and what was ours

**Not a limit:** the spectrum's density. It is dense enough at degree 9--10 to
hit any target we have needed, to a fraction of a percent, with {0,±1} alone.

**A real limit:** the ONE-ADDER family. At the eight-bit target the best
one-adder ratio is `1.0850702` under {0,±1} (5.6% error) and `1.0510545` under
{0,±1,±2} (2.4%). Approximation quality at fixed adder count does not improve
with degree beyond a point, and that is a property of the family rather than of
the search.

So the picture is two-sided and both sides matter. Any ratio is reachable
multiply-free if you will spend adders; only a coarser set is reachable with one.

## The methodological point, which is the reason to write this down

The claimed gap came from a search bound, reported as a property of the object.
Nothing in the output said "degree ≤ 8"; the table said "nearest multiply-free
ratio" and the reader -- us -- took that to mean nearest in the family rather
than nearest in the part of the family we had looked at.

An enumeration's bound belongs in the result, not in the script. The
corresponding rule for the gates already exists here in another form: a silent
exclusion reads as coverage. A silent search bound reads as exhaustiveness.
