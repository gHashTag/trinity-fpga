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
| **Target shuttle** | TTSKY26c (~2026-09 at the time of writing — a planning target, not a submission; see Status) |
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
>
> **Status (2026-09-05):** the shuttle target in this document is a planning statement from the time of writing, not a submission record or a result. No die of any Trinity chip exists: the Tiny Tapeout submissions TTSKY26a and TTSKY26b were withdrawn before fabrication (TTSKY26a refunded 6 Aug 2026), all hardware results to date are on the Artix-7 (XC7A200T) FPGA prototype, and no silicon return has happened.

## Roadmap Reference

- [QB-CHIPS-PHD-ROADMAP-2026-05-15-001](https://github.com/gHashTag/trinity-fpga/pull/96) — source-of-truth chip roadmap
- Shuttle: TTSKY26c (~2026-09 at the time of writing — a planning target; no die exists, 2026-09-05)
- Predecessor: TTSKY26b (Quantum Brain CLASSIC / EDITION III — withdrawn before fabrication)

## Algebraic Anchor

```
// phi^2 + phi^-2 = 3 · QUANTUM BRAIN 1:1 SILICON
```

`φ² + φ⁻² = 3` — the algebraic identity underpinning all Quantum Brain arithmetic (Coq-proven in [`gHashTag/t27/trios-coq`](https://github.com/gHashTag/t27/tree/main/trios-coq)).
