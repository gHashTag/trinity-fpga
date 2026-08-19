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

## What this does not establish

tekum is designed for a *ternary* fabric, where trit extraction is wiring the
same way TNF's fields are wiring here. This measures the cost of running it on
the fabric we have, which is the only fabric anyone has. Decode only — no
adder, no encode path. Post-synthesis, family-level, no board.
