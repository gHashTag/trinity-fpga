---
name: trinity-test
description: Run Trinity test suites and analyze results. Use for testing VSA, VM, Firebird, WASM, or full test suite.
argument-hint: [module] (vsa, vm, firebird, all)
---

# Trinity Test Runner

## Last Build Status
!`cd "$(git rev-parse --show-toplevel)" && zig build 2>&1 | tail -5`

## Task

Run tests for: $ARGUMENTS

### Test Commands by Module
| Module | Command |
|--------|---------|
| All | `cd "$(git rev-parse --show-toplevel)" && zig build test` |
| VSA | `cd "$(git rev-parse --show-toplevel)" && zig test src/vsa.zig` |
| VM | `cd "$(git rev-parse --show-toplevel)" && zig test src/vm.zig` |
| Single file | `cd "$(git rev-parse --show-toplevel)" && zig test src/<file>.zig` |

### Steps
1. Run the appropriate test command based on the module argument
2. Parse output for pass/fail counts
3. If failures: read the failing test, identify root cause, suggest fix
4. Report summary: total tests, passed, failed, duration

### Key Test Files
- VSA tests: `src/vsa.zig`, `src/vsa/tests.zig`
- VM tests: `src/vm.zig`
- BSD verification: `src/bsd/verify_bsd.zig`, `src/bsd/verify_lmfdb.zig`
- HSLM: `src/hslm/model.zig`, `src/hslm/trainer.zig`
- Self-improver: `src/vibeec/self_improver.zig`
