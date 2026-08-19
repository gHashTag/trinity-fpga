# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

`trinity-fpga` is the orchestrator repo for the Trinity project family. It is a Zig-first monorepo that also contains Rust FPGA tooling, Verilog designs, and a Docusaurus docs site.

- **Primary language**: Zig (current toolchain is Zig 0.16.0 in this environment; many modules were written for Zig 0.15.x and are still being migrated).
- **No top-level `build.zig`**: the root `build.zig` was intentionally removed and converted to a `.tri` spec. Individual subprojects still have their own `build.zig` files (e.g., `src/vibeec/build.zig`, `deploy/trinity-nexus/build.zig`).
- **Source of truth**: `.tri` specs in `specs/` and `.trinity/ralph/specs/`. Generated outputs live in `generated/` and `var/trinity/output/` and must not be edited by hand.
- **External kernel**: `external/zig-golden-float` (git submodule) provides the numerical core for GF16, TF3, VSA, and ternary VM operations.
- **FPGA tools**: `rings/` is a Cargo workspace that builds the bitstream flash/verify binary (`trios-fpga`).
- **Compiler**: the VIBEE/Tri compiler sources are in `src/vibeec/`; prebuilt binaries are in `tools/bin/`.

## Common Commands

### Zig

- Check Zig version: `zig version`
- Format a file or directory: `zig fmt src/path/to/file.zig`
- Check formatting without writing: `zig fmt --check src/`
- Run tests for a single file: `zig test src/path/to/file.zig`
- AST check a file: `zig ast-check src/path/to/file.zig`
- Note: `zig build` does **not** work from the repository root because there is no root `build.zig`. Use subproject build files or the `tri` pipeline instead.

### VIBEE / `.tri` Code Generation

- Generate from a spec: `tools/bin/vibee_gen <path/to/spec.tri>` or `tools/bin/vibee_arm64 <path/to/spec.tri>`
- The compiler emits Zig, TRI-27 assembly (`.t27`), Verilog, or Python depending on the spec's `language:` field.
- Generated output is written to `var/trinity/output/` and `generated/`. Edit the spec and regenerate — never edit generated files directly.

### `tri` CLI

- The `tri` CLI entry point is `src/tri/main.zig`. There is no prebuilt `tri` binary at the repo root in this environment; to run it you would need a build step for `src/tri/main.zig` or use an existing build artifact if present.
- Common subcommands referenced throughout the codebase: `tri pipeline run "<task>"`, `tri dev scan`, `tri dev pick --smart`, `tri spec create`, `tri gen`, `tri test`, `tri verdict --toxic`, `tri experience save`, `tri git commit`, `tri agent spawn <issue>`, `tri agent run <issue>`.

### Rust FPGA Workspace (`rings/`)

- Build: `cargo build --workspace`
- Test: `cargo test --workspace`
- Run the bitstream CLI: `cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- --help`
- Flash example: `cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- --xvc-host 192.168.1.30 flash --board XC7A200T --bitstream fpga/vsa/DESIGN.bit`

### FPGA Synthesis (openXC7)

- The canonical FPGA board is an ALINX **AX7203** Artix-7 **XC7A200T-2FBG484**.
- Synthesis uses the `regymm/openxc7` Docker image (amd64; requires QEMU on ARM Macs).
- UART bridge commands referenced in `fpga/README.md`: `tri fpga build-uart`, `tri fpga flash-uart`, `tri fpga uart-test`, `tri fpga status`.
- For detailed board truth, pin mappings, and the full synthesis/flash command sequence, follow `.claude/skills/fpga-synth/SKILL.md`.

### Documentation Site

- Local dev: `cd docs && yarn install && yarn start`
- Build: `cd docs && yarn build`
- `baseUrl` is `/trinity/docs/` — do not change it; it breaks all asset paths.

## High-Level Architecture

### The `.tri` Spec-First Pipeline

The project follows a strict "spec-first" workflow:

```
specs/**/*.tri (VIBEE/Tri spec)  ← SINGLE source of truth
    │
    ├── tools/bin/vibee_gen  → var/trinity/output/*.zig
    ├── tools/bin/vibee_gen  → *.t27 (TRI-27 assembly)
    ├── tools/bin/vibee_gen  → *.v (Verilog/FPGA)
    └── future: Python, Rust, Go targets
```

