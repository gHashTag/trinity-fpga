# Independent iverilog witness -- `gf_decode_param.v` Phase A (10 FP32 formats)

**What this is.** A witness No.2 (real Verilog simulator with fixed-width semantics)
for the parametric GoldenFloat decode module `fpga/openxc7-synth/gf_decode_param.v`.
Independent of the author's Python bit-model `rtl_bit_model.py`: the golden oracle
here (`golden_gen.py`) is written from scratch using Python `struct.pack` as the
FP32 reference, and the simulator is **Icarus Verilog 13.0** (not a Python
transcription of the always-block). This is exactly the witness class that catches
fixed-width bugs Python cannot (lesson 28.06: arbitrary-precision ints don't
truncate / have no out-of-bounds read).

**How to reproduce.**
```bash
bash fpga/witness/gf_decode/run_witness.sh   # exit 0 iff all 10 PASS
```
Requires `iverilog`+`vvp` and `python3`. Vectors/TBs/sims are generated under
`fpga/witness/gf_decode/build/` (not committed).

## Result (2026-07-04)

| fmt | vectors | coverage | verdict |
|-----|---------|----------|---------|
| gf4  | 16/16     | exhaustive | PASS |
| gf6  | 64/64     | exhaustive | PASS |
| gf8  | 256/256   | exhaustive | PASS |
| gf10 | 1024/1024 | exhaustive | PASS |
| gf12 | 4096/4096 | exhaustive | PASS |
| gf14 | 16384/16384 | exhaustive | PASS |
| gf16 | 65536/65536 | exhaustive | PASS |
| gf20 | 5055/5055  | representative + gradual-underflow boundary stress | PASS |
| gf24 | 5104/5104  | representative + gradual-underflow boundary stress | PASS |
| gf32 | 5104/5104  | representative + gradual-underflow boundary stress | PASS |

**ALL 10 Phase-A PASS, fails=0.** Coverage: exhaustive for N<=14, representative +
5-class (zero/subnormal/normal/inf/nan) + a sweep + explicit boundary stress around
`true_exp = -126` (the FP32 normal->subnormal transition) for the large formats.
NaN compared as `isNaN` (payload not specified by IEEE-754); all other classes
compared bit-exact.

## Two fixed-width bugs found by this witness (NOT by the Python bit-model)

Both were invisible to `rtl_bit_model.py` because Python ints are arbitrary-precision
and have no out-of-bounds read. Both are fixed in the committed RTL (see comments at
the fix sites).

### Bug #1 -- fixed-width shift truncation (g_widen branch)
`pack_frac` is declared `[M-1:0]` (M bits). The original
```verilog
assign norm_widen_result = { {..{1'b0}}, (pack_frac << (FP32_MANT-M)) };
```
shifted `pack_frac` *inside a self-determined M-bit context*, truncating every bit
that shifted above bit M-1 before the concatenation. Result: `mant23 = 0` for any
`pack_frac != 0`.
- **Witness symptom:** gf16 exhaustive = `1168/65536 bit-exact (fails=64368)` -- only
  zero/inf/nan and `mant_in=0` cases passed.
- **Fix (widen-before-shift):** widen `pack_frac` into `[WIDE:0]` first, then shift.
  Carry stays 0 on the widen path since `M + (FP32_MANT-M) = FP32_MANT <= WIDE`.

### Bug #2 -- out-of-bounds read in the FP32-subnormal packer
`sub_shifted` was declared `wire [M:0]` but read as `[22:0]`:
```verilog
wire [24:0] sub_mant_pre = {2'b0, sub_shifted[22:0]};   // sub_shifted only [M:0]!
```
For M<22 the bits `[22:(M+1)]` are out-of-bounds -> `X`, which propagated through
the round/carry logic whenever the FP32-subnormal packer path is entered
(`true_exp < -126`, i.e. `BIAS_GF > 127`).
- **Witness symptom:** gf24/gf32 emitted `dut=00Xxxxxx` on deep-underflow normals
  (e.g. gf24 `raw=0x004000`, `true_exp=-254`). gf4..gf16 (BIAS<=31) never enter this
  path, which is why they passed exhaustive while gf24/gf32 failed.
- **Fix:** declare `wire [23:0] sub_shifted` (RHS zero-extends; `[22:0]` then reads
  valid zeros).

After both fixes: 10/10 PASS (table above).

## Honesty status (binding)

- This witness proves **decode-law correctness of the Verilog RTL in simulation**
  (sim-witness No.2). It is **not** a hardware measurement.
- HW Tier-E for each format still requires the full 4/4 chain (CI synth GREEN +
  bitstream SHA256 + UART `HW RESULT: N/N bit-exact (fails=0)` @160000 + IDCODE
  `0x13636093`) on AX7203 -- out of scope for this PR (RTL + witness only).
- `gf16` decode (issue #237) = the `#(16,6,9,31)` instance proven here; #237 is
  closed-as-special-case of this parametric generator once the cell is flashed.
- Phase B (gf48/gf64 -> binary64) and Phase C (extended gf96+ -- SW-only, no FP-decode
  on HW) are **not** covered by this witness.
- Representative (not exhaustive) coverage for gf20/gf24/gf32: strong (5 classes +
  boundary stress) but not a total proof for those three; exhaustive is infeasible
  (2^20...2^32). gf4..gf16 are exhaustive.
