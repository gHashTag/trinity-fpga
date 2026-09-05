# One pipeline register in the node: worth it at eight and sixteen, not at thirty-two

The folded node costs 28 LUT per weight at fan-in 8 and closes at 87.29 MHz. The
critical path is the whole adder tree -- $\log_2 N$ levels of ACC-bit addition in
one cycle -- so cutting it once at the halfway level should trade a cycle of
latency and $N/2$ registers for frequency. Whether that trade is worth taking is
a measurement, not an assumption.

Equivalence first: 0 mismatches in 398 random $(x,w)$ vectors against the
unpipelined module, with the pipelined output trailing by exactly one cycle.

| fan-in | LUT/weight | MHz | MHz per LUT |
|---|---|---|---|
| 8 | $28.0 \to 32.4$ | $87.29 \to \mathbf{126.73}$ | $0.3897 \to 0.4893$ (**+25.6%**) |
| 16 | $33.1 \to 34.9$ | $73.42 \to \mathbf{106.38}$ | $0.1385 \to 0.1906$ (**+37.6%**) |
| 32 | $33.2 \to 47.3$ | $58.22 \to 75.68$ | $0.0548 \to 0.0500$ (**−8.7%**) |

Harness subtracted, isolated, full observation, median of five placement seeds,
xc7a200t, `-nodsp`. Zero DSP throughout, unchanged.

**The register cost overtakes the frequency gain between sixteen and
thirty-two.** At fan-in 8 and 16 the cut buys 45% more frequency for 16% and 5%
more area; at 32 it buys 30% for 42%, and the throughput per area falls. The
crossover is where $N/2$ registers stop being cheap relative to the tree they
cut.

> **Mechanism refuted and fan-in 32 withdrawn, same day — see
> `PIPELINE_MECHANISM_2026-08-11.md`.** The register-cost explanation above does
> not survive measurement: the cut costs a *constant* 9 FF and 2 CARRY4 per
> weight at every fan-in from 8 to 32, and the LUT penalty is **largest at the
> smallest fan-in**. What the register actually does is prevent yosys collapsing
> the tree into a carry-save compressor, forcing N standalone adders — carry-chain
> restructuring, not register cost. And the −8.7 % at fan-in 32 flips sign with
> the placement seed (the pipelined arm carries 14.6 % seed spread), so that row
> should not be quoted in either direction. The fan-in 8 and 16 measurements are
> unaffected.

So the quotable configuration is fan-in 8 or 16 with one pipeline stage:
**32.4 LUT per weight at 126.73 MHz**, or **34.9 at 106.38**, both at zero DSP
and one cycle of added latency. At fan-in 32 the unpipelined form is the better
one, which is the opposite of the usual advice and is why it was measured.
