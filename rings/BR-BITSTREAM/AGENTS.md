# AGENTS — BR-BITSTREAM

Primary: ALPHA
Review: LEAD

## Scope

- CLI binary that integrates FP-00..FP-02
- All subcommands via clap derive
- No direct I/O — delegates to ring crates

## Laws

- L3: ASCII-only, English identifiers
- L7: No .sh — CLI replaces all scripts