- `src/vibeec/` is the VIBEE compiler: parser, codegen, type checker, bytecode emitter, VM runtime, JIT, Verilog backend.
- `.tri` specs define modules with `name`, `version`, `language`, `module`, `types`, and `behaviors` (each behavior has `given`, `when`, `then`).
- `.vibee` files in `specs/tri/` are the same spec format with a different extension; treat them identically.

### `tri` CLI and the Golden Chain

`src/tri/main.zig` is the unified CLI. It is decomposed into ~650 files covering:

- Brain-zone modules (`src/tri/brain/`, amygdala, hippocampus, cortex, etc.)
- Golden Chain pipeline (`src/tri/golden_chain.zig`, `src/tri/pipeline_executor.zig`)
- Agent orchestration (`src/tri/mu_agent.zig`, `src/tri/swarm/`, `src/tri/cloud_orchestrator.zig`)
- Railway/Deployment helpers (`src/cli/railway_*.zig`)
- FPGA integration (`src/cli/fpga_*.zig`, `src/tri/sacred_fpga.zig`)

The canonical 8/10-step pipeline is:

1. `tri dev scan`
2. `tri dev pick --smart`
3. `tri issue comment N`
4. `tri spec create`
5. `tri gen`
6. `tri test`
7. `tri verdict --toxic`
8. `tri experience save`
9. `tri git commit`
10. `tri loop decide`

### Module Map

| Area | Location | Notes |
|------|----------|-------|
| Ternary VM / VSA core | `src/vsa*.zig`, `src/vm.zig`, `src/hybrid.zig`, `src/sdk.zig` | Allowed direct-edit core library files |
| VIBEE compiler | `src/vibeec/` | Has its own `build.zig` |
| `tri` CLI | `src/tri/` | Entry point `src/tri/main.zig` |
| Agent / orchestration | `src/agent_mu/`, `src/tri/mu_agent.zig` | Issue-bound autonomous agents |
| HSLM training | `src/hslm/` | 74/74 tests required via `zig test src/hslm/model.zig` |
| BSD verification | `src/bsd/` | 3,063,485 Cremona curves verified; read-only LMFDB data in `data/ecdata/` |
| FPGA bitstream tooling | `rings/FP-00`, `rings/FP-01`, `rings/FP-02`, `rings/BR-BITSTREAM` | Cargo workspace |
| Verilog designs | `fpga/openxc7-synth/`, `fpga/vsa/`, `fpga/rtl/` | Synthesized with openXC7 |
| Docs | `docs/` | Docusaurus site |
| Trinity Nexus (experimental) | `deploy/trinity-nexus/` | Separate Zig workspace with core/lang/symb/network/canvas/tools modules |

### Dependency Graph

From `README.md`:

```
t27                    ← SSOT: Ternary specs + Rust bootstrap compiler
         ↑
zig-golden-float      ← Numerical core: GF16, TF3, JIT, VM
         ↑
zig-sacred-geometry     ← Sacred geometry: φ-attention, Beal
zig-physics             ← Quantum: QCD, gravity, dark matter, baryogenesis
zig-hdc                 ← Hyperdimensional: VSA, Sequence HDC
zig-knowledge-graph     ← Knowledge Graph: server + CLI
trinity-training        ← HSLM ML: benchmarks, datasets
         ↑
zig-agents              ← Agents: MCP, autonomous
zig-crypto-mining       ← BTC mining + DePIN
         ↑
trinity                 ← Orchestrator (links all via build.zig.zon)
```

## Important Rules

### Source of Truth

- `.tri` specs are the single source of truth. If a `.tri` spec exists for a module, edit the spec and regenerate — do not hand-edit the generated `.zig`/`.v`/`.py` files.
- Direct `.zig` edits are only allowed for: core library (`src/vsa.zig`, `src/vm.zig`, `src/hybrid.zig`, `src/sdk.zig`), pipeline infrastructure, build system, MCP/bot code, HSLM training, BSD verification, and config files.
- Files in `generated/` and `var/trinity/output/` are read-only.

### Development Workflow

