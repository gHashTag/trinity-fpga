# The first tekum hardware, and what base 3 costs in a binary fabric

`tekum8_decode.v` is the first RTL in this repository that implements tekum as
published (arXiv:2512.10964, via `conformance/tekum_true_ref.py`): the anchor
subtraction, canonical balanced-trit extraction (eight compare-subtract
stages), the regime-dependent variable fields, and the base-3 significand
scaling ladder.

**Scope was a decision, not a shortfall.** The decoder is where everything
tekum-specific lives, and it is small enough to verify exhaustively. An adder
would bolt ordinary float machinery onto these outputs; shipping one without
exhaustive verification is how wrong numbers happened here before.

## Verified

All **6558 finite tekum8 codes** against the oracle, plus the three specials:

```
6558 codes checked exhaustively, 0 errors
```

One real bug was found on the way, worth its own line: **a Verilog
concatenation is unsigned, and one unsigned operand makes the whole expression
unsigned.** The sign-extension idiom `{{3{t[1]}}, t}` silently zero-extended
−1 to 3 inside the regime sum, and 9+9+1 read back as −13. Caught by the
exhaustive bench on code −3278; all thirteen sign-extension sites are now
wrapped in `$signed`.

## Measured — yosys 0.65, `synth_xilinx -family xc7 -nodsp`, last stat block

| decoder | LUT | CARRY4 |
|---|---:|---:|
| `tekum8_decode` — anchor, trits, tapered fields, base-3 ladder | **542** | 96 |
| `tnf10_decode` — TNF(2,3): field slice + one subtract | **1** | 1 |

The entry cost of tekum's encoding in a binary fabric is ~542 LUT **per operand
decode** — more than TNF's entire full adder (397 LUT, sign/subtract/round/
normalise, `fpga/tef/FULL_ADDER.md`). A tekum adder needs two of these before
its arithmetic begins.

## The adder — `tekum8_add.v`, verified on 3,600 oracle vectors, 0 errors

`tekum8_encode.v` closes the codec (round-trip on all 6,558 codes, 0 errors),
and `tekum8_add.v` is the full datapath: two decodes, exact alignment at scale
$3^{13}$, window normalisation, round-to-nearest, re-encode. The bench is
2,600 random pairs, 1,000 cancellation-edge pairs and saturation cases,
checked against `tekum_true_ref` encode-of-exact-sum; mutation controls
(inverted tie-break: 35 errors; `<=` in the candidate compare: 22 errors)
confirm the bench sees single-line defects.

Two findings from the debug are worth more than the module:

**Ties exist — exactly at window boundaries.** Inside one window the grid step
is odd and twice the numerator is even, so a tie is impossible. Across a
boundary the step changes by 3× and the gap between the last code below and
the first code above has a representable midpoint: `3213 + (−3215)` lands on
one exactly. The oracle's nearest-code search resolves ties toward the larger
value, so the RTL must compare both boundary candidates by exact integer
distance and break ties the same way. And at $|e| \ge 123$ (regime $p = 0$,
`fmax = 0`) the window's *single* code is both edge codes at once — the
cross-boundary direction must be taken from the sign of the residual, not from
the sign of F.

**The far threshold is provably $d \ge 13$.** At $d = 13$ the low operand
(≤ 364 in res units) cannot move the rounding: the distance from the aligned
high operand to any rounding midpoint is a nonzero multiple of $3^{13}$
(parity: $2(hg-243)$ is even, $(2F{+}1)\,3^k$ is odd). The RTL's $d \ge 14$
cutoff is conservative by exactly one and functionally equivalent — measured:
the $d>12$ mutant passes all 3,600 vectors.

### Measured — same flow, `-nodsp`, design-hierarchy totals

| full adder (decode + add + round + encode) | LUT | CARRY4 | DSP |
|---|---:|---:|---:|
| `tekum8_add` — 8 trits, true base-3 | **15,251** | 2,063 | 0 |
| `tef_add_full` @ TNF(4,8) — 16 bits | **397** | 45 | 0 |

38× LUT for the smaller format. With DSP inference on, the tekum adder still
needs 9,956 LUT + 57 DSP48E1 — the $3^k$ alignment and candidate values are
genuine multiplications, where TNF's alignment is a shift. This is a direct
implementation of the spec algorithm, not an optimised design; a table-driven
datapath would shrink it, but every stage it pays for (two trit extractions,
base-3 alignment, an 8-comparator window ladder, cross-boundary rounding) is
work the encoding demands and binary fabric does not discount.

`tekum8_encode.v` alone: 1,006 LUT / 329 CARRY4.

## What this does not establish

tekum is designed for a *ternary* fabric, where trit extraction is wiring the
same way TNF's fields are wiring here. This measures the cost of running it on
the fabric we have, which is the only fabric anyone has.  Post-synthesis, family-level, no board.
