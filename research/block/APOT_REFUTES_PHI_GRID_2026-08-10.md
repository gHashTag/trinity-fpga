# APoT refutes the phi scale-grid claim, and exactness turns out not to be ours

Two of our own claims from earlier tonight are bounded or withdrawn here. Both
were refuted by looking properly at a competitor rather than by a new experiment
of our own design.

## 1. The phi grid was measured against the wrong baseline

Yesterday's result — the `phi^k` grid costs 2.44% excess reconstruction error
against exact `alpha` where `2^k` costs 4.86%, ratio 0.501 against a predicted
0.500 — is reproduced and stands. **It was compared against the wrong thing.**

The state of the art for multiplier-free scales is not plain powers of two. It is
**APoT** (Additive Powers-of-Two, ICLR 2020): levels constrained to sums of
power-of-two terms, keeping shift-add hardware while densifying the grid.

Measured on the same 210 layers, same ternary support, same ruler check:

| scale grid | hardware | cycles | excess over exact |
|---|---|---:|---:|
| exact `alpha*` (BitNet) | **multiplier** | 1 | 0.0000% |
| `phi^k` (ours) | k adds | **k** | 2.4420% |
| `2^k` | 1 shift | 1 | 4.8579% |
| **APoT-2** `2^p ± 2^q` | 2 shifts + 1 add | **1** | **0.1651%** |
| **APoT-3** `2^p ± 2^q ± 2^r` | 3 shifts + 2 adds | 1 | **0.0054%** |

**APoT-2 is 15x more accurate than our grid and takes one cycle instead of k.**
Our grid wins in 17 layers of 210 against APoT-2, and 2 of 210 against APoT-3.

The narrower statement survives: `phi^k` does beat `2^k`, by exactly the density
ratio predicted. The claim that mattered — that ours is the right grid for a
multiplier-free scale — does not. **Withdrawn.**

## 2. Exactness is a property of any closed ring, and binary already had one

`dot_exact` says the linear path of a `{-phi,0,+phi}` network is exact because
`Z[phi]` is a ring. That is machine-checked and remains true. It was presented as
an advantage. It is not one.

An APoT scale `2^p ± 2^q` is a **dyadic rational**, and the dyadic rationals
`Z[1/2]` are also a ring closed under the datapath's operations. Checked in exact
arithmetic: a fan-in-512 layer with ternary weights, an APoT-2 scale and Q8 inputs
accumulates to a fraction whose denominator is `2^15` — representable in ordinary
fixed point with **no rounding at all**.

So exactness in the linear path is not something the golden alphabet provides and
binary lacks. Binary fixed point has had it since fixed point existed. The theorem
is correct; the significance we attached to it was not.

## What actually remains unique to phi

One thing, and it is not yet measured, so it is stated as a conjecture rather
than a result.

Products in `Z[phi]` do not grow in term count: `phi^a * phi^b = phi^(a+b)`, and
a value stays a two-component pair however many weights it passes through. An
APoT-2 value multiplied by another APoT-2 value has **four** terms, and the count
compounds with depth. Whether that growth costs anything in a datapath whose
weights are ternary — where the weight contributes a sign-select rather than a
general multiply — is an open question. It is the only remaining structural
difference we can point to, and it needs an experiment, not an assertion.

## Method note

Both findings came from measuring a competitor properly rather than from a new
idea of our own. The APoT comparison was not run for two iterations because the
baseline `2^k` was assumed to be the relevant one. **The cost of assuming a
baseline is that a favourable result can survive for a while without being
wrong-in-itself and still being the wrong comparison.** The rule adopted: before
reporting a grid, an encoding or a code as better, enumerate what the literature
actually deploys for that exact role, not what is nearest in our own catalogue.
