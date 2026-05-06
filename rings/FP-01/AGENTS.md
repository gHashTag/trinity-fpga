# AGENTS — FP-01

Primary: ALPHA
Review: LEAD

## Scope

- RTL synthesis via Docker (no local Vivado)
- All commands via std::process::Command
- No filesystem mutations outside output_dir

## Laws

- L3: ASCII-only, English identifiers
- L7: No .sh — all logic in Rust
