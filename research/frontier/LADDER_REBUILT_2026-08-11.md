# The ladder rebuilt on the low-waste rungs — faster *and* guarded

Last iteration proved a ternary exponent never tiles a binary field and that
$w(k)$ is wildly uneven. This turns that from a diagnosis into a construction
rule, and applies it.

## The rule needs a second constraint

Minimising $w(k)$ alone picks $E_t=5$ at every width — but its span is
$2^{\pm121}$, which does not cover a double-precision class. **The rule is:
choose the $k$ of least $w(k)$ among those whose span $3^k/2$ covers the class.**

| width | now | rebuilt | waste | mantissa cost |
|---|---|---|---|---|
| 17 b (half) | $E_t{=}4$, $M{=}9$ | **$E_t{=}5$, $M{=}8$** | 36.7% → **5.1%** | −1 bit |
| 36 b (single) | $E_t{=}6$, $M{=}25$ | $E_t{=}8$, $M{=}22$ | 28.8% → 19.9% | −3 bits |
| 65 b (double) | $E_t{=}7$, $M{=}52$ | **$E_t{=}8$, $M{=}51$** | 46.6% → **19.9%** | −1 bit |

Two clear wins at one mantissa bit each; the 36-bit case costs three and is left
as a judgement rather than a recommendation.

## The 17-bit rung, generated and swept

Generated from parameters, not hand-edited. Guarded. Exhaustive:
**124,416 of 124,416 in-spec codes exact, all 6,656 out-of-spec flagged, zero
errors.**

| 17-bit rung | $E_t$ | waste | MHz/LUT | guarded |
|---|---|---|---|---|
| TNF16, as built | 4 | 36.7% | 0.1173 | no |
| **TNF17e** | 5 | **5.1%** | **0.1312** | **yes** |

**11.9% faster per LUT while checking its offset field, which the rung it
replaces does not.** Both improvements at once, from choosing $k$ by the
corollary instead of by habit.

## My own generator made the bug I had built a gate for

`tnf64b`'s generated exponent width gave `11'sd3280` — a value needing 13 bits
in an 11-bit literal. **`check_literal_widths.py` did not catch it: it read `'b`
and `'h` and not `'d`.** iverilog printed *"Numeric constant truncated to 11
bits"* and, once again, the warning went to a log.

Extended the gate to decimal (and signed decimal). It immediately found a real
defect elsewhere: `q4_decode.v` had `wire [3:0] exp_r = 4'd123 - {2'b0, lzc}` —
**two defects in one line.** 123 truncates to 11, and the use below reads
`exp_r[7:0]` from a four-bit wire, so the top half of the fp32 exponent was
constant zero. Fixed. It also reports `8'd256` in a bfloat24 FMA outside the
measured path.

**Then the gate flagged my own correction**, because the comment explaining the
fix quotes the defective line. That is the third time in this work a gate has
read a comment as code. Comments are now stripped in both passes, and the gate
is negative-tested by planting `11'sd3280` back.

## Score

Thirteen decoder defects (eight ours, five competitors'). Table: 25 rows, all
conformance-checked, all utilisation-measured.
