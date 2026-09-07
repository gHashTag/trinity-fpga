---
name: negative-control
description: Before trusting any check, gate, test, or measurement, prove it can fail. Six gates in this repo were green because they were structurally incapable of reporting a problem. Use whenever you write a CI gate, a test, a census script, or are about to report "N problems found" — especially when N is zero.
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Prove the check can fail before you believe it passed

**A gate that has never said "no" has not been tested.**

This skill exists because that sentence was learned six separate times in one
codebase, each time expensively, and every instance produced confident green
output while measuring nothing.

## The six, so the shape is recognisable

| gate | why it could not fail |
|---|---|
| `git show HEAD:$f \| zig ast-check --stdin` | **the flag does not exist.** The baseline half errored for every file, so the "was it already broken?" branch never ran. Reported "0 broken" across 655, 224 and 206 files |
| `cd /Users/playra/trinity-w1 && zig build` | the directory is from another machine. `cd` fails, `&&` short-circuits, no build runs. Two agents "checked the build" this way for months |
| `zig test src/sacred_constants.zig` | the file contained no tests. "All 0 tests passed" |
| `tri stress --health` gate | gates on a `NotImplemented` stub. Its own comment records 47 runs, none passing |
| `zig fmt --check <path list>` | eight files fail to parse and **none is in the path list** |
| assert mode is 0600 after `save()` | the final mode is 0600 whether the narrowing happens before or after the write. Blind to the window it was written to catch |
| `vibeec_tests` in `build.zig` | its root, `src/vibeec/codegen_tests.zig`, imports nothing except `std`. Named after the compiler, reaches none of it — **nothing in `src/vibeec/` was covered by the test step at all** |
| `zig ast-check` on generated output | the generator had written a **0-byte file**. An empty file parses. "Regenerated output ast-checks OK" was a statement about nothing |

The 0600 one is the sharpest: **I wrote it myself, in this repo, while fixing
the other five.** Knowing the pattern does not confer immunity — and I then
nearly shipped the `vibeec_tests` one by adding a new test to a file no build
target reached.

## The procedure

Three commands. Do them before quoting any number.

### 1. Feed it something known-bad

```bash
# a test: reinstate the defect it was written for
# a gate: point it at a file you know violates the rule
# a census: add one instance of the thing being counted
```

It must fail, and **fail for the reason you expect** — read the message, do not
just check the exit code. A gate that fails for an unrelated reason is still
untested.

### 2. Feed it something known-good

Rarer but catches the opposite error: a gate that always fails is also useless,
and it trains everyone to ignore red. Piping a *known-good* file through
`ast-check --stdin` is what finally exposed that flag.

### 3. Check the denominator moved

If the check derives its own work list, break the derivation and confirm it
**fails** rather than passing over an empty set:

```zig
// an empty result is a failure, not a pass
if (items.len == 0) return error.NothingMatched;
```

Every derived-list gate in this repo now carries that guard. `tools/cmd_smoke.zig`
found its own stdout/stderr bug this way within a minute of first running.

## A test you added is not a test that runs

Writing the test is the easy half. Two failure modes, both hit in this repo:

- **The file has no route to a build target.** `zig test path/to/file.zig`
  passing proves nothing about CI. Confirm with the *step*, not the file:

  ```bash
  zig build test --summary all   # note the TEST COUNT before and after
  ```

  Adding `src/vibeec/validate_cmd.zig` as a test root moved it 2789 → 2811.
  A count that does not move means your tests did not run. Then break one on
  purpose and confirm `zig build test` exits 1.

- **The module boundary silently forbids the import.** `@import("../x.zig")`
  from inside a directory that is its own module root fails with *import of
  file outside module path*. Put the test on the side that can import
  downward, not the side that reads better.

## An empty artefact passes every checker

`zig ast-check` on a 0-byte file returns rc=0. So does `zig fmt --check`.
Before validating anything a tool just produced, check it exists and is
non-empty:

```bash
[ -s "$out" ] || { echo "generator wrote nothing"; exit 1; }
```

This is how `tools/bin/vibee_arm64` came to be 0 bytes and stay that way.

## Exit codes and pipes

```bash
zig build test | grep "Summary"; echo $?   # WRONG: that is grep's exit code
zig build test > /tmp/out.txt 2>&1; echo $?  # the build's
```

This cost a wrong "all green" report. `$?` after a pipeline is the **last**
command's.

## Grep patterns that under-report

Two failures, both of which reported a red build as green:

- **Anchoring too narrowly.** `grep -E "^src/|^tools/"` missed errors in
  `examples/`, `tests/` and `build.zig:` — and printed "0 errors" while the
  build was failing. Anchor to the shape, not the location:
  `^[a-zA-Z0-9_./-]+\.zig:[0-9]+:[0-9]+: error:`
- **Splitting on the wrong separator.** `gh pr checks | awk '$2=="fail"'`
  reads a *word from the check's name*, because names contain spaces. Use
  `awk -F'\t'`. This nearly produced "only pre-existing failures" when four
  were mine.

## Aliases hide work from every census

A count taken with one spelling is a **lower bound**:

```bash
grep -rlE "^const \w+ = std\.(fs|time|process|posix|crypto);" src/
```

48 files in this tree alias a std namespace and then never write the prefix
again. 17% of remaining call sites were invisible to a `std.fs.` grep, and one
file read as fully migrated while holding eight untouched calls.

## When the property is untestable, restructure until it is not

If a negative control cannot make the check fail, the check is measuring the
wrong thing — **change the code, not the assertion**.

The 0600 case: asserting the end state could not distinguish the orderings, so
the create-and-narrow pair was extracted into `createPrivateFile`, which
returns a file already narrowed and empty. The test now checks it at the one
moment the two orderings differ, and removing the narrowing fails three tests.

## What to write down

When a check is deliberately narrow, say so **in the check**, not in a commit
message nobody re-reads. `tools/api_census.zig` prints its own limitation
every run — that reachability follows path imports and named modules but
cannot see a module wired up by a helper, so its figure is a lower bound.
A number that travels without its caveat will be over-trusted.
