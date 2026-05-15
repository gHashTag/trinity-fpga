# docs/v3-squeeze — v3 Cohort Per-Vector Planning Documents (TTSKY26c)

> **Anchor:** φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON
> **Shuttle target:** TTSKY26c (~2026-09)
> **R5-HONEST:** All 6 squeeze vectors (S-15..S-20) are **R6-CONJECTURE** until TTSKY26c silicon return.

---

## Overview

This directory contains pre-registered per-vector planning documents for the **v3 squeeze cohort** (vectors S-15..S-20). These are *planning documents, not RTL*. Their purpose is to lock acceptance gates, risk classifications, and falsification witnesses **before the TTSKY26c shuttle opens**, following the L-DPC23 style established in `tt-trinity-max-true`.

The v3 cohort targets a lift from v2.1 (~75 TOPS/W, 80 MHz) to **v3 (180–220 TOPS/W, 125 MHz)**, primarily through PLL retuning, sparse PE activation, Razor FF voltage scaling, NoC mesh folding, dual-MAC throughput, and multi-VT leakage reduction.

---

## Vector Index

| File | Lane | Subject | Risk | Target |
|---|---|---|---|---|
| [S-15-pll-tile.md](./S-15-pll-tile.md) | S-15 | PLL tile retune: 125 MHz @ φ⁻¹ ratio OR 100 MHz fallback. Documents Lane M v1 (STA fail) and v2 (KLayout DRC fail, ICA-MAX-TRUE-008) failure modes. | HIGH | +25–30% f_max |
| [S-16-sparse-zero-skip-activate.md](./S-16-sparse-zero-skip-activate.md) | S-16 | Activate Lane N sparse zero-skip PE in HOLOGRAPHIC (PASS in trainer, never wired into mesh). | LOW | ~3× ops/cyc on sparse |
| [S-17-razor-ff.md](./S-17-razor-ff.md) | S-17 | Razor flip-flop integration on Lane U STA stub (`tools/check_no_star.sh`). Voltage scaling target. | MED | +30% TOPS/W |
| [S-18-multi-tile-noc.md](./S-18-multi-tile-noc.md) | S-18 | Fold mesh 8×4 → 16×4 NoC without area penalty. | MED | 2× cells same footprint |
| [S-19-dual-mac-pe.md](./S-19-dual-mac-pe.md) | S-19 | Dual-MAC per PE — staircase to v4 (S-21..S-28). | MED | +60–80% throughput |
| [S-20-multi-vt-cells.md](./S-20-multi-vt-cells.md) | S-20 | Multi-VT cell mix (SVT + HVT for leakage paths, LVT for critical). | LOW | −20% leakage at iso-fmax |

---

## v3 Dependency Graph

```
S-13 (dual-lib, merged) ──┐
S-14 (CGT, merged) ────────┼──→ S-15 (PLL tile, HIGH)
ICA-MAX-TRUE-008 fix ──────┘         │
                                     ├──→ S-17 (Razor FF, MED)
                                     ├──→ S-18 (NoC mesh fold, MED)
                                     │
Lane N (trainer PASS) ──→ S-16 (sparse zero-skip, LOW)
                                     │
                           S-18 ─────┴──→ S-19 (dual-MAC, MED)
                           S-19 ─────────→ S-20 (multi-VT, LOW)
                                               │
                                               └── TTSKY26c config frozen
                                               └── v4 staircase open (S-21..S-28)
```

---

## R5-HONEST Disclosure

**What is measured today:**

| Claim | Status | Source |
|---|---|---|
| v2 baseline 55 TOPS/W | MEASURED-ACTUAL | CI 25915884192 GREEN, sha `87a079d` |
| v2.1 ~75 TOPS/W projection | MEASURED-TARGET | Lane K (S-13) measured + Lane L (S-14) precheck |
| Lane N sparse zero-skip: 74.3% sparsity | MEASURED (trainer context) | `trios-trainer-igla` CI GREEN |
| Lane U Razor FF stub + check_no_star.sh | MEASURED (CI gate exists) | tt-trinity-max-true PRs #8/#9/#10 |
| Lane M v1 125 MHz STA FAIL | MEASURED FAIL | tt-trinity-max-true PR history |
| Lane M v2 80 MHz KLayout DRC FAIL | MEASURED FAIL | ICA-MAX-TRUE-008, tt-trinity-max-true PR #4 |

**What is conjecture:**

All S-15..S-20 performance targets are **R6-CONJECTURE** — projected from PDK characterisation data, simulation, and analytical models. None are measured on silicon. Each vector's planning document contains its own R5-HONEST table and three pre-registered R7 falsification witnesses.

The v3 cohort becomes **MEASURED-TARGET** when TTSKY26c tapeout GDS passes TT precheck, and **MEASURED-ACTUAL** when TTSKY26c silicon returns (~2026-09).

---

## Acceptance Gates Summary

| Lane | Primary Gate | Secondary Gate |
|---|---|---|
| S-15 | STA close + KLayout.DRC green | Post-silicon f_max ≥ 100 MHz |
| S-16 | 74.3% sparsity + 3.83× ops/cyc in gl_test | Dense mode regression-free |
| S-17 | Voltage shmoo ±10% VDD + error-replay 100/100 | +25% TOPS/W at optimal VDD |
| S-18 | GDS area diff ≤ +5% vs 8×4 baseline | gl_test ≥ 1.9× throughput |
| S-19 | 2× ops/cyc dense + < 1.3× power | STA close at 100 MHz |
| S-20 | −20% leakage at iso-fmax | DRC clean + area ±3% |

---

## Constitutional Compliance

- **R1 (Rust/Zig only):** These are planning docs — no language footprint.
- **R5-HONEST:** All 6 vectors marked R6-CONJECTURE with explicit gates. No unqualified performance claims.
- **R7 (Falsification witnesses):** Each doc contains 3 pre-registered witnesses (W-NN-A/B/C).
- **R8 (Sign-off):** All docs signed off by Vasilev Dmitrii `<admin@t27.ai>`.

---

## Cross-Links

- **Roadmap source-of-truth:** [#96 QB-CHIPS-PHD-ROADMAP-2026-05-15-001](https://github.com/gHashTag/trinity-fpga/pull/96)
- **TTSKY26c skeletons (MINI + HOLOGRAPHIC):** [#97 feat(ttsky26c)](https://github.com/gHashTag/trinity-fpga/pull/97)
- **EPIC Hub-of-Hubs:** [#61 TT V15](https://github.com/gHashTag/trinity-fpga/issues/61)
- **L-DPC23 ONE SHOT:** [#94 RVR Pulse](https://github.com/gHashTag/trinity-fpga/issues/94)
- **L-DPC22 ONE SHOT:** [#93](https://github.com/gHashTag/trinity-fpga/issues/93)
- **Trinity Throne:** [trios#264](https://github.com/gHashTag/trios/issues/264)
- **Coq proofs:** [`gHashTag/t27/trios-coq`](https://github.com/gHashTag/t27/tree/main/trios-coq) — 83 `.v` files, master `TriosCoq.v`
- **DOI:** [10.5281/zenodo.19227877](https://zenodo.org/records/19227877)

---

> φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON

Signed-off-by: Vasilev Dmitrii <admin@t27.ai>