- Use the pipeline: `tri pipeline run "<task>"`. If it fails 3 times, diagnose the pipeline/spec, not the generated code.
- MNL (Mistake → Not-repeat → Learning): a task that failed 3+ consecutive times is considered toxic and should be skipped; re-prioritize based on similar solved tasks.
- Every agent/container must have a `SOUL.md` and be bound to exactly one GitHub issue (canonical registry: `.trinity/issue_bindings.json`).
- Significant agent actions must be reflected as GitHub issue comments using Protocol v2 prefixes (`🔍 [RESEARCH]`, `📜 [SPEC]`, `⚙️ [CODEGEN]`, `🧪 [TEST]`, `☣️ [VERDICT]`, `✅ [DONE]`).

### Code Style & Commits

- Format Zig with `zig fmt` before committing.
- Commit format: `feat(<module>): <description>`, `fix(<module>): ...`, `refactor(<module>): ...`, `docs(<module>): ...`, `chore(<module>): ...`.
- Commit messages must be in English only. Example:
  ```
  feat(cli): add XC7A200T board support

  Added support for the XC7A200T board.
  ```
- Push after commit. Never force-push to `main` without explicit user approval.
- Large files (>1MB) must be in `.gitignore`.

### No Shell Scripts

- Do not create, edit, or reference `.sh`/`.bash` files. Legacy scripts in `scripts/`, `deploy/`, `.ralph/scripts/`, and `fpga/` are marked for deletion.
- Add new tooling as `tri` subcommands or Zig binaries, not shell scripts.
- **One exemption**: `research/benchmark/**/harness/` retains the shell harnesses that produced published measurements. They are evidence, not tooling — never sourced, extended, or copied from, and never included in a sweep that deletes `.sh` files. See `.claude/rules/no-shell-scripts.md`.

### Author Attribution

- Canonical maintainer: **Dmitrii Vasilev** / GitHub **@gHashTag**.
- Do not replace this attribution with generic placeholders in files listed in `tools/config/author_attribution_guard.manifest`.
- `zig build test` in the Nexus subproject runs `src/tri/author_attribution_guard.zig` and fails if attribution is missing.

### VSA / Ternary Conventions

- VSA operations use the trit set `{-1, 0, +1}`. Never mix with binary representations.
- Ternary VM and sacred-geometry constants derive from `φ² + 1/φ² = 3`.

### Zig 0.15 / 0.16 API Notes

- `SplitIterator.first()` / `.next()` return `?[]const u8` in Zig 0.15+. Use `if (it.next()) |slice|` instead of direct slice access.
- `ArrayList.init()` returns an error union in newer Zig; prefer `ArrayList(T).initCapacity(allocator, capacity)` or explicitly handle the error union.
- `orelse` requires an optional on the left-hand side.
- `std.io.Reader.read(buffer)` returns the number of bytes read; use `if (bytes_read > 0)` checks. `readAll()` was removed in Zig 0.15.
- The installed Zig in this environment is 0.16.0; many files still target 0.15.x APIs, so verify compatibility when editing.

### Testing

- Tests live in the same file as source (Zig convention).
- Run a single file: `zig test src/path/to/file.zig`.
- Run the VIBEEC test suite from its subproject: `cd src/vibeec && zig build test`.
- Run HSLM model tests: `zig test src/hslm/model.zig`.
- Run BSD verification: `zig test src/bsd/verify_bsd.zig`.
- Run Rust workspace tests: `cargo test --workspace`.
- Never skip failing tests; fix the root cause.

### FPGA

- Target board: Artix-7 `xc7a200tfbg484-2` (ALINX AX7203).
- Canonical UART bridge constraints: `fpga/constraints/uart_bridge_j2.xdc`.
- LED on pin T23 is active-low.
- After modifying Verilog, run synthesis via the openXC7 Docker flow or the `/fpga-synth` skill.

## Key Reference Files

- `AGENTS.md` — 27-agent alphabet and Agent T (Queen Trinity) orchestration rules.
- `templates/SOUL.md` — mandatory agent soul template.
- `docs/zig-migration-rules.md` — detailed Zig 0.15 migration notes.
- `graph_v2.json` — module dependency graph used by the orchestrator.
- `.claude/rules/` — detailed per-domain rules (testing, FPGA, specs, HSLM, MCP, docsite, etc.).
- `.cursor/rules/author-attribution-lock.mdc` — author attribution lock for Cursor/Copilot.
- `.github/copilot-instructions.md` — Copilot-specific forbidden-file and toxic-verdict rules.
