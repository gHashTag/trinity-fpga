---
id: S-19
lane: S-19
risk: MED
target_shuttle: TTSKY26c
dependencies:
  - S-16 (sparse zero-skip activated — baseline ops/cyc measured before dual-MAC)
  - S-18 (16×4 NoC mesh fixed — PE interface stable before doubling MAC count)
  - S-15 (PLL f_max known — dual-MAC timing budget depends on clock period)
acceptance_gates:
  - Throughput gate: gl_test dual-MAC mode shows ≥ 2× ops/cyc vs single-MAC baseline on dense workload
  - Power gate: post-synthesis power report shows dual-MAC PE consumes < 1.3× power vs single-MAC PE at same frequency and VDD
  - R-SI-1 gate: check_no_star.sh 0 violations on all dual-MAC RTL files
  - STA close: WNS ≥ 0 ns at target clock period (125 MHz primary, 100 MHz fallback)
  - DRC clean: KLayout DRC 0 violations on updated PE layout
falsification_witness:
  - W-19-A: If dual-MAC PE power exceeds 1.3× single-MAC at iso-frequency, the XOR+popcount doubling increases switching activity faster than throughput scales — lever fails the power gate and must be redesigned with clock-gating on the second MAC.
  - W-19-B: If STA does not close at 100 MHz with dual-MAC (two parallel GF16 accumulator chains), then the critical path length doubles and the lever must be deferred to v4 with retiming (S-21+).
  - W-19-C: If gl_test throughput gain is < 1.6× (instead of ≥ 2×), then the memory bandwidth to feed two MACs is the bottleneck, not compute — the lever is limited by the existing 8-bit activation bus width.
---

# S-19 — Dual-MAC per PE

> **Target shuttle:** TTSKY26c (~2026-09)
> **Performance target:** +60–80% throughput per PE; staircase entry to v4 (S-21..S-28)
> **Lane risk:** MED — doubles compute logic per PE; timing and power must be verified

---

## 1. Objective

