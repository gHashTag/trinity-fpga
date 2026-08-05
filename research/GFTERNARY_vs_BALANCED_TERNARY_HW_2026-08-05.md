# Measured on hardware-synth: GFTERNARY {−φ,0,+φ} is NOT balanced-ternary arithmetic

> Supports the honesty note in the GoldenFloat/catalog papers: on FPGA, the
> "GFTERNARY" cell is a GoldenFloat *float multiply*, not a ternary datapath. The
> genuine ternary hardware is TF3 (`trinet_mac32`). Numbers produced 2026-08-05 by
> `yosys synth_xilinx -arch xc7` (openXC7 `regymm/openxc7`), part xc7a200tfbg484-2.

## The two objects

- **TF3 — balanced ternary {−1, 0, +1}** (`fpga/vivado/trinet_mac32_ax7203.v`): a
  32-wide dot product `Σ w[i]·x[i]` computed as `popcount(pos) − popcount(neg)` —
  pure adder-tree, "no multipliers, no DSP" by construction.
- **GFTERNARY — golden ternary {−φ, 0, +φ}** (`fpga/openxc7-synth/corona_compute_gfternary_mul_ax7203.v`):
  the 2-bit code is decoded to **FP32 constants of ±φ** (`0x3FCF1BBD`=+φ,
  `0xBFCF1BBD`=−φ) and fed to a `gf_mul_param` GoldenFloat **float multiplier**.

## Measured resources (yosys synth_xilinx, xc7, DSP inference ON)

| Core | Work | **DSP48E1** | Est. LCs | CARRY4 | LUTs |
|---|---|---|---|---|---|
| **TF3** trinet_mac32 | **32** ternary MACs | **0** | **398** | 24 | 504 |
| **GFTERNARY** corona_gfternary_mul | **1** multiply | **2** | **1191** | 550 | 1552 |

Normalised per operation: TF3 ≈ **12 LCs, 0 DSP** per MAC; GFTERNARY ≈ **1191 LCs,
2 DSP** per multiply — roughly **~96× more LCs per op**, and DSP-dependent where
TF3 uses none.

## Conclusion

The "ternary" label on GFTERNARY hides a floating-point multiplier: yosys infers
**2 DSP48E1** hardware multipliers and 1191 logic cells for a *single* GFTERNARY
multiply, because the design multiplies two FP32 encodings of φ. Balanced ternary
(TF3) does 32 multiply-accumulates in 398 LCs with **zero** DSP. Therefore, as a
*ternary-compute cost* claim, GFTERNARY does not qualify — it is GoldenFloat
arithmetic wearing a 2-bit alphabet. The real ternary silicon result is TF3
(`trinet_mac32`, proven 512/512 on AX7203, 0 DSP).

This is the empirical form of the paper's honesty note (b): keep "1.58-bit / ternary
compute" claims anchored to TF3/BitNet-style adder-tree cores, and describe
GFTERNARY as a golden-ratio *alphabet over a float unit*, not a ternary ALU.
