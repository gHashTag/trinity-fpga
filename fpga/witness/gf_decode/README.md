# gf_decode — a parametric decode for the entire Trinity GF lineup

Sandbox design-time artifact set (2026-07-04). Synthesis/PnR/flashing on AX7203
— always `[REQUIRES USER ACTION]` (there is no iverilog/yosys in the sandbox).
Full spec: `fpga/gf16_decode_cell_TZ.md (issue #237)`.

## Why a single parametric module instead of N separate cores

The unified Trinity φ-rule (verified against the SSOT `formats_catalog.t27`,
master, 2026-07-04 — holds EXACTLY across the entire ladder of 17 GF cells):

```
e = round((N-1) / φ²)
m = N - 1 - e
bias = 2^(e-1) - 1
```

Since the decode law (5 classes: normal / subnormal / zero / Inf / NaN)
is the same for ANY (E, M, BIAS), a single Verilog generator
`gf_decode_param.v #(N, E, M, BIAS)` covers all of Phase A (10 formats) —
instead of rewriting a separate decode core for each format. This is the key
argument for the ARITH reviewer in both papers
([arXiv:2606.05017](https://arxiv.org/abs/2606.05017),
[arXiv:2606.09686](https://arxiv.org/abs/2606.09686)).

**gf16 (issue #237)** — is not a separate entity: it is simply an instance
`#(N=16, E=6, M=9, BIAS=31)` of the same generator. Issue #237 is closed as
a special case; a separate core for gf16 is not needed.

## Files in this folder

| File | Role |
|---|---|
| `gf_decode_ref.py` | Golden oracle: decode/encode on exact `fractions.Fraction` arithmetic, a catalog of all 17 GF cells, verification of the φ-rule against the SSOT |
| `gf_decode_param.v` | Parametric Verilog decode module `#(N,E,M,BIAS,OUT_REG)` → IEEE binary32 — lives at [`fpga/openxc7-synth/gf_decode_param.v`](../../openxc7-synth/gf_decode_param.v), not in this folder |
| `rtl_bit_model.py` | Exact Python bit-model of the `gf_decode_param.v` algorithm (the same integer semantics, field-width masks) — proves golden==RTL WITHOUT hardware |
| `gen_vectors.py` | Generator of check vectors (`vectors/vectors_<name>.txt`) from the golden oracle |
| `tb_gf_decode.v` | Verilog testbench template: reads a vector file, compares the DUT output, prints `HW RESULT: N/N bit-exact (fails=0)` |
| `vectors/` | Generated vector files for all 10 FP32 formats |
| `README.md` | This file |

## Phasing (by decode_target from the SSOT)

### Phase A — FP32 lineup (10 formats) — 10/10 PASS on iverilog-witness №2 (after TWO fixes)

`gf4, gf6, gf8, gf10, gf12, gf14, gf16, gf20, gf24, gf32` → output IEEE
binary32. **10/10 Phase-A PASS confirmed by a real independent
iverilog-witness №2** (the fixed-width semantics of a real simulator), NOT only
by the Python model. Golden Fraction-oracle == Python bit-model == iverilog-RTL.

**The path to green required TWO fixed-width fixes that the Python model
did NOT see** (lesson of 04.07, confirms the lesson of 28.06):

1. **Fix #1 (widen-before-shift, bug #4 below)** — fixes the gf16-class (formats
   outside the FP32-subnormal packer). First run of v1 RTL: gf16 exhaustive
   `HW RESULT: 1168/65536 bit-exact (fails=64368)` — ~98% failure due to
   shift truncation in the M-bit container.
2. **Fix #2 (widen sub_shifted [M:0]→[23:0], bug #5 below)** — the widen-fix
   was NOT sufficient: gf24/gf32 still fell over (`dut=00Xxxxxx`) due to
   an out-of-bounds read of `sub_shifted[22:0]` from a `[M:0]` wire (for gf24
   M=14 → bits 22:15 OOB → X). It triggers ONLY when true_exp < −126
   (deep underflow → FP32-subnormal path), which gf16 (BIAS=31) does not reach —
   therefore gf16 was clean and hid the bug. The Python model has no concept of
   an OOB-read → again did not catch it.

Both fixes are applied in `gf_decode_param.v` (the sandbox version is synchronized with
the user's verified-green RTL). The verified RTL + witness-harness
(`gen_golden.py`, `gen_tb.py`, TBs, iverilog logs) — is in
`/tmp/gf16_witness/` on the user side. **Status: [verified SW] on iverilog**
(fixed-width sim, NOT HW-synthesis/flashing). The decode-HW checkmark (4/4 chain on
AX7203) remains `[REQUIRES USER ACTION]`.

### Phase B — FP64 lineup (gf48, gf64) — NEXT STEP

Same generator, output IEEE binary64 (11 exp bits / 52 mantissa bits).
`gf_decode_ref.py` already contains `gf_decode_to_fp64_bits()` and the parameters
gf48 (E=18,M=29,BIAS=131071) / gf64 (E=24,M=39,BIAS=8388607) in the
`GF_LINEUP` catalog, but the Verilog module for binary64 output, the bit-model, and the vectors for
Phase B were NOT produced in this loop — that is `[NEXT LOOP]`. The mantissa of both
formats (29 and 39 bits) fits into the 52-bit binary64 mantissa without loss,
so the approach (LZC-normalization of subnormals, rebias BIAS→1023) carries over
without fundamental changes.

### Phase C — extended (gf96…gf1024) — SW-only, do NOT promise FP-decode on HW

The mantissa (59…632 bits) does not fit even into binary64 (52 bits). For these 5
formats `gf_decode_ref.py` provides only an exact SW-reference (`decode()` on
`Fraction` works for ANY width — this is already implemented and verified by the
φ-rule). A hardware FP-decode on HW for extended = **[open hypothesis
for HW]**, never to be claimed as implemented. When a real need arises — fixed-point or chunked-limb (double-double-style) decode,
NOT a single FP32/FP64 path.

## golden == RTL verification results (without hardware)

The methodology — following the denormal-loop template
(`(denormal-loop methodology, outside the repo)` §4): (1)
a golden on exact arithmetic, (2) a bit-model of the RTL with field-width masks on
each assignment (the 28.06 lesson on fixed-width bugs is taken into account), (3) exhaustive
for small formats, representative + 5 mandatory classes for the large ones.

| Format | N | BIAS | Coverage | Probes | Fails | Verdict |
|---|---|---|---|---|---|---|
| gf4  | 4  | 0    | exhaustive      | 16/16     | 0 | **PASS** |
| gf6  | 6  | 1    | exhaustive      | 64/64     | 0 | **PASS** |
| gf8  | 8  | 3    | exhaustive      | 256/256   | 0 | **PASS** |
| gf10 | 10 | 3    | exhaustive      | 1024/1024 | 0 | **PASS** |
| gf12 | 12 | 7    | exhaustive      | 4096/4096 | 0 | **PASS** |
| gf14 | 14 | 15   | representative+5cls | 4122/16384 | 0 | **PASS** |
| gf16 | 16 | 31   | representative+5cls | 4122/65536 | 0 | **PASS** |
| gf20 | 20 | 63   | representative+5cls | 4040/1048576 | 0 | **PASS** |
| gf24 | 24 | 255  | representative+5cls (+ full-exponent stress) | 4038 + 9198 | 0 | **PASS** |
| gf32 | 32 | 2047 | representative+5cls (+ full-exponent stress) | 4038 + 73710 | 0 | **PASS** |

**Summary: 10/10 of Phase A PASS golden==RTL [simulated].** Launch:
`python3 rtl_bit_model.py` (exit code 0 = all PASS).

GF4 (bias=0, e1m2) — the degenerate edge is checked SEPARATELY: EXP_MAX=1 is entirely
occupied by Inf/NaN, GF4 has no normal range (only subnormal/zero/Inf/
NaN — experimentally confirmed: the classes that occur among the 16/16 codes =
`{inf, nan, subnormal, zero}`, `normal` is absent, which is expected). The general
parametric decode correctly handles this edge WITHOUT a separate core
(unlike the GF-ADD denormal fix, where arithmetic on bias=0 required
a separate core — decode does not align exponents between operands,
so the degeneracy of GF4 does not create a separate problem for it).

### Bugs found and fixed (during this loop)

1. **The sign of zero was lost in the golden oracle.** `decode()` initially always
   returned `Fraction(0)` without a sign for `exp=0,mant=0`, whereas the RTL
   correctly preserves the sign (`-0`). Fix: a `SignedZero(Fraction)` class with
   a `.sign` attribute, used in the conversion to IEEE bits. Without this
   fix, divergences were falsely reported for EVERY format (1 fail per
   format, code `raw = 1<<(N-1)`, i.e. negative zero).

2. **A critical bug of the decode LAW (not of transcription): underflow-to-zero
   instead of gradual underflow in FP32.** For formats with `BIAS_gf > 127`
   (gf24 BIAS=255, gf32 BIAS=2047) part of the GF-normal range has a
   true exponent below the minimum normal FP32 exponent
   (-126), but is still representable as an FP32-**subnormal**. The first version
   of the algorithm (both in the bit-model and in Verilog v1), when `rebias-exp <= 0`, simply
   flushed the result to 0 — losing 187/4038 (gf24) and 22/4038 (gf32)
   values in the representative sample. Found by comparison with the golden
   (`fraction_to_ieee754_binary32_bits`, which itself knows how to saturate
   correctly via a native float). Fixed: a single function `_pack_fp32`
   (Python) / a common packer datapath (Verilog v2), which always tries the
   FP32-normal path, and when `true_exp < -126` switches to the
   FP32-subnormal path with an explicit guard/round/sticky relative to
   the FP32-subnormal LSB (2^-149).

3. **An intermediate error in the first attempt at fix #2**: the guard/sticky
   were counted relative to `FP32_MIN_NORM_EXP=-126` instead of the correct
   reference point `FP32_SUB_LSB_EXP=-149` — this gave a `shift` beyond the
   significant bits and erroneously rounded all such values TO ZERO instead of
   to the nearest representable subnormal. Counterexample: `gf24 raw=0x1a4d56`,
   exact value `0.604 × 2⁻¹⁴⁹`, is obliged to round to **1** (the smallest
   FP32-subnormal), not to 0. Fixed by the formula
   `shift = frac_w - true_exp + FP32_SUB_LSB_EXP`. After the fix —
   0 divergences on the full stress-test across all gf24/
   gf32 exponent powers (9198 and 73710 probes respectively).

Not a single divergence attributed to the sticky bit on SUBTRACTION (that
problem is specific to GF-ADD; decode does not perform subtraction of operands) or
to the implicit bit of denormals (implicit=0 for subnormal was handled correctly
from the very beginning in both implementations).

4. **Fixed-width shift truncation in Verilog (caught ONLY by iverilog, not by
   Python) — the 28.06 lesson in action.** Line 180 (v1) of `gf_decode_param.v`:
   `assign norm_widen_result = { {(WIDE-FP32_MANT+1){1'b0}}, (pack_frac <<
   (FP32_MANT-M)) };`. `pack_frac` is declared `[M-1:0]` (M bits), and in Verilog
   the width of a shift result equals the width of the LEFT operand — i.e.
   `pack_frac << (23-M)` was computed in an M-bit container and the high
   significant bits that went beyond the M boundary **were truncated BEFORE** the concatenation.
   The Python bit-model (`frac_bits << shift_amt` in an arbitrary-width int, then
   `& mask(23)`) modeled the MATHEMATICALLY correct (target) semantics,
   so it gave a PASS and did NOT see the truncation. Symptom on a real
   Verilog simulator: gf16 exhaustive `HW RESULT: 1168/65536 bit-exact
   (fails=64368)` — ~98% of normals failed (the stronger, the smaller M and the larger
   the shift). **Fix (v2):** first widen to the full result width,
   then shift —
   `wire [WIDE:0] pf_wide = { {(WIDE-M+1){1'b0}}, pack_frac };`
   `assign norm_widen_result = pf_wide << (FP32_MANT - M);`. The arithmetic of the fix:
   for all 10 formats the shift `= (23-M) >= 0`, the significant bits after the shift
   `= M + (23-M) = 23 <= WIDE=23`, plus the carry bit `[23]` = a 24-bit container
   `[WIDE:0]` fits without loss; carry on the widen-path = 0 (normal
   mantissa ≤23 bits). The fix repairs the gf16-class; BUT it alone is INSUFFICIENT —
   see bug #5.

5. **Out-of-bounds bit-read in the FP32-subnormal packer (caught ONLY by iverilog №2).**
   After fix #1 gf16 became clean, but gf24/gf32 continued to fail with output
   `dut=00Xxxxxx`. Root cause: `wire [M:0] sub_shifted` (for gf24 M=14 → 15 bits),
   but below it reads `sub_shifted[22:0]` → bits 22:(M+1) = out-of-bounds → X.
   It triggers ONLY on the FP32-subnormal path (true_exp < −126, deep
   underflow), which gf16 (BIAS=31) never reaches — that is why gf16
   remained clean and hid this bug (this is why fix #1 looked
   sufficient on gf16). The Python bit-model has no concept of an OOB-read
   (an arbitrary-width int is never "wider than declared") → again a PASS without
   warning. **Fix:** `wire [M:0] sub_shifted` → `wire [23:0]
   sub_shifted` (the RHS zero-extends to 24 bits, `[22:0]` reads valid
   zeros). After both fixes — **10/10 Phase-A PASS on iverilog** (fails=0).

## Honesty-status (binding)

- φ-rule = **[Verified as a rule]** — holds exactly across the whole 17-cell
  ladder (verified by `gf_decode_ref.py::verify_phi_rule()`).
- golden==Python-bit-model = **[simulated]** (the specification); by itself it is
  NOT a guarantee for the Verilog-RTL (bugs #4 and #5: the model passed, Verilog failed until
  TWO fixes were applied).
- Verilog `gf_decode_param.v` (both fixes) = **[verified SW on iverilog-witness
  №2]** — 10/10 Phase-A `HW RESULT: N/N bit-exact (fails=0)` on a real
  simulator with fixed-width semantics. This is sim-bitexact, NOT HW: decode-HW
  requires a 4/4 chain on AX7203 (synth+flash+UART+IDCODE), which has NOT been performed.
- gf16-decode from this generator closes **#237** as a special case.
- 1-ULP subnormal residuals — were not encountered in the runs performed for
  Phase A (0 divergences across all classes); if they appear on real hardware,
  this will be a `KNOWN_LIMITATION`, not a hard-fail (the `gf_decode_lineup_spec.md` once cited here is not in the
  repository — checked 2026-09-05).
- extended (gf96…gf1024) — SW-conformance / fixed-point ONLY, never
  claim FP-decode on HW.
- Catalog = 83 formats at the time of this note (2026-07-04); 109 at v3 of the
  catalogue paper (Sep 2026) — the count grows. This work = a 17-cell
  GF-subfamily inside the catalog. No "first/best".
- Every format remains decode-HW **[requires confirmation]** until a full 4/4
  chain (CI GREEN + SHA256 + UART `HW RESULT: N/N bit-exact (fails=0)`
  @160000 + IDCODE `0x13636093`) on AX7203 — the Tier-E bar is stated in the
  repository README, §2 (`gf_decode_lineup_spec.md` is not in the repository —
  checked 2026-09-05).

## What remained for the user (outside the sandbox)

1. **iverilog-witness №2 — DONE (green, both fixes).** 10/10 Phase-A
   `HW RESULT: N/N bit-exact (fails=0)` on the user's real iverilog
   (harness + logs in `/tmp/gf16_witness/`). Optionally (variant 3): a stronger
   witness — exhaustive gf20 (2^20=1M) / gf24 (2^24=16M) instead of
   a representative-sample (long, but possible).
2. **Synthesis + PnR + flashing on AX7203** (XC7A200T-2FBG484I,
   IDCODE `0x13636093`) for each of the 10 formats of Phase A — only then
   can the decode-HW checkmark (4/4 chain) be closed.
3. **CI-workflow(s)** synth→bitstream following the corona-decode-* template — one
   parametric workflow with a `strategy: matrix:` across 10 rows (N/E/M/BIAS),
   or 10 separate workflow files, by analogy with the existing
   `gf6_add`/`gf8_add`/... in trinity-fpga.
4. **Extending the corona-decode-host FMT-list** to the entire GF-lineup + fmt-codes
   (similar to the existing 13 decode-HW formats, see the wave-loop skill
   §"decode-HW 13 (Tier E)").
5. **Phase B (FP64: gf48/gf64)** — Verilog module with a binary64 output,
   bit-model, vectors — by analogy with this loop, but with an 11-bit exp./
   52-bit FP64 mantissa.
6. **Phase C (extended)** — decision on a fixed-point/chunked-limb SW-conformance
   approach (NOT FP-decode) for gf96…gf1024.
7. Publication of UART-logs to issue #199 (epic fpga-matrix) after every
   successful 4/4 chain, following the template from `burst-flash-checklist.md`.

## How to reproduce the verification in this same sandbox

```bash
cd fpga/witness/gf_decode
python3 gf_decode_ref.py      # phi-rule + catalog self-test
python3 rtl_bit_model.py      # golden==RTL check, 10/10 Phase-A PASS, exit 0
python3 gen_vectors.py        # (re)generate vectors/*.txt
```

Sources (SSOT/spec): `fpga/gf16_decode_cell_TZ.md (issue #237)`;
methodology — `(denormal-loop methodology, outside the repo)`;
papers — [arXiv:2606.05017](https://arxiv.org/abs/2606.05017),
[arXiv:2606.09686](https://arxiv.org/abs/2606.09686).
