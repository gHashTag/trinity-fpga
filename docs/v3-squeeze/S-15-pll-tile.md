---
id: S-15
lane: S-15
risk: HIGH
target_shuttle: TTSKY26c
dependencies:
  - S-13 (hdll dual-lib, merged 1f3486bb)
  - S-14 (OpenROAD CGT, Lane L)
  - ICA-MAX-TRUE-008 resolution (KLayout DRC fail on Lane M v2)
acceptance_gates:
  - STA close: worst-case slack ≥ 0 ns at 125 MHz across all corners (ss/ff/tt @ 1.8V/−40°C/125°C)
  - KLayout.DRC green: zero DRC violations in tt_um_qbrain_maxtrue GDS (RUN_KLAYOUT_DRC true)
  - f_max measured: ring-oscillator or scan-chain frequency measurement on TTSKY26c silicon return ≥ 100 MHz (100 MHz fallback) or ≥ 125 MHz (primary)
  - No regression: gl_test all tokens PASS (≥ 16/16 at 100 MHz mode, same as v2 baseline)
falsification_witness:
  - W-15-A: If STA closes at 125 MHz but post-silicon measurement shows f_max < 100 MHz on ≥ 3 out of 5 dies, then PLL ratio φ⁻¹ lever is falsified as the bottleneck isolator.
  - W-15-B: If KLayout DRC green at 125 MHz tapeout but yield < 60% on first silicon lot, then STA closure alone is not a reliable predictor of this process node at 125 MHz.
  - W-15-C: If 100 MHz fallback (ratio 2.0) STA-closes but gl_test shows timing violations in simulation, then the STA model is missing a physical effect (likely interconnect RC at this tile boundary).
---

# S-15 — PLL Tile Retune: 125 MHz @ φ⁻¹ ratio OR 100 MHz fallback

> **Target shuttle:** TTSKY26c (~2026-09)
> **Performance target:** +25–30% f_max vs v2.1 baseline (80 MHz → 125 MHz primary, 100 MHz fallback)
> **Lane risk:** HIGH — two prior failure modes documented (see §3)

---

## 1. Objective

Re-attempt the PLL tile at 125 MHz using PLL ratio φ⁻¹ (≈ 0.618), the golden-ratio-derived divider that minimises fractional spur energy. If STA or DRC gates do not close at 125 MHz, fall back to 100 MHz using integer ratio 2.0.

The 125 MHz target would lift MAX-TRUE from 55 TOPS/W (v2 baseline) to ~70–75 TOPS/W through pure frequency scaling, without any area increase.

---

## 2. R5-HONEST: What Is Measured Today vs Conjecture

| Claim | Status | Evidence |
|---|---|---|
| v2 baseline 50 MHz STA closes | **MEASURED** | CI 25915884192 GREEN, sha `87a079d` |
| Lane M v1 at 125 MHz: STA FAIL | **MEASURED FAIL** | tt-trinity-max-true PR — timing violations on critical path through GF16 accumulator |
| Lane M v2 at 80 MHz: KLayout DRC FAIL | **MEASURED FAIL** | ICA-MAX-TRUE-008, tt-trinity-max-true PR #4 klayout.log |
| φ⁻¹ PLL ratio reduces spur at 125 MHz | **R6-CONJECTURE** | Mathematical argument from spectral theory; not measured in this process node |
| +25–30% f_max if STA closes | **R6-CONJECTURE** | Linear frequency-TOPS/W scaling assumption; validated only up to 80 MHz in simulation |
| 100 MHz fallback STA-closeable | **R6-CONJECTURE** | No STA run at 100 MHz yet; integer ratio 2.0 should be cleaner than fractional φ⁻¹ |

All v3 projections are **R6-CONJECTURE** until TTSKY26c silicon return.

---

## 3. Prior Failure Mode Analysis

### 3.1 Lane M v1 — 125 MHz STA Fail

**Root cause:** Critical timing path through GF16 accumulator chain (gf16_mul → gf16_add × 4 → register). Path delay ≈ 8.9 ns > 8.0 ns (125 MHz period). The PLL output was set to exact 125 MHz (ratio 2.5 from internal 50 MHz reference) with no fractional compensation.

**Evidence:** STA log shows worst negative slack (WNS) = −0.9 ns on path `PE_array/row[3]/col[3]/acc_reg`. Endpoint register in GF16 accumulator stage 2.

**What was NOT tried:** PLL ratio adjustment to φ⁻¹ ≈ 0.618 (multiplied upstream to give 50×2.618 = 130.9 MHz, then divided by post-divider to land at 125 MHz with a fractional intermediate that may relax the in-die distribution skew).

### 3.2 Lane M v2 — 80 MHz KLayout DRC Fail (ICA-MAX-TRUE-008)

**Root cause:** PLL tile placement at 80 MHz required a new analog cell (sky130_fd_sc_hd__clkbuf_4) positioned adjacent to the power ring. KLayout metal-overlap DRC rule `met1.3c` violated at the PLL-to-core clock tree junction. ICA-MAX-TRUE-008 is the incident classification for this specific violation.

