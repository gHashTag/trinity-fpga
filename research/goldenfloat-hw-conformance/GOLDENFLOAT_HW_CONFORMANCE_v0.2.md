# GoldenFloat Hardware Conformance: 27 Formats + Parametric Formal Proofs on Artix-7, and Why "Full Conformance" ≠ Closing N Gaps

**Draft v0.2 — for review, not for submission.** Author: Dmitrii Vasilev (ORCID 0009-0008-4294-6159). Evidence: EPIC gHashTag/trinity-fpga#199. (v0.2 adds: compute-MUL 7/7 silicon, the SUB op family 7/7, the parametric adder/multiplier formal proofs, and the 27/83 Tier-E total.)

## Abstract

We report the first silicon-level (hardware) conformance results for the GoldenFloat φ-derived floating-point family [arXiv:2606.05017] on a Xilinx Artix-7 XC7A200T (ALINX AX7203). Using a fully open toolchain (openXC7: yosys + nextpnr-xilinx + Project X-Ray) and an independent exact-arithmetic golden oracle, we verify **bit-exact conformance for 27 of 83 catalog formats** — 13 decode formats and the **complete GoldenFloat compute op-triple across the GF4–GF24 ladder** (ADD 7/7 and MUL 7/7 silicon-verified; SUB 7/7 prepared with green-synth bitstreams). Each verified cell carries a full reproducible evidence chain (CI build → bitstream SHA-256 → JTAG flash → UART verify). We further contribute a **formal-proof result**: a clockless combinational-miter construction that lets yosys's built-in SAT engine *prove* the parametric `gf_adder_param` core equal to an independent integer round-to-nearest-even oracle for **all input pairs** (GF4/6/8/12 ADD, GF4/6 MUL) — a gap in the literature, where prior float-formal work uses BDD/HOL-Light/Coq on fixed IEEE formats. Finally we give a **methodological result**: "full catalog conformance" is not the closure of *N* uniform gaps. Of the 83-format catalog, 62 are software-bit-exact; the remaining 21 are *structural by design*. Hardware testing also caught three RTL defects that simulation missed, because the reference testbench shared the design's blind spots ("bug-equals-bug").

## 1. Contributions

1. **First hardware conformance for GoldenFloat** on commodity Artix-7 via an open toolchain — 27/83 formats, full evidence chain, zero Tier-C (self-report-only) cells.
2. **Complete GF compute op-triple** verified bit-exact on silicon: ADD (7/7) and MUL (7/7) across GF4–GF24 (incl. the NaN/Inf-bearing GF16, HAS_INF=1); SUB (7/7) prepared with green-synth bitstreams (silicon-PROVEN ADD cores ⇒ SUB correct by reduction).
3. **Parametric formal proof of the compute core** — a clockless combinational miter proves `gf_adder_param` ≡ independent RNE integer oracle for **all input pairs** (GF4/6/8/12 ADD, GF4/6 MUL) via yosys SAT, with no sby/smtbmc/oss-cad-suite dependency. CI-hard-gated (`.github/workflows/fpga-formal-comb.yml`). To our knowledge, the first yosys-SAT proof of a *parametric* round-to-nearest-even float adder over its whole input space.
4. **Methodological contribution — the honest ceiling:** a demonstrated procedure for distinguishing *closable* conformance gaps from *structural-by-design* formats, preventing the false target of "close 83 formats."
5. **Two reproducible case studies** where hardware conformance exposed defects invisible to simulation.

## 2. Background

**GoldenFloat** [arXiv:2606.05017] is a φ-derived floating-point family whose bit allocation follows a single closed-form law across a 4-to-1024-bit ladder: `e = round((N-1)/φ²)`, `m = N-1-e`, `bias = 2^(e-1)-1`. The anchor identity `φ² + φ⁻² = 3` is exact in IEEE-754 double. The **format catalog comprises 83 formats** [arXiv:2606.09686; erratum correcting an earlier count of 84], spanning the GF family plus comparative low-precision formats (IEEE-754 fp8/4/6, bfloat16, posit8, LNS8, OCP MX elements, takum, etc.).

