# Post-route resolution: three prior disputes, decided on the right instrument

Every area argument from iterations 3 through 11 used logic-synthesis LUT counts,
an instrument this work had itself shown non-monotonic and unreliable. Iteration
12 found `nextpnr-xilinx` present on the machine. Everything is re-measured.

## The measurements

XC7A200T, one harness, one clock, `nextpnr-xilinx` 1743d0f, no DSP.

| applier | LUT | Fmax | MHz/LUT |
|---|---:|---:|---:|
| multiplier, real `alpha` | 440 | 111.66 | 0.254 |
| APoT runtime, 5-bit field | 229 | 143.37 | 0.626 |
| APoT runtime, 2-bit field | 104 | 209.29 | **2.012** |
| **APoT frozen, constant shifts** | **76** | **456.62** | **6.008** |
| **`phi^k` iterative** | 156 | **323.42** | **2.073** |
| `phi^k` unrolled, K=8 | 140 | 110.93 | 0.792 |

## What each prior dispute becomes

**Withdrawal 4 -- frozen scale -- STANDS, and is stronger.** APoT at 6.008
MHz/LUT against unrolled `phi^k` at 0.792: **7.6x**. And a new reason appears
that gate counting could not show: the unrolled recurrence **loses frequency**,
110.93 MHz against the iterative version's 323.42, because eight steps in
sequence make one long carry chain. On area alone the unrolled version looked
10% *better* than the iterative one; on throughput per area it is 2.6x worse.

**Withdrawal 3 -- runtime scale at the field width the workload needs -- SOFTENS
TO A TIE.** APoT at 2.012 MHz/LUT against `phi^k` at 2.073, a difference of
**3.0%**. Synthesis had reported 130 LUT against 199, a 53% loss. Post-route
`phi^k` costs 1.50x the area and delivers 1.55x the frequency, and the two
cancel. Neither wins.

**At a 5-bit field `phi^k` leads by 3.3x**, which is the case originally
measured -- so the original number was right about its own configuration and
wrong as a general claim, exactly as withdrawal 3 said.

**The multiplier stays worst** at 0.254 MHz/LUT, unchanged.

## Theorem

**T (unrolling a recurrence is paid in frequency).** Unrolling `k` steps of a
recurrence into combinational logic removes the control overhead but concatenates
`k` critical paths into one. Measured: `phi^k` at `K=8` occupies 10% less area
than the iterative form and runs 2.92x slower, a net loss in throughput per area.
Gate-level estimation cannot see this -- there, unrolling looked like a win.

**Corollary.** For a recurrence applier there exists an unrolling factor
maximising throughput per area, strictly between fully iterative and fully
unrolled. Neither endpoint is optimal, and both endpoints are what a synthesis
estimate would recommend.

## The corrected rule

Iteration 4 concluded: "`phi^k` where the path is area-bound, APoT where it is
latency-bound." Right in form, wrong in content. Post-route:

| regime | winner | margin |
|---|---|---|
| scale frozen at compile time | **APoT** | 7.6x |
| runtime, narrow field | tie | 3.0% |
| runtime, wide field | **`phi^k`** | 3.3x |

The axis is not area against latency. **It is whether the scale is known before
execution.** Where it is, a constant shift is wiring and nothing competes with
it. Where it is not, the two families are within measurement of each other and
the field width decides.

## Method note

Twelve withdrawals came from auditing claims. This one came from auditing the
*instrument*, and it moved three results at once -- one confirmed, one softened
to a tie, one clarified. The rule that produced it: **an instrument documented as
unreliable must not be used again for the same class of claim; find a better one
or stop making the claim.** It had been documented as unreliable in iteration 5
and used for six more.
