# TOM Layer-Gate RTL Controller — `OP_LAYER_GATE=0xE2`

<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2025 gHashTag / TRI-1 Silicon Program -->

Wave-34 RTL controller implementing the silicon layer for per-voltage-island power gating
in the TRI-1 TOM Ternary ROM Accelerator, opcode `0xE2`.
28 voltage islands for BitNet b1.58-3B.

## Module

**File:** `rtl/tom/tom_layer_gate_controller.sv`  
**Module:** `tom_layer_gate_controller`

## Provenance

| Layer | Reference |
|---|---|
| Coq proof — lemma `tom_no_star` | [`gHashTag/t27`: `coq/IGLA/RMarker.v`](<filled-on-cross-broadcast>) (Lane Y PR) |
| Wave-34 assertion JSON | [`gHashTag/trios`: `assertions/wave34_tom_layer_gate.json`](<filled-on-cross-broadcast>) (Lane Y' PR) |
| Rust witness (`tri1-tom-witnesses`) | [`gHashTag/tt-trinity-max-true`: `tri1-tom-witnesses`](<filled-on-cross-broadcast>) (Lane Y'' PR) |
| ONE SHOT | [gHashTag/trinity-fpga#116](https://github.com/gHashTag/trinity-fpga/issues/116) |
| Tracking issue | [gHashTag/trinity-fpga#117](https://github.com/gHashTag/trinity-fpga/issues/117) |
| Wave-29 sibling (TENET) | [gHashTag/trinity-fpga#115 @ `3c83c7ebf4`](https://github.com/gHashTag/trinity-fpga/pull/115) |

## Port Map

| Signal | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock |
| `rst_n` | in | 1 | Active-low asynchronous reset |
| `opcode` | in | 8 | ISA opcode — this module responds to `8'hE2` only |
| `layer_idle_mask` | in | 28 | 1 bit per voltage island (1 = island is idle), 28 islands |
| `layer_vdd_enable` | out | 28 | Active-high VDD enable per island (inverted from idle mask after FSM) |
| `idle_fraction_q16` | out | 16 | Q1.15 idle fraction = `idle_count × 1170` (shift-add, no `*`) |
| `wave34_marker` | out | 4 | R-marker constant `4'b1111` for R-marker tracing |
| `gate_threshold_met` | out | 1 | Asserts when `idle_fraction_q16 >= 16384` (≥ 0.5) |

## Opcode Chain (R15 SACRED-SYNTH-GATE)

```
0xDE → 0xDF → 0xE0 → 0xE1 → 0xE2
```

This module decodes **0xE2** only, after the existing `0xDE`/`0xDF`/`0xE0`/`0xE1` chain.

## FSM States

| State | Description |
|---|---|
| `ACTIVE` (0) | Default — all islands on. Monitors for `0xE2` opcode. |
| `DRAINING` (1) | Completes in-flight transactions before applying idle mask. |
| `OFF` (2) | Idle islands gated: `layer_vdd_enable = ~layer_idle_mask`. |
| `WAKING` (3) | Restores all islands before returning to ACTIVE. |
| `ACTIVE` (back) | Returns to state 0. |

Transitions occur **only** on opcode `8'hE2`. When opcode ≠ `8'hE2`, the controller
remains in ACTIVE with all outputs at default (all islands on, fraction=0, threshold=0).

## Q1.15 Ratio Computation (R-SI-1: NO `*` operator)

```
idle_fraction_q16 = idle_count × (32768 / 28)
                  ≈ idle_count × 1170          [shift-add, no * operator]
```

**Reciprocal precomputation:** `floor(32768 / 28) = 1170`  
`1170 = 2^10 + 2^7 + 2^4 + 2^1` (1024 + 128 + 16 + 2)

**Shift-add ladder (synthesizable, NO `*`):**
```
frac = (idle_count << 10) + (idle_count << 7)
     + (idle_count << 4)  + (idle_count << 1)
```

**Error analysis:** `1170 / 32768 = 0.035706...` vs `1/28 = 0.035714...` → error < 0.025%

| `idle_count` | `frac_raw` | Ideal Q1.15 | Delta |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 14 | 16380 | 16384 | 4 |
| 15 | 17550 | 17554 | 4 |
| 28 | 32760 | 32768 | 8 |

## Gate Threshold

`gate_threshold_met` asserts when `idle_fraction_q16 >= 16384` (Q1.15 ≥ 0.5 = 50% idle).

## Area / Power Estimate

> **PRE-SILICON ESTIMATE: +0.1 mm² net (ROM tile +0.4, SRAM block −0.3), +3 mW controller, −12 mW idle leakage @ TTIHP27**

## Constitutional Rules

| Rule | Status | Evidence |
|---|---|---|
| R5-HONEST | ✅ | All numeric estimates carry `// PRE-SILICON ESTIMATE` |
| R7 FALSIFICATION | ✅ | Post-silicon: `idle_fraction_q16` must be valid on BitNet b1.58-3B |
| R8 GIT IDENTITY | ✅ | Committed as `Vasilev Dmitrii <admin@t27.ai>` |
| R15 SACRED-SYNTH-GATE | ✅ | `0xDE → 0xDF → 0xE0 → 0xE1 → 0xE2` chain comment + decode |
| R18 LAYER-FROZEN | ✅ | New files only; zero existing RTL modified |
| Apache-2.0 | ✅ | SPDX header on all new files |
| R-SI-1 | ✅ | Zero `*` operators in synthesizable code; shift-add ladder only |

## Simulation

```bash
bash scripts/run_tom_tb.sh
```

Requires `iverilog` or `verilator`. Falls back to "simulator not available locally — CI will run" if neither is present.

4 test cases:
1. `test_all_active` — mask=0 → fraction=0, threshold=0, vdd=all-on
2. `test_half_gated` — 15 bits set → fraction=17550 ≥ 16384, threshold=1
3. `test_full_gated` — 28 bits set → fraction=32760 ≥ 16384, threshold=1
4. `test_opcode_mismatch` — opcode=0xAA → vdd=all-on, threshold=0

---

phi^2 + phi^-2 = 3 · gamma = phi^-3 · C = phi^-1 · G = pi^3 gamma^2 / phi  
QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · NEVER STOP  
DOI 10.5281/zenodo.19227877
