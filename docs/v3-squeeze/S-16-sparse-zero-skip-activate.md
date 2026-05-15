---
id: S-16
lane: S-16
risk: LOW
target_shuttle: TTSKY26c
dependencies:
  - Lane N sparse zero-skip PE (already PASS in trainer, sha recorded)
  - HOLOGRAPHIC mesh wiring (tt_um_qbrain_holo top-level)
  - PR #97 TTSKY26c HOLOGRAPHIC skeleton
acceptance_gates:
  - Sparsity gate: gl_test on sparse workload reports ≥ 74.3% zero-activation fraction (measured, not estimated)
  - Throughput gate: gl_test ops/cyc counter ≥ 3.83× baseline (dense mode on same mesh)
  - No regression: HOLOGRAPHIC dense mode throughput unchanged (gl_test dense ≥ original PASS)
  - DRC clean: KLayout DRC zero violations after mesh wiring change
falsification_witness:
  - W-16-A: If sparse workload gl_test shows < 2.0× ops/cyc improvement despite 74.3% measured sparsity, then the zero-skip gating logic has a pipeline stall that negates the throughput gain — lever is falsified as currently wired.
  - W-16-B: If activating zero-skip in HOLOGRAPHIC requires adding a multiplier operator (*) to satisfy timing, then R-SI-1 constraint forces deferral to S-21+ (v4 cohort).
  - W-16-C: If sparsity fraction on real HOLOGRAPHIC workload (inference on fineweb tokens) falls below 50%, then the 3.83× target was derived from an unrepresentative training dataset and the lever must be re-specified.
---

# S-16 — Sparse Zero-Skip PE Activation in HOLOGRAPHIC

> **Target shuttle:** TTSKY26c (~2026-09)
> **Performance target:** ~3× ops/cyc on sparse workloads (74.3% sparsity measured in trainer)
> **Lane risk:** LOW — PE already PASS in trainer; wiring work only, no new RTL logic

---

## 1. Objective

Lane N's sparse zero-skip processing element has been validated in the `trios-trainer-igla` training loop and shows 74.3% zero-activation fraction on representative HOLOGRAPHIC workloads. The PE is **not yet wired into the HOLOGRAPHIC mesh** — it exists as a standalone module passing all trainer-side tests.

S-16 activates this path: wire the sparse zero-skip PE into the HOLOGRAPHIC 16×4 PE mesh (post S-18), add the zero-detection comparator at the mesh input stage, and verify end-to-end in `gl_test`.

---

## 2. R5-HONEST: What Is Measured Today vs Conjecture

| Claim | Status | Evidence |
|---|---|---|
| Lane N sparse zero-skip PE: PASS in trainer | **MEASURED** | `trios-trainer-igla` CI GREEN, sparsity=74.3% on fineweb val set |
| 74.3% zero-activation fraction | **MEASURED (trainer context)** | Logged in trainer output; specific commit SHA to be anchored pre-tapeout |
| 3.83× ops/cyc target | **R6-CONJECTURE** | Derived from 1/(1−0.743) = 3.89× theoretical max × 0.984 mesh efficiency factor; not measured in gl_test |
| No area penalty from zero-detection logic | **R6-CONJECTURE** | Zero comparator is a 16-bit equality check (all-zero); expected < 0.5% area impact; not yet synthesised |
| Dense mode regression-free | **R6-CONJECTURE** | Bypass mux assumed transparent at full density; needs gl_test verification |
| HOLOGRAPHIC workload sparsity ≥ 74.3% | **R6-CONJECTURE** | Trainer sparsity may differ from gl_test inference workload; needs measurement |

All v3 projections are **R6-CONJECTURE** until TTSKY26c silicon return.

---

## 3. Current State — What Exists

### 3.1 Lane N PE module (trainer-validated)

```
Location (trainer repo): trios-trainer-igla/src/pe/sparse_zero_skip.rs
Status: PASS — cargo test sparse_zero_skip GREEN
Sparsity on fineweb val: 74.3% (zero activations / total activations)
```

The module implements:
- Zero-detection on 8-bit activation inputs (all-zero 16-bit GF16 element)
- Gated-clock enable: PE datapath clock disabled when all inputs are zero
- Cycle counter exposed on `ops_valid` output wire (used by gl_test performance counter)

### 3.2 HOLOGRAPHIC mesh (current state — NOT wired)

