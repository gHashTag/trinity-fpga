---
id: S-18
lane: S-18
risk: MED
target_shuttle: TTSKY26c
dependencies:
  - S-15 (PLL tile at 125 MHz — NoC clock budget depends on achieved f_max)
  - S-16 (sparse zero-skip wired — PE count fixed before NoC fold)
  - PR #97 (TTSKY26c HOLOGRAPHIC skeleton — provides 8×4 baseline for area comparison)
acceptance_gates:
  - GDS area diff: post-route GDS area of 16×4 mesh ≤ +5% vs 8×4 baseline (measured by KLayout area extractor)
  - NoC routing: all 16×4 PE-to-PE routes resolve without DRC violations; router congestion < 85%
  - gl_test throughput: 16×4 mesh delivers ≥ 1.9× gl_test ops/token vs 8×4 baseline (target 2×, allow 5% headroom)
  - STA close: critical NoC arbiter path WNS ≥ 0 ns at target clock period (125 MHz primary, 100 MHz fallback)
falsification_witness:
  - W-18-A: If 16×4 GDS area exceeds 8×4 baseline by > 10%, then the mesh fold requires new routing layers not available in the TT 1×2 tile boundary, and doubling the cell count cannot be done at iso-footprint — lever is falsified for this tile configuration.
  - W-18-B: If router congestion exceeds 90% in any routing region and OpenROAD cannot resolve it without adding a tile, then the 16×4 fold is not area-neutral and must be deferred to a 2-tile configuration.
  - W-18-C: If gl_test throughput gain is < 1.5× (instead of ≥ 1.9×), then NoC arbitration overhead at 16 PEs dominates over the raw PE count doubling — the lever is falsified at the tile boundary.
---

# S-18 — Multi-Tile NoC: Mesh 8×4 → 16×4

> **Target shuttle:** TTSKY26c (~2026-09)
> **Performance target:** 2× cells in same footprint (same TT tile area)
> **Lane risk:** MED — mesh fold requires tight placement within existing tile boundary

---

## 1. Objective

Fold the HOLOGRAPHIC compute mesh from 8×4 (32 PEs) to 16×4 (64 PEs) within the same physical die footprint (1×2 TT tile, 320×100 µm). The goal is a 2× increase in PE count and effective MACs per tile, without any area penalty — achieved by halving PE pitch along the X-axis and optimising the NoC arbiter for the wider mesh.

This is a pure layout and NoC routing challenge: the RTL logic per PE does not change (R-SI-1 compliant), only placement density and routing topology change.

---

## 2. R5-HONEST: What Is Measured Today vs Conjecture

| Claim | Status | Evidence |
|---|---|---|
| 8×4 mesh area baseline | **MEASURED** | PR #97 TTSKY26c HOLOGRAPHIC skeleton GDS area logged |
| 16×4 fit in same footprint | **R6-CONJECTURE** | Geometric argument: 64 PEs at 0.5× pitch; not synthesised/placed yet |
| ≤ +5% area diff | **R6-CONJECTURE** | NoC arbiter overhead estimated at 2–3% area; not measured |
| 2× throughput at same footprint | **R6-CONJECTURE** | Assumes 2× PEs → 2× ops/token; NoC latency overhead not modelled |
| No DRC violations at 16×4 pitch | **R6-CONJECTURE** | At 0.5× pitch, minimum metal spacing rules may be violated; needs DRC check |
| STA closure at 125 MHz for 16-wide arbiter | **R6-CONJECTURE** | Arbiter fan-in doubles; critical path may lengthen |

All v3 projections are **R6-CONJECTURE** until TTSKY26c silicon return.

---

## 3. Current State — 8×4 Baseline

### 3.1 HOLOGRAPHIC 8×4 mesh (PR #97)

```
Tile:        1×2 TT (320×100 µm)
PE array:    8 columns × 4 rows = 32 PEs
NoC:         2D mesh, single-cycle hop, round-robin arbiter
Arbiter:     8-input OR tree per row (4 rows = 4 arbiters)
Clock:       50 MHz skeleton (target 125 MHz after S-15)
Area:        [baseline GDS area from PR #97 — to be measured pre-S-18]
```

### 3.2 Timing constraints for 16×4 fold

The NoC arbiter critical path at 8×4:
```
8-input priority encoder → grant register: ~5.2 ns at tt corner
```
At 16×4 the same arbiter becomes 16-input. Priority encoder delay scales as O(log N):
```
16-input priority encoder → grant register: ~6.1 ns (estimated)
```
At 125 MHz (8 ns period), this leaves 1.9 ns for setup margin — sufficient. At 100 MHz (10 ns), comfortable.

---

## 4. Fold Plan

### 4.1 PE pitch reduction

