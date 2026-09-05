# Trinity FPGA Compute-HW: arXiv v2 Comparison Data

**For inclusion in GoldenFloat paper v2 (arXiv:2606.05017)**
**Date: 2026-07-12 | Status: [verified SW-synth]**

## 1. Parametric Core LUT/FF/DSP Comparison

| Core | v1 LUTs | v2 LUTs | FFs | DSP48E1 | Algorithm | Cycles |
|------|---------|---------|-----|---------|-----------|--------|
| gf_adder_param | 410 | — | 16 | 0 | RNE add/sub + normalize | 1 |
| gf_mul_param | 321 | — | 17 | 0 | behavioral * + RNE | 1 |
| gf_div_param | 210 | — | 124 | 0 | iterative shift-subtract | MANT+1 |
| gf_sqrt_param v1 | **4467** | — | 85 | 0 | NR with behavioral / | 4 |
| gf_sqrt_param v2 | — | **131** | 59 | **8** | reciprocal sqrt NR (no /) | 3 |
| gf_quire_param | 75 | — | 69 | 0 | binary64 accumulator | 1 |

**Key result: SQRT v2 achieves 34× LUT reduction** (4467→131) by replacing
behavioral division with reciprocal-sqrt Newton-Raphson using only multiplies.

## 2. Compute Module LUT Comparison (gf16, all ops)

| Operation | LUTs (top) | Notes |
|-----------|-----------|-------|
| add | 132 | baseline |
| mul | 132 | same as add (UART dominates) |
| div | 156 | +18% vs add |
| sqrt v2 | ~135 | comparable to add (UART dominates) |
| quire | ~130 | cheapest (simple accumulator) |
| fma | ~260 | uses both adder + multiplier |
| cmp | 163 | decode-only, no compute core |
| alu | ~200 | runtime-selectable add/mul |

## 3. Format Width vs LUT (ADD operation)

| Width (bits) | Representative Format | LUTs (compute module) |
|-------------|----------------------|----------------------|
| 4 | gf4 | 121 |
| 8 | gf8 | 126 |
| 16 | gf16 / bf16 | 132-135 |
| 24 | fp24 | ~140 |
| 32 | gf32 / fp32_e8m23 | 148-187 |
| 48 | fp48_e10m37 | ~165 |
| 64 | binary64 | ~180 |
| 128 | fp128_e15m112 | ~210 |

**Observation**: LUT count grows ~0.7 LUTs/bit — UART infrastructure dominates
at small widths, decode/quantize datapath dominates at large widths.

## 4. Competitive Positioning

| System | Coverage | Ops | LUTs (per format) | Source |
|--------|---------|-----|-------------------|--------|
| **Trinity** | **434 families** | **10** | 121-210 | This work |
| Takum codec | 1 family | codec only | ~600 | arXiv:2408.10594 |
| SPADE | 3 posits | MAC | ~400 | arXiv:2601.17279 |
| PERCIVAL | 1 (posit32) | full ALU+quire | ~5000 | arXiv:2111.15286 |
| Big-PERCIVAL | 1 (posit64) | full ALU+quire | ~8000 | arXiv:2305.0646 |

**Trinity advantage**: breadth (434 vs 1-3) × depth (10 ops vs 1)
**Trinity limitation**: no Fmax data (yosys only), no silicon verification at scale

## 5. Catalog Statistics for Paper

| Metric | Value |
|--------|-------|
| Total format families | 434 |
| IEEE-like (fpN_eEmM) | 226 |
| Bit-width coverage | 3-128 (100%) |
| Widths with ≥2 E/M variants | 126/126 (100%) |
| Widths with ≥3 E/M variants | 86/126 (68%) |
| Exponent range | E=1..15 (BIAS 0..16383) |
| Total compute workflows | ~3092 |
| Total RTL lines | ~480,000 |
| Parametric compute cores | 5 |
| Operations per format | 10 |
| Conformance vectors | 16,640 |
| yosys PASS rate | 100% |

## 6. Honest Limitations (for paper)

1. All LUT counts from yosys (openXC7), NOT Vivado — no timing/Fmax
2. SQRT v2 uses DSP48E1 blocks (8 per instance) — competes with other DSP users
3. QUIRE is simplified (register-based, not true wide-add with exp alignment)
4. DIV latency = MANT_BITS+1 cycles (multi-cycle, not pipelined)
5. HW verification pending (0/77 decode + 0/25 compute on the FPGA)
6. Golden models use fp32 proxy (not correctly-rounded reference)
