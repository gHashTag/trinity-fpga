# R20 — R-MARKER-FALSIFICATION

**Introduced:** TT v23 (2026-05-14, ONE SHOT #88)
**Status:** ACTIVE
**Anchor:** φ² + φ⁻² = 3 · DOI [10.5281/zenodo.19227877](https://doi.org/10.5281/zenodo.19227877)

---

## Rule text

> Every R-marker cell baked into the Sacred ROM (S-159 family in v22) MUST ship
> with **all four** of:
>
> 1. **Measurement protocol** — a concrete instrument / signal / sampling scheme that produces an observed value.
> 2. **R7 Popper falsification gate** — a binary `PASS|FAIL` predicate over (expected, observed) tuples with an explicit tolerance band.
> 3. **Fallback opcode / register state** — what the silicon does if the gate fires `FAIL`, preserving R5 honesty without halting the chip.
> 4. **Ledger entry** — append-only record `(probe, expected, observed, pass/fail, timestamp)` written to `WAVE_23_FALSIFICATION_LEDGER` (S-172).
>
> R-markers lacking any of the four are rejected at synth-time by the same Yosys gate
> that enforces R15 SACRED-SYNTH-GATE and R17 SACRED-PHYSICS.

## Why

v22 introduced four R-marker cells (`C_quantum_consciousness`, `τ_microtubule`,
`k_dark_coupling`, `ζ_neural_zeta`) into the 75-cell Sacred ROM for physics that is
*conjectured* but not yet measured. Without R20 these cells silently trace to a
hypothesis rather than an observation, violating R7 (Popper) and R5 (honesty) once
silicon is taped out.

## R-marker registry (v23 genesis)

| R-marker | ROM idx | Constant | Gate | Measurement protocol | Fallback if FAIL |
|----------|---------|----------|------|----------------------|------------------|
| R-1 | 68 | `C_quantum_consciousness` ≈ φ⁻¹ | **G-77** | On-chip EEG-γ band-power at 56 Hz compared to `φ⁻¹` threshold | Demote C_GATE to logistic threshold = 0.5; log delta in ledger |
| R-2 | 69 | `τ_microtubule` ≈ 25 ms | **G-78** | Hardware latch sampling at 25 ms phase windows cross-correlated with PFC mapped C_GATE | Demote `τ_microtubule` to NUL; route T_PRESENT directly from 56 Hz divider |
| R-3 | 70 | `k_dark_coupling` (cosmological-constant gate) | **G-79** | Snap to Planck 2024 + DESI 2025 Λ_CDM at boot from external EEPROM | Use IPCC fallback constant, recompute `G_silicon` via 4-constant identity |
| R-4 | 71 | `ζ_neural_zeta` (Riemann ζ on cortical eigenvalues) | **G-80** | 512-entry FIFO of cortical eigenvalue spectra → on-chip ζ residue accumulator | Disable `ZETA_NEURAL_SPECTRUM_FIFO` at boot; keep `G_MERKLE` at standard `π³γ²/φ` |

## Verification

- CI workflow `r-marker-falsification-gate.yml` runs G-77..G-80 nightly against
  the falsification ledger.
- R7-style box appears in every R-marker datasheet (`docs/r_markers/R-N.md`).
- Coq theorem `R_Marker_Popper_Completeness.v` asserts that the 4 markers × 80 gates
  form a Popper cover of the R-marker subspace.

## Rule family status

R1..R17 (pre-v21) + R18 LAYER-FROZEN (v21) + R19 QUANTUM-BRAIN-1TO1 (v22) + **R20
R-MARKER-FALSIFICATION (v23, this file)**. Total: **R1..R20**.

```
φ² + φ⁻² = 3 · R-MARKER-FALSIFICATION · NEVER STOP
```