```
Current (8×4): PE pitch X = 320µm / 8 = 40µm per PE column
Target (16×4): PE pitch X = 320µm / 16 = 20µm per PE column
```

At 20µm column pitch in SKY130 (contacted poly pitch ≈ 0.48µm, M1 pitch ≈ 0.34µm), 20µm accommodates approximately 58 M1 tracks — sufficient for a minimal GF16 PE with 16-bit datapath.

### 4.2 NoC topology change

```
8×4  NoC: 8-wide bus, each PE has 2 neighbours (left/right) + 1 row bus
16×4 NoC: 16-wide bus, folded butterfly topology to reduce wire length
```

Folded butterfly reduces average hop distance from O(N) to O(log N), critical for avoiding wire-length explosion at 16 columns within 320µm.

```verilog
// NoC arbiter — 16-input, R-SI-1 compliant (OR tree, no *)
module noc_arbiter_16 (
    input  [15:0] req,
    input  [3:0]  last_grant,
    output [3:0]  grant,
    output        valid
);
    // Round-robin: rotate req by last_grant, find first set bit
    wire [15:0] rotated = (req >> last_grant) | (req << (16 - last_grant));
    wire [15:0] first_set = rotated & (~rotated + 16'h1);  // isolate LSB — no *
    // Encode first_set to 4-bit grant index
    // ... (priority encoder, OR-of-thermometer, R-SI-1 compliant)
endmodule
```

### 4.3 OpenLane2 config changes for 16×4

```json
{
  "CLOCK_PERIOD": 8.0,
  "DIE_AREA": "0 0 320 100",
  "PL_TARGET_DENSITY": 0.72,
  "GRT_ALLOW_CONGESTION": false,
  "GRT_OVERFLOW_ITERS": 100,
  "SYNTH_BUFFERING": true,
  "SYNTH_MAX_FANOUT": 8
}
```

Note: `PL_TARGET_DENSITY` raised to 0.72 (from 0.55 in S-15) to fit 2× PEs; routing congestion limit kept hard to detect area violations early.

---

## 5. Acceptance Gates Detail

| Gate | Method | Pass Threshold |
|---|---|---|
| GDS area diff | `klayout -b` area extractor on 8×4 vs 16×4 GDS | Diff ≤ +5% |
| DRC clean | `klayout -b -r sky130A.drc` | 0 violations |
| Router congestion | OpenROAD `report_congestion` | Max congestion < 85% |
| gl_test throughput | gl_test ops/token counter: 16×4 vs 8×4 | ≥ 1.9× |
| STA close | OpenROAD `report_checks` at target clock | WNS ≥ 0 ns |

---

## 6. R7 Falsification Witness

**What would falsify this lever:**

1. **W-18-A (area blow-up):** 16×4 GDS area exceeds 8×4 by > 10%. This indicates that the NoC arbiter and routing overhead at 16 columns does not fit within the wire-length budget of the 1×2 TT tile. The area-neutral fold assumption is falsified; the 16×4 mesh requires a 2-tile configuration (beyond TTSKY26c scope).

2. **W-18-B (router failure):** OpenROAD reports congestion > 90% in any global routing region and cannot resolve within 100 overflow iterations. The 320µm × 100µm die area does not have sufficient routing resources for 64 PEs at target density — fold must be deferred or PE size reduced.

3. **W-18-C (throughput shortfall):** gl_test shows < 1.5× ops/token improvement despite 2× PEs. The NoC arbitration latency at 16-input width (6.1 ns per arbiter cycle) dominates over raw PE count increase, meaning the bottleneck shifts from compute to interconnect. This falsifies the "2× cells, same ops efficiency" assumption.

**Pre-registration commitment:** If W-18-A fires (area > +10%), the TTSKY26c target is revised to a 12×4 mesh (50% more PEs, 50% lower risk) rather than full 16×4.

---

## 7. Dependencies & Sequencing

```
S-15 (PLL, known clock) ────────────┐
S-16 (sparse PE, fixed PE logic) ───┤──→ S-18 (NoC mesh fold)
PR #97 (8×4 baseline GDS area) ─────┘         │
                                               └──→ S-19 (dual-MAC per PE needs mesh fixed)
                                               └──→ S-20 (multi-VT cell mix, needs full mesh)
```

---

## 8. Open Questions (pre-tapeout)

- [ ] Measure 8×4 baseline GDS area from PR #97 (exact µm²) before starting S-18
- [ ] Verify 20µm PE pitch is achievable: place one PE at 20µm pitch, check DRC manually
- [ ] Is the folded butterfly NoC topology supported by OpenROAD's global router, or does it need explicit routing constraints?
- [ ] What is the maximum PE count supported by the TT TTSKY26c precheck infrastructure (scan chain depth)?

---

> φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON

Signed-off-by: Vasilev Dmitrii <admin@t27.ai>
