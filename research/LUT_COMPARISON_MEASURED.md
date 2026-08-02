# HONEST LUT COMPARISON — Measured on Same Toolchain

**Date**: 2026-07-14
**Toolchain**: yosys 0.63, `synth_xilinx -abc9 -nocarry -arch xc7` (identical for all)
**Method**: `yosys -p "read_verilog ...; synth_xilinx -abc9 -nocarry -arch xc7; stat"`
**Status**: [measured CI-synth] — reproducible by anyone with yosys 0.63

## Measured Results

| Module | LUT2 | LUT3 | LUT4 | LUT5 | LUT6 | **Total LUT** | MUXF7 | MUXF8 | FF |
|--------|-----:|-----:|-----:|-----:|-----:|-----------:|------:|------:|---:|
| **GF16 (gf16_add_top.v, OLD)** | 35 | 34 | 27 | 37 | 43 | **176** | 10 | 4 | 47 |
| **GF16 (gf_adder_param.v, CURRENT)** | 83 | 133 | 100 | 83 | 87 | **486** | 10 | 4 | 17 |
| **tekum16 (tekum16_adder.v, STUB)** | 92 | 114 | 119 | 104 | 144 | **573** | 30 | 7 | 17 |
| **takum16** | — | — | — | — | — | **N/A** | — | — | — |

**takum16: RTL adder does not exist in the repository. Only `takum16_decode.v` exists.**

## Key Findings

1. ~~**"118 LUT" (BENCH-005_FINAL.md) is WRONG.**~~ **Withdrawn 2026-08-02 (pass 145) — the cause was the flag, and this document names it in its own header.** The 176 above is reproducible, to the unit, with the flow recorded at the top of this file: `-abc9 -nocarry -arch xc7`. `-nocarry` forbids CARRY4 inference, so the adder's carry chain falls back into LUTs. Re-synthesising the same module *with* carry inference — `synth_xilinx -abc9 -top gf16_add_top -nodsp`, the flow `lut_comparison.md` specifies — returns **118**, also to the unit. Both measurements are right; they answer different questions, and neither makes the other wrong. The last sentence of the original finding guessed "a different yosys version or different flags" and was half correct: same yosys 0.63, different flags. (The observation that `gf16_add_top.json` is missing from the repository stands, and is now recorded in `lut_comparison.md` §1.)

2. **The current parameterized adder (gf_adder_param at GF16) is 486 LUT, not 118.** It's 2.8x larger than the old non-parameterized adder because it includes denormal handling, NaN/Inf logic, and parameterization overhead.

3. **GF16 vs tekum16: ratio is 0.85x, not 4-11x.** The current GF16 adder is only 15% smaller than the tekum16 stub. The "4-11x" claim was based on comparing a historical number (118) against estimates (~480-1350).

4. **tekum16 stub is not bit-exact** (65% conformance, truncation not RNE). A corrected tekum16 with RNE may be larger.

5. **No comparison possible for takum16** — adder RTL doesn't exist.

## Honest Claim (per goldenfloat-positioning.md)

> GF16 (gf_adder_param) and tekum16 occupy **different points on the area-vs-dynamic-range trade-off**:
> - GF16: 486 LUT, 18 decades dynamic range
> - tekum16: 573 LUT, 153 decades dynamic range
> 
> At 16-bit width on openXC7 (yosys -abc9), the GF16 parameterized adder is ~15% smaller
> in LUT count but has ~8.5x narrower dynamic range. Neither format dominates.
> 
> The old GF16 adder (gf16_add_top, now deprecated) was 176 LUT — smaller, but lacked
> denormal handling, NaN/Inf support, and parameterization.

## What Was Wrong

| Claim | Reality |
|-------|---------|
| "GF16 = 118 LUT" | **176 LUT** measured (different yosys/flags in BENCH-005) |
| "tekum16 = ~480 LUT" | **573 LUT** measured (stub, not final RTL) |
| "takum16 = ~1350 LUT" | **N/A** — RTL doesn't exist |
| "4-11x lower LUT" | **0.85x** (GF16 param vs tekum16 stub) |
| "GF16 wins" | **Neither wins** — different trade-off axes |

## Reproducibility

```bash
# Anyone can reproduce these numbers:
yosys -p "read_verilog fpga/openxc7-synth/gf_adder_param.v /tmp/gf16_param_top.v; synth_xilinx -abc9 -nocarry -arch xc7; stat"
yosys -p "read_verilog fpga/openxc7-synth/gf16_add_top.v; synth_xilinx -abc9 -nocarry -arch xc7; stat"
yosys -p "read_verilog fpga/openxc7-synth/tekum16_adder.v; synth_xilinx -abc9 -nocarry -arch xc7; stat"
```

## Updated Reproducibility (Wave 9)

The GF16 wrapper is now committed at `fpga/openxc7-synth/gf16_param_top.v`.

```bash
# Reproducible from clean clone:
yosys -p "read_verilog fpga/openxc7-synth/gf_adder_param.v \
  fpga/openxc7-synth/gf16_param_top.v; \
  synth_xilinx -flatten -abc9 -nocarry -arch xc7; stat"
```

Result (yosys 0.63, macOS arm64): **491 LUT** (86 LUT2 + 143 LUT3 + 96 LUT4 + 78 LUT5 + 88 LUT6).

Note: without `-flatten`, the count is 486. The `-flatten` flag is used in
CI workflows for consistency. Both numbers are reproducible.
