# A whole ternary layer, and what the 7.1× actually was

`README.md` in this directory reports the φ scale applier at **171 LUT and 0
DSP** against **1215 LUT or 2 DSP48** for a real multiplier, and calls it 7.1×.
That number is correct and it is about a *fragment*. Every file here measured a
piece — the neuron, or the scale applier — and the number asked from outside is
the layer.

This is the layer: fan-in N, ternary weights, accumulator in Z[φ], layer scale
φ^k by iterated Fibonacci step, against the same MAC with a real multiplier for
the scale.

## Correctness first

`tern_layer_phi_tb.v` checks 60 randomised cases against a golden model computed
independently in integers, and asserts a deliberately wrong expectation to prove
the bench can fail:

```
60 checks, 0 errors
negative control: a wrong expectation would be caught
```

## Measured — Yosys 0.65, `synth_xilinx -family xc7`, W=8, ACC=24

| N | arm | DSP allowed | LUT | DSP48 | FF |
|---:|---|---|---:|---:|---:|
| 16 | **φ** | either | **1433** | **0** | 127 |
| 16 | multiplier | no | 2197 | 0 | 49 |
| 16 | multiplier | yes | **1302** | **1** | 49 |
| 64 | **φ** | either | **6386** | **0** | 127 |
| 64 | multiplier | no | 7135 | 0 | 49 |
| 64 | multiplier | yes | **6273** | **1** | 49 |

> **Corrected 2026-08-18.** The figures first published here were inflated by
> exactly 3.0 and the DSP count by 3, because the extraction summed LUT lines
> across every stat block `synth_xilinx` emits rather than the last one. The
> RTL has one 16×16 multiply and fits **one** DSP48E1.

## What that changes about the claim

**The saving is a constant, not a ratio.** φ is ~760 LUT smaller than the
DSP-less multiplier arm at both fan-ins, because what it removes is the
multiplier itself and the MAC tree in front of it is identical in both arms. As
a ratio that is **1.53× at fan-in 16 and 1.12× at fan-in 64** — the wider the
layer, the more the fixed saving is diluted.

So "7.1×" is true of the scale block and misleading if read as a layer claim.
The layer claim is: a fixed ~760 LUT removed against a multiplier denied its
DSPs, and **one** DSP48 removed against one allowed them — for which the φ arm
pays 131 LUT more at N=16 and 113 more at N=64. Against a multiplier on its
normal footing the φ arm is the LARGER one, at 0.91× and 0.98×.

**With DSPs available the multiplier arm is smaller in LUTs** (1302 against
1433 at N=16) and pays one DSP48 for it. The φ arm is DSP-invariant —
identical with and without — because there is no multiply to map. On a part
where DSPs are scarce or already spent, that invariance is the point; on a part
with DSPs to spare, the multiplier arm wins on LUTs.

**φ costs 2.6× the registers**, 127 against 49, at every fan-in. The pair
representation carries two components where the multiplier carries one.

## Nothing here touched silicon

`synth_xilinx` targets a family, not a device, and no place-and-route ran: these
are post-synthesis cell counts. No board is attached to this machine and no
bitstream for this family was built.

## What this does not establish

No Fmax: `nextpnr-xilinx` is not installed on this machine, so this is area
only. No board. One clock domain, one output element, no memory for weights or
activations — a deployed layer has all three and they are not counted here.

## A note on the harness, because it cost most of the time

The first version of `tern_layer_phi_tb.v` drove stimulus on the **posedge** and
so raced the flops sampling it. Nothing fired. From that I concluded, in order,
that the two blocks did not compose and then that `scale_phi` was broken. Both
were false: `scale_phi_tb.v` in this directory drives on the **negedge** and
passes 200 of 200, and once this bench does the same, the blocks wire straight
together with no pipeline register between them.
