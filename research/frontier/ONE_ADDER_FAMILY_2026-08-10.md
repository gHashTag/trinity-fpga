# Fineness costs registers, not adders

The hierarchy was reported by algebraic degree, and the cost was reported as the
minimal ratio available at each degree. That framing hid the result.

## The family

`r^d = r + 1` has exactly two non-zero coefficients at every degree, so its
companion map is **one addition** regardless of `d`:

    (x_0, ..., x_{d-1})  ->  (x_{d-1},  x_0 + x_{d-1},  x_1, ..., x_{d-2})

verified exact over 3000 random coordinate vectors at `d = 5` and `d = 8`.

| d | r | 2^(1/d) | r / 2^(1/d) | level error | adds |
|---|---|---|---|---|---|
| 2 | 1.618034 | 1.414214 | 1.144123 | 23.607% | 1 |
| 3 | 1.324718 | 1.259921 | 1.051429 | 13.968% | 1 |
| 5 | 1.167304 | 1.148698 | 1.016197 | 7.719% | 1 |
| 8 | 1.096982 | 1.090508 | 1.005937 | 4.625% | 1 |
| 16 | 1.045751 | 1.044274 | 1.001415 | 2.236% | 1 |

**T38 (the one-adder family).** For every `d` the polynomial `r^d = r + 1` has a
unique real root above one, its companion map costs one addition and `d`
registers, and the roots converge to `2^(1/d)` from above. Any granularity a
logarithmic subdivision offers is therefore reachable multiply-free, at the cost
of registers alone.

The earlier statement -- that the hierarchy "stops being cheap at degree four,
where the coefficient vector loses its sparsity and the cost doubles" -- was
about the *minimal ratio at that degree* and is misleading as a claim about the
hierarchy. Read along the one-adder family instead, the adder count never grows.

## Measured on silicon

Same harness as every other scale measurement: isolated unit, every output bit
folded into the observed reduction, median of five placement seeds, xc7a200t,
16-bit components.

| step | LUT | FF | Fmax (MHz) | level error | adds |
|---|---|---|---|---|---|
| `phi`, r^2 = r+1 | **149** | 128 | 307.69 | 23.607% | 1 |
| r^5 = r^3 + 1 | 164 | 160 | 306.56 | 10.575% | 1 |
| **r^8 = r + 1** | 225 | 212 | **815.66** | **4.625%** | 1 |

A fivefold refinement costs 51% more LUTs, 66% more flip-flops, and **no
frequency at all** -- the eight-register step measured 2.65x the frequency of
the two-register one, because its single adder sits on one of eight parallel
paths rather than one of two.

So the trade is registers against granularity, and nothing else. That is a much
better trade than the one the degree framing implied.

## Against the optimal geometric ratio

The scale grid that minimises relative error is geometric with ratio
`R^(1/N)`, an arbitrary real needing a multiplier. The one-adder family
approximates it:

| block scale width | optimal r* | nearest multiply-free | error |
|---|---|---|---|
| 4 bits | 1.551145 | 1.551532 | 0.06% |
| 5 bits | 1.236662 | 1.236506 | 0.06% |
| 6 bits | 1.110180 | 1.110187 | 0.01% |
| 7 bits | 1.053217 | 1.053852 | 1.16% |
| 8 bits | 1.026159 | 1.049852 | 88.40% |

At four to six bits -- which is the width a block scale actually occupies, the
range being 8.32 to 9.12 binades -- a multiply-free ratio matches the optimum to
within 0.06%. At eight bits the spectrum has a gap and the optimum falls in it.

So the tension recorded yesterday resolves in the practical range: *the optimal
grid needs a multiplier* is true in general and false where the scale actually
lives.
