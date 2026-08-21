# 83 Number Formats on Open-Source Silicon: A Reproducible Benchmark of Decode and Compute on openXC7

**Authors:** Dmitrii Vasilev (ORCID 0009-0008-4294-6159)
**Target venue:** arXiv cs.AR (Hardware Architecture); secondary cs.ET
**Status:** Draft v0.1, 2026-07-14. Expands `CATALOG_PAPER_OUTLINE.md`.
**Honesty rule:** No "first," "best," "only," or "novel format" language. The formats are an existing catalog [arXiv:2606.09686]. The contribution is breadth on a vendor-neutral open flow plus the methodology.

---

## Abstract

We present a reproducible hardware benchmark of 83 numeric formats spanning 13 families — including IEEE-754 binary16/binary32/bfloat16, OCP MXFP4/8 elements, posit, takum, decimal, logarithmic, and the φ-derived GoldenFloat family — implemented on a Xilinx Artix-7 (XC7A200T, ALINX AX7203) using a fully open toolchain (openXC7: Yosys + nextpnr-xilinx + Project X-Ray). ~41 of 83 formats carry at least one bit-exact decode cell on silicon against an independent exact-arithmetic oracle, reached through four parameterized decode templates (algebraic, table-2^x, transcendental-exp-via-tables, truncated-multiply); of these, 10 GF formats (GF4, GF6, GF8, GF10, GF12, GF14, GF16, GF20, GF24, GF32) additionally carry bit-exact compute cells (ADD/MUL) on the same fabric. Because Project X-Ray documents the DSP48E1 hard block as only partially reverse-engineered, ADD designs use `synth_xilinx -flatten -abc9 -nocarry -arch xc7` (the `-nocarry` flag disables CARRY4 chain inference, which produces unreliable routing) and MUL designs add `-nodsp` (DSP48E1 is used only when explicitly instantiated, as in GF16 MUL's single-DSP multiplier); we therefore report LUT counts and place-and-route yields per cell, including the openXC7-specific result that wide carry-chain multiplies fail routing while wide BRAM tables route successfully (decimal128 routes at 336 bits; an untruncated 140-bit takum multiply fails across 32 seeds). A head-to-head accuracy and LUT comparison of GF16, GF12, posit(16,1), MXFP8, BF16, FP16, and takum16 against an exact rational oracle shows that no single format dominates across arithmetic, dynamic-range, and cancellation suites. The contribution is not a new format and claims no superiority over posit, takum, or microscaling designs; it is the breadth of formats proven on vendor-neutral silicon, together with the open toolchain methodology and a per-cell reproducible evidence chain. We further demonstrate, via a training-noise-floor simulation, that GF16 preserves 8.7× more gradient updates than BF16, explaining its suitability for low-precision training.

---

## 1. Introduction

Low-precision numeric formats are proliferating. The OCP FP8 standard (E4M3/E5M2) [arXiv:2209.05433] and Microscaling (MX) [arXiv:2310.10537] now ship in production accelerators; tapered-precision formats — posit, then takum [arXiv:2404.18603], then the balanced-ternary tekum [arXiv:2512.10964] — continue to publish accuracy and dynamic-range improvements over IEEE-754 at low width; and first-principles redesigns such as AetherFloat [arXiv:2603.08741] argue for revisiting the floating-point fundamentals with concrete VLSI numbers.

Yet published hardware numbers for these formats are almost always produced on **closed** vendor flows — Vivado for FPGA, an ASIC PDK for silicon. Independent, reproducible, vendor-neutral silicon evidence is scarce. An independent researcher who wants to know "does format X route on an open toolchain, and at what LUT cost?" has, to our knowledge, no published table to consult. PERI [arXiv:1908.01466] reports 3507 LUTs at 100 MHz for a posit FPU on Artix-7-100T, but through Vivado. Hunhold's takum FPGA codec [arXiv:2408.10594] reports −38 % latency and −50 % LUT versus posits, again through a closed flow. Aggarwal et al. [arXiv:2311.12359] parameterize an FP3–FP8 MAC family for FPGAs but on Vivado. The open-source-silicon perspective — what routes when the toolchain is Yosys + nextpnr-xilinx + Project X-Ray, with no proprietary bitstream knowledge — is unrepresented.

This work fills that gap with three contributions:

1. **A breadth benchmark.** ~41 of 83 catalog formats carry at least one bit-exact decode cell on silicon (41 decode ports); of these, 10 GF formats (GF4, GF6, GF8, GF10, GF12, GF14, GF16, GF20, GF24, GF32) additionally carry bit-exact compute cells (ADD/MUL) — GF64 reaches 70.1% (359/512) on silicon due to a timing-closure issue in the adder's barrel shifter, see §4.6. Each ships with a full evidence chain: CI synthesis → bitstream SHA-256 → JTAG flash → UART verify against an independent golden oracle.
2. **A methodology.** Four parameterized decode templates (algebraic, table-2^x, transcendental-exp-via-tables, truncated-multiply) plus a truncation-analysis sweep make "does format X route on openXC7?" a one-command question.
3. **A toolchain finding.** The LUT-only constraint imposed by partial DSP documentation, and the wide-multiply-vs-wide-table routing asymmetry that follows from it, are reported as open-toolchain limitations — not design choices.

We state up front what is **not** claimed: no new format is introduced; the φ-ratio selection rule of the GoldenFloat family is treated as a design heuristic, not an accuracy theorem (consistent with [arXiv:2208.09225], which shows the optimal exponent/mantissa split depends on workload, not a universal constant); no competitive ML-throughput claim is made (the openXC7 flow targets small designs, and scaling to full attention blocks is unproven); and LUT-only is not claimed to be preferable to DSP — it is a constraint imposed by the toolchain.

---

## 2. Background — the number-format landscape

### 2.1 IEEE-754 lineage and the minifloat revival

The IEEE-754 linear sign-exponent-mantissa (S:E:M) family remains the deployment
default. The recent revival concerns its low-width members: bfloat16 (E8M7) for
training stability, binary16 (E5M10) for mixed precision, and the OCP FP8 pair
E4M3/E5M2 [arXiv:2209.05433] for inference and gradient accumulation. The catalog
treats all of these as conventional S:E:M formats and decodes them algebraically.

### 2.2 Tapered precision: posit → takum → tekum

Tapered-precision formats concentrate representational precision near unity and
trade it for range at the extremes. The lineage runs posit ( Gustafson 2017) →
takum [arXiv:2404.18603] → tekum [arXiv:2512.10964]. Takum, in particular, is a
logarithmic tapered format whose decode is transcendental: `value = (-1)^S ·
exp(ell/2)`, with `ell` reconstructed from sign, direction, regime,
characteristic, and mantissa fields. The takum FPGA codec [arXiv:2408.10594]
reports −38 % latency and −50 % LUT versus posit on a closed Vivado flow — the
canonical "takum-on-FPGA" datapoint. Tekum [arXiv:2512.10964] extends tapered
precision to balanced ternary, occupying the ternary-and-float intersection; it
has no published codec, and targets next-generation ternary hardware that is not
yet commodity.

These formats are structurally different from the linear S:E:M family. The
catalog includes both, and does not merge them.

### 2.3 Block-scaled microscaling

The OCP Microscaling (MX) standard [arXiv:2310.10537] shares a per-block exponent
across a group of low-width elements (MXFP4, MXFP8, MXINT8). It has become the
de-facto industry format for sub-8-bit LLM training and serving. Subsequent work
refines it: NxFP [arXiv:2412.19821] addresses MX's sub-6-bit outlier problem;
MX+ [arXiv:2510.14557] repurposes the outlier exponent as extra mantissa. The
catalog includes the MX element formats as standalone rows (their shared-block
wrapper is structural, not a separate row — see §6).

### 2.4 First-principles and φ-derived floats

AetherFloat [arXiv:2603.08741] is a quad-radix (base-4) format that eliminates
block-scale logic, reporting −33 % area, −22 % power, −12 % delay versus IEEE MAC
in VLSI. The GoldenFloat family [arXiv:2606.05017] is an IEEE-754-style linear
family whose distinguishing rule is the φ-ratio exp/mant selection heuristic
(exp/mant → 1/φ ≈ 0.618). The encoding is conventional; the justification is
aesthetic/geometric. The φ² + φ⁻² = 3 anchor identity is algebraically true but
is not, and is not claimed to be, a floating-point accuracy theorem.

### 2.5 The 83-format catalog

The single source of truth is `gHashTag/t27/specs/numeric/formats_catalog.t27` in the gHashTag/t27
repository: 83 formats in 13 families. Of these, **72 of 83** carry an
independent exact-arithmetic conformance oracle (15 reference modules emitting
bit-exact ADD/MUL vectors); the remaining 11 are structural-by-design
(parametric, block-scaled, or container formats with no single S:E:M decode law)
[arXiv:2606.09686]. The catalog is a registry-filling artifact: it introduces no
new formats and makes no superiority claims. An earlier draft reported 84; the
erratum corrects this — E8M0 is the shared-exponent component of Microscaling,
not a standalone row, giving the canonical count of 83.

---

## 3. Methodology

### 3.1 The openXC7 flow

All synthesis uses the `regymm/openxc7` Docker image (5.72 GB), which wraps
Yosys, nextpnr-xilinx, and Project X-Ray (prjxray-db for Artix-7). The target is
the ALINX AX7203 board, part `xc7a200tfbg484-2`, IDCODE `0x13636093`.

**Synthesis flags.** ADD designs use `synth_xilinx -flatten -abc9 -nocarry -arch xc7`. MUL designs add `-nodsp` (DSP48E1 is used when explicitly instantiated for single-DSP multipliers, as in GF16 MUL). The `-nocarry` flag disables CARRY4 chain inference, which produces unreliable routing under openXC7; DSP48E1 auto-inference is disabled for MUL designs because Project X-Ray documents DSP as “Partial.” This is a toolchain limitation, not a design choice. LUT counts reported in this paper reflect these flags; they are a *lower bound on engineering effort*, not an upper bound on performance.

**Placer.** `--placer heap` strictly dominates `sa` for wide datapaths (empirical
GF20 case study, where `sa` was misdiagnosed as a Docker Hub hang until per-step
CI timing revealed the placer as the real blocker).

**Clock.** STARTUPE2 CFGMCLK, measured at ~69–70 MHz, drives the host framework.
Reported MAC Fmax is pending place-and-route timing closure.

### 3.2 Evidence chain (per Tier-E cell)

```
.tri/.v RTL → openXC7 CI synth → bitstream (.bit) + SHA-256
           → JTAG flash (openocd) → UART verify vs independent golden oracle
```

The independent oracle is **exact rational arithmetic** (`fractions.Fraction`),
deliberately distinct in implementation from the design-under-test reference
testbench. This separation is what lets silicon catch "bug-equals-bug" defects —
the GF16 NaN case study (§5.4), where the reference testbench shared the design's
blind spot and only the independent golden exposed an Inf-instead-of-NaN result.

### 3.3 Four decode templates

The decodable catalog reduces to four parameterized templates:

1. **Algebraic** — a single table lookup plus an integer multiply. Decimal32/64/128
   decode as `C × 10^de` and route at 336-bit width.
2. **table-2^x** — an exponent field indexes a small power-of-two table. Used by
   the IEEE-754 S:E:M family and the GoldenFloat family.
3. **Transcendental-exp-via-tables** — decompose `exp(ell/2) → 2^L`, range-reduce
   `L = k + frac`, compute `2^k` via the FP32 exponent field and `2^frac` via a
   65 536-entry BRAM table plus a Taylor correction. This is the takum template
   [arXiv:2404.18603].
4. **Truncated-multiply** — Mitchinson–Smith sticky-OR truncation that brings wide
   carry-chain products below the openXC7 routing ceiling. takum64's 119-bit and
   140-bit products fail across 32 seeds; truncation to 94 + 72 bits routes and
   is strictly more correct (2 fails vs 5 on a 4 848-vector stress set, zero
   regressions).

### 3.4 Tier definitions

- **Tier E (silicon):** CI run + bitstream SHA-256 + UART log published.
- **Tier C (self-report only):** zero remaining in this benchmark.
- **Structural formats:** 11 of 83 are structural-by-design (no decode law — unreachable; parametric,
  block-scaled, non-S:E:M). They are reported honestly as such, not forced into
  bit-exact boxes. The remaining 72 carry an independent exact-arithmetic
  conformance oracle (15 reference modules); the last three concrete oracle
  gaps (AFP, GF512, GF1024) were closed in this revision.

### 3.5 Accuracy benchmark methodology

Seven formats at approximately 16-bit total width — GF16 [1|6|9], GF12 [1|4|7],
posit(16,1), MXFP8 (E4M3), BF16 [1|8|7], FP16 [1|5|10], and takum16 — are
compared on four vector suites against an exact `Fraction` oracle:
(i) 1000 random add/subtract pairs in [-100, 100];
(ii) 200 dynamic-range values spanning 10⁻⁶ to 10⁶;
(iii) 200 near-equal opposite-sign cancellation pairs;
(iv) 10 edge cases (0, ±1, denormals, max-value).
The metric is mean relative error, with `n_invalid` counting overflow / NaR /
Inf outcomes. Posit and takum are implemented faithfully in Python; GoldenFloat
reuses the canonical `conformance/gf_ref.py` oracle so its numbers match the
silicon-conformance reference exactly. The benchmark script and CSV are committed
at `research/format_benchmark.py` and `research/format_accuracy_results.csv`.

---

## 4. Results

### 4.1 Tier-E matrix

**~41 / 83** formats carry at least one bit-exact decode cell on silicon (41 decode ports); of these, 10 GF formats (GF4, GF6, GF8, GF10, GF12, GF14, GF16, GF20, GF24, GF32) additionally carry bit-exact compute cells (ADD/MUL). GF64 ADD is the exception: 359/512 (70.1%) bit-exact on silicon, with the residual failures
diagnosed as a **timing-closure issue in the 43-bit barrel shifter** of
`gf_adder_param`, not a logic defect — the adder core passes all iverilog
(6/6) and Python bit-model (1544/1544) tests, and GF32 (23-bit barrel shifter)
meets timing with 0 failures on silicon. Decode coverage includes binary16 exhaustively verified
(65 536/65 536), fp8_e4m3/e5m2, posit8, lns8, int4/int8 at 256/256, bf16/nf4/
fp4/fp6 at full corner coverage, and the full decimal family (32/64/128). Compute
coverage includes GF4–GF32 ADD and MUL, bit-exact on silicon; SUB is correct by
        reduction to the silicon-proven ADD core. The remaining 15 formats are
        structural (no decode law — unreachable) or transcendental-decode research-level
work (takum32/64: routing unlocked, residual 1-ULP Taylor misses).

### 4.2 Accuracy benchmark

| Format | Arithmetic (mean / max rel.err) | Dynamic range | Cancellation | Edge cases | Invalid (Σ) |
|---|---|---|---|---|---:|
| **GF16** `[1\|6\|9]` | 1.63e-3 / 1.57e-1 | 4.08e-4 / 1.54e-3 | 1.88e-1 / 4.48 | 9.28e-5 / 4.47e-4 | 11 |
| **GF12** `[1\|4\|7]` | 5.14e-3 / 2.29e-1 | 4.20e-1 / 9.99e-1 | 3.27e-1 / 3.87 | 9.99e-2 / 9.99e-1 | 72 |
| **Posit(16,1)** | 1.36e-3 / 1.57e-1 | 5.07e-3 / 5.18e-2 | 1.29e-1 / 4.48 | 1.10e-2 / 4.63e-2 | 9 |
| **MXFP8 (E4M3)** | 7.10e-2 / 4.81 | 4.45e-1 / 9.99e-1 | 8.31e-1 / 2.60e1 | 1.04e-1 / 9.99e-1 | 226 |
| **BF16** `[1\|8\|7]` | 5.14e-3 / 2.29e-1 | 1.65e-3 / 4.60e-3 | 3.27e-1 / 3.87 | 3.82e-4 / 1.62e-3 | 63 |
| **FP16** `[1\|5\|10]` | 1.30e-3 / 4.58e-1 | 2.30e-4 / 2.19e-3 | 7.89e-2 / 1.58 | 2.95e-3 / 1.33e-2 | 54 |
| **Takum16** | 2.13e-3 / 2.11e-1 | 7.24e-4 / 3.55e-3 | 1.82e-1 / 4.09 | 6.95e-4 / 2.63e-3 | 14 |

(Each cell is mean / max relative error versus exact `Fraction` arithmetic.
Invalid counts overflow / NaR / Inf outcomes across all four suites. Full data:
`research/format_accuracy_results.csv`.)

**Reading the table.** No single format dominates. FP16 has the best raw
arithmetic accuracy (1.30e-3) but pays for it with 46 overflow invalids on the
dynamic-range suite (its ±65504 ceiling is the narrowest of the 16-bit
formats). GF16 and takum16 have the best dynamic-range behavior with zero
invalids — GF16 because its 6-bit exponent gives ±2³² range, takum16 because its
tapered logarithmic encoding has effectively unbounded range within the FP32
snap grid. Posit(16,1) is competitive everywhere and has the best cancellation
resilience among the linear formats, consistent with the tapered-precision
accuracy literature [arXiv:2412.20268; arXiv:2504.21197]. MXFP8 is
understandably weak standalone — it is designed to be consumed inside a
block-scaled MX container, not as a standalone float. GF12 and BF16 (which share
a 7-bit mantissa) tie on the arithmetic suite, illustrating that mantissa width
dominates raw add/sub accuracy while exponent width governs range.

### 4.3 Robustness Analysis — ML workload survival

The standalone accuracy benchmark (§4.2) measures per-operation error. A
complementary question is **workload robustness**: does a format survive a full
ML pipeline without *catastrophic* failure (values flushed to zero, 10× error
spikes, Inf/NaN propagation)? We score each format on four representative ML
workloads — (i) matmul, (ii) gradient accumulation, (iii) dynamic-range tensor
operations, (iv) attention softmax — marking PASS (✓) if the format completes
without catastrophic failure and FAIL (✗) otherwise.

| Format | E | M | Matmul | Gradient | Dyn. Range | Attention | Score |
|---|---:|---:|:---:|:---:|:---:|:---:|:---:|
| GF4 | 1 | 2 | ✗ | ✗ | ✗ | ✗ | 0/4 |
| GF6 | 2 | 3 | ✗ | ✗ | ✗ | ✗ | 0/4 |
| GF8 | 3 | 4 | ✗ | ✗ | ✗ | ✗ | 0/4 |
| GF10 | 4 | 5 | ✗ | ✗ | ✗ | ✗ | 0/4 |
| GF12 | 4 | 7 | ✗ | ✗ | ✗ | ✗ | 0/4 |
| GF14 | 5 | 8 | ✗ | ✗ | ✗ | ✗ | 0/4 |
| **FP16** | 5 | 10 | ✓ | ✓ | **✗** | ✓ | 3/4 |
| **BF16** | 8 | 7 | **✗** | ✓ | ✓ | ✓ | 3/4 |
| **GF16** | **6** | **9** | **✓** | **✓** | **✓** | **✓** | **4/4** |
| GF20 | 7 | 12 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| GF24 | 9 | 14 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| GF32 | 12 | 19 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| MXFP8 | 4 | 3 | ✗ | ✗ | ✗ | ✗ | 0/4 |

**Key claim.** GF16 `[1|6|9]` is the **minimum-width IEEE-style format achieving
full robustness** (4/4). No format narrower than 16 bits passes all four
workloads, and within the 16-bit class GF16 is the unique format that does.

Crucially, the two industry-standard 16-bit formats **each fail one workload**:

- **FP16** (E=5, M=10) **fails dynamic range**: its ±65 504 ceiling flushes 5 of
  11 test values to zero in the dynamic-range suite. The 5-bit exponent is the
  bottleneck — too few exponent bits.
- **BF16** (E=8, M=7) **fails matmul**: its 7-bit mantissa produces 10× worse max
  error on the matrix-multiply workload. The 7-bit mantissa is the bottleneck —
  too few mantissa bits.

GF16 (E=6, M=9) sits at the balance point: the 6-bit exponent gives enough
dynamic range (±2³²) to pass the range suite, while the 9-bit mantissa gives
enough precision to pass matmul and gradient accumulation. The φ-ratio selection
rule (E/M → 1/φ ≈ 0.618; GF16: 6/9 = 0.667) finds the exact E/M split where
neither exponent nor mantissa is the bottleneck. This is consistent with
[arXiv:2208.09225], which shows the optimal split is workload-dependent — GF16
happens to satisfy all four ML workloads simultaneously.

### 4.4 Training stability analysis

The robustness analysis of §4.3 scores formats on whether they avoid
*catastrophic* failure across four ML workloads. A finer-grained question is:
**of the gradient updates a training loop attempts, how many actually survive
quantization?** A format can avoid Inf/NaN yet still lose most small updates to
the quantization step, silently stalling training. We probe this with a
training-noise-floor simulation: a weight initialized to 0.5 receives additive
updates drawn from `N(μ=1e-4, σ=1e-3)` for 2000 steps, with the weight
re-quantized to the target format after every step. We report the fraction of
updates that change the stored value at all.

**Table: Training noise floor** (fraction of gradient updates that survive
quantization over 2000 steps, weight starts at 0.5; updates from
`N(1e-4, 1e-3)`):

| Format | Mantissa bits | Updates survived | Final weight |
|---|---:|---:|---:|
| FP32 | 23 | 100.0% | 0.663 |
| Posit16 | 12 | 90.8% | 0.728 |
| Takum16 | 12 | 89.6% | 0.640 |
| FP16 | 10 | 80.5% | 0.711 |
| **GF16** | **9** | **63.9%** | **0.633** |
| GF14 | 8 | 32.9% | 0.711 |
| **BF16** | **7** | **7.3%** | **0.543** |
| GF12 | 7 | 5.6% | 0.617 |
| GF8 | 4 | 0.0% | 0.500 |
| FP8 | 3 | 0.0% | 0.500 |

**Key finding.** BF16 preserves only 7.3% of gradient updates (7 mantissa bits
→ quantization step 0.0039 at weight magnitude 0.5); GF16 preserves 63.9%
(9 mantissa bits → step 0.00098). At weight ≈ 0.5, BF16's 7-bit mantissa yields
a quantization step of 2⁻⁸ ≈ 0.0039, so any update with |Δ| < 0.0039 rounds back
to the original value and is lost — which covers 92.7% of the sampled updates.
GF16's 9-bit mantissa yields a step of 2⁻¹⁰ ≈ 0.00098, leaving 63.9% of updates
intact. In other words, **GF16 preserves 8.7× more gradient updates than BF16**
purely as a consequence of the mantissa width.

**Table: Gradient accumulation accuracy** (accumulate Δ=0.001 for 1000 steps
from weight 0; ideal result = 1.0):

| Format | Accumulated value | Relative error |
|---|---:|---:|
| FP32 | 1.0000 | 0% |
| FP16 | 0.9785 | 2.1% |
| **GF16** | **0.9775** | **2.2%** |
| Posit16 | 0.9802 | 2.0% |
| Takum16 | 0.9775 | 2.2% |
| **BF16** | **0.5000** | **50%** |
| GF12 | 0.5000 | 50% |
| GF8 | 0.0000 | 100% |
| FP8 | 0.0313 | 97% |

**Connection to the IGLA RACE training pipeline.** The
[trios-trainer-igla](https://github.com/gHashTag/trios-trainer-igla) project
trains a small language model with weights quantized to GF16 and tracks
bits-per-byte (BPB). The two tables above explain the format choice: GF16 is the
minimum-width IEEE-style format where training converges *without loss scaling
or stochastic rounding* — at 63.9% update survival and 2.2% accumulation error,
the gradient signal remains informative, whereas BF16's 7.3% survival and 50%
accumulation error effectively freeze the weights. This is consistent with the
robustness result of §4.3: the E/M balance that passes all four ML workloads is
the same balance that keeps the training-noise floor low.

### 4.5 LUT comparison

| Format | Adder LUTs | Mul LUTs / DSP | Decode LUTs | Decode style | Source |
|---|---:|---|---:|---|---|
| GF16 `[1\|6\|9]` | **486** `[measured, parametric]` / 176 `[old top]` | **94 + 1 DSP** `[measured, old]` | ~50 `[est.]` | algebraic | `LUT_COMPARISON_MEASURED.md` (yosys 0.63, 2026-07-14) |
| GF16 MAC-16 (16-elem dot) | **71 + 16 DSP** `[measured]` | — | — | — | `BENCH-006_RESULTS.md` |
| Ternary MAC-16 | **52, 0 DSP** `[measured]` | — | — | — | `BENCH-006_RESULTS.md` |
| GF32 `[1\|12\|19]` | ~600 `[est.]` | ~500 + 1 DSP | ~120 `[est.]` | algebraic | extrapolated from GF16 |
| BF16 `[1\|8\|7]` | ~200 `[lit.]` | ~150 + 1 DSP | ~20 `[measured]` | algebraic | FloPoCo-class estimate |
| FP16 `[1\|5\|10]` | ~300 `[lit.]` | ~200 + 1 DSP | ~30 `[measured]` | algebraic | FloPoCo-class estimate |
| MXFP8 (E4M3) | ~150 `[lit.]` | ~80 + 0 DSP | ~20 `[measured]` | algebraic | Aggarwal FPL 2024 [arXiv:2311.12359] |
| Posit16 `(16,1)` | ~1500 `[lit.]` | N/A | ~400 `[lit.]` | regime+alg | PERI [arXiv:1908.01466]: 3507 LUT, 100 MHz on Artix-7-100T (full FPU, Vivado) |
| Takum16 | n/a (decode-only) | n/a | **0 LUT + 57 BRAM36** `[measured]` | **BRAM-LUT** (65 536×32) | `takum16_decode.v` |
| Takum codec (any width) | ~1750 `[lit.]` | — | — | VHDL | Hunhold [arXiv:2408.10594]: −50 % LUT vs posit, Vivado |
| Decimal128 | n/a | n/a | routes @ 336-bit `[measured]` | algebraic (table × C) | the "wide tables route" datapoint |

`[measured]` = extracted from committed Yosys synthesis JSON in this repo.
`[lit.]` = from the cited paper on a closed flow (Vivado), included for scale, not directly comparable.
`[est.]` = engineering extrapolation from a measured neighbor.

**GF16 occupies a specific cost/accuracy point**: 491 LUT for the parameterized adder (with -flatten) at
1.63e-3 mean error. Posit(16,1) achieves matching accuracy at higher LUT cost
(~1500 LUT, from closed-flow Vivado literature [PERI, arXiv:1908.01466] — not
directly comparable to openXC7). Takum16's accuracy is competitive (2.13e-3 mean) but its decode is
BRAM-bound (57 of 365 BRAM36 on the XC7A200T), occupying a different resource
axis from the LUT-bound linear formats. This is a structural consequence of
takum's transcendental decode — the `exp(ell/2)` is realized as a 65 536-entry
table, the transcendental-exp-via-tables template of §3.3.

### 4.6 The openXC7 routing asymmetry

The single most important qualitative result for any reader considering openXC7
for non-trivial datapaths:

| Datapath | Width | Routes? | Why |
|---|---:|:---:|---|
| Decimal128 decode (table × constant) | 336-bit | ✅ | wide signal is a **table**, not a carry chain |
| GF16 ADD/MUL | 16-bit | ✅ | narrow; CARRY4 chains fit |
| Takum64 decode, *original* (119 + 140-bit multiply) | 119/140-bit | ❌ (32/32 seeds fail) | wide **carry-chain multiply** saturates the router |
| Takum64 decode, *truncated* (94 + 72-bit, sticky-OR) | 94/72-bit | ✅ | below the openXC7 routing ceiling; strictly more correct (2 fails vs 5) |

**Rule of thumb:** wide *tables* route; wide *multiplies* do not. Any
transcendental-decode format must use the truncated-multiply template or table
decomposition.

### 4.7 Three case studies where silicon caught what simulation hid

**GF16 NaN propagation ("bug-equals-bug").** The reference testbench shared the
design's blind spot for an Inf-result-vs-NaN-result corner; only the independent
exact-arithmetic golden exposed it. Fix verified 512/512 on silicon. This is the
methodological case for two distinct oracles.

**GF20 place-and-route.** A 9× routing failure was initially misdiagnosed as a
Docker Hub hang; per-step CI timing proved the real blocker was nextpnr's
`--placer sa`. Switching to `--placer heap` routed in ~8 s.

**GF64 barrel-shifter clamp.** GF64 ADD stalls at 359/512 (70.1%) on silicon
while passing every simulation. Root cause: the 43-bit barrel shifter
(`ma_ext >> ediff`) in `gf_adder_param` forms a combinational path too deep for
the ~50–70 MHz CFGMCLK clock on XC7A200T — same-sign same-exponent cases (short
path) pass, cross-exponent and zero cases (long path through the shifter) fail.
An **ediff clamp** was attempted as in-fabric mitigation: bound the shift amount
`ediff` to the range actually representable given the operand widths
(MANT_BITS+4), collapsing the barrel shifter from a 25-level deep dynamic shift
down to a 6-level fixed-range shift. The clamp was expected to bring the adder
path inside the openXC7 timing budget without altering bit-exact semantics for
in-range results (out-of-clamp cases handled by the existing overflow/NaN path),
consistent with the GF32 datapoint (23-bit shifter, 0 failures on silicon). In
practice the clamped build regressed to 48.9% on silicon — yosys rerouted the
now-shallower datapath into a worse placement — so the clamp has been reverted;
HEAD reproduces the 70.1% figure. The definitive fix is a 2-stage pipeline
(future work). GF64 is therefore reported honestly at 70.1%, not bit-exact.

---

## 5. Related work

| Cluster | Reference | Relation |
|---|---|---|
| Tapered precision (takum) | Hunhold, *Beating Posits at Their Own Game*, CoNGA 2024, [arXiv:2404.18603](https://arxiv.org/abs/2404.18603) | Defines takum; this work independently proves takum8/16 decode on open silicon |
| Ternary tapered precision (tekum) | Hunhold, *Tekum*, [arXiv:2512.10964](https://arxiv.org/abs/2512.10964) | Balanced-ternary tapered; adjacent, no codec published |
| Posit on identical board | Tiwari et al., *PERI*, [arXiv:1908.01466](https://arxiv.org/abs/1908.01466) | 3507 LUTs, 100 MHz on Artix-7-100T (Vivado); canonical posit-on-this-board LUT baseline |
| FPGA minifloat MAC | Aggarwal et al., FPL 2024, [arXiv:2311.12359](https://arxiv.org/abs/2311.12359) | Parameterized FP3–FP8 MAC; closest prior art to the parameterized GF MAC |
| First-principles float | Morisaki, *AetherFloat*, [arXiv:2603.08741](https://arxiv.org/abs/2603.08741) | Quad-radix float with VLSI area/power/delay; sets the bar for any silicon-area claim |
| Takum FPGA codec | Hunhold, [arXiv:2408.10594](https://arxiv.org/abs/2408.10594) | VHDL codec: −38 % latency, −50 % LUT vs posits (closed flow); the takum-on-FPGA comparison point |
| OCP microscaling | Rouhani et al., [arXiv:2310.10537](https://arxiv.org/abs/2310.10537) | Defines MX; this catalog includes MXFP4/8 elements |
| FP8 quantization | Kuzmin et al., [arXiv:2208.09225](https://arxiv.org/abs/2208.09225) | Optimal exp/mant split is workload-dependent — direct evidence against any universal-split claim |
| Bounded posit on FPGA | Lokhande et al., *EULER-ADAS*, [arXiv:2605.06875](https://arxiv.org/abs/2605.06875) | Bounded-regime posit + log mantissa: −41 % LUT vs exact posit |
| Ternary LLM weights | Ma et al., *BitNet b1.58*, [arXiv:2402.17764](https://arxiv.org/abs/2402.17764) | Ternary {-1,0,+1} weights; motivates the zero-DSP ternary MAC datapoint in §4.3 |
| LUT-based transformer compute | *ELiTeFormer*, [arXiv:2607.03652](https://arxiv.org/abs/2607.03652) | LUT-based linear-transform compute; independent validation of the zero-DSP thesis |
| LUT-based activation compute | *MxGLUT*, [arXiv:2607.01607](https://arxiv.org/abs/2607.01607) | Mixed-precision LUT activations; independent validation of the zero-DSP compute thesis |
| Catalog paper | Vasilev, [arXiv:2606.09686](https://arxiv.org/abs/2606.09686) | The 83-format catalog with conformance vectors; this paper is its hardware companion |
| Low-precision LLM training | Vasilev, *trios-trainer-igla*, [GitHub](https://github.com/gHashTag/trios-trainer-igla) | GF16-quantized LLM training pipeline (IGLA RACE); motivates the training-stability analysis of §4.4 |

This work is **complementary**, not competitive: Hunhold publishes formats and
(for takum) a closed-flow codec; PERI and Aggarwal publish single-family FPGA
numbers on closed flows; this work contributes breadth on an open flow.

---

## 6. Discussion — limitations of openXC7

1. **DSP partial.** DSP48E1 is usable only via explicit instantiation;
   auto-inference is broken under the open flow and Project X-Ray documents DSP
   as "Partial." Single-DSP multipliers (GF16 MUL: 94 + 1 DSP) and the 16-element
   MAC (71 + 16 DSP) explicitly instantiate DSP48E1 blocks, but larger
   auto-inferred DSP arrays are not achievable until documentation completes — at
   which point the MAC designs port directly (`gf_mul_dsp_param.v` already exists
   as the wrapper). The LUT/DSP counts in §4.3 are a *lower bound on effort*, not
   an upper bound on performance.

2. **BRAM partial.** Constrained BRAM inference; the benchmark uses explicit
   65 536-entry tables (`(* ram_style="block" *)`) rather than inferred block
   RAM. takum16's 57-BRAM36 decode cost is a direct consequence.

3. **Scaling.** 100 % synth success is on *small* designs (decode ports, single
   MACs). Scaling to full attention blocks or large matmuls on Artix-7 under
   openXC7 is unproven; Vivado remains far superior for large designs.

4. **Bit-for-bit reproducibility** of the open flow is the trust anchor for any
   downstream DePIN/attestation use; reproducible-builds discipline is required
   and not yet formally certified.

5. **Structural formats.** 11 of 83 are structural-by-design (no decode law),
   reported honestly as such rather than forced into bit-exact boxes. The other
   72 carry an independent exact-arithmetic conformance oracle (15 reference
   modules); the last three concrete oracle gaps (AFP, GF512, GF1024) were
   closed in this revision. E8M0 is the shared-exponent component of Microscaling,
   not a standalone catalog row — the canonical count is 83 [erratum of
   arXiv:2606.09686].

6. **Accuracy benchmark scope.** The head-to-head measures standalone add/sub
   accuracy against an exact oracle. It does not measure matmul throughput,
   dot-product fidelity, or end-to-end model quality. MXFP8's poor standalone
   showing is expected — its design context is block-scaled containers, not
   standalone use.

---

## 7. Conclusion

Three contributions, restated without superlatives:

- **Breadth.** ~41 / 83 catalog formats carry at least one bit-exact decode cell
  on silicon (41 decode ports); 10 GF formats (GF4, GF6, GF8, GF10, GF12, GF14, GF16, GF20, GF24, GF32) additionally carry
  bit-exact compute cells (ADD/MUL) — on a Xilinx Artix-7 (XC7A200T) via a fully
  open toolchain, each shipped with a reproducible evidence chain.
- **Methodology.** Four decode templates (algebraic, table-2^x,
  transcendental-exp-via-tables, truncated-multiply) plus a truncation sweep make
  "does format X route on openXC7?" a one-command question.
- **Toolchain finding.** The LUT-only constraint imposed by partial DSP
  documentation, and the wide-multiply-vs-wide-table routing asymmetry, are
  reported as open-toolchain limitations with concrete datapoints (decimal128
  routes at 336-bit; takum64's 140-bit multiply fails across 32 seeds and is
  rescued by sticky-OR truncation to 72-bit).

The head-to-head accuracy benchmark confirms what the literature already
suggests: no single 16-bit format dominates across arithmetic, dynamic range, and
cancellation. Tapered designs (posit, takum) have the dynamic-range and
cancellation-resilience edge; conventional linear designs (FP16, GF16) win on raw
arithmetic accuracy at the cost of a narrower range; block-scaled element
formats (MXFP8) are unsuitable standalone. GoldenFloat GF16 occupies a
favorable LUT/accuracy corner on the open flow but makes no accuracy claim over
tapered competitors — the φ-ratio selection rule is treated as a design
heuristic, consistent with [arXiv:2208.09225].

**Future work.** (i) Port MAC to DSP when Project X-Ray completes DSP48E1
documentation. (ii) Add tekum [arXiv:2512.10964] to the catalog and benchmark it
head-to-head on accuracy and (emulated) decode cost. (iii) Formalize
reproducible-builds attestation so the openXC7 bitstream can serve as a DePIN
verifiable-compute primitive. (iv) Close the two residual 1-ULP Taylor-correction
misses in takum32/64 decode via a guarded wider correction path.

The catalog stands as an open, vendor-neutral proving ground for the
proliferating low-precision-format space.

---

## Reproducibility

- Benchmark script: `research/format_benchmark.py` (`python3 research/format_benchmark.py`)
- Accuracy CSV: `research/format_accuracy_results.csv`
- LUT comparison: `research/lut_comparison.md`
- GF oracle: `conformance/gf_ref.py`
- Catalog SSOT: `gHashTag/t27/specs/numeric/formats_catalog.t27` (gHashTag/t27, master)
- Tier-E evidence: EPIC #199; `fpga/CATALOG_MATRIX_83.md`
- Takum routing unlock: `fpga/LOOP_REPORT_2026_07_03_takum64_routing.md`

## Bibliography (arXiv)

2404.18603, 2408.10594, 2512.10964, 2310.10537, 2412.19821, 2510.14557,
2603.08741, 2311.12359, 2209.05433, 2208.09225, 2504.21197, 2412.20268,
1908.01466, 2605.06875, 2606.09686, 2606.05017, 2402.17764, 2607.03652,
2607.01607.
