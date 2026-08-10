# Withdrawal 14: observing four bits pruned 85% of the design

Found by hunting the same class of defect that overturned the silicon table one
iteration earlier -- a shared or asymmetric element in the harness rather than in
the designs.

## The defect

Every scale-applier measurement wrapped the design in an LFSR harness ending in
`assign led = out[3:0] ^ ...`. Synthesis correctly removes any logic that does
not feed an output. A design with two 32-bit outputs, observed four bits at a
time, loses most of itself:

| `phi_step`, 32-bit datapath | LUT | Fmax |
|---|---:|---:|
| observing 4 bits of each output | 91 | 410.51 |
| observing all 32 | **243** | **243.78** |
| harness alone | 64 | 907.44 |

**27 LUT of real logic survived where 179 should have.** And the effect is
unequal: `apot_requant` emits two 6-bit fields, so observing four bits of each
pruned it barely at all. The comparison was between a design cut to 15% of itself
and one left nearly whole.

## Re-measured, full observation on both sides

All outputs folded into one 32-bit register, that register observed, median of
three seeds:

| design | LUT | net of harness | Fmax median | MHz/LUT |
|---|---:|---:|---:|---:|
| harness | 68 | — | 905.80 | — |
| `phi_step` | 243 | 175 | **228.78** | 0.941 |
| `apot_requant` | 213 | **145** | 91.25 | 0.428 |
| `zphi_add` | 212 | **144** | **231.00** | 1.090 |
| `lns32_t4096` | 645 | 577 | 80.35 | 0.125 |

## What moves

**Withdrawal 12's area claim is wrong.** It reported `phi_step` at 91 LUT against
`apot_requant` at 213 and concluded a 2.34x area win. With both fully observed,
`phi_step` is **larger**: 175 against 145 net of harness. The area claim is
withdrawn.

**The conclusion survives on the other axis.** `phi_step` runs at 228.78 MHz
against 91.25 -- **2.51x** -- so on throughput per area it leads by **2.2x**. The
mesh-case result stands, for a different reason than was given.

**The LNS comparison survives with a corrected magnitude.** `zphi_add` against
`lns32`: 144 against 577 LUT net and 231.00 against 80.35 MHz, so **4.0x on area
and 2.9x on frequency, 11.5x on throughput per area** -- against the 14x claimed
from the partially-observed run. Same conclusion, smaller number.

## Theorem

**T (partial observation is an unequal pruner).** Synthesis removes logic not
reaching an observed output. A harness observing a fixed number of output bits
therefore prunes each design in proportion to its output width, favouring designs
whose outputs are narrow. Two designs measured through such a harness are not
comparable unless their output widths match.

**Corollary.** The correct harness folds every output of the design under test
into a single register of fixed width and observes that register, so the pruning
is identical across designs. Measured here: this changed one design by 2.7x in
area and 1.7x in frequency, in opposite directions.

## Method note

This is the second harness confound in two iterations. The first was a shared
component holding the critical path; this is an asymmetric observation window.
Both were invisible in the numbers themselves -- each design synthesised, routed
and reported plausible figures.

**The pattern: a comparison can be wrong in the harness while every measurement
in it is correct.** Nothing about the individual numbers signals it, so the
harness has to be audited separately from the results it produces.
