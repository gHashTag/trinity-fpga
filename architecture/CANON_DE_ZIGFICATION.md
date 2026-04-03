# CANON_DE_ZIGFICATION.md — Trinity Canonical Foundation

**Status:** Canonical (v1.0)
**Date:** 2026-04-04
**Reference:** ADR-001

---

## Purpose

Trinity Project transition to **t27 as the canonical language specification**.

### Why t27?

1. **Single Source of Truth** — All implementations (Zig, C, Verilog, Python) derive from .t27 specs
2. **Hardware-First Design** — t27 models Ternary Computing directly (27 registers, Coptic ISA)
3. **Zero Zig in Specs** — Specifications are hardware-agnostic, language-agnostic
4. **Multi-Target Generation** — One .t27 spec generates Zig, C, Verilog, and more

---

## The Canonical Hierarchy

```
architecture/          ← Foundation documents (THIS FILE)
├── CANON_DE_ZIGFICATION.md  ← This foundation
├── ADR-001-de-zigfication.md  ← Architectural Decision
├── graph.tri                  ← Dependency graph
│
t27/                    ← NEW CANONICAL LANGUAGE
├── specs/                    ← .t27 specifications (SOURCE OF TRUTH)
│   ├── base/                 ← Base types and operations
│   │   ├── types.t27       ← Trit, PackedTrit, TernaryWord
│   │   └── ops.t27         ← trit multiply, add, carry
│   ├── numeric/               ← Numeric formats
│   │   ├── gf16.t27        ← GoldenFloat16 encode/decode
│   │   └── tf3.t27         ← TF3 format, 8-bit weights
│   ├── math/                  ← Mathematical constants
│   │   └── constants.t27   ← φ, identities, sacred chain
│   ├── vsa/                   ← Hyperdimensional computing
│   │   └── ops.t27          ← bind/unbind/bundle
│   ├── isa/                   ← Coptic ISA
│   │   └── registers.t27   ← 27 registers, Coptic opcodes
│   ├── nn/                    ← Neural network primitives
│   │   ├── attention.t27   ← Sacred Attention d_k^(-φ³)
│   │   └── hslm.t27         ← HSLM architecture
│   ├── fpga/                  ← FPGA primitives
│   │   └── mac.t27          ← Zero-DSP LUT MAC
│   └── queen/                  ← Orchestration
│       └── lotus.t27        ← 6-phase orchestration
│
├── compiler/               ← T27 Compiler
│   ├── parser/               ← .t27 parser
│   ├── codegen/              ← Code generators
│   │   ├── zig/            ← .t27 → Zig
│   │   ├── verilog/        ← .t27 → Verilog
│   │   └── c/              ← .t27 → C
│   └── runtime/             ← Runtime for T27
│
├── conformance/            ← Language-agnostic test vectors
│   ├── trit-multiply.json
│   ├── gf16-roundtrip.json
│   ├── sacred-constants.json
│   └── vsa-bind.json
│
├── bindings/               ← Interop layers
│   ├── zig/
│   ├── python/
│   └── c/
│
├── tests/
├── examples/
├── docs/                  ← Documentation
│   ├── language.md
│   └── migration-map.md  ← trinity/src/* → specs/*
│
└── build.tri              ← CANONICAL build (NOT build.zig!)
```

---

## The Law

**All Trinity development MUST follow this hierarchy:**

1. ✅ **.t27 spec = Source of Truth** — No direct .zig coding where .tri spec should be used
2. ✅ **zig-golden-float = Kernel** — Numerical operations live in the kernel
3. ✅ **trinity/ = Language Layer** — Configs, docs, .tri CLI

---

## Migration Path

| Old Location | New Location | Notes |
|------------|--------------|--------|
| `src/formats.zig` | `t27/specs/numeric/gf16.t27` | GF16 encode/decode |
| `src/ternary/*.zig` | `t27/specs/base/*.t27` | Ternary types |
| `src/vsa/*.zig` | `t27/specs/vsa/*.t27` | VSA operations |
| `build.zig` | `t27/build.tri` | Build system |
| `specs/**/*.tri` | `t27/specs/**/*.t27` | Same format, canonical location |

---

## Conformance Testing

All implementations MUST pass conformance tests in `t27/conformance/`:

```
conformance/
├── trit-multiply.json     ← 3×3=7, 7×1=7, etc.
├── gf16-roundtrip.json    ← f32↔gf16 conversion accuracy
├── sacred-constants.json  ← φ² + 1/φ² = 3
└── vsa-bind.json          ← bind operation correctness
```

---

## Build System

**Canonical build file:** `t27/build.tri`

```
.t27 (VIBEE spec)              ← Source of truth
    │
    ├── tri gen → .t27 (TRI-27 Assembly)
    ├── tri gen → .zig (via zig-golden-float kernel)
    ├── tri gen → .py  (Python target, future)
    ├── tri gen → .rs  (Rust target, future)
    └── tri gen → .go  (Go target, future)
```

**NOT** `build.zig` — that's for Zig-only projects.

---

## Status

| Component | Status |
|----------|--------|
| Architecture foundation | ✅ DONE |
| t27/specs/base/* | 🚧 IN PROGRESS |
| t27/specs/numeric/* | 🚧 IN PROGRESS |
| t27/specs/math/* | ⏳ TODO |
| t27/compiler/* | ⏳ TODO |
| t27/conformance/* | ⏳ TODO |
| t27/build.tri | ⏳ TODO |
| docs/migration-map.md | ⏳ TODO |

---

**Maintained by:** Architecture Decision ADR-001
**Updated:** 2026-04-04
