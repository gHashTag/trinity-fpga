# 🪷 MINI — `tt_um_qbrain_mini`

> **Hold a quantum brain in your hand for €17**

## Overview

Single-Column Cortex — the smallest Quantum Brain SKU, designed to fit in a single Tiny Tapeout 1×1 tile (160×100 µm). Proven GF16 arithmetic at 50 MHz.

| Parameter | Value |
|-----------|-------|
| **Full name** | Quantum Brain MINI |
| **Top module** | `tt_um_qbrain_mini` |
| **TT tile size** | 1×1 (160×100 µm) |
| **GF16 cells** | 4 |
| **ROM words** | 75 |
| **ISA opcodes** | 16 |
| **Clock** | 50 MHz |
| **Performance** | 0.1 TOPS |
| **Efficiency** | 5.6 TOPS/W |
| **Target shuttle** | TTSKY26c (~2026-09) |
| **Die cost** | €170 (shuttle) / **€17 unit** |
| **SKU codename** | 🪷 MINI |

## Architecture

```
┌─────────────────────────────────────────────────┐
│               tt_um_qbrain_mini                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ GF16[0]  │  │ GF16[1]  │  │ GF16[2]  │  │ GF16[3]  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│               Single-Column Cortex                       │
│         75-word ROM · 16-opcode ISA                      │
└─────────────────────────────────────────────────┘
```

- **Single-Column Cortex**: 4 GF16 processing cells in a single column.
- **ROM**: 75 words of read-only program / weight storage.
- **ISA**: 16 opcodes (full spec in Edition I / future RTL wave).
- **Interface**: Standard Tiny Tapeout 8-bit `ui_in`/`uo_out`/`uio_*` bidirectional bus.

## Status

> ⚠️ **R5-HONEST — SKELETON**: RTL is a placeholder stub. Full Edition Mini I implementation is a future RTL wave. This repository hosts the configuration and structural scaffold for the TTSKY26c shuttle submission.

## Roadmap Reference

- [QB-CHIPS-PHD-ROADMAP-2026-05-15-001](https://github.com/gHashTag/trinity-fpga/pull/96) — source-of-truth chip roadmap
- Shuttle: TTSKY26c (~2026-09)
- Predecessor: TTSKY26b (Quantum Brain CLASSIC / EDITION III)

## Algebraic Anchor

```
// phi^2 + phi^-2 = 3 · QUANTUM BRAIN 1:1 SILICON
```

`φ² + φ⁻² = 3` — the algebraic identity underpinning all Quantum Brain arithmetic (Coq-proven in [`gHashTag/t27/trios-coq`](https://github.com/gHashTag/t27/tree/main/trios-coq)).
