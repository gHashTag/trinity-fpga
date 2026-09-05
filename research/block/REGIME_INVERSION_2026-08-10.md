# The area ordering inverts with the regime, and our number was measured in the wrong one

This iteration set out to attack our own area claim at its weakest point. It
succeeded, twice.

## Attack 1: freeze the scale, and the shifts become free

If a layer's scale is fixed after training, APoT's shifts are compile-time
constants, and a constant shift in hardware is wiring. Built and measured:

| regime 1 -- frozen scale, dedicated hardware per layer | LUT |
|---|---:|
| **APoT-2, constant shifts** | **26** |
| `phi^k` unrolled, K=2 | 64 |
| `phi^k` unrolled, K=4 | 128 |
| `phi^k` unrolled, K=8 | 256 |

**APoT wins by 10x at the realistic K = 8, and at every K.** An unrolled
recurrence costs one adder per step, so it is linear in K at about 32 LUTs per
step, while a constant-shift APoT applier is one adder regardless. The lines do
not cross even at K = 1 (32 against 26).

## Attack 2: the barrel only costs what the range demands

Our regime-2 advantage was measured with a 5-bit shift field. The real
requirement is far narrower: across 210 layers the scales span **3.15 octaves**
(`log2 alpha` from -4.21 to -1.06), so the leading term needs a 2-bit field.

| regime 2 -- runtime scale, one engine for all layers | shift field | LUT |
|---|---|---:|
| APoT-2 | SW=5 | 384 |
| APoT-2 | **SW=2** | **130** |
| `phi^k` iterative | KW=5 | 173 |
| `phi^k` iterative | **KW=2** | **199** |

**At the shift width the workload actually requires, APoT wins regime 2 as
well** -- 130 against 199. Our 2.22x advantage was an artefact of giving the
competitor a wider field than it needs.

## Instrument limitation, stated

The APoT sweep is non-monotonic: 130, 380, 230, 384 for SW = 2, 3, 4, 5. The
parameter demonstrably takes effect (port bits 74 vs 80), and yosys is
deterministic, so this is not random noise -- it is `abc` mapping heuristics, and
it means **LUT counts from yosys alone are not a reliable area metric at this
granularity.** Same class as having no Fmax without `nextpnr-xilinx`. A claim
resting on a 30% difference between two of these points would not be safe;
resting on the 10x of regime 1 is.

## Theorems

**T-1 (unrolled recurrence is linear).** A recurrence applier unrolled to depth
`K` over `W`-bit operands costs `Theta(K W)`; an additive-term applier with
compile-time constant shifts costs `Theta(W)` independent of the scale. Hence in
the frozen regime the recurrence loses for every `K >= 1`.

**T-2 (regime inversion).** The ordering between the two families is not a
property of either. It inverts with whether the scale is compile-time constant or
runtime variable, because a constant shift is wiring and a variable shift is a
barrel of `Theta(W log W)`. Neither family is better; the architecture decides.

**T-3 (the barrel is priced by range, not by width).** A runtime shift field need
only span the workload's scale range. Measured here that range is 3.15 octaves,
so the barrel is 2 bits and small. Any area comparison against an additive-term
applier must size its field from the workload, or it is measuring a competitor
that was never going to be built.

## What survives

Not the area advantage. What survives is narrower and still true:

- `phi^k` is the only applier whose area is **independent of composition depth**
  (Theorem on term growth). At `d = 2` APoT-8 costs 1217 LUTs where the pair
  still costs 173. That regime is real but uncommon -- chains without
  requantisation.
- The alphabet uniqueness and `Z[phi]` closure are machine-checked and untouched
  by any of this. They were never area claims.

## Method note

Both attacks were ours. The pattern across the last three iterations is the same
each time: **a favourable number came from a comparison whose terms we chose.**
Powers of two instead of APoT; a 5-bit shift field instead of the 2 bits the
workload needs; a runtime regime instead of the frozen one. The rule that would
have caught all three: *before reporting a ratio, write down what the competitor
would build if it were trying to win, and build that instead of the convenient
version.*
