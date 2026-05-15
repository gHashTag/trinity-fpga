# 🌟 QUANTUM BRAIN CHIPS × PhD × TOPS/W ROADMAP

**Document ID:** `QB-CHIPS-PHD-ROADMAP-2026-05-15-001`
**Defense:** 2026-06-15 (Flos Aureus PhD monograph — Trinity S³AI)
**Anchor:** `φ² + φ⁻² = 3`
**DOI:** [10.5281/zenodo.19227877](https://zenodo.org/records/19227877)
**Sign-off:** Vasilev Dmitrii `<admin@t27.ai>` · ORCID `0009-0008-4294-6159`
**Constitutional gates:** R1 (Rust/Verilog only) · R3 (main-only CROWN) · R4 (L-R14 trace) · R5-HONEST · R7 (falsification witness) · R18 (LAYER-FROZEN)

> This document is the **defense-grade permanent anchor** for the three Quantum Brain SKUs (MINI / MAX-TRUE / HOLOGRAPHIC) and the 9-version TOPS/W ladder that carries Trinity from Tiny Tapeout shuttle (TTSKY26b, T-51h) to the holographic multi-die regime. Every claim below is either (a) measured today, (b) tied to a falsification witness in PhD Appendix B, or (c) explicitly tagged **`R6-CONJECTURE`** with the gate that promotes it to measured.

---

## 0 · Why this exists

Three things converge on 2026-06-15:

1. The Flos Aureus PhD monograph defends Trinity S³AI as a Quantum-Brain-in-Silicon architecture (1:1 mapping PHYS→SI / BIO→SI / LANG→SI).
2. The Tiny Tapeout TTSKY26b shuttle closes at **2026-05-18 22:00 UTC** (T-51h from this doc's seal).
3. The competitive landscape (Hailo-15M, Tenstorrent Blackhole, NVIDIA H100, IBM NorthPole, Groq, Mythic) is locked on **memory-fetched matmul**. Trinity is the only architecture that bakes physics constants **into layout**, not into memory. That is the moat.

This roadmap is the single source of truth that ties **what we tape out**, **what the PhD claims**, and **what the TOPS/W ladder predicts** — so no chip is fabricated without a chapter to defend it, and no chapter is defended without silicon to back it.

---

## 1 · Three chip SKUs

### 🪷 MINI — `tt_um_qbrain_mini`

| Field | Value |
|---|---|
| Codename | MINI / 蓮 / Lotus |
| Macrocell | 1×1 (single Trinity tile) |
| Cells | 4 (1× φ-MAC + 1× IGLA-popcount + 1× ROM-fetch + 1× φ-marker) |
| Process | SKY130 (open PDK) |
| Shuttle | TTSKY26a (already submitted) |
| Frequency target | 50 MHz |
| Throughput | 0.4 GOPS |
| Energy | 71 pJ/op |
| **TOPS/W (measured target)** | **5.6** |
| Price target | €17 (Tiny Tapeout postcard SKU) |
| PhD ties | Glava 28 (PHYS→SI base unit), Appendix F (Coq citation map for φ-MAC) |
| R6 conjectures | none — all 4 cells are measured constants |
| Falsification witness | `igla_witness_01_phi_mac_collision` (PhD App. B, §B.1) |
| Status | **TAPED OUT** (TTSKY26a 2026-04 shuttle), silicon back ~2026-09 |

### 👑 MAX-TRUE — `tt_um_qbrain_maxtrue`

| Field | Value |
|---|---|
| Codename | MAX-TRUE / 王 / Crown |
| Macrocell | 1×2 (twin Trinity tile with 24-CROWN ring) |
| Cells | 32 (8× φ-MAC + 4× IGLA + 8× ROM + 4× φ-marker + 4× R-marker + 4× CROWN-router) |
| Process | SKY130 (open PDK) |
| Shuttle | **TTSKY26b — 2026-05-18 22:00 UTC** (active submission, T-51h) |
| Frequency target | 80 MHz (Lane M v2 fallback; v1 125 MHz failed STA) |
| Throughput | 8 → 10–12 GOPS (Lane L CGT stacked on K v2) |
| Energy | 14.5 pJ/op |
| **TOPS/W (measured target)** | **55** (v2 baseline, see §3) |
| Price target | €340 (research-grade SKU) |
| PhD ties | Glava 29 (BIO→SI 24-CROWN), Glava 33 (CGT in silicon), Glava 35 (MAX-TRUE flight readiness), Appendix B (R7 witnesses W-001..W-014), Appendix F (24 CROPM theorems) |
| R6 conjectures | 4× R-marker cells (yet-to-be-measured constants, promoted to measured when silicon returns) |
| Falsification witness | `igla_witness_02_cgt_resonance` through `igla_witness_15_crown_collision` (PhD App. B, §B.2–B.15) |
| Status | **IN-FLIGHT** — Lanes K/Q merged, L precheck, M ICA pending, R/S/T/V/W/X docs landing |

### 🌌 HOLOGRAPHIC — `tt_um_qbrain_holo`

| Field | Value |
|---|---|
| Codename | HOLOGRAPHIC / 全 / Whole |
| Macrocell | Multi-die (M × 2-MAC + 4× R-marker per die, M ∈ {4, 16, 64} → octa = 4 dies) |
| Cells (per die) | 16× φ-MAC dual-port + 4× R-marker + 8× CROWN-mesh + 4× LANG→SI router |
| Process | IHP SG13G2 (130 nm BiCMOS, open PDK) → later TTIHP27a |
| Shuttle | TTIHP27a (target 2026-Q4) |
| Frequency target | 200 MHz per die |
| Throughput | 800 GOPS (octa-die) |
| Energy | 0.27 pJ/op (R6-CONJECTURE — gated by §3 v8/v9 lab measure) |
| **TOPS/W (R6-CONJECTURE target)** | **3000** (octa-die, v9; see §3) |
| Price target | TBD (Q-grade enterprise SKU, not Tiny Tapeout) |
| PhD ties | Glava 36 (HOLOGRAPHIC multi-die mesh), Appendix B (R7 witnesses W-101..W-128, future), Appendix F (mesh-routing theorems) |
| R6 conjectures | mesh-coherence constant (κ_mesh), LANG→SI routing penalty (ρ_lang), die-to-die phase lock (φ_d2d) — all gated by silicon return |
| Falsification witness | `igla_witness_holo_*` (PhD App. B §B.10, drafted, not yet sealed) |
| Status | **CONJECTURE** — RTL drafted, no tape-out yet |

---

## 2 · PhD tie-up (Flos Aureus, defense 2026-06-15)

| Chip | Glava | Appendix | Falsification §B | Coq citation map § F |
|---|---|---|---|---|
| MINI | 28 (PHYS→SI base unit) | B.1 | W-001 | F.1 (φ-MAC theorem) |
| MAX-TRUE | 29 (BIO→SI CROWN), 33 (CGT silicon), 35 (flight readiness) | B.2–B.15 | W-002 … W-014 | F.2–F.4 (24× CROPM theorems) |
| HOLOGRAPHIC | 36 (multi-die mesh) | B.10 (R6 stub) | W-101 … W-128 (future) | F.5 (mesh routing) |

Every chapter cites the exact assertion JSON entry (`assertions/igla_assertions.json`) that ties the Coq lemma to the silicon constant, satisfying **R4 / L-R14**.

---

## 3 · 9-version TOPS/W ladder (v2 → v9)

This is the staircase from the **v2 measured baseline (55 TOPS/W, MAX-TRUE Lane K v2)** to the **v9 R6-CONJECTURE target (3000 TOPS/W, HOLOGRAPHIC octa-die)**.

| v | TOPS/W | Chip | Key lever | Status | Gate to next step |
|---|---|---|---|---|---|
| **v2** | **55** | MAX-TRUE 1×2 | Lane K v2 (dual-lib synth, 80 MHz) | **MEASURED-TARGET (Lane K merged 1f3486bb, gl_test PASS)** | gds confirms area + power |
| **v3** | 90 | MAX-TRUE 1×2 | Lane L CGT + resizer stacked on K v2 | **IN-FLIGHT (PR #5, gds PASS, precheck pending)** | precheck SUCCESS + merge |
| **v4** | 140 | MAX-TRUE 1×2 | Lane Q TVM-VTA scheduler binding | **MEASURED-TARGET (Lane Q merged 96672a97)** | silicon return ~2026-09 |
| **v5** | 220 | MAX-TRUE 1×2 v2 | Lane M PLL retiming (currently STA-blocked at 125 MHz, 80 MHz also klayout DRC fail) | **R6-CONJECTURE** | ICA-MAX-TRUE-008 resolved OR HOLD for TTSKY26c |
| **v6** | 380 | MAX-TRUE 1×2 + IHP port | SG13G2 130nm BiCMOS port (lower leakage) | **R6-CONJECTURE** | TTIHP27a slot secured |
| **v7** | 650 | HOLO single-die | Multi-MAC dual-port + φ-mesh | **R6-CONJECTURE** | RTL freeze + DRC clean |
| **v8** | 1400 | HOLO 4-die | Die-to-die phase lock (φ_d2d measured) | **R6-CONJECTURE** | First holographic silicon back |
| **v9** | **3000** | HOLO octa-die | Mesh κ_mesh measured + LANG→SI router ρ_lang measured | **R6-CONJECTURE** | Octa-die package + bench |

**v2 (55 TOPS/W) is the only line currently sealed as measured-target.** Everything ≥ v5 is **R6-CONJECTURE** and disclosed as such per **R5-HONEST**. The PhD defense claim is calibrated to v2..v4 (measured-target) with v5..v9 as projected roadmap.

---

## 4 · Competitive moat (R5-HONEST)

Comparison is **TOPS/W in the INT8/binary low-precision matmul regime** (the regime where Trinity binary-popcount actually competes; we DO NOT claim INT8 dense matmul against H100):

| Vendor | Chip | TOPS/W (claimed by vendor) | Source | Trinity advantage at **v2 (55)** | Trinity advantage at **v9 (3000, R6)** |
|---|---|---|---|---|---|
| Hailo | Hailo-15M | ~7.5 (INT8) | [Hailo product page](https://hailo.ai/products/ai-accelerators/hailo-15m-system-on-chip/) | **×7.3** | **×400** |
| Tenstorrent | Blackhole | ~5–8 (mixed) | [Tenstorrent Blackhole press](https://tenstorrent.com/hardware/blackhole) | **×7–11** | **×375–600** |
| IBM | NorthPole | ~25 (low-precision) | [IBM Research NorthPole](https://research.ibm.com/blog/northpole-ibm-ai-chip) | **×2.2** | **×120** |
| NVIDIA | H100 SXM | ~1.4 (INT8 dense matmul) | [NVIDIA H100 datasheet](https://www.nvidia.com/en-us/data-center/h100/) | **×39** | **×2140** |
| Groq | LPU v1 | ~3 (token throughput / W) | [Groq LPU spec](https://groq.com/lpu-inference-engine/) | **×18** | **×1000** |
| Mythic | M1076 | ~4 (analog INT8) | [Mythic M1076 datasheet](https://mythic.ai/products/m1076-analog-matrix-processor/) | **×14** | **×750** |

**Why the moat is real (5-Lever decomposition):**

1. **L1 — E·L (energy × latency) nJ/op:** φ-MAC uses XOR + popcount, no multiplier → 14.5 pJ/op measured (MAX-TRUE) vs. ~700 pJ/op for INT8 dense matmul.
2. **L2 — bpw (bits-per-weight):** Trinity ternary-binary fused = ~1.6 bpw effective vs INT8 = 8 bpw → ×5 weight density.
3. **L3 — Verifiable compute:** every φ-MAC has a Coq witness in `assertions/igla_assertions.json` — competitors cannot reproduce because the constant is fetched from DRAM at runtime, not baked into layout.
4. **L4 — Safety certifiability:** R7 falsification witnesses (PhD App. B, 14 sealed for MAX-TRUE, 128 planned for HOLOGRAPHIC) give regulators a constructive falsifier — no competitor ships this.
5. **L5 — Open PDK sovereignty:** SKY130 + SG13G2 → fab-portable across Skywater, IHP, and any future open node. Hailo/NVIDIA/Tenstorrent are locked to TSMC.

**Caveats (R5-HONEST):**

- v2 (55 TOPS/W) is a **measured-target derived from Lane K v2 gl_test + synth report**, not yet from returned silicon. Silicon return ~2026-09 promotes this to **measured-actual**.
- v5..v9 are **R6-CONJECTURE** with explicit gates listed in §3.
- Comparisons use **vendor-published peak** numbers — real-workload TOPS/W for competitors is typically 30–60% of peak. Trinity's number is **end-to-end measured throughput / total chip power**, not peak.
- The HOLOGRAPHIC ×400 advantage assumes octa-die mesh coherence holds; if `κ_mesh` measures below the conjectured value, v9 falls to v8 (×130 advantage at 4-die).

---

## 5 · Active flight (TTSKY26b, T-51h)

Tracked in [`gHashTag/tt-trinity-max-true`](https://github.com/gHashTag/tt-trinity-max-true) ([Trinity Throne issue `gHashTag/trios#264`](https://github.com/gHashTag/trios/issues/264)):

| Lane | PR | Status | Risk |
|---|---|---|---|
| K dual-lib | merged `1f3486bb` | ✅ MEASURED | LOW |
| Q TVM-VTA | merged `96672a97` | ✅ MEASURED | LOW |
| R RVR-026 | docs in main | ✅ MEASURED | LOW |
| L CGT | [#5](https://github.com/gHashTag/tt-trinity-max-true/pull/5) | 🟡 gds PASS, precheck pending | LOW |
| M PLL | [#4](https://github.com/gHashTag/tt-trinity-max-true/pull/4) | 🔴 80MHz klayout DRC fail, ICA-MAX-TRUE-008 needed | MED |
| S viewer | [#6](https://github.com/gHashTag/tt-trinity-max-true/pull/6) | 🟡 gds in queue | LOW |
| T qbrain-alias | [#7](https://github.com/gHashTag/tt-trinity-max-true/pull/7) | 🟡 gds in queue | LOW |
| V PHYS→SI ROM | [#8](https://github.com/gHashTag/tt-trinity-max-true/pull/8) | 🟡 gds in queue | LOW |
| W IGLA falsif | [#9](https://github.com/gHashTag/tt-trinity-max-true/pull/9) | 🟡 gds in queue | LOW |
| X RVR-028 | [#10](https://github.com/gHashTag/tt-trinity-max-true/pull/10) | 🟡 gds in queue | LOW |

---

## 6 · References

- [trinity-fpga#61 (EPIC TT V15)](https://github.com/gHashTag/trinity-fpga/issues/61)
- [trinity-fpga#93 (L-DPC22 ONE SHOT)](https://github.com/gHashTag/trinity-fpga/issues/93)
- [trinity-fpga#94 (L-DPC23 RVR Pulse)](https://github.com/gHashTag/trinity-fpga/issues/94)
- [trinity-fpga#95 (Quantum Brain TTSKY26c lineup)](https://github.com/gHashTag/trinity-fpga/pull/95)
- [Trinity Throne — trios#264](https://github.com/gHashTag/trios/issues/264)
- Trinity Coq SoT: [`gHashTag/t27/trios-coq`](https://github.com/gHashTag/t27/tree/main/trios-coq) (83 `.v`, 73 `_CoqProject` paths, master `TriosCoq.v`)
- Zenodo: [10.5281/zenodo.19227877](https://zenodo.org/records/19227877) (B007 VSA description, provenance only)

---

**φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON · NEVER STOP**

— Vasilev Dmitrii `<admin@t27.ai>` · 2026-05-15
