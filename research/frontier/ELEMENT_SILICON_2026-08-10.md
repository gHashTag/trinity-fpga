# The six-bit ladder in silicon: +37% area takes 70% error to 3.7%

The one-adder family was measured on networks and in silicon separately -- the
scale STEP on the fabric, the ladder on perplexity. This closes the loop by
measuring what the element form actually costs.

## The asymmetry that decides the implementation

Applying a ladder weight `r^-j` costs `j` steps of the companion map. As a
**block scale** that is one value per thirty-two weights and the steps amortise;
as an **element** it is paid per weight, and a six-bit ladder needs `j` up to
31. So the element form is not an iteration but a coordinate table: the code
selects a vector in `Z[r]` directly.

That distinction was nearly missed. A ladder's cost is not a property of the
ladder; it is a property of the ladder **in a role**.

## Measured

Coordinate-table decoders, isolated, every output bit folded into the observed
reduction, median of five placement seeds, xc7a200t. Perplexity from the element
sweep on SmolLM2-135M, fp32 baseline 14.3607.

| decoder | table | LUT | Fmax (MHz) | ppl | above fp32 |
|---|---|---|---|---|---|
| `phi`, 4-bit | 7 x 2 x 5b | **89** | 621.89 | 24.4280 | +70.1% |
| `r^5=r^3+1`, 5-bit | 15 x 5 x 4b | 95 | 482.39 | 15.9242 | +10.9% |
| **`r^6=r+1`, 6-bit** | 31 x 6 x 5b | **122** | 612.00 | **14.8882** | **+3.7%** |

**Thirty-three more LUTs -- 37% -- move the error from 70% to 3.7%, at no cost
in frequency.** Applying the scale remains one addition and the datapath remains
free of DSP.

The middle rung is the interesting one for a budget: five bits and 95 LUT for
+10.9%, a 6 LUT premium over `phi` for a sixfold reduction in error.

## What this completes

The chain is now measured end to end at every link:

* **Theorem.** `r^d = r + 1` has two non-zero coefficients at every degree, so
  its companion map is one addition and `d` registers.
* **Fabric.** The scale step: `phi` 149 LUT / 307.69 MHz, `r^8` 225 / 815.66 --
  fineness costs registers, not adders or frequency.
* **Element.** The coordinate table: 89, 95, 122 LUT at four, five and six bits.
* **Network.** 24.43, 15.92, 14.89 perplexity, the optimal degree rising with
  the budget exactly as the ladder law requires.

Nothing in the chain is asserted; each link has its own measurement and its own
harness, and the harnesses are the ones the rest of this work used.
