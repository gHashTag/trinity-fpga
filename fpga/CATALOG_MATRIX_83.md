# Catalog matrix: 83 formats (snapshot 2026-06-28) × {SW-conformance / FPGA port}

> **Snapshot note (2026-09-05):** this matrix is a snapshot of the catalogue at t27 master `92f3506`, verified 2026-06-28; the count in the file name and every denominator below are that snapshot's, not the current count, and the file keeps its original name.
> The catalogue has since grown: 109 formats in 12 clusters at v3 of arXiv:2606.09686 (Golden Ruler, announced 7 Sep 2026); the statuses below have not been recounted against v3.

> **GF16 robustness: 4/4 ML workloads passed** (matmul, gradient accumulation, dynamic range, attention softmax). GF16 (E=6, M=9) is the minimum-width IEEE-style format achieving full robustness — FP16 fails dynamic range, BF16 fails matmul.

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

## HW progress to global goal [synced to #199 EPIC body, 2026-07-02]
> Live source of truth = #199 EPIC body (top table). The earlier 18/21/39 figures
> below were the 2026-07-01 snapshot; superseded by the counts here.
- **SW-bitexact: 62/83** (t27 master 92f3506). 15 structural remain → 77+ target.
- **decode-HW: 41/83 rigorous Tier-E** (dedicated `### Tier-E proof:` posts; UART @160000 on AX7203, IDCODE `0x13636093`). All 13 `corona_decode_host` formats + Corona-decoded cells now rigorous: bcd, bf16, binary16, binary32, binary64, binary128, bitnet, e8m0, fp4_e2m1, fp6_e2m3, fp6_e3m2, fp8_e5m2, gf10, gf14, ibm_hfp32, ibm_hfp64, int4, int8, int16, int32, lns8, lns16, ms_mbf32, ms_mbf64, mxfp8_e4m3, mxint8, nf4, posit8, posit16, posit32, takum8, tf32, vax_d, vax_f, vax_g + **decimal64** (track-b new-RTL, IEEE 754 BID table+multiply, 2026-07-02 — FIRST new-RTL cell on HW). **Track-b now proven viable on openXC7** (heap+sa routing + -nodsp).
- **compute-HW: 30/83** Tier E — **ADD 10/10 + MUL 10/10 + SUB 10/10**, GF4–GF32 ALL COMPLETE. 2026-07-02 audit: **every cell now individually Tier-E proof-backed** (10 cells that previously lacked individual proofs — gf4/6/8/12/16/20/24-add + gf6/8/20-mul — re-flashed + proofs posted; GF4 bias=0 fix, GF16 NaN-precedence fix, GF32-mul `-nodsp` fix).
  - **`*` DIV / SQRT are NOT bit-exact and NOT counted above.** Every `corona_compute_*_{div,sqrt}_ax7203.v` wrapper is a **binary32 proxy** (decode→binary32→compute→quantize), not native-format arithmetic. `gf_sqrt_param.v` is internally hardcoded to binary32 despite its parameters; both `gf_div_param` and `gf_sqrt_param` carry an NBA stale-output bug (`out_y <= result_packed` reads the prior cycle's value); and no div/sqrt conformance vectors exist. See `research/DIV_SQRT_HONESTY.md`. For the paper, div/sqrt must be described as *"binary32-proxy approximation, not bit-exact"*.
- **Total Tier-E HW (rigorous, §1.1): 71/83** (decode 41 + compute 30; 2026-07-02) — **withdrawn 2026-09-05:** it added decode *formats* to compute *operations* and double-counted gf10 and gf14; the recomputable figure is 72 (format, operation) cells over 49 base formats from `research/measure_tier_e_cells.py` (README §2). **decimal64 + decimal32 + decimal128 + double_double + takum16 + quad_double PROVEN on HW** (6 track-b cells; decimal family 32/64/128 COMPLETE). Remaining: ~10 structural (no decode law — unreachable) + takum32/64 (transcendental exp, research-level). **SW-bitexact = 69/83** (t27 PRs merged).
- **2026-07-02 CLEARED (were FLASH-PENDING):** `vax_g`, `ibm_hfp64`, `binary128`, `ms_mbf64` — flashed + UART 64/64 bit-exact this pass (NOPASSWD `sudo -n openocd` unblocked; runs vax_g 28540940028 / ibm_hfp64 28541409616 / binary128 run 28541409622 / ms_mbf64 28538987924). decode-HW 31→35. **Flash queue DRAINED — every CI-built bitstream now HW-proven.**
- **Remaining catalog formats are NOT cheap-shift clones** (need dedicated conversion blocks or t27 LUT vectors not present locally): decimal32/64/128 (decimal→binary, ~wide datapath), takum16/32/64 (log-domain 2^x; takum8 sidesteps via 256-entry LUT from t27 vectors), double_double / quad_double (multi-component). `INDEX_all_formats.json` (the SSOT index; 83 entries in this snapshot) still not in the local t27 checkout.

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
- **compute-HW (ADD+MUL+SUB) = 21/83** Tier E — ADD 7/7 + MUL 7/7 + SUB 7/7 measured on AX7203 (2026-07-01). Live source of truth = #199 EPIC body.
