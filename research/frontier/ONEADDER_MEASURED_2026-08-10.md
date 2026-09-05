# The one-adder family measured on networks, and a calibration error of ours

T38 says `r^d = r + 1` costs one addition at every degree and its roots approach
`2^(1/d)`. T37 says a geometric scale grid beats a float one at equal width. The
two together predict that the whole geometric advantage should be available
without a multiplier. This measures it, on the block scale, K=32, E2M1 elements,
40 windows.

| block scale | r | bits | b/w | SmolLM2 | Qwen |
|---|---|---|---|---|---|
| `phi`, r^2=r+1 | 1.618034 | 4 | 4.1250 | 21.3545 | 14.8512 |
| geometric | 1.236662 | 5 | 4.1562 | 21.5872 | 14.7814 |
| **MF r^5=r^3+1** | 1.236506 | 5 | 4.1562 | **21.5040** | **14.7342** |
| geometric | 1.110180 | 6 | 4.1875 | 20.0199 | 13.8915 |
| **MF r^8=r+1** | 1.096982 | 6 | 4.1875 | **19.3209** | **13.8528** |
| MF r^6=r^4+1 | 1.210608 | 6 | 4.1875 | 23.6337 | 14.8309 |

**On both models, at both widths, the one-adder multiply-free ratio measures at
least as well as the geometric ratio beside it.** The geometric grid's advantage
is therefore available with no multiplier -- one addition and `d` registers.

## A calibration error of ours, and what it explains

The rows labelled "geometric" above were computed as `2^(9.5/(2^b - 1))`, using
9.5 binades for the scale range. The range was **measured** at 8.32 binades on
SmolLM2 and 9.12 on Qwen, and 9.5 was a rounding of the larger one applied to
both. With the measured value the six-bit optimum is `1.095860`, not
`1.110180`, and `r^8 = r + 1` at `1.096982` sits **1.12%** from it.

So the multiply-free ratio did not beat the optimum. It sat near the optimum
while the row we labelled "optimum" did not. The formula was right and the
substitution was wrong, and the correction is worth stating because the
uncorrected reading -- *a multiply-free ratio beats the optimal one* -- is
impossible and would have been noticed by a referee rather than by us.

Recomputed against the measured range:

| width | optimum (8.32 binades) | nearest multiply-free | error | polynomial |
|---|---|---|---|---|
| 4 bits | 1.468829 | 1.465571 | 0.58% | r^3 = r^2 + 1 |
| 5 bits | 1.204461 | 1.210608 | 2.74% | r^6 = r^4 + 1 |
| 6 bits | 1.095860 | 1.096982 | 1.12% | r^8 = r + 1 |
| 7 bits | 1.046456 | 1.062169 | 32.82% | r^12 = r + 1 |

## What replicates and what does not

**Replicates.** A one-adder multiply-free ratio measures as well as a geometric
ratio of similar value, on both models, at both widths. This is the claim that
matters: multiply-free costs nothing in accuracy.

**Does not.** That the multiply-free six-bit scale beats E4M3 at eight bits while
being cheaper. True on SmolLM2 -- 19.3209 at 4.1875 bits per weight against
19.8628 at 4.2500 -- and false on Qwen, where it is cheaper and 0.6% worse,
13.8528 against 13.7636. Not claimed.
