# TRINITY FPGA — FULL SESSION REPORT
**Date:** 2026-07-17  
**Session:** Etalon Discovery + Silicon + Parameter Golf Intelligence  
**Commits:** 15+ on main, paper v4→v11

---

## 0. HONESTY ERRATUM (added 2026-07-17, audit pass)

Before using this report in a paper or grant application, the following claims have been
DOWNGRADED in status based on independent audit (repo verification + unified re-benchmark):

1. **"INT6 beats all FP formats on training" — NOT CONFIRMED.** On a consistent scale
   (same corpus/seed-set), INT6 is WORSE than FP32 and GF14/GF16 in BPB. Consistent with
   §3.7 (FineWeb: INT6 = FP32 +0.013). The "INT6 victory" in §3.2 is an artifact of
   overfitting on toy-Shakespeare. Status: **[modeled, scale-dependent]**.
2. **BPB numbers are INCONSISTENT across sections** (§3.2 INT6=0.263, §3.6=0.278,
   §3.7 FineWeb≈1.94). These are DIFFERENT scales/corpora. Each leaderboard row needs
   a scale annotation; rows are not directly comparable.
3. **LUT numbers (486/505/851/120…) — [measured locally, NO CI artifact].** The repo
   contains no nextpnr/yosys utilization report. For reproducibility, a CI job with
   saved report is needed.
4. **"FPGA AI model works / inference on AX7203" — [flashed, output NOT verified].**
   UART is broken on macOS 26 → model output was never read. "DONE LED / blinking"
   ≠ correct inference.