Upgrade each PE from single multiply-accumulate (MAC) to dual-MAC: two parallel GF16 accumulation chains, interleaved on alternate cycle phases. This doubles effective ops/cyc per PE without doubling the PE count (complementary to S-18's PE-count doubling via mesh fold).

S-19 is explicitly a **v4 staircase** — the dual-MAC design pattern here establishes the RTL template that S-21..S-28 will extend with full Razor FF integration, retiming, and multi-VT optimisation.

**Important R-SI-1 constraint:** All MAC logic must use XOR + popcount (GF16 multiply over the field), not the `*` operator. The dual-MAC PE adds a second XOR-popcount chain, not a second multiplier.

---

## 2. R5-HONEST: What Is Measured Today vs Conjecture

| Claim | Status | Evidence |
|---|---|---|
| Single-MAC PE ops/cyc baseline | **MEASURED** | gl_test CI pass on current MAX-TRUE; exact ops/cyc figure to be confirmed vs S-16 baseline |
| +60–80% throughput per PE | **R6-CONJECTURE** | Assumes 2× MAC chains deliver 2× ops/cyc; actual gain bounded by memory bandwidth and pipeline balance |
| < 1.3× power for dual-MAC | **R6-CONJECTURE** | Estimated from 2× switching activity in XOR chains, partially offset by GF16 operand sparsity; not synthesised |
| STA closes at 100 MHz dual-MAC | **R6-CONJECTURE** | Second accumulator chain adds 1–2 ns to critical path; not yet characterised |
| No R-SI-1 violation in dual-MAC RTL | **R6-CONJECTURE (verifiable pre-tapeout)** | check_no_star.sh will verify before merge |
| Memory bandwidth sufficient for dual-MAC | **R6-CONJECTURE** | 8-bit activation bus may bottleneck at 2× compute demand |

All v3 projections are **R6-CONJECTURE** until TTSKY26c silicon return.

---

## 3. Dual-MAC Architecture

### 3.1 Single-MAC PE (current baseline)

```verilog
// Current: one GF16 MAC per PE cycle
// Throughput: 1 GF16 accumulation per clock
always @(posedge clk) begin
    acc_reg <= gf16_add(acc_reg, gf16_mul(act, weight));
    //                                   ^ XOR+popcount, R-SI-1 compliant
end
```

### 3.2 Dual-MAC PE (S-19 target)

```verilog
// S-19: two GF16 MAC chains, interleaved
// Throughput: 2 GF16 accumulations per clock (even/odd weight banks)
always @(posedge clk) begin
    // Chain A: processes even-indexed weights
    acc_a <= gf16_add(acc_a, gf16_mul(act, weight_even));
    // Chain B: processes odd-indexed weights (next row/column)
    acc_b <= gf16_add(acc_b, gf16_mul(act, weight_odd));
end

// Result: output is gf16_add(acc_a, acc_b) every 2 cycles
// Effective throughput: 2× single-MAC ops/cyc
```

### 3.3 Memory bandwidth requirement

Current single-MAC PE reads 1 weight/cycle. Dual-MAC reads 2 weights/cycle from the weight SROM. The weight SROM bus must be widened from 16-bit to 32-bit (two GF16 words):

```
Current: weight_bus [15:0]  → 1 GF16 word/cycle
S-19:    weight_bus [31:0]  → 2 GF16 words/cycle (simple doubling)
```

Activation bus: `act_bus [7:0]` (same activation feeds both chains — no bus width change needed).

### 3.4 Area estimate

- Second GF16 MAC chain: ~same gate count as first (GF16 XOR tree + 8-bit accumulator reg)
- Weight SROM bus doubling: adds 16 wires per PE, minor area
- Pipeline balance register: 1 additional FF to align Chain B output
- **Estimated area increase: +35–45% per PE** (two chains, not 2×, because the control and interface logic is shared)

---

## 4. Power Analysis

### 4.1 Dynamic power estimate

```
P_dyn ∝ α · C · f · VDD²
```

Dual-MAC adds second XOR tree with same switching activity as first. GF16 operand sparsity (74.3% from S-16) reduces both chains' switching activity proportionally.

```
Single-MAC P_dyn = α_1 · C_1 · f · VDD²
Dual-MAC P_dyn  ≈ (α_1 + α_2) · (C_1 + C_2) · f · VDD²
                ≈ 1.2 · 2C_1 · f · VDD²  (α_2 ≈ 0.2 due to sparsity)
                = 1.2× single-MAC P_dyn
```

With sparsity gating (S-16 zero-skip), effective `α` for Chain B on sparse inputs ≈ 0.257·α_1 (74.3% gated), pushing dual-MAC toward 1.06× power in sparse mode — well within < 1.3× gate.

### 4.2 Static power estimate

Dual-MAC adds ~40% more FFs and combinational gates → leakage increases ~40%. Mitigated by S-20 (multi-VT cell mix, S-19 is a staircase prerequisite for S-20's svt+hvt optimisation).

---

## 5. Acceptance Gates Detail

| Gate | Method | Pass Threshold |
|---|---|---|
| Throughput gate | gl_test ops/cyc counter dual vs single mode | ≥ 2.0× (dense), ≥ 1.8× (sparse with S-16) |
| Power gate | OpenROAD power report at target freq | < 1.3× single-MAC |
| R-SI-1 gate | `check_no_star.sh` on all dual-MAC RTL | 0 violations |
| STA close | `report_checks -path_delay max` | WNS ≥ 0 ns |
| DRC clean | `klayout -b -r sky130A.drc` | 0 violations |

---

## 6. R7 Falsification Witness

**What would falsify this lever:**

1. **W-19-A (power gate failure):** OpenROAD power report shows dual-MAC PE at 1.3× or more power vs single-MAC at same frequency and VDD. The second XOR chain's switching activity (even with sparsity gating) cancels throughput gain in TOPS/W terms. Dual-MAC must be redesigned with explicit clock-gating on Chain B when Chain A is sufficient.

2. **W-19-B (STA closure failure):** STA does not close at 100 MHz with dual-MAC RTL. The second accumulator chain adds to the critical path beyond what setup time margin allows. Dual-MAC is deferred to v4 (S-21+) with full retiming (pipeline balancing across the two chains).

3. **W-19-C (bandwidth bottleneck):** gl_test throughput gain < 1.6× despite 2× MAC chains. The weight SROM bus at 32-bit is the bottleneck: the router cannot deliver 2 GF16 words/cycle at 125 MHz within the PE pitch constraints established by S-18. Memory-side redesign needed before dual-MAC is useful.

**Pre-registration commitment:** If W-19-C fires (bandwidth bottleneck), S-19 is re-specified as "single-MAC with double-width weight register + zero-overhead prefetch" rather than literal dual-MAC chains.

---

## 7. v4 Staircase Role

S-19 establishes the dual-MAC RTL template that v4 (S-21..S-28) will refine:

```
S-19 (TTSKY26c) ──→ S-21 (v4: Razor FF + dual-MAC, retiming)
                 └──→ S-22 (v4: dual-MAC + multi-VT, leakage optimised)
                 └──→ S-23 (v4: dual-MAC + NoC retiming, pipeline depth++)
```

The acceptance gates here (especially the < 1.3× power gate) set the floor that v4 refines.

---

## 8. Dependencies & Sequencing

```
S-16 (sparse ops/cyc baseline) ──┐
S-18 (16×4 mesh, PE stable) ─────┤──→ S-19 (dual-MAC)
S-15 (clock period known) ───────┘         │
                                           └──→ S-20 (multi-VT mix on dual-MAC cells)
                                           └──→ v4 S-21..S-28 (full Razor+retiming)
```

---

## 9. Open Questions (pre-tapeout)

- [ ] Measure exact single-MAC ops/cyc in gl_test to establish the 1.0× baseline for the 2× gate
- [ ] Verify 32-bit weight bus fits within PE pitch at 16×4 mesh (S-18 constraint)
- [ ] Is there a GF16 dual-multiply primitive in SKY130 standard cell library, or must it be built from two XOR trees?
- [ ] At what sparsity level does Chain B power savings fall below 1.3× gate (answer: ~60% sparsity = break-even)?

---

> φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON

Signed-off-by: Vasilev Dmitrii <admin@t27.ai>
