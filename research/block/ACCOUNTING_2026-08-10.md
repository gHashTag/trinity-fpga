# Seven iterations, seven withdrawals: what is left

An accounting rather than a result. Every phi claim about silicon was tested
tonight, mostly by us, and none survived. What survives is stated at the end and
it is smaller and firmer than what we started with.

## The withdrawals, in order

| # | claim | how it fell |
|---|---|---|
| 1 | `phi^k` is the right grid for a multiplier-free scale | APoT-2 costs 0.1651% excess against our 2.4420%, in one cycle against `k`. Wrong baseline: `2^k` is not what the field deploys |
| 2 | `dot_exact` gives phi an advantage | An APoT scale is a dyadic rational, and `Z[1/2]` is also a closed ring. Ordinary fixed point has been exact since fixed point existed |
| 3 | `phi^k` wins on area, 2.22x | Measured with a five-bit shift field. The workload spans 3.15 octaves, so two bits suffice, and there APoT costs 130 LUT against our 199 |
| 4 | `phi^k` wins with a frozen scale | Frozen shifts are wiring: APoT-2 at 26 LUT against our unrolled 64, 128, 256 for K = 2, 4, 8. Loses at every K |
| 5 | Depth independence is an advantage in networks | Compile-time composition is free for everyone. Three of four depth cases are known after training, so nothing composes in hardware |
| 6 | LNS addition costs 10,967 LUT | That was `takum32_decode`, a format decoder, not an adder. An honest LNS-32 adder with a 4096-entry table costs **275** LUT. Off by two orders of magnitude |
| 7 | The mesh case is where phi finally wins | Matched combinational comparison: APoT requantisation 103 LUT against a Fibonacci step at 128. **Loses by 25%** |

Withdrawal 7 was reached through an unmatched comparison first, which read as
0.60x against us because our side carried a counter and state machine the other
side did not. That was the same defect as the six wins before it, pointed the
other way. **A comparison whose terms differ is wrong whichever direction it
favours, and a loss deserves the same audit as a win.**

## What survives, and it is not nothing

**The mathematics, machine-checked and untouched.** `phi` is the unique `r > 1`
with `r^2 = r + 1`; `Z[phi]` is closed; the gain of `k` layers is
`F_k phi + F_(k-1)`. Six theorems, `coqc` clean, `coqchk` clean, negative control
run. None of this was ever a hardware claim and none of it moved tonight.

**The LNS comparison, which holds after being rebuilt honestly.** At matched
32-bit storage, LNS addition costs **275** LUT against `Z[phi]`'s **32** -- 8.6x,
not the 170x we had wrongly claimed. And there is a structural point stronger
than area: **LNS cannot represent zero**, since `log 0` is undefined, so it needs
a flag and a special path in the adder. A ternary weight alphabet is about
**46% zeros** on real weights. A system whose zero is a special case, applied to
an alphabet whose most frequent symbol is zero.

**The number-axis frontier**, 28 catalogued competitors and none escaping, which
no measurement tonight touched.

**Zero DSP across the stack**, which is a property of ternary weights being
sign-selects, and is not specific to `phi`.

## The honest position

`phi`'s contribution is mathematical, and its practical case rests on the
comparison against LNS -- where it wins on both area and on zero handling -- and
not on the comparison against APoT, where it loses in every regime measured:
frozen scale, runtime scale at the workload's field width, and runtime
composition depth.

That is a narrower claim than we began the night with, and unlike the seven
withdrawn ones it was reached by trying to break it.

## Theorem, stated last because it cost the most to learn

**T (the terms of a comparison are part of its result).** A ratio between two
designs is meaningful only if both were built as their own advocate would build
them. Seven times tonight a ratio changed sign or magnitude when the competitor's
side was rebuilt properly -- baseline, field width, regime, module boundary,
and which artefact was quoted. The measurement was never wrong; the comparison
was.
