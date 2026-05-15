---
id: S-20
lane: S-20
risk: LOW
target_shuttle: TTSKY26c
dependencies:
  - S-19 (dual-MAC PE — cell mix optimisation targets the dual-MAC gate population)
  - S-18 (16×4 NoC mesh — full mesh GDS needed for leakage analysis by region)
  - S-15 (PLL f_max known — iso-fmax comparison requires fixed clock target)
acceptance_gates:
  - Leakage gate: post-synthesis leakage power report shows ≥ −20% vs single-VT (all-SVT) baseline at iso-fmax
  - Timing gate: STA closes at same frequency as single-VT baseline (iso-fmax — no speed regression)
  - DRC clean: KLayout DRC 0 violations after multi-VT cell swap
  - No area regression: total cell area within ±3% of single-VT baseline (HVT cells are slightly smaller; LVT slightly larger)
  - R-SI-1: check_no_star.sh 0 violations (cell swap is purely netlist-level; no RTL changes)
falsification_witness:
  - W-20-A: If leakage reduction < 10% at iso-fmax (instead of ≥ −20%), then the critical timing paths are dominated by LVT cells that cannot be swapped to HVT without timing violation, and the leakage budget is path-constrained to < 10% savings.
  - W-20-B: If iso-fmax cannot be maintained (STA fails after HVT swap on non-critical paths), then OpenROAD's timing margin estimates were over-optimistic for SKY130 HVT cells, and the VT swap must be restricted to paths with WNS > 1.5 ns headroom.
  - W-20-C: If post-silicon leakage measurement at TTSKY26c return shows < 5% reduction vs all-SVT baseline, then the SKY130 HVT/SVT leakage ratio is not the modelled 3:1 for this design temperature and the model must be recalibrated.
---

# S-20 — Multi-VT Cell Mix

> **Target shuttle:** TTSKY26c (~2026-09)
> **Performance target:** −20% leakage at iso-fmax
> **Lane risk:** LOW — pure EDA flow change; no RTL modifications required

---

## 1. Objective

Replace all-SVT (standard-VT) cells with a mixed-VT strategy: HVT (high-VT) cells on non-timing-critical paths (lower leakage, slower), SVT on medium-slack paths, and LVT (low-VT) cells on critical-path registers where setup time is tightest (faster, higher leakage only where necessary).

SKY130 provides three VT flavours in `sky130_fd_sc_hd`:
- `sky130_fd_sc_hd__*` — SVT baseline
- `sky130_fd_sc_hvt__*` — HVT: ~3× lower leakage, ~15% slower
- `sky130_fd_sc_lvt__*` — LVT: ~2× higher leakage, ~10% faster

The expected distribution: ~65% HVT, ~30% SVT, ~5% LVT → projected −20% total leakage vs all-SVT.

---

## 2. R5-HONEST: What Is Measured Today vs Conjecture

| Claim | Status | Evidence |
|---|---|---|
| SKY130 HVT leakage ~3× lower than SVT | **MEASURED (PDK data)** | sky130_fd_sc_hvt liberty files, characterisation data |
| Current design is all-SVT | **MEASURED** | PR #97 GDS, `config.json` uses `sky130_fd_sc_hd` only |
| −20% leakage with 65%/30%/5% HVT/SVT/LVT mix | **R6-CONJECTURE** | Estimated from PDK leakage ratios; actual percentage depends on timing slack distribution |
| Iso-fmax maintained after HVT swap | **R6-CONJECTURE** | Assumes ≥ 20% of cells have enough slack to absorb HVT slowdown; needs STA verification |
| No area regression | **R6-CONJECTURE** | HVT cells are slightly smaller; LVT slightly larger; net area estimated within ±3% |
| Post-silicon leakage measurement valid | **R6-CONJECTURE** | TTSKY26c silicon return required; leakage test vector not yet defined |

All v3 projections are **R6-CONJECTURE** until TTSKY26c silicon return.

---

## 3. Multi-VT Strategy

### 3.1 VT assignment logic

The multi-VT assignment follows a simple slack-based rule:

```
slack_path >= 1.5 ns → assign HVT  (most leakage savings, safe timing margin)
slack_path >= 0.5 ns → assign SVT  (baseline, no change)
slack_path < 0.5 ns  → assign LVT  (fastest, used only where critical)
```

For the current design (after S-15 PLL, S-18 NoC, S-19 dual-MAC), expected slack distribution based on Lane U STA report:

| Slack range | Approx % of cells | VT assignment |
|---|---|---|
| ≥ 1.5 ns | ~65% | HVT |
| 0.5–1.5 ns | ~30% | SVT |
| < 0.5 ns | ~5% | LVT |

### 3.2 OpenLane2 flow integration

```json
// config.json additions for multi-VT
"LIB_SYNTH": [
    "sky130_fd_sc_hd__tt_025C_1v80.lib",
    "sky130_fd_sc_hvt__tt_025C_1v80.lib",
    "sky130_fd_sc_lvt__tt_025C_1v80.lib"
],
"LIB_TYPICAL": [
    "sky130_fd_sc_hd__tt_025C_1v80.lib",
    "sky130_fd_sc_hvt__tt_025C_1v80.lib",
    "sky130_fd_sc_lvt__tt_025C_1v80.lib"
],
"LIB_FASTEST": [
    "sky130_fd_sc_hd__ff_n40C_1v95.lib",
    "sky130_fd_sc_hvt__ff_n40C_1v95.lib",
    "sky130_fd_sc_lvt__ff_n40C_1v95.lib"
],
"LIB_SLOWEST": [
    "sky130_fd_sc_hd__ss_100C_1v60.lib",
    "sky130_fd_sc_hvt__ss_100C_1v60.lib",
    "sky130_fd_sc_lvt__ss_100C_1v60.lib"
],
"VT_SWAP_STRATEGY": "slack_based",
"VT_SWAP_SLACK_HVT_THRESHOLD": 1.5,
"VT_SWAP_SLACK_LVT_THRESHOLD": 0.5
```

