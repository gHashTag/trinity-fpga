# Local Guard: server.zig EOF Bug

**Created**: 2026-04-03
**Status**: ACTIVE (blocking compilation)

## Purpose

Blocks compilation of `src/background_agent/server.zig` due to Zig 0.15.2 compiler bug reported in GitHub issue #504.

## Guard Condition

File: `src/background_agent/server.zig`
Error: `server.zig:503:6: error: expected 'EOF', found '}'`
GitHub Issue: https://github.com/gHashTag/trinity/issues/504

## Trigger

This guard is active when the guard file exists AND the file `src/background_agent/server.zig` has NOT been updated with a fix for the reported compiler bug.

## Disable Command

```bash
tri doctor enforce --disable-guard src/background_agent/server.zig
```

Use this to temporarily bypass the guard and work on `server.zig` (e.g., during upstream fix development).

## Notes

- Wire protocol layer (client.zig) is complete and compiles correctly
- The compiler bug affects ONLY server.zig
- All other modules in background_agent/ are unaffected