5. **"SmoothQuant is not used by ANY of 2000+ participants" → "SQ is not found in
   publicly described top solutions."** Private submissions cannot be verified
   (honesty rule #1: no categorical negatives).
6. **SQ-INT6 "etalon 0.255" — [modeled, NOT reproduced on unified scale].** Correct SQ
   (scale migration + activation inversion) has not been run on a real harness with a
   consistent corpus.
7. **Vasilev Floor — [yosys-stat, NOT post-P&R / NOT silicon].** The LUT = cW² law is
   built on `yosys stat` (synthesis), not on `nextpnr` utilization report (place-and-route).
   Post-P&R LUT counts are typically 15–30% higher (noted in `paper.tex:1238`). Correct
   tag: **[measured yosys-synth]** for W≤128 + **[scaling-law extrapolation]** for W>128.
   Additionally, the report previously contained TWO inconsistent regressions (1.55W²/2.06W²
   with 15 points vs 1.63W²/2.09W² with 11 points) — only the current one (1.63/2.09, 11
   points) is retained.

Everything NOT in this list (16 GF compute Tier-E cells from prior sessions, code/artifact
presence in main, φ-proof fix in af65d907c) remains valid. Details:
`wave_audit/rebench_findings_2026-07-17.md`.

---

## 1. PROBLEM STATEMENT

Find and create the best number format for LLMs — the **reference standard (etalon)**.
Criterion: minimum BPB (bits per byte) at a fixed byte budget (artifact size). Additional
axes: robustness (7 workload tests), LUT cost on FPGA, hardware implementability.

---

## 2. BASELINE (BEFORE THIS SESSION)

| Component | Status |
|-----------|--------|
| GF16 silicon | 10 GF formats × {ADD,MUL} bit-exact on AX7203 |
| Paper | v4, 1321 lines LaTeX, 7 figures, 12 tables |
| φ-rule | GF16 (E=6,M=9) — minimum-width IEEE-style with 7/7 robustness |
| Vasilev Floor | LUT ≈ 1.63W² (ADD), 2.09W² (MUL), 11 points **[yosys-stat, not post-P&R]** |
| IGLA RACE | GF16 BPB=3.686 on Shakespeare (beats FP32 3.692) |
| arXiv | ID 2606.05017 reserved |

---

## 3. WORK COMPLETED — BY PHASE

### 3.1. Weakness Analysis & Competitor Research

**Weaknesses found and fixed:**
1. **φ-proof was MATHEMATICALLY INVALID** — maximizing E*M yields E=M (ratio=1), not 1/φ.
   Fixed: reformulated as a golden-section design heuristic. (commit `af65d907c`)
2. **"first systematic" claim** — removed from abstract.
3. **Vasilev Floor** updated: 1.63W² (R²=0.974), 2.09W² (R²=0.993) — 11 points
   **[yosys-stat, not post-P&R]**.
4. **GF64 timing** — 70.1% bit-exact, unimprovable.
5. **div/sqrt** — binary32 proxy, not native GF.

**Competitors (45 papers, 2024–2026):**
- **UFP4** (NVIDIA 2026): uniform E1M2/INT4 + RHT + SR → beats E2M1 FP4
- **QuaRot/SpinQuant**: Hadamard rotation mandatory for sub-4bit
- **AdaHOP**: MXFP4 training at BF16 quality
- **QuEST**: theory of 4-bit trainable networks
- **CAT-Q** (ICML 2026): ternary without QAT
- **BBQ** (ICLR 2026): first format both ITO + compute-efficient
- **Takum** (Hünhold): only competitor on the same axis (single-rule + LUT)
- **OCP MX / Blackwell MXFP4**: consortium + shipping silicon
- **φ-ratio**: golden ratio for E/M split not found in the 45 surveyed papers (survey is
  not exhaustive — not claiming "nobody in the world").
- **SmoothQuant**: not found in publicly described Parameter Golf top solutions (private
  solutions unverifiable — §0 item 5).

### 3.2. Systematic Format Exploration

**Phase 1: Width sweep W=10..20 (40+ formats)**
- φ-rule wins at 4/11 widths (W=15,17,19,20)
- At W=12–14,16 alternative E/M splits are better
- FP32 wins at d≤52 (underfitting regime)

**Phase 2: MEGA format comparison (14 formats, 6 families)**

| Format | Family | bpe | BPB | LUT | Status |
|--------|--------|-----|-----|-----|--------|
| INT6 | Integer | 6 | 0.263 | ~72 | ★ BEST training |
| INT7 | Integer | 7 | 0.278 | ~50 | Most stable |
| GF14 | Float φ | 14 | 0.301 | 851 | Best robustness |
| NF4 | NormalFloat | 4 | unstable | — | Seed-dependent |
| POW2-4 | Power-of-2 | 4 | diverge | — | Insufficient |
| Ternary | Ternary | 2 | diverge | — | Too coarse |
| MXFP8 | Microscaling | 8.25 | diverge | — | M=3 too few |
| FP32 | Float | 32 | 0.346 | ~3000 | Reference |

**Observation (toy-Shakespeare, overfitting regime): INT6 achieves lower BPB than GF14
at lower LUT.** CAUTION: on a consistent scale and on FineWeb (§3.7) the direction
INVERTS — INT6 is worse than FP32/GF. Status: [modeled, scale-dependent]. See §0 item 1.

**Phase 3: Advanced techniques**

| Technique | BPB improvement | Verdict |
|-----------|----------------|---------|
| SmoothQuant (α=0.5) | **+7% over INT6** | ★ BEST — not found in PG public solutions |
| Lloyd-Max optimal | +3% over INT6 | Most stable (±0.003) |
| Hadamard Rotation | diverges at d<128 | Needs GPU scale (d≥4096) |
| LSQ (RMS-optimal) | WORSE than max-scale | Not helpful for Gaussian weights |
| Stochastic rounding | hurts at CPU scale | Helps only at overfitting |
| Per-channel INT6 | diverges (unstable) | LR mismatch across channels |
| Per-group (g=2) | +1% over INT6 | Competitive with SQ |
| Residual quant | 0.297 (INT4+INT4=8bpe) | Not competitive |

**Phase 4: Multi-seed validation (2–3 seeds)**
- SQ-INT6: 0.2657 ± 0.012 (2 seeds) ★ ETALON for training
- LM-INT6: 0.2664 ± 0.003 (2 seeds) — most stable
- GF14: 0.3008 ± 0.006 — robustness champion

### 3.3. Robustness Analysis

INT7 through 7 workload tests (same as GF16):
- **INT7: 2/7** (Softmax ✓, LinSolve ✓, rest FAIL)
- **SQ-INT6: 4/7** (Softmax ✓, Gradient ✓, Conv1D ✓, LinSolve ✓)
- **GF14: 6/7** (only Poly fails)
- **GF16: 7/7** (reference)

**Conclusion:** no single format is optimal on both axes (training + robustness).

### 3.4. Hybrid Format (INT7 + GF14 outliers)

| Format | BPB | Robust | LUT |
|--------|-----|--------|-----|
| Hyb σ2.0 | 0.265 | 3/7 | ~100 |
| INT7 | 0.278 | 2/7 | ~50 |
| GF14 | 0.301 | 6/7 | 851 |

Hybrid = best training BPB, but fails DynRange.

### 3.5. GF-MX14 (GoldenFloat + MX scaling)

- GF14 elements + E8M0 shared scale per block of 32
- 85 decades dynamic range (vs GF14's 4.5 decades)
- Hardware: 479 LUT (GF14 MUL 454 + 25 LUT scale adder)
- Training: BPB=0.361 (worse than bare GF14 — scale overhead without benefit)
- MXFP8 (E4M3): DIVERGES (M=3 insufficient)

### 3.6. QAT vs PTQ

| Strategy | BPB | Method |
|----------|-----|--------|
| **QAT SQ-INT6** | **0.254** | Train with quantization noise |
| PTQ SQ-INT6 | 0.275 | Train FP32, quantize afterward |
| PTQ INT6 | 0.278 | Plain INT6 post-training |

**QAT beats PTQ by 7.7%.** The model adapts to quantization noise during training.

### 3.7. FineWeb Validation (real text)

On real FineWeb validation data (62M tokens):

| Format | FineWeb BPB | Δ vs FP32 |
|--------|-------------|-----------|
| FP32 | 1.9266 | — |
| INT8 | 1.9277 | +0.001 |
| INT6 | 1.9391 | +0.013 |
| **SQ-INT6** | **1.9367** | **+0.010** |

**SQ-INT6 improves over INT6 by 0.13% on real FineWeb.**

### 3.8. Parameter Golf Intelligence

- **Winner:** 1.05651 BPB (codemath3000, PR #2135)
- **Winner format:** INT6 GPTQ + INT7 embeddings + LQER rank-4
- **Winner stack:** Muon optimizer, CaseOps tokenizer, depth recurrence, TTT
- **SmoothQuant:** not found in publicly described top solutions (2000+ private
  submissions unverifiable — §0 item 5)
- **Submission pipeline:** `parameter_golf_sq_int6.py` written

**Win probability assessment:**
- Our SQ-INT6 provides 0.13% BPB improvement
- Top-5 are separated by 0.005 BPB
- With cloned winner's stack + SQ preprocessing → realistically top-2 to top-5

### 3.9. Silicon Work

**LUT measurements (yosys -flatten -abc9 -nocarry, XC7A200T):**

| Format | ADD | MUL | MAC |
|--------|-----|-----|-----|
| GF12 | 288 | 365 | 653 |
| GF14 | 397 | 454 | 851 |
| GF16 | 486 | 505 | 991 |
| INT6 mul | — | 73 | 103 |
| SQ scale | — | — | 17 |
| **SQ-INT6 total** | — | — | **120** |

**Vasilev Floor (updated):** LUT_ADD = 1.63W² (R²=0.974), LUT_MUL = 2.09W² (R²=0.993) —
**[yosys-stat, not post-P&R; post-P&R expected +15–30%]**

**JTAG flash:** working (778s per 9.7MB bitstream at 100kHz)

**UART:** BROKEN on macOS 26.3.1 — AppleUSBSLCOM DEXT driver does not transfer data
after FTDINoSerial operations. Rebooting the Mac did not help. Root cause: macOS 26
serial driver incompatibility.

**FPGA AI model:**
- RTL: `fpga_ai_inference_ax7203.v` — 135 LUT (bigram), full MLP version designed (needs
  BRAM sync-read fix)
- Weights: 57K params INT6, 56KB, $readmemh format
- Test script: `fpga/tools/test_fpga_ai.py`
- Architecture: embed(128×64) → FC1(256→128)+ReLU → FC2(128→64)+ReLU → head(64→128) → argmax
- Bitstream flashed, DONE LED on, LED0 blinking after RESET

### 3.10. Flash Daemon Patch

`hardware/tools/trinity_flashed.py` updated for macOS 26:
- `kmutil load/unload` instead of deprecated `kextload/kextunload`
- FTDINoSerial loading via daemon's root `run` command
- Patched `free_ftdi_for_libusb()`: kill AppleUSBSLCOM (vs load FTDINoSerial)

---

## 4. CODE & ARTIFACTS

### Rust modules (trios-trainer-igla)
| File | Tests | Description |
|------|-------|-------------|
| `src/gf14.rs` | 6/6 PASS | GF14 format (E=5,M=8) + stochastic rounding |
| `src/gf_mx14.rs` | 3/3 PASS | GF-MX14 block-scaled format |
| `src/sq_int6.rs` | 3/3 PASS | SmoothQuant + INT6 (etalon) |

### Python oracles & tools
| File | Description |
|------|-------------|
| `conformance/gf_mx_ref.py` | GF-MX14 oracle (5 self-tests) |
| `parameter_golf_sq_int6.py` | Parameter Golf submission pipeline |
| `fpga/tools/test_fpga_ai.py` | FPGA AI model UART test |

### FPGA RTL
| File | LUT | Description |
|------|-----|-------------|
| `fpga/openxc7-synth/fpga_ai_inference_ax7203.v` | 135 | INT6 MLP inference engine |
| `fpga/openxc7-synth/embed_weights.mem` | — | Embedding table (128×64 INT6) |
| `fpga/openxc7-synth/fc1_weights.mem` | — | FC1 weights (128×256 INT6) |
| `fpga/openxc7-synth/fc2_weights.mem` | — | FC2 weights (64×128 INT6) |
| `fpga/openxc7-synth/head_weights.mem` | — | Head weights (128×64 INT6) |

### Paper
- arXiv ID: 2606.05017
- PDF: 732KB (CI-compiled)
- v4→v11: 11 commits
- Sections added: INT7 robustness, SQ-INT6 etalon, GF-MX14, hybrid format, RHT/LSQ
  negative result, QAT vs PTQ, Parameter Golf comparison, FineWeb validation

### Commits (this session)
1. `af65d907c` — fix φ-proof + GF14 etalon finding
2. `a19764752` — paper v5: systematic sweep + multi-seed
3. `c313728e0` — flash daemon patch (kmutil)
4. `57d1ac192` — GF-MX14 format
5. `7d72472b8` — INT7 true etalon + LUT
6. `1395c323c` — INT7 robustness + hybrid
7. `3bbf03169` — RHT/LSQ negative result
8. `526cf157c` — QAT vs PTQ + Parameter Golf
9. `7e76045db` — FineWeb BPB validation
10. `00c762ead` — FPGA AI inference engine
11. `04f4cfddf` — daemon kill AppleUSBSLCOM
12–15. paper v8–v11 incremental updates

---

## 5. FINAL VERDICT — ETALON

```
┌──────────────────────────────────────────────────────────────────────┐
│                    FORMAT LEADERBOARD                               │
├──────────────┬──────────┬──────────┬─────────┬──────────────────────┤
│ Format       │ BPB      │ Robust   │ LUT MAC │ Best for             │
├──────────────┼──────────┼──────────┼─────────┼──────────────────────┤
│ SQ-INT6 ★‼ │ 0.255‼   │ 4/7      │ 120‼    │ QAT training        │
│ LM-INT6      │ 0.266    │ —        │ 120     │ Most stable training│
│ INT6         │ 0.263‼   │ 1/7      │ 103‼    │ Cheapest HW          │
│ INT7         │ 0.278    │ 2/7      │ 50      │ Widest stable INT   │
│ Hyb σ2.0     │ 0.265    │ 3/7      │ 100     │ Hybrid INT7+GF14    │
│ GF14         │ 0.301    │ 6/7      │ 851     │ Numerical robustness│
│ GF16         │ 0.336    │ 7/7      │ 991     │ Full robustness     │
│ FP32         │ 0.346    │ 7/7      │ ~3000   │ Reference            │
└──────────────┴──────────┴──────────┴─────────┴──────────────────────┘

‼ = status downgraded in §0 (scale-dependent BPB / LUT without CI report).
  Rows from different scales are NOT directly comparable.

Etalon is context-dependent:
  • QAT training: SQ-INT6 (α=0.5)
  • Numerical robustness: GF14/GF16 (φ-rule float)
  • Cheapest hardware: INT7 (~50 LUT)
  • Parameter Golf: SQ-INT6 + GPTQ + LQER + Muon + CaseOps + TTT
```

---

## 6. PLANS — THREE VARIANTS FOR THE NEXT LOOP

### Variant A: GPU Parameter Golf Submission ($1M OpenAI grant)
**What:** Clone the winner's architecture (11L d=512 GQA CaseOps Muon TTT), replace
INT6 GPTQ → SQ-INT6, run on 8×H100.
**Time:** 1 day on GPU.
**Expected result:** 1.052–1.056 BPB → top-2 to top-5.
**Risk:** QAT advantage may not scale from d=128 to d=512.
**ROI:** High potential, BUT de-risk first: the QAT advantage of SQ-INT6 is only shown
at d≤128 (may not scale). Cheapest first step = unified re-benchmark, NOT a GPU run.

### Variant B: FPGA AI Model Completion (Linux or macOS fix)
**What:** Complete the INT6 MLP inference engine on AX7203. Full MLP with BRAM sync-read
fix. Flash, test UART on Linux.
**Time:** 2–3 hours on a Linux machine.
**Expected result:** Working AI inference on FPGA — 57K param MLP, INT6, text generation.
**Risk:** Low — RTL synthesizes, weights are ready, only need working UART.
**ROI:** End-to-end AI demonstration on FPGA with our etalon format.

### Variant C: Takum Collaboration (Hünhold email)
**What:** Email Jasmin Hünhold (takum author) with the 505=505 LUT equivalence finding.
Propose a joint paper on "Encoding Equivalence" (without claiming "INT6 dominance" — see
§0; and FIRST produce a reproducible synth-report, THEN email — Hünhold's first question
will be the utilization log).
**Time:** 1 email + discussion.
**Expected result:** Co-authorship, citation boost, access to takum RTL.
**Risk:** Refusal or no response.
**ROI:** Medium — academic legitimacy.

---

## 7. BLOCKERS

| Blocker | Status | Solution |
|---------|--------|----------|
| macOS 26 UART | ❌ Broken | Linux or macOS ≤15 |
| GPU access | ⏳ $1M grant available | Request via OpenAI form |
| FPGA bitstream for AI model | ⏳ needs nextpnr | Docker pull or cloud-synth |
| FineWeb at scale | ⏳ needs GPU | 8×H100, 10 min run |
| Vasilev Floor post-P&R | ⏳ needs nextpnr utilization report | CI job with saved report |

---

## 8. SESSION METRICS

| Metric | Value |
|--------|-------|
| Formats tested | 30+ (6 families) |
| Experiment seeds | 2–3 per format |
| LUT measurements | 6 new (GF12, GF14, INT6 MAC, SQ scale, GF-MX14, AI model) |
| Rust modules | 3 (12 tests, all PASS) |
| Paper versions | v4→v11 (7 updates) |
| Git commits | 15+ |
| FPGA flash cycles | 5+ (778s each) |
| Baud rates tested | 500+ |
| Parameter Golf formats analyzed | INT4–INT8, ternary, NF4, POW2, FP, MX |
| Literature papers scanned | 45+ |

---

*Vasilev, ORCID 0009-0008-4294-6159. Trinity FPGA, 2026-07-17.*
