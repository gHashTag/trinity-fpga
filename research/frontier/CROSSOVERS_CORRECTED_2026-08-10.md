# The staircase form decides how a taper must be compared

Applying T18's window standard to all eleven crossovers exposed a pattern, and
the pattern removes the problem for six of them.

## The window dependence splits cleanly by taper form

| taper | crossover, window 1..9 | window 1..20 | spread |
|---|---:|---:|---:|
| posit16 | 8.2 | 7.6 | **1.08x** |
| posit32 | 9.3 | 9.3 | **1.00x** |
| posit64 | 59.6 | 54.9 | **1.09x** |
| posit8 | 1.5 | 2.3 | 1.58x |
| takum16 | 3.8 | 5.3 | 1.41x |
| takum32 | 5.9 | 10.2 | 1.72x |
| takum64 | 27.5 | 38.1 | 1.39x |
| tekum16 | 4.2 | 6.5 | 1.55x |
| tekum32 | 6.0 | 9.6 | 1.60x |

**Every posit is robust. Every takum and tekum is not.** That is not a
coincidence and not noise.

## Why, and the fix

This paper already classifies tapers by staircase form. posit's is
**arithmetic**: it sheds a constant `2^-es` bits per binade, so `M_eff` is linear
in `|e|` and a straight-line fit is the right model. takum's and tekum's is
**geometric**: one bit per *doubling*, so

```
M(e) = p − log2(e)
```

`M_eff` is linear in `log|e|`, not in `|e|`. Fitting a straight line to a
logarithmic curve gives a slope that is entirely a property of the window --
which is exactly what the spread column shows.

**For a geometric taper the crossover has a closed form and needs no window at
all.** Setting `p − log2(x) = m`:

```
x = 2^(p − m)
```

## The corrected table

| taper | form | crossover, binades |
|---|---|---:|
| posit8 | arithmetic | 1.5 -- 2.5 |
| posit16 | arithmetic | **8.5** |
| posit32 | arithmetic | **9.2** |
| posit64 | arithmetic | **54.0** |
| takum16 | geometric | **1.8** (exact) |
| takum32 | geometric | **2.6** (exact) |
| takum64 | geometric | **62.7** (exact) |
| tekum16 | geometric | **2.1** (exact) |
| tekum32 | geometric | **2.4** (exact) |
| takum8, tekum8 | geometric | TNF wins everywhere |

The takum and tekum crossovers move substantially: takum32 from a 5.9--10.2 range
to an exact 2.6, tekum16 from 4.2--6.5 to 2.1. The straight-line fit had been
**overstating** every geometric taper's reach, because a line fitted over a
window under-reports how fast a logarithm falls near the origin.

## Theorem

**T19 (the staircase form decides whether a window is needed).** A crossover
depends on the fitting window if and only if the taper's staircase form is not
arithmetic. An arithmetic taper's `M_eff` is linear in `|e|`, so its slope is
well-defined and no window need be named. A geometric taper's is linear in
`log|e|`, so no line fits it and its "slope" is a property of the window alone.

Measured, exactly as predicted: posit at 1.00x--1.09x across windows, takum and
tekum at 1.39x--1.72x.

**Corollary.** The staircase taxonomy introduced in this work to *describe*
formats also **prescribes how they must be compared**: arithmetic tapers by a
linear crossover, geometric tapers by `2^(p−m)`. A classification that only
labelled would not do this.

## What it costs and what it gains

**Costs:** six crossovers previously reported as ranges were computed by the
wrong model, and the takum and tekum figures in the selection table shift down by
a factor of two to four.

**Gains:** those six are now exact rather than ranges, and the remaining
window-dependence is confined to posit8, whose peak sits within 0.45 bits of
TNF8's so that any slope estimate divides a very small number.
