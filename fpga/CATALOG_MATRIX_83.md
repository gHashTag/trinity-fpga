# Catalog matrix: 83 formats × {SW-conformance / FPGA port}

> Starter map for the "flash the full catalog" focused session on AX7203 (XC7A200T).
> SW-conformance statuses are from `gHashTag/t27` SSOT (master HEAD `92f3506`,
> INDEX_all_formats.json). [verified HEAD 2026-06-28]

## Summary (SW-conformance, t27 master 92f3506)
- **83** formats (total_formats, INDEX_all_formats.json)
- **62** strict SW-bitexact packs (independent decoder, abs_error=0)
- **6** bitexact_selfconsistent packs (single decode law, NO independent 2nd witness — weaker tier, NOT counted as strict bitexact)
- **15** structural packs
- **14** P0 (Corona RTL ready + bit-exact) — fast port
- **47** P1 (bit-exact, RTL to write) — medium cost
- **22** P2 (structural / parametric, need bit-exact generator) — backlog

> **Recent t27 promotions (2026-06-28):** PR #1221 (+gf10, decimal32/64/128,
> double_double, quad_double; 55->61) and PR #1222 (+takum8 via independent
> log-decoder vs libtakum; 61->62) MERGED. takum16/32/64 honestly stay structural
> (no external libtakum oracle = no 2nd witness). takum defining cite =
> arXiv:2404.18603 (CoNGA 2024), NOT 2412.20273.

