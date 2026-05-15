# 🌌 HOLOGRAPHIC — `tt_um_qbrain_holo`

> **One brain, many dies, one frozen hash**

## Overview

The Quantum Brain HOLOGRAPHIC SKU implements a 4×4 PE mesh with multi-die hologram capability, spanning 1×2 TT tiles. D2D (die-to-die) ports allow coherent, frozen-hash replication across multiple physical dies.

| Parameter | Value |
|-----------|-------|
| **Full name** | Quantum Brain HOLOGRAPHIC |
| **Top module** | `tt_um_qbrain_holo` |
| **TT tile size** | 1×2 (320×100 µm) |
| **PE count** | 16 PE × 2 MAC = 32 effective |
| **D2D ports** | 4 cross-die ports (N/E/S/W) |
| **ROM** | 75 + 4 R-marker words |
| **ISA opcodes** | 16 + 4 R-MARKER ops |
| **R-MARKER ops** | `R_MARKER_LOAD`, `R_MARKER_STORE`, `R_MARKER_SWAP`, `R_MARKER_SEAL` |
| **Clock** | 250 MHz |
| **Performance** | 4–25 TOPS |
| **Efficiency** | 55 TOPS/W |
| **Target shuttle** | TTSKY26c (~2026-09) |
| **SKU codename** | 🌌 HOLOGRAPHIC |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     tt_um_qbrain_holo  (1×2 tile)               │
│                                                                  │
│   d2d_n (North)                                                  │
│      │                                                           │
│  ┌───┴──────────────────────────────────────────────────────┐   │
│  │              4×4 PE Mesh (16 PE × 2 MAC)                 │   │
│  │  ┌───┐ ┌───┐ ┌───┐ ┌───┐   ┌───┐ ┌───┐ ┌───┐ ┌───┐     │   │
│  │  │PE0│ │PE1│ │PE2│ │PE3│   │PE4│ │PE5│ │PE6│ │PE7│     │   │
│  │  └───┘ └───┘ └───┘ └───┘   └───┘ └───┘ └───┘ └───┘     │   │
│  │  ┌───┐ ┌───┐ ┌───┐ ┌───┐   ┌───┐ ┌───┐ ┌───┐ ┌───┐     │   │
│  │  │PE8│ │PE9│ │PE10│ │PE11│  │PE12│ │PE13│ │PE14│ │PE15│  │   │
│  │  └───┘ └───┘ └───┘ └───┘   └───┘ └───┘ └───┘ └───┘     │   │
│  │                                                          │   │
│  │  R-marker ROM (75 + 4 words) │ R_MARKER_LOAD/STORE/     │   │
│  │                               │ SWAP/SEAL                │   │
│  └──────────────────────────────────────────────────────────┘   │
│      │                                          │                │
│  d2d_w (West)                            d2d_e (East)           │
│                        │                                         │
│                    d2d_s (South)                                 │
└─────────────────────────────────────────────────────────────────┘
```

- **4×4 PE mesh**: 16 Processing Elements, each with 2 MAC units = 32 effective MACs total.
- **D2D ports**: 4 directional cross-die ports (`d2d_n/e/s/w`) routed through `uio_*` for multi-die hologram coherence.
- **R-marker ROM**: 75 standard words + 4 holographic reference-marker entries.
- **Extended ISA**: 16 standard opcodes + 4 R-MARKER opcodes (`R_MARKER_LOAD`, `R_MARKER_STORE`, `R_MARKER_SWAP`, `R_MARKER_SEAL`).
- **Frozen hash**: All dies in a holographic cluster share one canonical hash sealed at `R_MARKER_SEAL` time.

## R-MARKER Protocol

| Opcode | Code | Description |
|--------|------|-------------|
| `R_MARKER_LOAD` | `5'h10` | Load holographic reference marker into active register |
| `R_MARKER_STORE` | `5'h11` | Store current state snapshot to R-marker ROM slot |
| `R_MARKER_SWAP` | `5'h12` | Swap active state with a stored R-marker snapshot |
| `R_MARKER_SEAL` | `5'h13` | Freeze and hash the holographic state across all D2D ports |

## Status

> ⚠️ **R5-HONEST — SKELETON**: RTL is a placeholder stub. Full Edition III / HOLOGRAPHIC I implementation is a future RTL wave. This repository hosts configuration and structural scaffold for the TTSKY26c shuttle submission.

## Roadmap Reference

- [QB-CHIPS-PHD-ROADMAP-2026-05-15-001](https://github.com/gHashTag/trinity-fpga/pull/96) — source-of-truth chip roadmap
- Shuttle: TTSKY26c (~2026-09)
- Predecessor: TTSKY26b (Quantum Brain CLASSIC / EDITION III)

## Algebraic Anchor

```
// phi^2 + phi^-2 = 3 · QUANTUM BRAIN 1:1 SILICON
```

`φ² + φ⁻² = 3` — the algebraic identity underpinning all Quantum Brain arithmetic (Coq-proven in [`gHashTag/t27/trios-coq`](https://github.com/gHashTag/t27/tree/main/trios-coq)).