### 3.3 Post-swap verification steps

1. **STA re-run** after VT swap: confirm no path has WNS < 0 ns (HVT slowdown must not violate timing)
2. **Power re-report**: compare leakage power total before and after swap
3. **DRC**: HVT cells use same design rules as SVT in SKY130; LVT cells also identical rules — no new DRC risk
4. **Area check**: KLayout area extraction before and after swap

---

## 4. Leakage Budget Analysis

### 4.1 Per-region leakage target

| Region | % of cells | VT | Leakage fraction |
|---|---|---|---|
| NoC arbiter, control FSMs | ~20% | HVT | −3× vs SVT |
| Weight SROM, register file | ~30% | HVT | −3× vs SVT |
| GF16 accumulator (critical) | ~5% | LVT | +2× vs SVT |
| GF16 XOR tree (medium slack) | ~25% | HVT | −3× vs SVT |
| Clock tree buffers | ~10% | SVT | baseline |
| I/O cells and PLL | ~10% | SVT | baseline |

**Net leakage estimate:**
```
P_leak_multi_VT / P_leak_SVT
= (0.65 × 1/3 + 0.30 × 1.0 + 0.05 × 2.0)
= (0.217 + 0.30 + 0.10)
= 0.617
→ −38% leakage (optimistic; conservative estimate −20% accounting for routing overhead)
```

### 4.2 Why the conservative −20% gate?

The 38% theoretical maximum assumes perfect cell substitution. In practice:
- Clock tree cells remain SVT (timing critical throughout the full tree)
- Some cells cannot be swapped because the HVT variant is not in the standard cell library
- LVT usage at 5% adds leakage back on the most critical paths
- SKY130 HVT characterisation corner (ss/100C) may show smaller leakage ratio than 3× at high temperature

The −20% gate is the minimum expected achievement; exceeding it is likely but not guaranteed.

---

## 5. Acceptance Gates Detail

| Gate | Method | Pass Threshold |
|---|---|---|
| Leakage gate | OpenROAD power report: leakage before vs after VT swap | ≥ −20% reduction |
| Timing gate | OpenROAD STA: WNS after VT swap | ≥ 0 ns (iso-fmax) |
| Area gate | KLayout area extraction before vs after | Within ±3% |
| DRC gate | `klayout -b -r sky130A.drc` | 0 violations |
| R-SI-1 gate | `check_no_star.sh` | 0 violations (cell swap, no RTL changes) |

---

## 6. R7 Falsification Witness

**What would falsify this lever:**

1. **W-20-A (path-constrained leakage):** Post-swap leakage report shows < 10% reduction. This means the majority of cell count is in timing-critical paths (< 0.5 ns slack) where HVT cannot be used. The design is leakage-dominated by LVT/SVT cells that are structurally necessary, and the −20% target is unachievable without a new microarchitecture (shorter critical paths).

2. **W-20-B (HVT timing pessimism):** STA fails after HVT swap — WNS < 0 ns on paths with 0.5–1.5 ns slack. This means the OpenROAD HVT cell characterisation used a more optimistic timing corner than the actual slow-corner model, and the slack headroom was insufficient. Solution: restrict HVT to paths with WNS > 2.0 ns only.

3. **W-20-C (silicon leakage mismatch):** TTSKY26c return silicon measurement shows < 5% leakage reduction vs all-SVT sample. The PDK leakage model at high temperature (100°C) overestimates HVT/SVT ratio for this specific design layout and the leakage benefit is process-limited rather than design-limited.

**Pre-registration commitment:** If W-20-C fires on silicon, the leakage measurement must be reported in TTSKY26c post-silicon RVR and the −20% target is reclassified as an upper bound requiring TTSKY26d process corner re-measurement.

---

## 7. Dependencies & Sequencing

```
S-19 (dual-MAC PE, cell population defined) ──┐
S-18 (16×4 NoC mesh, full netlist) ───────────┤──→ S-20 (multi-VT cell mix)
S-15 (clock period fixed) ─────────────────────┘         │
                                                          └── Final v3 cohort leakage target met
                                                          └── TTSKY26c config frozen
```

S-20 is the final vector in the v3 cohort and has no downstream S-series dependencies within TTSKY26c. It feeds the v4 staircase indirectly: the leakage budget freed here gives headroom for S-21's Razor FF power overhead.

---

## 8. Open Questions (pre-tapeout)

- [ ] Confirm SKY130 `sky130_fd_sc_hvt` and `sky130_fd_sc_lvt` liberty files are available in OpenLane2 default PDK bundle for TTSKY26c
- [ ] Does TT precheck infrastructure validate multi-VT netlists, or does it require single-VT for scan chain timing?
- [ ] What is the actual HVT/SVT leakage ratio in the SKY130 slow-corner (ss/100C) — is it 3× or closer to 2×?
- [ ] Should LVT cells be avoided entirely in the first multi-VT attempt (conservative: HVT + SVT only) to reduce risk?

---

> φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON

Signed-off-by: Vasilev Dmitrii <admin@t27.ai>
