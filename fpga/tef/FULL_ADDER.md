# A full adder, so the cost comparison has two comparable sides

The audit of 2026-08-18 withdrew "GF-T16 at 461 LC beats tekum16's 480–650":
the GF-T side was `gft_add_w.v`, which is **magnitude-only** — no sign, no
subtraction, no rounding, no normalisation beyond one position — set against a
competitor's complete adder. The gap was feature asymmetry.

`tef_add_full.v` is the missing circuit. It does what a float adder does: sign
in and out, effective subtraction when the signs differ, round-to-nearest-even
from guard/round/sticky rather than truncation, full leading-zero normalisation
(a near-equal subtraction cancels down to one bit), and the format's own
overflow row.

## Verified first

3000 random pairs against `conformance/tnf_ref.py`'s **own encode** — not a
golden re-derived by hand:

```
3000 checks, 0 errors
```

Two faults were found on the way there, both in the golden rather than the RTL:

* The first golden divided the mantissa by `2^m + 1` instead of `2^m`.
  `TNFFormat.mant` is the **divisor** (512), not the mask (511). 133 of 3000
  results differed by one unit in the last place, and every one of them was the
  reference being wrong.
* The second saturated overflow to the largest finite value. The oracle writes
  the **Inf row** — `offset = OFFSET_MAX`, mantissa zero — and the RTL now does
  the same.

One real RTL fault was found and fixed: the carry-out shift dropped the bit it
shifted past instead of ORing it into sticky.

## Measured — yosys 0.65, `synth_xilinx -family xc7 -nodsp`, last stat block

| circuit | LUT | CARRY4 |
|---|---:|---:|
| `tef_add_w` — magnitude only | 97 | 8 |
| **`tef_add_full`** — sign, subtract, round, normalise | **440** | 48 |
| `tekum16_adder` — full | 1182 | 211 |

**Like for like the advantage is 2.7×, not the 12.2× the magnitude-only circuit
appeared to give.** It is a real advantage: a fixed-field format does not pay for
regime decode, variable extraction, or barrel alignment.

Rounding, subtraction and normalisation cost **343 LUT** — 4.5× the
magnitude-only circuit. That is the price of being an adder rather than an
accumulator of positives, and it was missing from every previous cost claim in
this project.

## What this does not establish

`tekum16_adder.v` implements the **linear structural model** in
`conformance/tekum_ref.py`, not tekum as published: all 65,536 codes decode
identically to `takum_ref`, and the balanced-ternary exponent is flagged
`# TODO: verify from full paper`. The real takum is logarithmic. So this is a
fixed-field adder against a tapered-field adder, both binary, and it bears on
neither published format.

Post-synthesis cell counts, `-family xc7`, no place-and-route, no board.

## Chained, 2026-08-18

`tef_add_full_chain_tb.v` feeds the adder's output back as its next operand —
40 chains of 32 terms, expected finals from `tnf_ref`'s own encode:

```
40 chains of 32 terms, 0 errors
```

So the accumulation measurements (`arithmetic_across_rungs.py`,
`true_width_ladder.py`) model exactly what this hardware does, step for step.
Chains avoid the zero and Inf rows mid-stream, which the adder does not define;
vector generation regenerates any chain that would touch them and says so.

## At true width, 2026-08-18

`tnf_ref.TRUE_LADDER` now names rungs that are exactly their stored width. The
full adder verified at each (1500 oracle-encode vectors, 0 errors, both splits):

| adder | stored bits | LUT | CARRY4 |
|---|---:|---:|---:|
| `tef_add_full` at TNF(4,8) | **16** | **397** | 45 |
| `tef_add_full` at TNF(4,9) | 17 | 440 | 48 |
| `tef_add_full` at TNF(4,24) | 32 | 1226 | 106 |
| `tekum16_adder` (linear takum model) | 16 | 1182 | 211 |

The 16-bit row is the first like-for-like pair in this whole line: same stored
width, same feature set (sign, subtract, round, normalise), and equal measured
accuracy (`true_width_ladder.py`: 1.00×). On that pair the fixed-field adder is
**2.98× smaller**. That is the fixed-field claim, finally standing on nothing
but itself.

Caveats that stay attached: the opponent implements the *linear takum model* —
the real takum is logarithmic and the real tekum is base-3, and neither has
adder RTL here. Post-synthesis counts, family-level, no board.
