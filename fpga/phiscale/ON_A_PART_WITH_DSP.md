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
| φ | 16 | either | 5133 | 0 | 1767 |
| multiplier | 16 | forbidden | 5607 | 0 | 1022 |
| **multiplier** | 16 | **allowed** | **3825** | **3** | 1022 |
| φ | 32 | either | 9270 | 0 | 2727 |
| multiplier | 32 | forbidden | 9579 | 0 | 1982 |
| **multiplier** | 32 | **allowed** | **7794** | **3** | 1982 |

With DSP inference forbidden the φ arm is smaller, as on iCE40. **With DSPs
available — the normal case on this family — the multiplier arm is 1308 LUT
smaller at fan-in 16 and 1476 smaller at 32, and uses 745 fewer flip-flops.**

## The exchange rate, which is the honest way to state it

The φ arm does not save area on this family. It **trades**: it spends LUTs and
flip-flops to avoid three DSP48 blocks.

| N | LUT cost | DSP freed | LUT per DSP |
|---:|---:|---:|---:|
| 16 | 1308 | 3 | **436** |
| 32 | 1476 | 3 | **492** |

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
multiplier built from logic — 5133 against 5607 at N=16, 9270 against 9579 at
N=32. On a device with no DSPs, or one where they are spent, that is the whole
product.

**Also stands**: exactness. The lattice accumulates without rounding, which is a
property no LUT count reflects and which this comparison does not measure.

## Method note

The memory inferred as `RAM32M` — distributed LUT RAM — rather than block RAM,
because 16 rows is small enough that yosys prefers it. Both arms are affected
identically, so the comparison is like for like, but the absolute LUT figures
include the operand memory and are not the logic alone.
