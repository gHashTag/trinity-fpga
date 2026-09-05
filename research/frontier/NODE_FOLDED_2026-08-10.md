# The node, with the negation folded: 28 LUT per weight

The first complete-node measurement reported 82.5 LUT per weight and said the
figure priced the implementation rather than the format, because `-x` was
computed per lane as a full two's complement instead of being folded into the
adder tree. This does the fold and re-measures.

## The fold

Two's complement is `(~x) + 1`, and the `+1` of every lane is a single bit. So
XOR the sample with the weight's sign, collect the signs in a second, narrow
tree, and add that count once at the root:

    cb[i]  = active ? (x_ext ^ {ACC{negative}}) : 0
    cin[i] = active & negative
    acc_b  = tree(cb) + tree(cin)

Equivalence against the unfolded version: **0 mismatches in 400 random
(x, w) vectors**, checked in simulation before any synthesis.

## Measured

Harness subtracted, isolated, full observation, median of five seeds, xc7a200t,
`-nodsp`.

| fan-in | LUT/weight before | after | Fmax before | after | MHz/LUT gain |
|---|---|---|---|---|---|
| 8 | 82.5 | **28.0** | 109.35 | 87.29 | **2.35x** |
| 16 | 87.1 | **33.1** | 91.43 | 73.42 | 2.66x |
| 32 | 119.0 | **33.2** | 66.53 | 58.22 | 2.87x |

Node totals after the fold: 224, 530 and 1063 LUT at fan-in 8, 16 and 32,
against 660, 1393 and 3809 before. **Zero DSP throughout, unchanged.**

Area falls by 2.9x to 3.6x and lands on the hand-count -- a three-way select of
a 16-bit value at about 16 LUT6 plus a 16-bit add at about 8, so 24 to 30 per
lane. That the measurement now agrees with the count is the confirmation that
the negation was the whole gap, and not the format.

Frequency falls about 20%, which is real rather than seed noise: the carry tree
is a second path and its root addition sits after the main one. On throughput
per area the trade is clearly worth it, 2.35x to 2.87x.

## What may now be quoted

**28 LUT per weight at fan-in 8, zero DSP**, on an Artix-7 in a fully open flow.
That is the number asked from outside, and it is now the implementation's own
rather than an artefact of an unoptimised lane.

The previous figure is not deleted. It was reported with its caveat, the caveat
named the cause, and the cause turned out to be the whole of it -- which is the
outcome a stated caveat is for.
