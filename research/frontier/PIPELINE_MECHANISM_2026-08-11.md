# The pipeline crossover is not where it was said to be, and not for the reason given

`NODE_PIPELINED_2026-08-11.md` measured one pipeline register inside the ternary
node's adder tree, found MHz-per-LUT rising at fan-in 8 and 16 and falling at 32,
and explained it:

> The register cost overtakes the frequency gain between sixteen and thirty-two.
> The crossover is where N/2 registers stop being cheap relative to the tree they
> cut.

Two claims sit there: that a crossover exists between 16 and 32, and that
registers cause it. Both were tested. **The mechanism is wrong, and the crossover
is not located because the effect is smaller than the instrument.**

## The mechanism, measured

The cut's cost per weight is **exactly constant** at every fan-in measured:

| fan-in | 8 | 12 | 20 | 24 | 28 | 32 |
|---|---:|---:|---:|---:|---:|---:|
| extra FF per weight | 9.00 | 9.00 | 9.00 | 9.00 | 9.00 | 9.00 |
| extra CARRY4 per weight | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 |
| LUT penalty | +30.8 % | +18.7 % | +16.1 % | +18.4 % | +20.0 % | +18.6 % |

Net flip-flops are exactly `16 + 9N` in every pipelined row. Nothing "stops being
cheap relative to the tree" as N grows — the penalty is **largest at the smallest
fan-in**, which is the opposite of the stated mechanism, and flattest in the
middle. At N = 16 it is +11.9 %.

And the added area is not registers at all. Flip-flops occupy SLICE_FFX and
consume no LUTs. What actually happens:

- yosys collapses the **unpipelined** tree into two `$macc_v2` carry-save
  compressor cells — 5 to 6 CARRY4 total at *every* fan-in from 8 to 32
- pinning the level-1 partials in a register **forbids that collapse**, forcing
  exactly N standalone `$alu` adders and raising post-route CARRY4 by exactly 2N

**It is carry-chain restructuring, not register cost.** The register is not
expensive; it is a barrier that prevents the compressor from forming.

## The crossover is not located, and the published −8.7 % is not safe

The pipelined arm carries **14.6 % placement-seed spread** against 0.6 % for the
unpipelined arm. At fan-in 32 the sign of the MHz/LUT change flips with the seed:
−3.8 % on one, +3.5 % on the median of two. Under this project's own rule — a gap
smaller than the seed spread asserts no ordering — the fan-in 32 result does not
support the direction it was published with.

Measured MHz/LUT gain: +7.8 % at 8, +18.7 % at 12, +34.9 % at 20, +31.5 % at 24,
+5.2 % at 28, +3.5 % at 32. That is not a clean crossover; it is a rise, a peak
around 20, and a decay into noise.

## The two builds are different, which is the sharper finding

The adversarial check compared the reproducible flow against the published table
across the whole sweep rather than at one point, and found the disagreement is
not a seed artefact — **area is seed-invariant in both flows, verified**:

| fan-in | published pipelined LUT/weight | reproducible flow |
|---|---:|---:|
| 8 | 32.4 | 36.62 |
| 16 | 34.9 | 36.56 |
| 32 | 47.3 | 39.59 |
| slope across the sweep | **+46 %** | **+8 %** |

The published pipelined arm has a different area-versus-N slope from anything
this flow produces. The "+42 % area at fan-in 32" that the published mechanism
rests on is a property of that build, not of the design — which is why the
mechanism derived from it does not survive.

## What should change

`NODE_PIPELINED_2026-08-11.md`'s **measurements stand as measurements**; what does
not stand is the explanation attached to them and the advice drawn from it. Its
closing line — "at fan-in 32 the unpipelined form is the better one, which is the
opposite of the usual advice" — rests on a −8.7 % that flips sign with a
placement seed.

The defensible statements from this work are narrower:

- one pipeline register costs a **constant** 9 FF and 2 CARRY4 per weight, at
  every fan-in from 8 to 32
- it buys frequency by **preventing a carry-save compressor from forming**, which
  is why it costs carry chains rather than logic
- MHz per LUT peaks around fan-in 20 and decays into seed noise by 28
- **fan-in 32 is not resolved** and should not be quoted in either direction

---

*Method: yosys 0.65 + nextpnr-xilinx, xc7a200t, `-nodsp`, harness subtracted
(438 LUT / 328 FF / 0 CARRY4, verified independently rather than taken on trust),
full observation confirmed by tracing every `acc_b` bit into the output fold.
`acc_a` is dropped because both `tern_node2.v` and `tern_node3.v` literally assign
it zero — symmetrically, in both arms. The reported paths are posedge-to-posedge,
starting inside the DUT, so this is not a repeat of the withdrawn 323 MHz
combinational-block error. **Under-seeded: 1 seed for 11 of 13 designs against the
project's rule of five, because the machine was saturated.** Area conclusions are
unaffected — area is seed-invariant and that was checked — but every Fmax here is
weaker than the rule requires, and the crossover question needs the full five
seeds before it can be closed.*