## HW progress to global goal [verified 2026-06-28]
- **SW-bitexact: 62/83** (t27 master, above).
- **decode-HW: 0/83** — design ready on trinity-fpga main (#208 `corona_decode_top_ax7203.v`, CFGMCLK, 5 Corona decoders) + 2-oracle SW cross-check (Python golden == Corona RTL, fp8_e4m3_fnuz + posit8: 512/0) [verified SW]. NOT run on AX7203 yet. `encoding != compute != FPGA`.
- **compute-HW: 0/83** — ADD (`gf_adder_param.v`) + MUL (`gf_mul_param.v`) cores on main, GF6-GF20 verified by 2 independent SW oracles. NOT run on AX7203 yet.
- decode-HW / compute-HW cells close ONLY after a real synth+flash+UART run on the board — **[REQUIRES USER HARDWARE ACTION]**.

## P0 — Corona RTL ready + bit-exact (14) — FAST PORT
| Format | SW | n_vec | Corona RTL | FV | FPGA |
|--------|-----|-------|------------|-----|------|
| bfloat16 | bit-exact | 0 | ✅ bf16_decode.v | ✅ | ☐ |
| fp4_e2m1 | bit-exact | 16 | ✅ fp4_decode.v | ✅ | ☐ |
| fp6_e2m3 | bit-exact | 64 | ✅ fp6_e2m3_decode.v | ✅ | ☐ |
| fp6_e3m2 | bit-exact | 64 | ✅ fp6_e3m2_decode.v | ✅ | ☐ |
| fp8_e4m3 | bit-exact | 0 | ✅ fp8_e4m3_fnuz_decode.v | ✅ | ☐ |
| fp8_e5m2 | bit-exact | 0 | ✅ fp8_e5m2_decode.v | ✅ | ☐ |
| int4 | bit-exact | 16 | ✅ int4_decode.v | ✅ | ☐ |
| int8 | bit-exact | 256 | ✅ int8_decode.v | ✅ | ☐ |
| lns8 | bit-exact | 256 | ✅ lns8_decode.v | ✅ | ☐ |
| mxfp4 | bit-exact | 0 | ✅ fp4_decode.v | ✅ | ☐ |
| mxfp8 | bit-exact | 256 | ✅ mxfp8_e4m3_decode.v | ✅ | ☐ |
| nf4 | bit-exact | 16 | ✅ nf4_decode.v | ✅ | ☐ |
| posit8 | bit-exact | 256 | ✅ posit8_decode.v | ✅ | ☐ |
| tf32 | bit-exact | 8 | ✅ tf32_decode.v | ✅ | ☐ |

## Achieved on AX7203 [verified 2026-06-27]
| Format | SW | FPGA encoding | FPGA ADD compute |
|--------|-----|---------------|------------------|
| gf4 | bit-exact | ✅ 6/6 | ☐ (HW exhaustive pending — re-verify after ADD fix) |
| gf8 | bit-exact | ✅ 7/7 | ☐ (HW exhaustive pending — re-verify after ADD fix) |
| gf12 | bit-exact | ✅ 7/7 | ☐ (SW exhaustive done; HW pending) |
| gf16 | bit-exact | ✅ 10/10 | ☐ (HW pending) |

> Note: earlier "GF4/GF8 ADD 256/256, 65536/65536 exhaustive [proven] on HW" was **not backed by an artifact** and is re-classified as **[needs confirmation]** until re-run on hardware against the now-fixed `gf_adder_param.v`. SW-level proof is below.

## Infrastructure (fully debugged)
- UART: CP2102N `/dev/cu.usbserial-120`, TX=N15, RX=P20, CFGMCLK ≈70 MHz
- CI: seed-search 1..16 + routing-guard, NO --force
- Conveyor: parameterized `gf_conformance_ax7203.py` + identity-echo bitstream
- ALU cores (on `main`): `gf_adder_param.v` (ADD), `gf_mul_param.v` (MUL) — parametric, RNE+GRS, denormal I/O
- **CI debt (P0, pre-existing, not a regression)**: `main` is UNSTABLE because the "Build & Test" workflow expects a root `build.zig` that was intentionally removed (CLAUDE.md) + several stub jobs (Brain Health, VIBEE Codegen, etc.) fail. None compile the Verilog/Python under test. Relevant checks are green: Code Format, Regression Tests, Sacred Constants, φ²+φ⁻²=3, GitGuardian. Fixing the `build.zig` workflow = P0 next.

## ADD compute primitive — `gf_adder_param.v` (on `main`)
- **Subtraction→subnormal bug [proven, fixed]**: subtraction yielding a subnormal result was flushed to ±0 or packed with wrong mantissa magnitude. Fix: stop normalize at `ew==0` (no over-shift) + sticky right-shift to align with the `ew==0` denormal pack. Addition untouched. Commit `fe2deaad3`.
- **Overflow + zero-sign fix [proven, fixed]**: family-split via `HAS_INF` parameter — GF16 (HAS_INF=1): overflow→Inf `{sg,all-ones-exp,0}` (`gf16.t27:249`, `:19` SPECIAL_EXP); GF6/8/12/20 (HAS_INF=0): overflow→max-finite (`gf8.t27` has no Inf/NaN). IEEE zero-sign: `(−0)+(−0)=−0`, else `+0`; cancellation→`+0`. Commit `c0d24cac2`.
- **Rounding = RNE+GRS** [verified from spec `gf16.t27:219` "Round-to-nearest, ties to even"]. The old "truncation" comment in the RTL was stale and corrected.
- **compute-SW ADD [verified, 2 independent oracles]**: GF6 (×2) / GF8 / GF12 **exhaustive** (4096 / 65536 / 16 777 216 pairs = 0 mismatches); GF16 (HAS_INF=1) / GF20 **representative** 1M random = 0. Oracles: (1) Python Fraction+RNE; (2) iverilog from-spec integer-reference (`formal/gf_adder_ref_tb.v`).
- **Q1 resolved [verified from spec]**: canonical GF16 adder = `gf_adder_param.v` (RNE+denormal-result). `gf16_adder.v` (15-bit 1S+6E+8M, FTZ, truncation) is a non-conformant bring-up adder; its "6/6" does not count for compute-conformance.
- **GF24 ADD not covered**: integer-scaling reference needs ~525-bit (impractical). Needs a different reference approach (exponent-alignment + sticky). GF4 (BIAS=0) needs a reference branch (no denormals → bug N/A). These are reference-model limits, not DUT bugs.

## MUL compute primitive — `gf_mul_param.v` (on `main`, PR #197 `fbb1019e2`)
- Behavioral parametric core, mirror of `gf_adder_param.v` (RNE+GRS, denormal I/O, HAS_INF family-split overflow, IEEE zero/Inf/NaN, gradual-underflow single-rounding). The old `gf16_mul.v` was broken (did not compile: `in_ready` wire+procedural; DSP48E1 OPMODE=0) — replaced by the clean parametric core.
- **Rounding-carry bug [proven, found+fixed]** (`59acaad`): `mant_rnd` `[MANT_BITS:0]` (MANT+1 bits) wrapped to 0 on carry-out, so the `> {1,all-ones}` check never fired and `exp++` was lost — 1376/65536 GF8 pairs. **Caught by independent iverilog from-spec oracle #2** (`formal/gf_mul_ref_tb.v`); the Python transcription missed it (native-int is wider than the RTL's fixed-width reg). Fix: widen `mant_rnd` → `[MANT_BITS+1:0]`.
- **Method lesson**: an RTL transcription using native-width ints HIDES fixed-width-wrap bugs → `reg_mask()` is mandatory; a from-spec reference (different implementation) catches them. This is why two DIFFERENT oracles matter.
- **compute-SW MUL [verified, 2 oracles]**: GF6/GF8 exhaustive + GF12/GF16/GF20 representative (300k) = 0 mismatches (Python faithful + reg_mask; iverilog from-spec).
- **`gf_mul_dsp_param.v` (DSP48E1 wrapper) — [NEEDS ACTION]**: rounding-carry fix applied, but UNISIM does not simulate without Vivado → behavioral↔DSP equivalence = Vivado xsim co-sim + run on AX7203. **compute-HW MUL = 0/83.**

## Totals
- **compute-SW [verified]**: ADD + MUL (`gf_adder_param.v` + `gf_mul_param.v`) — GF6–GF20, each verified by two independent oracles.
- **compute-HW (ADD+MUL) = 0/83** — needs AX7203 (DSP co-sim + flash + UART exhaustive, §2 user step).
