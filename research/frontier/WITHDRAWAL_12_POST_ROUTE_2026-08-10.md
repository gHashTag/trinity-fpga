# Withdrawal 12: the instrument limitation was false, and it reverses withdrawal 7

## The method error

From iteration 5 onward this work recorded an instrument limitation: "logic
synthesis LUT counts are not reliable at this granularity, and there is no Fmax
because `nextpnr-xilinx` is not installed on this machine." The second half was
checked by looking at `PATH`.

The repository's own build script `fpga/tnet/mk8.sh` points at
`t27/target/nextpnr-xilinx/build/nextpnr-xilinx`. **The tool is present, version
1743d0f, with the `xc7a200tfbg484` chipdb beside it.** Three iterations of area
arguments rested on an instrument I had documented as unreliable, while the
reliable one sat in the tree unlooked-for.

**Rule: an absent tool is a claim about the machine, and `PATH` is not the
machine. Check the repository's own build scripts before recording a ceiling.**

## What routing changes

Same modules, same harness, one clock, XC7A200T:

| design | yosys LUT | **post-route LUT** | **Fmax** |
|---|---:|---:|---:|
| `phi_step` (Fibonacci step) | 128 | **91** | **411.35 MHz** |
| `apot_requant` (2 priority encoders + subtract) | 103 | **213** | 91.51 MHz |
| `zphi_add` (componentwise) | 64 | **84** | **449.24 MHz** |
| `lns32_t4096` (table + compare + add) | 275 | 293 | 109.61 MHz |

Logic synthesis ranked `apot_requant` below `phi_step`. **Placement and routing
reverses it by 2.34x**, and the frequency gap is larger still: 411 MHz against
91.5, a factor of 4.5. Throughput per area is **10.5x** in our favour where the
synthesis estimate said we lost by 25%.

## Withdrawal 7 is itself withdrawn

Iteration 7 concluded that the mesh case -- runtime composition depth, the last
place a `Z[phi]` depth advantage could live -- was lost, on the strength of
103 LUTs against 128. Post-route the same comparison is 213 against 91.

The conclusion was wrong, and it was wrong for a reason already written down at
the time: the synthesis estimate had been shown non-monotonic and unreliable in
iteration 5, and was used anyway.

## The LNS comparison strengthens

`Z[phi]` addition against an honest LNS-32 adder, post-route: **84 LUT at 449 MHz
against 293 LUT at 110 MHz.** That is 3.5x the area and 4.1x the frequency, so
14x the throughput per area -- against 8.6x on area alone from synthesis. The
structural point stands unchanged: LNS additionally has no representation for
zero, and a ternary alphabet is 46% zeros.

## Theorem

**T (placement is not a scaling of synthesis).** Technology mapping optimises
gate count; placement and routing optimise a physical objective under congestion
and delay. The two orderings are not related by a monotone transform, so a ratio
from logic synthesis cannot be used as an estimate of a post-route ratio, even
for designs of similar size. Measured here: `apot_requant` moves from 0.80x to
2.34x of `phi_step`, a reversal, at a size difference of under 2x.

## Running count

Twelve. This one is different in kind: eleven were claims that measurement broke,
and this is a measurement that a better instrument broke -- in our favour. The
audit that produced it is the same one, applied to the instrument rather than to
the claim.