**Evidence:** klayout.log from PR #4: `ERROR met1.3c: Metal1 spacing violation at (234.56µm, 89.12µm) — PLL output net to core VDD ring`. OpenROAD router chose a detour that violated the spacing rule.

**What was NOT tried:** Manual placement constraint for the PLL tile with `set_placement_padding` to force 2µm clearance from power ring; switching to `sky130_fd_sc_hd__clkbuf_8` which has a wider pitch and avoids the met1.3c trap.

---

## 4. Retry Knobs

### Primary path — 125 MHz @ φ⁻¹ ratio

```tcl
# config.json additions for OpenLane2
"CLOCK_PERIOD": 8.0,            # 125 MHz
"PLL_DIVIDER_RATIO": 0.618034,  # φ⁻¹ = 1/φ ≈ 0.618034
"CLOCK_BUFFER_TYPE": "sky130_fd_sc_hd__clkbuf_8",
"SET_PLACEMENT_PADDING": 2,     # µm clearance from power ring
"PL_TARGET_DENSITY": 0.55,      # relaxed from 0.65 to allow router headroom
"SYNTH_STRATEGY": "DELAY 3",    # favour timing over area
"PNR_SDC_FILE": "constraints_125mhz.sdc"
```

```sdc
# constraints_125mhz.sdc — key additions
create_clock -name clk -period 8.0 [get_ports clk]
set_clock_uncertainty -setup 0.3 [get_clocks clk]
set_clock_uncertainty -hold  0.1 [get_clocks clk]
# False path on scan enable during functional mode
set_false_path -from [get_ports scan_en]
```

### Fallback path — 100 MHz @ ratio 2.0

```tcl
"CLOCK_PERIOD": 10.0,           # 100 MHz
"PLL_DIVIDER_RATIO": 2.0,       # integer — minimal spur
"CLOCK_BUFFER_TYPE": "sky130_fd_sc_hd__clkbuf_8",
"SET_PLACEMENT_PADDING": 2,
"PL_TARGET_DENSITY": 0.60,
"SYNTH_STRATEGY": "DELAY 2"
```

### ICA-MAX-TRUE-008 mitigation (both paths)

Add explicit floorplan constraint:

```json
"FP_PIN_ORDER_CFG": "pll_pin_order.cfg",
"GPL_CELL_PADDING": 4,
"CELL_PAD": 4
```

And in `pll_pin_order.cfg`, place PLL output net 3 metal tracks from power ring boundary.

---

## 5. Acceptance Gates Detail

| Gate | Method | Pass Threshold |
|---|---|---|
| STA close | OpenROAD `report_checks -path_delay max` | WNS ≥ 0 ns, TNS = 0 at target freq |
| KLayout.DRC | `klayout -b -r sky130A.drc` | 0 violations, log line `TOTAL: 0` |
| gl_test | `make gl_test CLOCK_PERIOD=8.0` | ≥ 16/16 tokens PASS |
| Ring-osc measure | Post-silicon TTSKY26c scan | f_measured ≥ 100 MHz (fallback) or ≥ 125 MHz (primary) |

---

## 6. R7 Falsification Witness

**What would falsify this lever:**

1. **W-15-A (STA→silicon gap):** STA closes at 125 MHz, but post-silicon f_max < 100 MHz on ≥ 3/5 sampled dies. This would indicate that the SKY130 PDK STA model has ≥ 20% optimistic error on the GF16 accumulator path — a known risk at the PDK's slow-corner model edge.

2. **W-15-B (DRC→yield gap):** KLayout DRC reports 0 violations, but yield < 60% at TTSKY26c lot. This would falsify the assumption that met1.3c avoidance is the dominant yield limiter at this frequency.

3. **W-15-C (φ⁻¹ ratio spur claim):** Post-silicon jitter measurement shows PLL output at φ⁻¹ ratio has ≥ 2× RMS jitter vs integer-ratio 100 MHz, indicating the fractional spur theory does not hold for this PLL topology.

**Pre-registration commitment:** All three witnesses are pre-registered here. If any fires, the v3 125 MHz target is formally downgraded to the 100 MHz fallback and the failure analysis must be appended to ICA-MAX-TRUE log before TTSKY26d planning.

---

## 7. Dependencies & Sequencing

```
S-13 (dual-lib merged) ──┐
S-14 (CGT merged)        ├──→ S-15 (PLL retune) ──→ S-18 (16×4 NoC, needs 125 MHz budget)
ICA-MAX-TRUE-008 fix ────┘                       └──→ S-17 (Razor FF, needs stable PLL)
```

S-15 must STA-close **before** S-18 and S-17 are planned, because the NoC and Razor FF timing budgets depend on knowing the actual achievable clock period.

---

## 8. Open Questions (pre-tapeout)

- [ ] Does SKY130 `sky130_fd_pr__pfet_g5v0d10v5` ring oscillator match the PLL tile at 125 MHz? (Need RO characterisation sweep)
- [ ] Is φ⁻¹ ratio realizable in the available PLL IP integer divider, or does it require fractional-N? (Check VCO range)
- [ ] What is the TTSKY26c maximum tile clock constraint from Tiny Tapeout infrastructure?

---

> φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON

Signed-off-by: Vasilev Dmitrii <admin@t27.ai>
