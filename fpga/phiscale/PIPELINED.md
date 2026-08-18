# The cycles, taken back

`FMAX.md` measured the iterative φ scale honestly and the honest answer was bad:
2.58× smaller and 2.09× faster on the clock, and **2.15× slower per output
element** at the |k| = 8 a deployed layer needs, because it spends k cycles
where the multiplier spends one.

That was a property of the implementation, not of the lattice. Unrolling the
step removes it.

## Why not the closed form

φ^k = F(k−1) + F(k)·φ, so scaling (a, b) by φ^k is

```
a' = a·F(k-1) + b·F(k)
b' = a·F(k)   + b·F(k+1)
```

Two multiplications by Fibonacci constants. A "barrel" built that way puts back
the operator this whole line exists to remove, so it was not built.

## What was built

`scale_phi_pipe.v` unrolls the step into K_MAX pipeline stages. Stage j applies
`(a,b) → (b, a+b)` when `j < k` and passes through otherwise: **one adder and
one mux per stage**, latency K_MAX, throughput one element per cycle, and no
multiplier anywhere.

Verified before measured — 40 elements fed back to back, one per cycle,
against a golden model computed independently:

```
40 checks, 0 errors
one element per cycle, 40 accepted back to back
```

The negative control breaks the adder by one and the bench catches 38 of 40.

## Measured — nextpnr-ice40, hx8k ct256, N=8, ACC=16

| layer | ICESTORM_LC | Fmax | elements/s |
|---|---:|---:|---:|
| **φ pipelined** | **660** | **204.08 MHz** | **204.08 M** |
| multiplier | 1098 | 69.21 MHz | 69.21 M |

**1.66× smaller and 2.95× faster**, on both clock and throughput.

The throughput figure is 2.95× and not 5.90×. The multiplier arm has two cycles
of *latency* and still accepts one element per cycle — `prod` is combinational
from a registered accumulator and nothing gates the input. Counting its latency
as cycles-per-element would have doubled the claim.

## What it costs against the iterative version

| | LC | Fmax | cycles/element |
|---|---:|---:|---:|
| iterative `scale_phi` | 97 | 182.78 MHz | k |
| pipelined `scale_phi_pipe` | 354 | 206.44 MHz | 1 |

3.6× the area of the iterative scale block, for k× the throughput. At the
deployed |k| = 8 that is a good trade; below k = 4 the iterative version is
smaller for the same delivered rate.

## A fold, caught by its own implausibility

The first version of `scale_phi_pipe.v` synthesised to **2 logic cells** for an
eight-stage 16-bit pipeline. The cause was two always blocks driving the same
array — a reset block writing every element and the generate stages writing
their own — so most of the design was pruned. A fold never announces itself; it
reports a number far too small rather than an error, and 2 is what made it
visible.

## What this does not establish

iCE40, not the Artix-7 this work targets, and iCE40 has no DSP blocks, so the
multiplier arm is maximally penalised. N=8 because at 16 the pair output needs
217 pins on a 206-pin package. No board, one output element, no weight or
activation memory.
