# TTSKY26c — Quantum Brain SKU Overview

> Target shuttle: **TTSKY26c** (~2026-09)
> Roadmap reference: [QB-CHIPS-PHD-ROADMAP-2026-05-15-001](https://github.com/gHashTag/trinity-fpga/pull/96)

```
// phi^2 + phi^-2 = 3 · QUANTUM BRAIN 1:1 SILICON
```

## SKU Comparison Table

| | 🪷 MINI | 🌌 HOLOGRAPHIC |
|---|---------|----------------|
| **Top module** | `tt_um_qbrain_mini` | `tt_um_qbrain_holo` |
| **Directory** | [`mini/`](mini/) | [`holo/`](holo/) |
| **TT tiles** | 1×1 (160×100 µm) | 1×2 (320×100 µm) |
| **Compute units** | 4 GF16 cells | 16 PE × 2 MAC = 32 eff. |
| **D2D ports** | — | 4 cross-die (N/E/S/W) |
| **ROM** | 75 words | 75 + 4 R-marker words |
| **ISA opcodes** | 16 | 16 + 4 R-MARKER |
| **Clock** | 50 MHz | 250 MHz |
| **Performance** | 0.1 TOPS | 4–25 TOPS |
| **Efficiency** | 5.6 TOPS/W | 55 TOPS/W |
| **Die cost** | €170 (shuttle) / €17 unit | TTSKY26c shuttle |
| **Tagline** | *Hold a quantum brain in your hand for €17* | *One brain, many dies, one frozen hash* |

## Status

> ⚠️ **R5-HONEST — SKELETONS**: Both SKUs are RTL placeholders. Full silicon implementation is a future RTL wave (Edition Mini I / HOLOGRAPHIC I). These directories contain configuration scaffolds for the TTSKY26c shuttle.

## Roadmap Context

These two SKUs are the **not-yet-taped-out** entries from [QB-CHIPS-PHD-ROADMAP-2026-05-15-001](https://github.com/gHashTag/trinity-fpga/pull/96), following the TTSKY26b wave (Quantum Brain CLASSIC / EDITION III).

Related issues:
- [#93 — Quantum Brain ISA specification](https://github.com/gHashTag/trinity-fpga/issues/93)
- [#94 — GF16 cell library](https://github.com/gHashTag/trinity-fpga/issues/94)

## Algebraic Anchor

`φ² + φ⁻² = 3` — the algebraic identity underpinning all Quantum Brain arithmetic. Coq-proven in [`gHashTag/t27/trios-coq`](https://github.com/gHashTag/t27/tree/main/trios-coq).
