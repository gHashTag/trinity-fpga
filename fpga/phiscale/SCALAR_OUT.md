# Leaving the lattice, and what the previous comparison was missing

`PIPELINED.md` reported the pipelined φ layer at **660 LC, 204.08 MHz** against
the multiplier's **1098 LC, 69.21 MHz** — 1.66× smaller and 2.95× faster.

**That comparison was not like for like.** The φ layer's output is the pair
`(a, b)`; the multiplier's is one number. Something has to reconstruct
`a + b·φ` before the next layer can consume it, and nothing did — the cost sat
outside the measured design.

## The reconstruction

`zphi_to_scalar.v` computes `a + b·207/128` as shift-adds — 0.05% off φ, no
multiplier — and requantises to W bits with saturation. It is split across two
register stages, and that split is not cosmetic: the first version summed all
six shifted terms and the saturate in one combinational block, and the layer's
Fmax fell from 204 MHz to **72.57 MHz**. Latency at a layer boundary is free;
depth is not.

Verified before measured: 200 randomised cases against a golden model, 0 errors,
with the saturation branch exercised deliberately (`a=b=32000 → 127`).

The rounding introduced here is not a loss the lattice was preventing. The layer
boundary is where a quantised pipeline requantises anyway, to feed the next
layer's W-bit input. The lattice's job was to keep the **accumulation** exact up
to this point, and it did.

## Measured — nextpnr-ice40, hx8k ct256, ACC=16

| layer | N | LC | SB_IO | Fmax |
|---|---:|---:|---:|---:|
| **φ, scalar out** | 8 | **839** | 96 | **106.26 MHz** |
| multiplier | 8 | 1098 | 116 | 69.21 MHz |
| **φ, scalar out** | 16 | **1195** | 176 | **94.21 MHz** |
| multiplier | 16 | 1457 | 196 | 71.75 MHz |

Both accept one element per cycle, so the frequency ratio is the throughput
ratio: **1.54× at fan-in 8, 1.31× at fan-in 16**, with 1.31× and 1.22× the area
advantage.

**Not 2.95×.** That figure compared a layer that cannot be deployed as it stands
against one that can.

## The pin blocker is gone

At fan-in 16 the pair output needed **217 pins on a 206-pin package** and
place-and-route stopped with the logic at 10% utilisation. With one output it
needs 176, and fan-in 16 is measurable for the first time. Fan-in 32 still does
not fit — 336 pins for the φ arm and 356 for the multiplier — so that is an
input-width limit both arms share, not a property of the lattice.

## A real bitstream, and a second opinion on timing

`icepack` produces a 135,100-byte bitstream for both arms — the design reaches a
programmable artifact, not just a netlist. No board is attached, so nothing was
loaded.

`icetime` was run as an independent check and disagreed with nextpnr by 3.4×:
**60.87 MHz against 204.08**. The disagreement is real and it resolves: icetime's
default report is the longest path in the design, which here is **pin to
register** (16.43 ns), and nextpnr reports that separately as
`<async> → posedge` (15.88 ns). Register to register, the two agree.

Both arms carry a ~15.7 ns pin-to-register path. As built, on pads, both are
capped near 63 MHz; a deployed layer feeds from memory or registers and sees the
synchronous number. That caveat applies to every frequency in this directory and
was not visible until a second tool was pointed at the same artifact.
