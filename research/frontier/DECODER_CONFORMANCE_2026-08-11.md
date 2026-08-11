# The decoders were priced but never checked, and one of ours decodes a different format

The throughput table prices twenty decoders by area and frequency. Neither says
anything about whether the circuit computes the right value, and a decoder that
is wrong is small for a reason. Every code of every 8- and 16-bit format was
swept through the same RTL that was synthesised and compared against the
format's reference.

| format | codes | mismatches |
|---|---|---|
| binary16 | 65,536 | **0** |
| GFTernary (ours) | 4 | **0** |
| GF10 (ours) | 1,024 | **0** |
| GF14 (ours) | 16,384 | **0** |
| posit16 | 65,536 | 4 |
| fp8 e5m2 | 256 | 6 |
| fp8 e4m3 | 256 | 14 |
| **TNF16 (ours)** | **65,536** | **65,536** |

## Ours first, because that is the one that matters

**Every code of TNF16 disagrees**, and the reason is structural rather than
arithmetic. The RTL and the reference implement different formats:

| | RTL `tnf16_decode` | reference `tnf16_ref` |
|---|---|---|
| sign at bit | 15 | **16** |
| exponent shift | 8 | **9** |
| mantissa bits | 8 | **9** |
| total width | **16** | **17** |

The reference is $1+7+9 = 17$ bits. The RTL squeezed the same format into
sixteen by dropping a mantissa bit. Section~\ref{sec:width} of the paper already
states the fabric width: *a trit stored as a two-bit code makes TNF16 eighteen
bits, and the offset stored as a plain binary integer makes it seventeen*. So
seventeen is the correct width and the sixteen-bit module is the divergence.

**The consequence is that the TNF16 row of the throughput table prices a module
that is not the specified format.** It is one mantissa bit narrower, so its area
is a lower bound on the specified one. This is recorded rather than repaired
because repairing it means re-measuring, and the number is quoted.

## Theirs, stated with the same care

The `fp8` decoders map exponent zero to fp32 exponent zero and place the
mantissa as if normal, so every subnormal decodes to a denormal fp32 instead of
its value: code 1 of e4m3 gives $1.469\times10^{-39}$ where the format says
$0.001953125$. Fourteen of 256 codes for e4m3, six for e5m2 --- exactly the
subnormal range. Nothing in the module says subnormals are out of scope.

`posit16` errs at the extremes: four codes of 65,536, at the smallest positive
value and the two largest magnitudes, each by a factor of four.

**Both make the competitor smaller than a complete implementation would be**, so
the comparison in the table flattered them rather than us. That is worth saying
plainly, and it does not make our own divergence smaller.

## What this changes

Area without conformance is the area of a circuit that may compute the wrong
thing. Four decoders in the table --- three theirs, one ours --- do not implement
their formats completely, and the one that is ours is the one whose every code
is wrong. The check is now a gate: a decoder that enters the table must pass its
reference.

An instrument note belongs here too. The first version of this check reported
`OK: every decoder compared agrees with its reference` while comparing **zero**
codes, because the format objects were looked up under the wrong names. A check
that compared nothing has not found agreement; it has found nothing. Zero
comparisons is now a failure.