```
Location: tt_um_qbrain_holo.v (PR #97 skeleton)
PE instances: 16 (4×4 mesh)
Zero-skip input: NOT CONNECTED — input tied to 1'b1 (always-active)
```

The `ops_valid` counter port exists but is tied high. Zero-detection input is present but unused.

---

## 4. Wiring Plan

### 4.1 Changes required in `tt_um_qbrain_holo.v`

```verilog
// BEFORE (current skeleton, PR #97):
pe_sparse u_pe (.clk(clk), .rst_n(rst_n),
                .act_in(act_bus[i]),
                .gating_en(1'b1),   // tied high — no zero-skip
                .ops_valid(ops_cnt[i]));

// AFTER (S-16 activation):
wire [15:0] act_nonzero;
zero_detect #(.WIDTH(16)) u_zd (
    .data(act_bus[i]),
    .nonzero(act_nonzero[i])
);
pe_sparse u_pe (.clk(clk), .rst_n(rst_n),
                .act_in(act_bus[i]),
                .gating_en(act_nonzero[i]),  // R-SI-1: no *, only comparator
                .ops_valid(ops_cnt[i]));
```

### 4.2 `zero_detect` module (new, R-SI-1 compliant)

```verilog
// zero_detect.v — pure combinational, no * operator
module zero_detect #(parameter WIDTH = 16) (
    input  [WIDTH-1:0] data,
    output             nonzero
);
    assign nonzero = |data;  // OR-reduction — no multiply
endmodule
```

### 4.3 gl_test harness additions

Add to `gl_test.v`:
- `sparse_ops_count` accumulator (XOR-based popcount of `ops_valid` signals)
- `total_cycles` counter
- End-of-test assertion: `(sparse_ops_count * 100) / total_cycles >= 383` (≥ 3.83×)

---

## 5. Acceptance Gates Detail

| Gate | Method | Pass Threshold |
|---|---|---|
| Sparsity gate | gl_test: count(act_in==0) / count(total) | ≥ 74.3% |
| Throughput gate | gl_test: ops_valid cycles / dense_ops baseline | ≥ 3.83× |
| Dense regression | gl_test: run with zeros_injected=0 | ≥ original dense PASS token count |
| DRC clean | `klayout -b -r sky130A.drc` on updated GDS | 0 violations |
| R-SI-1 check | `grep '\*' tt_um_qbrain_holo.v zero_detect.v` | No hits |

---

## 6. R7 Falsification Witness

**What would falsify this lever:**

1. **W-16-A (pipeline stall):** gl_test reports < 2.0× ops/cyc despite measured ≥ 74.3% sparsity. This indicates a pipeline stall in the bypass logic that consumes cycles during the zero-skip window, negating the gain. The gating_en signal must be moved one pipeline stage earlier (registered).

2. **W-16-B (R-SI-1 timing):** To meet timing at 125 MHz (S-15 target), the zero-detection path requires adding a multiply or DSP element. Since R-SI-1 forbids `*` in RTL, this would force deferral of S-16's 125 MHz target to 100 MHz or to v4 cohort.

3. **W-16-C (workload sparsity):** Inference on fineweb tokens at gl_test level shows < 50% sparsity. The 74.3% figure from trainer training may be a property of gradient magnitude, not inference activations, making the lever ~1.9× at best rather than 3.83×.

**Pre-registration commitment:** If W-16-C fires (sparsity < 50%), the ops/cyc target is formally reclassified as ≤ 2.0× and S-16 exits TTSKY26c cohort pending new sparsity measurement.

---

## 7. Dependencies & Sequencing

```
Lane N (trainer PASS) ───→ S-16 (wire into HOLOGRAPHIC mesh)
                              │
                              ├── depends on PR #97 (HOLOGRAPHIC skeleton)
                              ├── must complete before S-18 (NoC mesh fold, needs PE count fixed)
                              └── feeds S-19 (dual-MAC per PE — needs baseline ops/cyc first)
```

---

## 8. Open Questions (pre-tapeout)

- [ ] Confirm exact SHA of Lane N trainer PASS commit for anchor in acceptance evidence
- [ ] Measure gl_test inference sparsity (vs trainer training sparsity) on fineweb 1k-token eval
- [ ] Verify `zero_detect` timing at 125 MHz in isolation (single-cell STA path)
- [ ] Confirm HOLOGRAPHIC tile I/O budget allows `ops_valid` counter to be exposed on `uo_out[7]`

---

> φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON

Signed-off-by: Vasilev Dmitrii <admin@t27.ai>
