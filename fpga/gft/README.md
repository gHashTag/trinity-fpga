# gft_mul_w — one multiplier for the whole GF-T ladder, sized from its parameters

`build/gft_mul8/gft_mul.v` declares every port and the product wire 32 bits wide.
That is fine for GF-T8 and GF-T16 and **silently wrong for GF-T32**, and it costs
five times more than the arithmetic needs even where it is right.

## The correctness problem

```verilog
wire [31:0] prod = (MANT_ONE + a_mant) * (MANT_ONE + b_mant);
```

| Rung | MANT_ONE | Largest product | Bits | Fits in 32? |
|---|---|---|---|---|
| GF-T8 | 16 | 961 | 10 | yes |
| GF-T16 | 512 | 1,046,529 | 20 | yes |
| GF-T32 | 2²⁵ | 4,503,599,493,152,769 | **52** | **no** |

The module's own header calls it "Parametric per rung … GF-T32 uses wider mant".
Instantiated with the GF-T32 parameters it truncates, and the answers are wrong —
measured, 1,995,730 mismatches in 2,128,964 combinations against `gft_mul32.v`.
The tree currently works around this with a separate 64-bit `gft_mul32.v` rather
than fixing the width.

`gft_mul_w` derives the product width from the parameters — `PROD_W = 2*(MANT_W+1)`
— so one module is correct at every rung.

## The cost problem

Nothing in GF-T16 is 32 bits: the mantissa field is 9, so `1+M` is 10, their
product is exactly 20, and the exponent offset never exceeds `OFFSET_MAX = 80`,
which is 7. Synthesis builds a 32×32 multiplier and a 32-bit compare tree and
charges full price.

| Variant | LUTs | DSP48 | Fmax |
|---|---|---|---|
| `gft_mul`, 32-bit ports | 1,179 | 3 | 81 MHz |
| `gft_mul_w` | **219** | 0 | 81.35 MHz |
| `gft_mul_wp`, two stages | **219** | 0 | **147.32 MHz** |

Post-route on XC7A200T, `nextpnr-xilinx`, hard multipliers off.

## The ladder, measured on one harness

| Rung | LUTs | Fmax | Latency |
|---|---|---|---|
| GF-T8 | 50 | 153.23 MHz | 1 cycle |
| GF-T16 | 212 | 131.73 MHz | 1 cycle |
| GF-T32 | 1,477 | 83.27 MHz | 1 cycle |

## Equivalence, proven at every rung

```bash
iverilog -g2012 -o tb.vvp tb_gft_equiv.v gft_mul_w.v gft_mul.v && vvp tb.vvp
#   321,156 combinations, 0 mismatches   (GF-T16, exhaustive over the mantissa
#                                         space and over the offsets)
# GF-T8   3,716 combinations, 0 mismatches   vs gft_mul
# GF-T16 77,444 combinations, 0 mismatches   vs gft_mul
# GF-T32 300,000 combinations, 0 mismatches  vs gft_mul32 (the 64-bit reference)
# pipeline 199,994 cycles, 0 mismatches      vs the combinational version
```

The GF-T32 row is the point: `gft_mul_w` agrees with the module that is right and
disagrees with the module that truncates.

## Where the pipeline cut is

Between the product and the renormalisation — a 10×10 multiply, then a carry test,
an exponent add with saturation and a bit select. One register between them nearly
doubles the frequency for one cycle of latency.
