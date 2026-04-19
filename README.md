# trinity-fpga

**FPGA Synthesis and Hardware Deployment for Trinity** — T27 VM, openxc7-synth, and ternary computing on FPGAs.

## Modules

- `src/tvc/` — Ternary Vector Computing VM, JIT, indexer, RAG
- `fpga/` — Hardware synthesis, flash scripts, guides

## Hardware

DSLogic Plus, Artix-7, Kintex-7, ESP32

## License

MIT © 2026 Trinity Project

## Architecture

Trinity is an orchestrator connecting a family of focused micro-repositories. Each repo has a single responsibility and can be used independently.

### Dependency Graph

```
t27                    ← SSOT: Ternary specs + Rust bootstrap compiler
         ↑
zig-golden-float      ← Numerical core: GF16, TF3, JIT, VM
         ↑
zig-sacred-geometry     ← Sacred geometry: φ-attention, Beal
zig-physics             ← Quantum: QCD, gravity, dark matter, baryogenesis
zig-hdc                 ← Hyperdimensional: VSA, Sequence HDC
zig-knowledge-graph     ← Knowledge Graph: server + CLI
trinity-training        ← HSLM ML: benchmarks, datasets (208MB)
         ↑
zig-agents              ← Agents: MCP, autonomous (~519KB)
zig-crypto-mining       ← BTC mining + DePIN (~60KB)
         ↑
trinity                 ← Orchestrator (links all via build.zig.zon)
```

### Repository Overview

| # | Repository | Status | Size | Description |
|---|---|---|---|---|
| 1 | [t27](https://github.com/gHashTag/t27) | ✅ LIVE | 577+ specs | Ternary SSOT + Rust bootstrap |
| 2 | [zig-golden-float](https://github.com/gHashTag/zig-golden-float) | ✅ LIVE | ~1MB | Numerical core: GF16, TF3, JIT, VM |
| 3 | [zig-hdc](https://github.com/gHashTag/zig-hdc) | ✅ LIVE | 352KB | VSA, HRR, hyperdimensional computing |
| 4 | [zig-sacred-geometry](https://github.com/gHashTag/zig-sacred-geometry) | ✅ LIVE | 58KB | Sacred φ-geometry, Beal, sacred constants |
| 5 | [zig-physics](https://github.com/gHashTag/zig-physics) | ✅ LIVE | 36KB (src) | Quantum: QCD, gravity, dark matter |
| 6 | [zig-knowledge-graph](https://github.com/gHashTag/zig-knowledge-graph) | ✅ LIVE | ~100KB | KG server + CLI |
| 7 | [zig-agents](https://github.com/gHashTag/zig-agents) | ✅ LIVE | ~519KB (src!) | Agents, MCP, autonomous |
| 8 | [zig-crypto-mining](https://github.com/gHashTag/zig-crypto-mining) | ✅ LIVE | ~60KB | BTC mining + DePIN |
| 9 | [trinity-training](https://github.com/gHashTag/trinity-training) | ✅ LIVE | 208MB data | HSLM, benchmarks, datasets |
| 10 | [trinity](https://github.com/gHashTag/trinity) | ✅ LIVE | ~500MB | Orchestrator, API, CLI, VIBEE, FPGA |

### Migration Status

**Phase 1 — HIGH Priority:** ✅ Complete
- [zig-golden-float](https://github.com/gHashTag/zig-golden-float) — Cloned as submodule in trinity-training
- [zig-knowledge-graph](https://github.com/gHashTag/zig-knowledge-graph) — Extracted from trinity
- [zig-crypto-mining](https://github.com/gHashTag/zig-crypto-mining) — Extracted from trinity
- [zig-physics](https://github.com/gHashTag/zig-physics) — Extracted from trinity
- [zig-hdc](https://github.com/gHashTag/zig-hdc) — Extracted from trinity
- [zig-agents](https://github.com/gHashTag/zig-agents) — Extracted from trinity
- [zig-sacred-geometry](https://github.com/gHashTag/zig-sacred-geometry) — Extracted from trinity

**Phase 2 — MEDIUM Priority:** 🔄 In Progress
- Firebird/BitNet → trinity-training
- DePIN/$TRI → zig-crypto-mining
- VIBEE compiler → t27

**Phase 3 — LOW Priority:** ⏳ Pending
- trinity-fpga — Create new repo
- trinity-cli — Unify TRI CLI
- trinity-www — Docsite

### Using a Module Independently

Each micro-repo is a standalone Zig package. To use any module independently:

\`\`\`zig build.zig.zon\`\` — Clone and cache dependencies

Example: Using zig-golden-float from any repo
\`\`\`// build.zig.zon
.dependencies = .{
    .zig_golden_float = .{
        .url = "https://github.com/gHashTag/zig-golden-float/archive/refs/heads/main.tar.gz",
    },
},
\`\`

\`\`\`zig fetch --save https://github.com/gHashTag/zig-golden-float/archive/refs/heads/main.tar.gz`\`\`

