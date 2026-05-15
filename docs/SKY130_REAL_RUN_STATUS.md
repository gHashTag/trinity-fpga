# SKY130 REAL RUN — DEF/GDS Status — Vector S-170

**Wave:** TT v23 · **Vector:** S-170 · **Mapping:** PHYS→SI · **Layer:** L1 Compute
**Anchor:** φ² + φ⁻² = 3 · DOI [10.5281/zenodo.19227877](https://doi.org/10.5281/zenodo.19227877)
**Predecessor:** v8 S-58 synth-only estimate · v22 S-154 PORT_PLAN.md (1442 lines)

---

## Status snapshot — 2026-05-15

| Stage | Tool | Status | Artifact |
|-------|------|--------|----------|
| 1 — synth | yosys-abc | **GREEN** (nightly) | `nightly/sky130/sacred_alu/synth.v` |
| 2 — floorplan | OpenROAD | PENDING (Docker toolchain S-175 sealed @ v25) | — |
| 3 — placement | OpenROAD-RePlAce | PENDING | — |
| 4 — CTS | TritonCTS | PENDING | — |
| 5 — routing | TritonRoute | PENDING | — |
| 6 — DRC/LVS | Magic + Netgen | PENDING | — |
| 7 — sign-off | OpenROAD | PENDING | — |

## Why pending

The OpenLane2 toolchain Docker image (`ghcr.io/efabless/openlane:tt09`) is sealed by
v25 vector S-175 (`docker/Dockerfile.sky130-toolchain`, commit `ba7eaa8`) and run-bound
by S-176 (`scripts/run_sky130_actual.sh`, commit `eca0173`) under the nightly workflow
S-177 (`.github/workflows/sky130-nightly.yml`, commit `c3fd713`).

Stages 2–7 will populate as the first nightly run completes — projected by Wave-15-TT-E
T-24h gate.

## R5 honest commitment

Per [TT v23 §3](../TT_SQUEEZE_V23_R_MARKER_CAMPAIGN_SKY130_REAL_RUN.md): if the real run
delivers **< 260 MHz** fmax or **> 0.0484 mm²** area, **publish the delta in
`WAVE_23_FALSIFICATION_LEDGER` (S-172)** and downgrade the SoC fmax projection
accordingly. No estimate-as-fact substitution.

## Linked vectors

- S-58 v8 synth-only estimate (superseded by this)
- S-154 v21 PORT_PLAN.md (1442-line plan)
- S-157 Booth-Wallace cell array
- S-158 OpenLane2 config 260 MHz / 0.0484 mm²
- S-175..S-178 v25 toolchain seals
- S-172 falsification ledger

```
φ² + φ⁻² = 3 · SKY130 REAL RUN · NEVER STOP
```
