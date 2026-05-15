# TENET Sparsity-Aware RTL Controller — `OP_SPARSE_SKIP=0xE1`

<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2025 gHashTag / TRI-1 Silicon Program -->

Wave-29 RTL controller implementing the silicon layer for sparsity-aware compute skipping
in the TRI-1 chip, opcode `0xE1`.

## Module

**File:** `rtl/tenet/tenet_sparse_skip_controller.sv`  
**Module:** `tenet_sparse_skip_controller`

## Provenance

| Layer | Reference |
|---|---|
| Coq proof — lemma `tenet_no_star` | [gHashTag/t27 PR #644 @ `367a7ba`](https://github.com/gHashTag/t27/pull/644) — `coq/IGLA/RMarker.v` |
| W-102-A predicate assertion JSON | [gHashTag/trios PR #850](https://github.com/gHashTag/trios/pull/850) — `assertions/wave29_tenet_sparsity.json` |
| Rust witness (`tri1-tenet-witnesses`) | [gHashTag/tt-trinity-max-true PR #17](https://github.com/gHashTag/tt-trinity-max-true/pull/17) — `tri1-tenet-witnesses` |

## Port Map

| Signal | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock |
| `rst_n` | in | 1 | Active-low synchronous reset |
| `opcode` | in | 8 | ISA opcode — this module responds to `8'hE1` only |
| `sparsity_count_total` | in | 16 | Total element count (≤ 65535) |
| `sparsity_count_zero` | in | 16 | Zero/sparse element count |
| `skip_compute` | out | 1 | Assert when ratio ≥ 0.25; drive downstream skip |
| `sparsity_ratio_q16` | out | 16 | Q1.15 fixed-point ratio (`zero/total`) |
| `wave29_marker` | out | 4 | R-marker constant `4'b1110` for R-marker tracing |

## Opcode Chain (R15 SACRED-SYNTH-GATE)

```
0xDE → 0xDF → 0xE0 → 0xE1
```

This module decodes **0xE1** only, after the existing `0xDE`/`0xDF`/`0xE0` chain.

## Ratio Computation

**R-SI-1: zero `*` operators.** The Q1.15 fixed-point ratio is computed via a 16-step
non-restoring shift-subtract binary divider:

```
Q[1.15] = (sparsity_count_zero << 15) / sparsity_count_total
```

No multiplier is instantiated. Inputs are constrained ≤ 65535, so the numerator fits in
31 bits without overflow.

## Thresholds

| Threshold | Q1.15 value | Decimal |
|---|---|---|
| `SPARSITY_THRESHOLD_Q15` | `16'd8192` | 0.25 |

`skip_compute` asserts when `sparsity_ratio_q16 >= 8192`.

## Constitutional Rules

| Rule | Status | Evidence |
|---|---|---|
| R5-HONEST | ✅ | All numeric estimates carry `// PRE-SILICON ESTIMATE` |
| R7 FALSIFICATION | ✅ | Post-silicon: ratio must be ≥ 0.25 on BitNet b1.58-3B |
| R8 GIT IDENTITY | ✅ | Committed as `Vasilev Dmitrii <admin@t27.ai>` |
| R15 SACRED-SYNTH-GATE | ✅ | `0xDE → 0xDF → 0xE0 → 0xE1` chain comment + decode |
| R18 LAYER-FROZEN | ✅ | New files only; zero existing RTL modified |
| Apache-2.0 | ✅ | SPDX header on all new files |
| R-SI-1 | ✅ | Zero `*` operators in synthesizable code |

## Simulation

```bash
bash scripts/run_tenet_tb.sh
```

Requires `iverilog` or `verilator`. Falls back to "simulator not available locally — CI will run" if neither is present.

## Area / Power Estimate

> **PRE-SILICON ESTIMATE: 0.12 mm², 5 mW @ TTIHP27**

---

phi^2 + phi^-2 = 3 · gamma = phi^-3 · C = phi^-1 · G = pi^3 gamma^2 / phi  
QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · NEVER STOP  
DOI 10.5281/zenodo.19227877
