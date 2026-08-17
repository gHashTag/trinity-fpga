# The ternary multiplier was functionally wrong, and its testbench printed its own refutation

The ninth pass of the assert-vs-prose sweep reached Verilog. `ternary_mul_top.v`
— the ternary baseline against which GF16's cost is quoted — computes the wrong
product in **4 of its 9 possible inputs**, and the bench that certifies it prints
`ALL TESTS PASSED (8 tests)` on the same run in which it displays results that
contradict the expectations printed beside them.

## The design fault

```verilog
wire a_is_zero = (a_reg == 2'b01);   // correct
wire b_is_zero = (b_reg == 2'b10);   // 2'b10 is +1 on the input side
```

The module uses **two different encodings, and documents both, ten lines apart**:

| | −1 | 0 | +1 |
|---|---|---|---|
| **input**, from the port declarations | `00` | `01` | `10` |
| **output**, from `mul_result` | `01` | `10` | `11` |

`b_is_zero` compared an *input* against the *output* table's code for zero. One
character. Measured exhaustively, all nine pairs, with the two-cycle pipeline the
design actually has:

```
FAIL  -1 * 0 should be 0, got 01 = -1
FAIL  -1 * 1 should be -1, got 10 = 0
FAIL   1 * 0 should be 0, got 11 = 1
FAIL   1 * 1 should be 1, got 10 = 0
ternary_mul_top: 4/9 wrong -- BROKEN
```

`2'b10` → `2'b01` gives **9/9 correct**, reproduced. `ternary_add_top.v` is
correct 9/9 under the same bench; the fault is confined to the multiplier.

## The bench fault, which is the reason it survived

`ternary_ops_tb.v` interpolates `$signed(...)` into a display string and emits
its verdict unconditionally. It compares nothing, so nothing can fail. It also
waits `#20` — one clock — for a design that registers both its input and its
output, so every value it prints is stale. Two faults, one of them a real design
bug, and the bench could not have distinguished them because it could not detect
either.

## The trap that made the first audit report the wrong count

Recorded because it is the same class of error as the bug itself. The first
exhaustive run — mine — decoded the **output with the input table** and reported
**7 of 9** wrong, and then reported that the one-character fix made it **9 of 9**,
i.e. that the fix was a regression. It was the decode that was wrong.

Both encodings are documented in the file. Two independent readers used one of
them for both sides. The fix is the same fix the module needed: **write the table
down at the site where it is used**, which the corrected source now does.

## What this does and does not change

**Does not:** the area. `yosys synth_xilinx -flatten` gives **2 × LUT4** for both
the broken and the fixed multiplier, identical cell counts. The published
comparisons — "GF16 mul is 47× ternary", "GF16 add is 59× ternary" — use that
denominator and it survives the fix. The numbers are not retracted on this
account.

**Does:** what the denominator *means*. Until now it was the area of a circuit
whose correctness had never been established and was in fact false. A cost ratio
against a broken baseline is not a cost ratio. It is now the area of a circuit
that passes an exhaustive test, and the ratio is the same number with a claim
behind it.

## The bench that replaces it

`ternary_mul_exhaustive_tb.v` — all nine pairs, compared rather than displayed,
both decode tables written out, the comparison **count** asserted so an early
loop exit cannot report zero errors over zero comparisons, and `$fatal` on
failure so an exit-code gate reads it correctly.

**Verified in both directions**, which is the only thing that makes it evidence:

| design | result | exit |
|---|---|---:|
| fixed | `9/9 exhaustive, 0 errors -- CORRECT` | 0 |
| broken (`2'b01` → `2'b10` reverted) | `4/9 wrong -- BROKEN` | **1** |

---

*Icarus Verilog 13.0, yosys 0.65, `xc7a200t`. The exhaustive bench and the
synthesis are reproducible from the repository:*

```
iverilog -g2012 -o /tmp/tmt ternary_mul_exhaustive_tb.v ternary_mul_top.v && /tmp/tmt
```
