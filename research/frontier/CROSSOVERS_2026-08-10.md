# Crossovers for all eleven tapers, measured

T8 said a fixed field against a taper needs a crossover, not a verdict. Here are
the crossovers, from measured peaks and measured slopes rather than from the
`2^-es` the specifications quote.

## Measured

TNF's `M_eff` is constant across binades, as the precision law requires: 3.81 at
8 bits, 9.17 at 16, 24.85 at 32, 52.09 at 64.

| taper | peak at \|e\|=1 | slope / binade | TNF, same width | **crossover** |
|---|---:|---:|---:|---:|
| posit8 | 4.08 | 0.802 | 3.81 | **1 binade** |
| posit16 | 10.93 | 0.261 | 9.17 | **8** |
| posit32 | 27.26 | 0.260 | 24.85 | **10** |
| posit64 | 58.19 | **0.115** | 52.09 | **54** |
| takum8 | 1.87 | 0.329 | 3.81 | **−5** (TNF everywhere) |
| takum16 | 10.11 | 0.241 | 9.17 | **5** |
| takum32 | 26.13 | 0.223 | 24.85 | **7** |
| takum64 | 58.05 | 0.229 | 52.09 | **27** |
| tekum8 | 2.00 | 0.368 | 3.81 | **−4** (TNF everywhere) |
| tekum16 | 10.08 | 0.255 | 9.17 | **5** |
| tekum32 | 26.21 | 0.246 | 24.85 | **7** |

`posit64`'s slope is less than half the others', so it holds precision to 54
binades. `takum8` and `tekum8` peak *below* TNF8 and never lead at all.

## Against the workload we measured

From real SmolLM2 weights: within-block span **3.04** binades at the 99th
percentile, full weight span **13.4**, accumulator at fan-in 512 up to **13.9**.

| object being quantised | span | winner |
|---|---:|---|
| an element inside a block | 3.04 | **taper**, at every width except 8 |
| a whole weight | 13.4 | **TNF** at 16 and 32, **taper** at 64 |
| the accumulator | 13.9 | **TNF** at 16 and 32, **taper** at 64 |

**The answer depends on what is being quantised, and both answers occur in the
same network.**

## Theorem

**T9 (a crossover is a statement about the workload).** For a taper with peak `p`
and slope `s` against a fixed field of constant `m`, the crossover is
`x = (p−m)/s + 1`, and the taper is preferable exactly when the workload's span
is narrower than `x`. A verdict of the form "fixed beats tapered" is therefore an
assertion about the **workload**, not about the formats, and it is true precisely
for workloads wider than `x` binades.

Measured `x` runs from **−5 to 54** across eleven tapers in one catalogue, so the
claim changes sign within a single family as the width changes.

## What this does to the frontier claim

The 28-format frontier is now fully partitioned:

- **14 fixed formats**: compared soundly, domain-independent, unchanged.
- **11 tapers**: each replaced by a crossover and a workload condition. No
  domination claim survives as stated; each becomes a statement with a named
  threshold.

That is more information than the original claim carried, and unlike it, a reader
cannot reverse it by choosing where to measure.

## What it costs us

Our own headline is narrowed. "TNF dominates every catalogued format" becomes
"TNF is preferable for workloads spanning more than 5 to 10 binades at 16 and 32
bits, and posit64 is preferable below 54 binades at 64." For quantising an
element inside an MX-style block -- a 3-binade span -- **a taper is the better
choice at every width above 8 bits**, and we say so.
