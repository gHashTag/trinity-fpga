# How much of `src/tri` is reachable?

**Nothing is deleted on the strength of this.** It is a measurement with a
stated method and a known weakness, offered so someone can decide.

## The number

| | |
|---|---|
| `.zig` files under `src/tri` | **744** |
| reachable from `build.zig` or a relative `@import` chain | 349 |
| reached by **neither** | **395** (3,134,987 bytes) |

## Method, and why it under-counts rather than over-counts

Two sources of reachability were followed:

1. every `@import("….zig")` between files under `src/tri`, resolved relative to
   the importing file;
2. every path named by `b.path("…")` in `build.zig`.

Adding (2) moved the count from 407 to 395, so named modules account for twelve
files. That is the correction worth making before quoting a figure — the first
number was wrong by that much.

**The remaining weakness runs one way.** If a dead file imports another dead
file, the second is counted as *reached*. So whole dead clusters keep each other
alive in this analysis, and the true unreachable set is **larger than 395, not
smaller**. Anyone acting on this should re-run it iteratively — remove the
orphans, recompute, repeat — rather than treating one pass as final.

## The largest orphans

```
228,915  src/tri/tri_math_backup.zig
 61,811  src/tri/tri_serve.zig
 56,044  src/tri/testing/generated_tests.zig
 55,024  src/tri/safeguards/safeguards.zig
 54,833  src/tri/safeguards/sacred_safeguards.zig
 51,623  src/tri/queen_tamagotchi.zig
 49,427  src/tri/queen_cron.zig
 47,934  src/tri/orchestrator_v2_full.zig
```

## Why this was looked at, which is the useful part

Not curiosity. While scanning for command handlers safe to add to the smoke
test, the scan pointed at `runFibCommand`, `runLucasCommand` and
`runPhiCommand` in **`tri_math_backup.zig`** — a file imported by nothing.

I had fixed those three handlers earlier in the session, in
`src/tri/math/commands.zig`. Two copies of each exist; the live one is the one I
edited, confirmed by the fact that nothing imports the backup. **But I nearly
edited the dead copy this iteration, on the strength of a search result.**

That is the hazard a 228 KB orphan carries. It is not wasted disk; it is a file
that answers `grep` with plausible, editable, unreachable code — and the repair
of a defect landing in it would look correct, pass review, and change nothing.

`zig-hdc`'s own header records the same failure from the other side: two
maintained copies of `src/vsa/*` diverged, and fixing sixteen defects in one
left all sixteen standing in the other.

## What would settle it

A gate. `zig build` already knows the reachable set; a step that compares it
against the files on disk and reports the difference would keep this from
growing back, and would have made this note unnecessary.

That is worth more than a one-time deletion, and it is the same argument as the
part-coverage gate: the value is in noticing, not in the single repair.
