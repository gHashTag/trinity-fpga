# The first real frequency, and what it costs to read it correctly

Every area number in this directory has carried the same disclaimer: *no Fmax,
because no place-and-route is installed*. `nextpnr-xilinx` still is not, and
neither is Vivado. But `nextpnr-ice40` is installable, the RTL is generic, and
a real place-and-route on a real fabric beats no number at all.

**Fabric caveat, first because it bounds everything below.** This is iCE40 HX8K,
not the Artix-7 the rest of this work targets. iCE40 has **no DSP blocks**, so
the multiplier arm is maximally penalised here; on xc7 with DSPs available the
multiplier arm is *smaller* in LUTs (3906 against 4299) and pays three DSP48.

## Measured — nextpnr-ice40, hx8k ct256, fan-in 8, ACC=16

| arm | ICESTORM_LC | SB_IO | Fmax |
|---|---:|---:|---:|
| **φ, Fibonacci step** | **425** | 121 | **144.80 MHz** |
| multiplier | 1098 | 116 | 69.21 MHz |

φ is **2.58× smaller and 2.09× faster on the clock**. That is the structure
showing through: the φ scale's register-to-register path is one adder, the
multiplier's is a multiply.

## The clock is not the throughput

The φ scale takes **k cycles** where the multiplier takes one. Per output
element:

| k | φ cycles | φ ns | multiplier ns | winner |
|---:|---:|---:|---:|---|
| 1 | 2 | 13.8 | 28.9 | φ |
| 2 | 3 | 20.7 | 28.9 | φ |
| 3 | 4 | 27.6 | 28.9 | φ |
| 4 | 5 | 34.5 | 28.9 | multiplier |
| 8 | 9 | 62.2 | 28.9 | multiplier |

**Break-even is k = 3.18.** README.md in this directory states the deployed
scale is `α = mean|W| ≈ 0.02`, and `log_φ 0.02 = −8.13`, so a deployed layer
needs |k| = 8 — well past break-even. **At |k| = 8 the multiplier arm is 2.15×
faster per output element**, despite running at half the clock.

So the honest summary of the φ scale path on a DSP-less fabric is: *2.6× the
area efficiency, 2.1× the clock, and 2.2× LESS throughput at the exponent a
real layer uses.* An unrolled or barrel variant would trade that back at more
area; it is not built.

## Why `ltp` was not used instead

Before the place-and-route worked, `ltp` looked like a substitute for timing.
It is not, and the numbers say so plainly: it reported **213** topological hops
for a one-adder scale path and **20** for a 32×16 multiplier. It counts hops in
netlists whose structure ABC restructures differently per design, so it does not
compare across designs. Neither number was published as depth.

## Why fan-in 8 rather than 16

At N=16 the φ arm needs 217 pins on a 206-pin package and place-and-route stops
with `Unable to find a placement location`. The pair representation carries two
24-bit components where the multiplier carries one, and on a pin-limited part
that is what binds first — the logic fits at 10% utilisation. Both arms are
therefore measured at N=8, where both fit.
