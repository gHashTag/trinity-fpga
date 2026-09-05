# Spec: gf16-decode cell (a clean decode-only head-to-head for ARITH)

**Why:** the matched-substrate quartet ([#233](https://github.com/gHashTag/trinity-fpga/issues/233)) currently compares gf16 as an **ADD-compute** (512/512) against posit16/takum16/binary16 as **decode**. This is not apples-to-apples. An ARITH reviewer ([#4](https://github.com/gHashTag/arith2027-goldenfloat/issues/4)) will ask about exactly this. A separate gf16-**decode** cell puts all 4 formats into one operation (decode→FP32).

**Asset status:** the cell does NOT exist. All gf16-RTL is compute (`gf16_add.v`, `gf16_mul.v`, `gf16_alu.v`, `gf16_mac_16.v`). There is no `gf16_decode.v`/`corona_decode_gf16`, no entry in the corona-decode-host FMT-list, no CI-workflow. This is a **fresh design-loop**, not a flash-session.

## Format parameters (from the SSOT `formats_catalog.t27`, [Verified])
- gf16: **bits=16, s=1, e=6, m=9, bias=31** (PHI_BIAS=60), storage=u16, cluster=GoldenFloat.
- FPGA component artifact: 35/35 @ 323 MHz Artix-7 (Zenodo 10.5281/zenodo.19227877).

## RTL-spec (gf16_decode.v: gf16 u16 → binary32)
A combinational decoder, a mirror of the gf16 decode law (the same one the conformance golden-oracle uses):
1. Field parsing: `s = bits[15]`, `e = bits[14:9]` (6 bits), `m = bits[8:0]` (9 bits).
2. Classes (5, as in the §3.5 denormal-methodology): normal / subnormal (e=0) / zero / Inf / NaN (the HAS_INF-semantics of gf16).
3. Normal: `value = (-1)^s * 2^(e-bias) * (1 + m/2^9)`, bias=31 → the exponent range and the mantissa shift into FP32 (8 exp / 23 mantissa), rebias 31→127.
4. Subnormal (e=0, m≠0): `value = (-1)^s * 2^(1-bias) * (m/2^9)` — normalization into FP32 (a leading-zero count over the 9-bit mantissa, exponent correction).
5. Zero/Inf/NaN → the corresponding FP32 patterns.
6. Output: `fp32[31:0]` (IEEE binary32), fully combinationally (or a 1-cycle output register for Fmax).

## What to write (design-loop, NOT in this session)
- [ ] `fpga/openxc7-synth/gf16_decode.v` (~50-100 lines) + an optional output register.
- [ ] Testbench: golden-oracle (Python decode gf16→fp32) == RTL in simulation; the classes normal/subnormal/zero/inf/nan.
- [ ] XDC for AX7203 (clock 200 MHz LVDS R4/T4 → IBUFDS; UART @160000).
- [ ] Add gf16 to the corona-decode-host FMT-list + a fmt-code.
- [ ] CI-workflow (following the corona-decode-* template): synth (openXC7 Yosys+nextpnr) → bitstream artifact.
- [ ] Conformance-vector: a 64-vec (like the quartet) or an exhaustive-subset for apples-to-apples.

## Readiness criteria (Tier-E chain 4/4)
- CI run GREEN URL + bitstream SHA256 + UART `HW RESULT: N/N bit-exact (fails=0)` @160000 + IDCODE live `0x13636093`.
- Result: [measured on FPGA], decode-only.
- Attach to the quartet on [#233](https://github.com/gHashTag/trinity-fpga/issues/233): now all 4 formats in one operation (decode) → the cost-spread is strictly comparable.

## LUT estimate (rough, [simulated])
Decode gf16→fp32 ≈ parsing + LZC(9) + rebias + class multiplexers. A reference from neighboring corona-decode cells: tens–~150 LC (for comparison: binary16-decode=131 LC, posit16-decode=175 LC). The exact number will come from synth.

## Honesty (binding)
- No "first/best". gf16-decode ≠ gf16-compute — these are different cells; tag both honestly.
- Until the cell is flashed on the FPGA — the status is [REQUIRES USER ACTION] (synth+flash is outside the sandbox).
- 1-ULP subnormal residuals (if they appear) = KNOWN_LIMITATION, not a hard-fail.

*The gf16 parameters are cross-checked against the live SSOT 2026-07-04. This is a spec for the next design-loop, not a result of this session.*
