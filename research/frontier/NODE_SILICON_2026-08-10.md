# The complete node: LUTs per neuron, and why the figure is not yet the format's

Every silicon number in this work so far measured a piece -- a decoder, a scale
step, an element table. The number asked from outside is LUTs per neuron, and
this is the first measurement of the assembled thing: fan-in N, weights from
`{-phi, 0, +phi}`, accumulator in `Z[phi]`, 8-bit samples.

## What the node is

The alphabet is two bits per weight. Applying `+phi` to a sample `x` taken as
the coordinate pair `(x, 0)` gives `(0, x)`, so a weight application is a select
among `(0,x)`, `(0,-x)` and `(0,0)` --- no arithmetic. The neuron is then the
accumulation tree and nothing else. That is the closure result in hardware: the
multiply is a select because the product never leaves the lattice the adder tree
already works in.

## Measured

Harness subtracted. Isolated, every output bit folded into the observed
reduction, median of five seeds, xc7a200t, `-nodsp`.

| fan-in | LUT (node) | LUT/weight | Fmax | DSP |
|---|---|---|---|---|
| 8 | 660 | 82.5 | 109.35 MHz | **0** |
| 16 | 1393 | 87.1 | 91.43 MHz | **0** |
| 32 | 3809 | 119.0 | 66.53 MHz | **0** |

Harness alone: 182 LUT at 872.60 MHz (128-bit), 393 LUT at 888.89 MHz (320-bit,
needed at N=32).

## Two defects of ours found while measuring, and one that was not there

**The N=32 row was invalid on the first pass.** With 8-bit samples a fan-in of
32 needs 256 bits of stimulus, and the harness offered a 128-bit register:
`lf[255:0]` on a 128-bit reg. Re-measured against a 320-bit LFSR, which is why
the harness baseline differs between rows.

**A comment claimed a balanced tree over a ripple chain.** The first version
wrote `for (j = 0; j < N; j = j + 1) sum = sum + cb[j];` under a comment saying
"balanced adder tree". Replaced with a real tree -- and the measurement barely
moved, 842 against 847 LUT at N=8, because the synthesiser was already
balancing it. The suspicion was reasonable and the check disproved it, which is
the outcome a check is for.

## The figure is above a hand-count, and the reason is ours

A three-way select of a 16-bit value costs about 16 LUT6 and a 16-bit add about
8 with carry chains, so a lane should be near 24 and a fan-in-8 node near 200.
Measured is 660. The gap is the negation: `-x` is computed per lane as a full
two's-complement subtract rather than folded into the adder tree as a
carry-in, so every negative weight pays a 16-bit inverter and an increment that
the tree could have absorbed.

**So 82.5 LUT per weight prices this implementation, not the format.** The
number is reported because it is what was measured and because the next step is
obvious --- fold the negation into the tree and re-measure --- not because it is
the number the format deserves. Quoting it as the format's cost would be the
same error as quoting a single-seed table as a median.

What does not depend on the implementation: **zero DSP at every fan-in**, and
the fact that the weight application contains no arithmetic at all.
