# On the family this work targets, the area claim does not hold

Every frequency and area number in this directory before now was measured on
**iCE40**, which has no DSP blocks at all. That is the fabric where a design
avoiding multipliers looks best, because the competitor has to build its
multiplier out of logic.

Artix-7 is the family this work targets, and it has 90 to 740 DSP48 blocks
depending on the part. Measured there, with the same memory-backed layer:

## Measured — yosys 0.65, `synth_xilinx -family xc7`, ACC=16, ROWS=16

| arm | N | DSP inference | LUT | DSP48 | FF |
|---|---:|---|---:|---:|---:|
| φ | 16 | either | 1711 | 0 | 723 |
| multiplier | 16 | forbidden | 1869 | 0 | 346 |
| **multiplier** | 16 | **allowed** | **1275** | **1** | 346 |
| φ | 32 | either | 3090 | 0 | 1043 |
| multiplier | 32 | forbidden | 3193 | 0 | 666 |
| **multiplier** | 32 | **allowed** | **2598** | **1** | 666 |

> **Corrected 2026-08-18.** The figures first published here were inflated by
> exactly 3.0, and the DSP count by 3. `synth_xilinx` prints its own statistics
> before the script's explicit `stat`, and the extraction summed LUT lines
> across every block in the log. `tern_layer_mem` contains one 16×16 multiply,
> which fits **one** DSP48E1 — three was never obtainable from this RTL, and
> nothing in the original run questioned it. Every conclusion below survives,
> because numerator and denominator were inflated by the same factor.

With DSP inference forbidden the φ arm is smaller, as on iCE40. **With DSPs
available — the normal case on this family — the multiplier arm is 436 LUT
smaller at fan-in 16 and 492 smaller at 32, and uses 377 fewer flip-flops.**

## The exchange rate, which is the honest way to state it

The φ arm does not save area on this family. It **trades**: it spends LUTs and
flip-flops to avoid three DSP48 blocks.

| N | LUT cost | DSP freed | LUT per DSP |
|---:|---:|---:|---:|
| 16 | 436 | 1 | **436** |
| 32 | 492 | 1 | **492** |

Against what the parts themselves carry:

| part | LUT | DSP48 | LUT per DSP |
|---|---:|---:|---:|
| XC7A35T | 20800 | 90 | 231 |
| XC7A100T | 63400 | 240 | 264 |
| XC7A200T | 134600 | 740 | **182** |
| XC7K325T | 203800 | 840 | 243 |

**Spending 436–492 LUT to free one DSP is a worse exchange than the device's own
mix**, by roughly two to three times. The trade pays only when DSPs are already
exhausted — when their marginal value is not merely high but infinite — or on a
part that has none.

## What is withdrawn and what stands

**Withdrawn**: any claim that the φ layer is smaller on a DSP-bearing part. It is
not, and the earlier 1.13× was measured on iCE40 where the multiplier has no
DSP to use.

**Stands**: the φ arm needs **zero DSP48 at any fan-in**, and it is smaller than a
multiplier built from logic — 1711 against 1869 at N=16, 3090 against 3193 at
N=32. On a device with no DSPs, or one where they are spent, that is the whole
product.

**Also stands**: exactness. The lattice accumulates without rounding, which is a
property no LUT count reflects and which this comparison does not measure.

## Nothing here touched silicon

`synth_xilinx` targets a **family**, not a device — it has no device option — and
no place-and-route ran. These are post-synthesis cell counts. No board is
attached to this machine, `nextpnr-xilinx` and `prjxray` are not installed, and
no bitstream for this family was ever built, let alone loaded.

## Method note

The memory inferred as `RAM32M` — distributed LUT RAM — rather than block RAM,
because 16 rows is small enough that yosys prefers it. Both arms are affected
identically, so the comparison is like for like, but the absolute LUT figures
include the operand memory and are not the logic alone.