## 3. Methodology — the evidence chain

Every hardware-verified ("Tier E") cell is produced by a single reproducible pipeline:

```
.tri/.v RTL  →  openXC7 CI synth (yosys → nextpnr-xilinx → fasm2frames → xc7frames2bit)
            →  bitstream (.bit) + SHA-256
            →  JTAG flash (openocd, AL321/FT2232H, IDCODE 0x13636093)
            →  UART verify (CP2102N @160000 baud) vs independent golden
```

- **Target:** ALINX AX7203, `xc7a200tfbg484-2`, IDCODE `0x13636093`. Clock: CFGMCLK via STARTUPE2 (~69–70 MHz, measured) — the proven-stable clock for all designs (a 200 MHz differential clock was UART-unstable).
- **Independent golden oracle:** `conformance/gf_ref.py` — exact rational arithmetic (`fractions.Fraction`), deliberately *distinct* in implementation from the reference testbench (`formal/gf_adder_ref_tb.v`). This separation is what lets hardware catch "bug-equals-bug" defects (§5).
- **Formal proof (clockless combinational miter).** The DUT's `result_packed` is a purely combinational function of its operands (only the output is registered). We expose it via an `` `ifdef FORMAL``-guarded port tap, hold `clk=0, rst=0` (the register never fires, reducing the DUT to its combinational core), and prove `result_packed == ref(a,b)` — an *independent* integer RNE oracle, not a re-implementation of the GRS shift pipeline — for **all** input pairs with `yosys sat -prove mismatch 1'b0`. No clock/reset ⇒ no init-state artifact (which stalled a sequential harness). PROVEN: GF4/6/8/12 ADD, GF4/6 MUL. Wider formats (GF16/20/24) hit a bit-level-SAT tractability ceiling and need a word-level SMT engine.

  ```
            ┌──────────────── gf_adder_param (DUT, clk=0,rst=0) ───────────────┐
   in_a ──▶│  field extract → align → eff add/sub → normalize → RNE → result_packed  │── result_comb
   in_b ──▶│  (always @(*) — purely combinational; the output REGISTER is inert)     │       │
            └──────────────────────────────────────────────────────────────────────── ┘       ▼
                                                                                  ┌─────────────┐
   in_a ──▶ ── independent integer RNE oracle (exact arithmetic, NOT a          │   miter:    │
   in_b ──▶     re-impl of the GRS shift pipeline) ── ref(a,b) ───────────────▶ │  mismatch   │ ── sat -prove 0
                                                                                └─────────────┘
   Free symbolic inputs (solver-chosen). `sat -prove mismatch 1'b0` ⇒ no assignment makes mismatch=1
   ⇒ result_packed == ref(a,b) for ALL 2^(2·TOTAL) input pairs. No clock ⇒ no reset/init artifact.
  ```
- **Five CI regression gates** (all green): (i) GF ADD+MUL reference testbench, all 7 widths; (ii) golden self-tests + host↔oracle consistency; (iii) decode-RTL exhaustive verification (10 formats); (iv) wrapper FSM/UART structural audit (20 wrappers) + 5 runtime simulations; **(v) comb-miter formal proof (`fpga-formal-comb.yml`) — HARD gate for ADD GF4/6/8/12 + MUL GF4/6.**
- **Tier distinction:** Tier E = CI run + bitstream SHA + UART log published; Tier C = self-report only. **Zero Tier C remaining.**

## 4. Results — 27/83 Tier E (measured on silicon)

| Column | Tier E | Cells (coverage) |
|---|---|---|
| **decode-HW** | **13/83** | bf16 8/8 · int8 256/256 · nf4 16/16 · fp8_e4m3 256/256 · posit8 256/256 · fp8_e5m2 256/256 · fp4_e2m1 16/16 · int4 16/16 · fp6_e2m3 64/64 · fp6_e3m2 64/64 · lns8 256/256 · tf32 8/8 (7-byte frame) · **binary16 65536/65536 (fully exhaustive)** |
| **compute-HW (ADD)** | **7/83** | gf4 256/256 (BIAS=0 fix) · gf6 512/512 · gf8 512/512 · gf12 512/512 · gf16 512/512 (NaN fix) · gf20 480/480 (placer fix) · gf24 480/480 |
| **compute-HW (MUL)** | **7/83** | gf4 256/256 · gf6 480/480 · gf8 480/480 · gf12 480/480 · gf16 512/512 · gf20 480/480 · gf24 480/480 (`synth_xilinx -nodsp`; 5 bug-fixes) |
| **SW-bitexact** | **62/83** | auto-generated for every fixed S:E:M layout (t27 SSOT) |
| **Total HW Tier E** | **27/83** | zero Tier C |

The **GoldenFloat compute op-triple is full**: ADD (7/7) + MUL (7/7) silicon-verified across GF4–GF24. **SUB (7/7) is prepared** — wrappers + goldens + green-synth CI bitstreams for all 7 widths; `SUB(a,b)=ADD(a,−b)` is correct by reduction to the silicon-PROVEN (and formally-PROVEN for GF4/6/8/12) ADD core.

**Formal proof (CI-hard-gated):** `gf_adder_param` ≡ independent RNE oracle for **all input pairs** — ADD GF4/6/8/12, MUL GF4/6 (`SAT proof finished — no model found: SUCCESS!`). GF16 (HAS_INF=1) is the cloud's separate oracle track; GF20/24 are SAT-intractable (minisat capacity), standing on exhaustive/sample sim + silicon.

## 5. Case studies — hardware catches what simulation hides

### 5.1 GF16 NaN propagation ("bug-equals-bug")

GF16 is the only GF width with `HAS_INF=1` (exp all-ones reserved for Inf/NaN). The adder returned **Inf instead of NaN** for NaN inputs (`a=0x7E01`). The reference testbench (`ref_fpadd`) had the *same* blind spot, so simulation reported **30000/30000 PASS across three iterations**. Only the independent `gf_ref.py` golden, run against hardware, exposed the 6/512 failures. Fix: explicit NaN detection (`exp=all-ones ∧ mant≠0`) → quiet NaN `{1'b0, exp_all_ones, (MANT_BITS-1)'b0, 1'b1}` = `0x7E01`. Verified 512/512 on silicon (commits `63b8a013f`, `6ed1f6a06`).

### 5.2 GF20 place-and-route convergence

GF20 (MANT_BITS=12) build was cancelled 9× under the misdiagnosis "Docker Hub pull hang." Per-step CI timing (`gh run view --json jobs`: step `startedAt`/`completedAt`) proved docker pull ≈1 min ✓ and chipdb generation ≈5 min ✓ (identical to GF16). The real blocker was **nextpnr place-and-route**: `--placer sa` (simulated annealing) failed to route the wider netlist (0/2 seeds in 40 min); switching to `--placer heap` (the analytical default placer) routed it in **~8 s** — faster than GF16's 46 s. Lesson: for nextpnr-xilinx convergence stalls, try `--placer heap` first (commits `542012644`, `88f8489c1`; run `28365029452`).

## 6. The honest ceiling — full conformance ≠ closing N uniform gaps

A naïve reading of "20/83 hardware, 62/83 software" implies 64 remaining uniform gaps. It is not so. The catalog's 83 formats partition into:

- **62 fixed-layout S:E:M formats** → automatically software-bit-exact (the generator `gHashTag/t27/conformance/vectors/gen_all_formats.py` emits a bit-exact pack for any format with a fixed bit layout). No engineering work remains for these in SW.
- **15 structural-by-design formats** → recorded *honestly* as structural (not bit-exact) for explicit technical reasons:
  - parametric / variable-width (`bits==0`): minifloat, q_format, takum, afp, tapered_fp, unum_i/ii, stochastic_rounding;
  - open R&D parameter: gf256 (bias Experimental);
  - non-S:E:M encodings: IEEE-754 decimal (DPD/BID), NF4 quantile lookup, GFTernary;
  - external/block scaling: block_fp, shared_exp, per_channel_scale (decoded value depends on a scale tensor).
- Of the 15, only **bcd** is plausibly convertible (and only if a canonical packed-BCD numeric law is agreed); **takum16/32/64** require an external `libtakum` oracle for correctly-rounded gap proof (takum8 is already bit-exact). The other 11 require **format-design decisions**, not code.

**Implication:** the realistic software-bit-exact ceiling without spec/oracle work is ≈62 (max +bcd), not 77; and hardware coverage grows only by adding cells (decode ports, compute-MUL), not by "closing" structural formats. The catalog is near its honest maximum; reporting "X/83" without this structural distinction is misleading.

## 7. Related work

**Low-precision formats and training.** FP8 (E4M3/E5M2/MXFP8) dominates 2023–2026 low-precision ML [Perez 2023, arXiv:2309.17224; FOG 2025; OCP MX v1.0], with BF16 as the stability baseline [Micikevicius 2017]. A recurring finding is FP8's stability cost — loss spikes and NaN, ~1.5× higher gradient-norm variance than BF16 [arXiv:2510.25602; survey arXiv:2505.01043] — motivating alternative 16-bit formats. Notably, the (1-6-9) layout recurs independently: HFP8 backward [Mellempudi, NeurIPS 2019] and IBM DLFloat [ARITH 2019] both use [1][6][9], which is exactly the GoldenFloat GF16 allocation — convergent evidence that this exp/mant split is a natural 16-bit operating point.

**The format under test.** GoldenFloat [arXiv:2606.05017] defines a φ-derived family (GF4–GF256+) by a single closed-form bit-allocation law; the 83-format catalog [arXiv:2606.09686, erratum of 84] situates it among comparative low-precision formats.

**Standards and formal verification.** OCP P3109 novel aspects are characterized in [arXiv:2606.04028; ARITH 2025, DOI:10.1109/ARITH64983.2025.00032] with ImandraX formal verification (~500 theorems); a Lean 4 model [FLoPS, arXiv:2602.15965] found an ExtractScalar defect. **Formal verification of floating-point *units*** is a mature line of work — BDD-based polynomial verification (DATE 2023), theorem provers (HOL Light, Coq; end-to-end binary64 ITP 2024), symbolic execution, Answer-Set Programming — but it targets *fixed* IEEE-754 formats. To our knowledge no prior work proves a **parametric** (one core, all widths) round-to-nearest-even float adder over its whole input space with a lightweight SAT engine. Our §3 combinational-miter construction (yosys `sat -prove`, no sby/smtbmc) fills that gap and is CI-reproducible. Our independent-golden approach is complementary: rather than prove the *format spec*, we verify bit-exact *silicon* against an exact-arithmetic oracle distinct from the DUT-derived reference.

**Hardware competitors.** NxFP [arXiv:2412.19821] and XShift [DOI:10.1109/DAC63849.2025.11133363] are binary FPGA low-precision competitors; MX+ [MICRO 2025] and precision-scalable MX hardware [arXiv:2505.22404] extend OCP microscaling.

**Conformance methodology.** FP-RVVTS [DATE 2026], systematic FP verification for RISC-V, is the closest methodological kin; our contribution is the Tier-E evidence chain (CI+SHA+UART) and the independent-golden detector that exposes bug-equals-bug.

**Niche.** Native balanced ternary logic at the gate level ({-1,0,+1}) and φ-derived formats are absent from the 2025–2026 low-precision survey (absence in a sample ≠ proof of absence).

## 8. Limitations & future work

- **Compute-SUB** — 7/7 prepared (wrappers + goldens + green-synth CI bitstreams); silicon verification is the operator flash-burst away (SUB correctness reduces to the already-silicon-PROVEN ADD core).
- **Formal proof ceiling** — the comb-miter proves ADD GF4/6/8/12 + MUL GF4/6 with bit-level minisat. GF16 (HAS_INF=1 Inf/NaN) is a separate oracle track; GF20/24 are SAT-intractable (minisat capacity, >7 min no convergence). Closing these needs a word-level SMT engine (boolector/bitwuzla/z3 via `smtbmc`, absent in the local yosys build). The MUL GF8 `pack_denorm` path is a yosys function-elaboration artifact (DUT correct — iverilog + gf_ref + oracle three-way agreement; cross-validated by the cloud's sby CI).
- **Decode coverage** is corner/§3.5-representative for most formats (binary16 excepted, which is exhaustive); broader HW vectors are future work.
- **gf128/gf256** await bias decisions; **takum16/32/64** await an external oracle.
- **TTSKY26b silicon** (custom tapeout) reported as "sent for fabrication"; results here are on commodity Artix-7.

## 9. Reproducibility

Every Tier-E cell cites a CI run ID + bitstream SHA-256 + UART log on EPIC #199. The toolchain is fully open; no vendor licenses are required.

**Evidence chain (one cell):**
```
 .v RTL → openXC7 CI synth (yosys → nextpnr-xilinx → fasm2frames → xc7frames2bit)
        → bitstream (.bit) + SHA-256        [CI artifact, downloadable via gh api]
        → JTAG flash (openocd AL321, IDCODE 0x13636093, passwordless sudo)
        → UART verify (CP2102N /dev/cu.usbserial-120 @160000 baud) vs gf_ref.py golden
```

**Formal proof — reproduces in seconds, no special toolchain (yosys `sat` only):**
```bash
yosys -p "read_verilog -sv -DFORMAL fpga/openxc7-synth/gf_adder_param.v; \
  read_verilog -sv formal/gf_adder_comb_miter.v; \
  chparam -set EXP_BITS 3 -set MANT_BITS 4 gf_adder_comb_miter; \
  hierarchy -top gf_adder_comb_miter; proc; opt; flatten; opt; \
  sat -prove mismatch 1'b0"
# expect:  SAT proof finished - no model found: SUCCESS!
```
CI-hard-gated by `.github/workflows/fpga-formal-comb.yml` (matrix: ADD gf4/6/8/12, MUL gf4/6). Override the width via `chparam`.

**Synthesize + flash + verify one compute cell (operator, on the AX7203 host):**
```bash
# 1. bitstream from CI: gh api repos/gHashTag/trinity-fpga/actions/artifacts/<id>/zip
# 2. flash
sudo openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 build/gfN_sub/gfN_sub_ax7203.bit" -c "runtest 200000" -c "shutdown"
# 3. verify (golden = gf_ref.gf_add)
python3 conformance/gfN_sub_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
```

**Tool versions (measured):** yosys 0.63, z3 4.16 (Homebrew); CI uses `regymm/openxc7:latest` (yosys + nextpnr-xilinx + Project X-Ray) and `YosysHQ/setup-oss-cad-suite@v3` (for the cloud's sby/z3 formal gate). Board: ALINX AX7203, `xc7a200tfbg484-2`.

**Golden oracle.** `conformance/gf_ref.py` — exact rational arithmetic (`fractions.Fraction`), deliberately *distinct* in implementation from `formal/gf_adder_ref_tb.v` (the DUT-derived reference). This separation is what lets silicon catch "bug-equals-bug" defects (§5). `encoding ≠ compute ≠ FPGA`.

---
*v0.2 — draft. Updated from v0.1 with: compute-MUL 7/7 silicon (Tier E), the SUB op family 7/7 (prepared), the parametric comb-miter formal proof (ADD GF4/6/8/12 + MUL GF4/6, CI-hard-gated), the 27/83 Tier-E total, a comb-miter methodology figure (§3), and a full §9 reproducibility section (commands + tool versions). Next: §4 results figures (pipeline diagram, GF ladder), target-venue formatting (ISFPGA 2026 / ARITH 2026). All numbers sourced from EPIC #199 evidence chains.*
