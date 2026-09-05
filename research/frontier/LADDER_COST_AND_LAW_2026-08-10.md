# The granularity/cost curve is not smooth, and the optimum has a closed form

Two results, one measured on the fabric and one derived from the weights.

## 1. Degree 4 is where the hierarchy stops being cheap

`deg4_step` implements the smallest degree-4 multiply-free scale,
`r^4 = -r^3 + r^2 + r + 1`, `r = 1.178724`. The map is
`(x0,x1,x2,x3) -> (x3, x0+x3, x1+x3, x2-x3)`, verified exact over 3000 random
coordinate vectors. Measured in the harness that produced the other tables:
isolated, fully observed, median of five seeds, xc7a200t.

| 32-bit scale application | LUT | FF | Fmax (MHz) | level error | add/subs |
|---|---|---|---|---|---|
| phi (degree 2) | **223** | 192 | **247.10** | 23.61% | 1 |
| plastic (degree 3) | 228 | 200 | 231.21 | 13.97% | 1 |
| degree 4 (1.1787) | 469 | 320 | 184.98 | **8.20%** | 3 |

Degrees 2 and 3 both cost **one addition**, and their areas differ by 2.2%. At
degree 4 the coefficient vector stops being sparse -- three non-zero
coefficients instead of one -- and the cost jumps: 2.1x the area, 1.67x the
registers, 25% slower.

So the hierarchy is cheap exactly as far as degree 3. A finer ladder than
1.3247 exists and is multiply-free, but it is no longer nearly free.

## 2. The optimal ratio follows from the weight histogram

T31 said ranking ladders by weight MSE gives the perplexity order. Measuring
that MSE still needs a pass over every weight per candidate. It has a closed
form.

Normalise each channel by its maximum, so levels are `r^-k`, `k = 0..n-1`,
`n = (2^b - 1)/2`. Then

    MSE(r,b)  ~  c(r)^2 * E[x^2 . 1{x>t}]  +  E[x^2 . 1{x<t}],   t = r^-(n-1) / 2

where `c(r)^2` is the mean square relative rounding error of a geometric ladder
of ratio `r` -- a one-dimensional integral over the log-position within a bin,
independent of the data. The first term falls as `r` falls; the second rises as
the clipping threshold `t` rises. The minimum is the crossover.

Against the measured MSE on SmolLM2-135M (106,168,320 normalised weights):

| bits | agreement in ratio | picks the same ladder |
|---|---|---|
| 3 | 0.63 -- 0.80 | yes |
| 4 | 0.91 -- 1.00 | yes |
| 5 | 1.00 -- 1.01 | yes |

Three of three. At 4 and 5 bits the formula reproduces the measured error to
within 1--9%; at 3 bits it underestimates by a third, and the reason is a real
limit rather than a fitting failure: at seven codes almost everything is
clipped, and a model built on bounded *relative* rounding error does not
describe a regime dominated by *absolute* truncation.

### The law

Minimising over continuous `r` gives the optimal ratio per budget, from the
histogram alone and with no model evaluation:

| bits | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|
| r* | 2.054 | 1.4115 | 1.1999 | 1.1050 | 1.0576 | 1.0319 |

`ln r*` roughly halves per bit, which is what the structure predicts: doubling
the code count halves the available log-spacing at a fixed span.

**T33 (the optimal-ratio law).** For a weight distribution and a code budget the
optimal multiply-free ratio is the minimiser of `MSE(r,b)` above, and the
required algebraic degree is the smallest whose minimal scale is at most `r*`.
Reading the hierarchy against the table: 3 bits wants degree 1, 4 bits sits
between degree 2 and degree 3, 5 bits wants degree 4, and 8 bits would want
degree 9 or beyond.

### What this says about our own alphabet, plainly

`phi` is the right rung at four bits, where `r* = 1.4115` sits between `phi`'s
1.618 and supergolden's 1.4656 and the two tie in perplexity. It is the wrong
rung at five bits and above, where `r*` has fallen past the plastic number --
but by then the cheap part of the hierarchy has been left behind too, since
degree 4 costs 2.1x the area. The interesting regime for a multiply-free
datapath is exactly the one where degrees 2 and 3 are the only affordable rungs,
and that is three to five bits.
