# A GFTernary product costs 13 cells, not a floating-point multiplier

`corona_compute_gfternary_mul_ax7203.v` computes the product of two 2-bit
GFTernary codes by decoding both to fp32, running `gf_mul_param` — a full
IEEE-shaped multiplier, `EXP_BITS(8), MANT_BITS(23)` — and thresholding the
32-bit result back down to 2 bits.

The theorem in `conformance/phi_is_phi.py` says that work is unnecessary: every
digit is `phi * t` with `t` in `{-1, 0, +1}`, so a product is `phi^2 * (t*u)`.
`phi^2` scales the whole result and never interacts with the data, so all that
remains is the sign product of two balanced-ternary digits.

## Measured

Instrument: **Yosys 0.65** (`aec814bdf`). The version is part of the number —
the same script on 0.33 reports different cell counts.

| unit | cells | wires | flops |
|---|---|---|---|
| `gf_mul_param`, free 32-bit inputs | **1654** | 1664 | 17 |
| `gft_mul_exact` (this file) | **13** | 14 | 0 |
| `gft_mul_fp32_path`, 2-bit inputs | 14 | 63 | 2 |

The third row is not a design. It is yosys reaching the theorem's conclusion by
constant propagation: given only four input codes, the multiplier folds away.
That fold is luck, not architecture — the design still *asks* for a general
multiplier to compute a function of four bits, and a tool that does not fold it
pays the first row.

## Equivalent, not merely smaller

`tb_gft_mul_exact_equiv.v` drives all 16 input pairs through the fp32
pipeline's handshake and compares against the combinational unit.

```
16/16 input pairs agree
```

Reproduce:

```
yosys -p "read_verilog gf_mul_param.v; hierarchy -top gf_mul_param; proc; opt; fsm; opt; memory; opt; techmap; opt; flatten; opt; abc -g simple; opt; stat"
yosys -p "read_verilog gft_mul_exact.v; hierarchy -top gft_mul_exact; proc; opt; fsm; opt; memory; opt; techmap; opt; flatten; opt; abc -g simple; opt; stat"
iverilog -g2012 -o tb.vvp gf_mul_param.v gft_mul_fp32_path.v gft_mul_exact.v tb_gft_mul_exact_equiv.v && ./tb.vvp
```

`-g2012` is required: `gf_mul_param.v` drives an output from a continuous
assignment, which plain Verilog-2005 rejects.

## What this does not claim

No frequency. No board. No power. The flop count is zero because the unit is
combinational — that is a property of this unit, not a speed claim.

It also does not claim `phi` is a bad choice everywhere. It says that in a
*digit alphabet* `phi` is a scale factor, so paying a multiplier for it buys
nothing. Where `phi` sits in the positional weights — Stakhov, *The Computer
Journal* 45(2):221-236, 2002, doi:10.1093/comjnl/45.2.221 — it does carry
information and cannot be factored out.

## An anomaly found on the way

The quantiser in `corona_compute_gfternary_mul_ax7203.v` is **not** the sign
rule `conformance/gfternary_ref.py` documents. Read from the RTL:

* positive result -> code 1 when `>= 0x3E800000` (+0.25)
* negative result -> code 2 when magnitude `>= 0xBF000000` (0.5)

So `+0.3` becomes non-zero and `-0.3` becomes zero: an asymmetric dead zone.
The oracle says "any positive -> +phi". The two agree on every *reachable*
input, because products of `{0, +-phi}` are `{0, +-phi^2}` and `phi^2 = 2.618`
clears both thresholds — which is why no test caught it. Widen the input set
(accumulate before quantising, add a scale) and the oracle stops describing the
hardware.
