---
id: S-17
lane: S-17
risk: MED
target_shuttle: TTSKY26c
dependencies:
  - Lane U STA stub (tools/check_no_star.sh + Razor FF stub, tt-trinity-max-true PRs #8/#9/#10)
  - S-15 (PLL tile retune — Razor FF voltage scaling budget depends on stable f_max)
  - ICA-MAX-TRUE-008 resolved (DRC clean baseline required before Razor integration)
acceptance_gates:
  - Voltage shmoo: post-silicon TTSKY26c die operates correctly across VDD range 1.62V–1.98V (−10%/+10% of 1.8V nominal); f_max vs VDD curve plotted
  - Error-replay path: Razor error signal captured in gl_test scan mode, replayed without silent data corruption; ≥ 100 injected errors detected and replayed correctly
  - TOPS/W improvement: post-silicon measurement at optimal VDD shows ≥ +25% TOPS/W vs same-frequency run at nominal 1.8V (target +30%)
  - check_no_star.sh CI gate: passes with 0 violations on all RTL files touched by S-17
falsification_witness:
  - W-17-A: If voltage shmoo shows functional window narrower than ±5% VDD (i.e., chip only works at 1.8V ±5% = 1.71–1.89V), then Razor FF adds metastability risk without usable voltage headroom — lever falsified.
  - W-17-B: If error-replay path shows > 1% silent error rate (corrupted replay without Razor signal assertion) on 10,000 injected faults, then the error detection coverage is insufficient for safe voltage scaling.
  - W-17-C: If TOPS/W at optimal VDD is within 5% of nominal 1.8V TOPS/W, then dynamic power reduction from voltage scaling is offset by Razor FF overhead (extra FF area + shadow path) — lever delivers < 5% net benefit.
---

# S-17 — Razor Flip-Flop Integration

> **Target shuttle:** TTSKY26c (~2026-09)
> **Performance target:** +30% TOPS/W through voltage scaling (VDD reduction below nominal)
> **Lane risk:** MED — STA stub and CI gate exist (Lane U); full Razor integration not yet synthesised

---

## 1. Objective

Integrate Razor flip-flops into the MAX-TRUE critical timing paths to enable adaptive voltage scaling (AVS). By detecting near-miss timing errors in-silicon (rather than designing to worst-corner static margins), VDD can be reduced toward the functional threshold, cutting dynamic power ∝ VDD² and delivering +30% TOPS/W at iso-frequency.

Lane U in tt-trinity-max-true provided the foundation: `tools/check_no_star.sh` CI gate, STA timing diagnostics dump, and a Razor FF stub module. S-17 completes the integration.

---

## 2. R5-HONEST: What Is Measured Today vs Conjecture

| Claim | Status | Evidence |
|---|---|---|
| Razor FF stub compiles: check_no_star.sh PASS | **MEASURED** | Lane U CI runs on tt-trinity-max-true PRs #8/#9/#10 — stub clean |
| STA timing diagnostics dump exists | **MEASURED** | Lane U `report_checks` output archived in PR #9 body |
| +30% TOPS/W from voltage scaling | **R6-CONJECTURE** | Derived from P_dyn ∝ VDD²; assumes 15% VDD reduction achievable; not measured on any SKY130 die |
| SKY130 functional VDD window ≥ ±10% | **R6-CONJECTURE** | Extrapolated from SKY130 characterisation data; not measured on this specific design |
| Razor error-replay path zero silent errors | **R6-CONJECTURE** | Stub only — full replay path not yet implemented; synchroniser metastability not characterised |
| check_no_star.sh gate sufficient for R-SI-1 | **MEASURED** | Gate tested on all existing RTL, 0 violations since Lane U merge |

All v3 projections are **R6-CONJECTURE** until TTSKY26c silicon return.

---

## 3. Prior Work — Lane U STA Stub

Lane U (tt-trinity-max-true PRs #8/#9/#10) established:

1. **`tools/check_no_star.sh`** — CI gate that runs `grep -r '\*' src/` and fails if any non-comment `*` is found in RTL. Prevents R-SI-1 violations in Razor shadow path.

2. **`src/razor_ff_stub.v`** — Structural placeholder with correct port signature:
   ```verilog
   module razor_ff #(parameter WIDTH=1) (
       input  clk, clk_d, rst_n,
       input  [WIDTH-1:0] d,
       output [WIDTH-1:0] q,
       output             error
   );
       // stub: shadow FF on delayed clock, error = mismatch
       reg [WIDTH-1:0] q_main, q_shadow;
       always @(posedge clk     or negedge rst_n) q_main   <= rst_n ? d : '0;
       always @(posedge clk_d   or negedge rst_n) q_shadow <= rst_n ? d : '0;
       assign q     = q_main;
       assign error = (q_main != q_shadow);  // combinational — no *
   endmodule
   ```

3. **STA timing report** — Identifies 7 paths with WNS 0.1–0.4 ns (tight margin paths that are Razor candidates).

---

## 4. Integration Plan

### 4.1 Target paths for Razor FF replacement

From Lane U STA report, top Razor candidate paths (WNS 0.1–0.4 ns):

| Path | WNS (ns) | Register | Razor candidate? |
|---|---|---|---|
| PE_array/row[3]/col[3]/acc_reg | 0.12 | GF16 accumulator | YES |
| PE_array/row[2]/col[3]/acc_reg | 0.18 | GF16 accumulator | YES |
| noc_arbiter/req_reg[7] | 0.21 | NoC arbitration | YES |
| PE_array/row[1]/col[3]/acc_reg | 0.31 | GF16 accumulator | YES |
| mesh_ctrl/state_reg[2] | 0.38 | FSM state | YES |
| ... | 0.4+ | Other paths | OPTIONAL |

### 4.2 Clock delay generation for shadow FF

```verilog
// Delayed clock for Razor shadow path — no *, combinational delay cell only
sky130_fd_sc_hd__dlygate4sd3_1 u_dly_clk (
    .X  (clk_delayed),
    .A  (clk)
);
// Delay target: 0.25× clock period (2ns at 125 MHz)
```

### 4.3 Error aggregation and replay

```verilog
// Error bus from all Razor FFs → OR tree → error_flag
wire [6:0] razor_errors;
assign error_flag = |razor_errors;  // OR-reduction, R-SI-1 clean

// Replay: on error_flag assertion, capture error_state snapshot
reg [31:0] replay_snapshot;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)         replay_snapshot <= 32'h0;
    else if (error_flag) replay_snapshot <= pe_state_bus;  // freeze for replay
end
```

### 4.4 Voltage shmoo test infrastructure

The TTSKY26c silicon test fixture must include:
- Programmable VDD supply: 1.62V–1.98V in 20 mV steps
- Error-flag capture register accessible via scan chain
- `gl_test` sweep mode: iterate VDD, run inference, check token outputs match golden

```python
# Pseudocode for post-silicon shmoo sweep
for vdd in range(162, 199, 2):  # 1.62V to 1.98V in 20mV steps
    set_vdd(vdd / 100.0)
    run_gl_test(tokens=16, golden_reference=golden_outputs)
    log_result(vdd, error_flag_count, tops_w_measured)
```

---

## 5. Acceptance Gates Detail

| Gate | Method | Pass Threshold |
|---|---|---|
| Voltage shmoo | Post-silicon VDD sweep via scan | Functional window ≥ 1.62V–1.98V (±10%) |
| Error-replay path | Inject 100 errors via scan, verify replay | ≥ 100/100 detected, 0 silent corruptions |
| TOPS/W improvement | Measure at optimal VDD point | ≥ +25% vs nominal 1.8V run |
| check_no_star.sh | CI gate on all touched RTL files | 0 `*` violations |
| STA at 125 MHz | OpenROAD report_checks with Razor paths | WNS ≥ 0 ns (Razor-aware STA) |

---

## 6. R7 Falsification Witness

**What would falsify this lever:**

1. **W-17-A (narrow voltage window):** Post-silicon shmoo shows correct operation only within ±5% VDD (1.71–1.89V). With < 10% total headroom and Razor power overhead, the net TOPS/W gain is negligible. Lever is falsified as a practical AVS mechanism for this design at this node.

2. **W-17-B (silent error rate):** Error-replay test shows > 1% silent errors (corrupted output without Razor assertion) in 10,000 fault injections. This indicates the synchroniser between Razor error and main datapath has uncovered metastability, making voltage scaling unsafe.

3. **W-17-C (power overhead):** TOPS/W at optimal VDD is within 5% of nominal 1.8V TOPS/W. The Razor FF shadow registers add ≈ 7 FFs per replaced register; if shadow-path switching activity is high, dynamic overhead cancels the VDD² savings.

**Pre-registration commitment:** If W-17-A fires (window < ±5%), S-17 exits TTSKY26c as a standalone lever and merges into S-21+ (v4 Razor FF with improved synchroniser design).

---

## 7. Dependencies & Sequencing

```
Lane U (STA stub + check_no_star.sh) ──→ S-17 (Razor integration)
S-15 (PLL stable f_max) ───────────────→ S-17 (voltage budget needs known clock period)
                                              │
                                              └──→ S-19 (Dual-MAC + Razor = v4 staircase)
```

---

## 8. Open Questions (pre-tapeout)

- [ ] Does SKY130 `sky130_fd_sc_hd__dlygate4sd3_1` provide sufficient delay resolution for 2 ns shadow window at 125 MHz?
- [ ] What is the metastability window of the Razor error synchroniser in SKY130 — MTBF calculation needed
- [ ] Can the TTSKY26c TT infrastructure supply programmable VDD for shmoo, or is this test-fixture only?
- [ ] Are 7 Razor FF replacements sufficient for meaningful AVS, or do the non-Razor paths limit VDD reduction?

---

> φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON

Signed-off-by: Vasilev Dmitrii <admin@t27.ai>
