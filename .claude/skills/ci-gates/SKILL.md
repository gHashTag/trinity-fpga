---
name: ci-gates
description: How trinity-fpga's CI gates actually behave — which checks are pre-existing failures, why adding a build.zig target can break the build, and how to verify a Zig change the way CI will. Use before pushing anything that touches build.zig, .github/workflows/, or a file with a pub fn main.
allowed-tools: Bash(gh *), Bash(zig *), Bash(grep *), Bash(python3 *), Read, Grep, Glob
---

# CI gates in trinity-fpga

Written after an iteration that burned two CI cycles rediscovering all of this.

## The single most important fact

**One toolchain now: Zig 0.16.0, locally and in CI alike.** All 16 workflow
pins read 0.16.0 as of #759.

    zig build tri-compile   rc=0
    zig build -Dci=true     rc=0   (also cross-compiled to x86_64-linux-gnu)
    zig build test          rc=0   143/143 steps, 2664/2679 passing
    zig build smoke         rc=0   108 commands in a sandbox, 0 crashes

This section previously said the opposite -- "neither toolchain builds this
tree", with a table of what each one broke, and that bumping CI to 0.16 was
"not available as a fix". That was true when written and was retired by
#758/#759/#760. If you are reading a claim like that anywhere else in the
tree, re-measure before acting on it.

**The bump is what found the work.** All seven remaining workflows were GREEN
on 0.15.2, and that green was the defect: the pin hid 43 compile errors across
30 files -- every target beyond `tri`. A version pin that no longer matches
the code is a gate measuring the wrong thing.

### The 0.16 essentials

Six shim modules restore removed stdlib surface -- `tri_time`, `tri_env`,
`tri_proc`, `tri_mutex`, `tri_rand`, `tri_io`. They are **build modules**:
import by name, never by relative path. Full reference:
`.claude/rules/zig-016-migration.md`.

**Always call subprocesses through `tri_proc`.** Neither `std.process.spawn`
nor `std.process.run` resolves a bare program name through PATH in 0.16, so
`.{ "zig", "fmt" }` compiles perfectly and fails at runtime. That shipped once.

**Cross-compile before pushing.** `zig build -Dci=true -Dtarget=x86_64-linux-gnu`
takes seconds and reaches the comptime-dead branches a macOS build never
analyses. Three Linux-only breaks were found exactly this way, each of which
had compiled cleanly locally.

## Before you push

### Touching `build.zig`?

Adding an executable target is the highest-risk edit in this repo, because two
gates pull in opposite directions:

- **`ratchet`** (reachability) wants every entry point declared, and reads
  `build.zig` **as text** — `re.findall(r'b\.path\("([^"]+)"\)')` plus an
  `@import` walk. It never runs the build.
- **`Validate VIBEE Codegen`** runs `zig build -Dci=true` under **0.16.0** and
  will try to compile whatever you declared.

If the file uses any Zig 0.16 API, satisfying the first gate breaks the second.
The resolution already in the tree:

```zig
// b.path() stays literal inside the guard, so the text-reading ratchet still
// sees the entry point while CI never compiles it.
if (!ci_mode) {
    const exe = b.addExecutable(.{ ... .root_source_file = b.path("src/tri/foo.zig") ... });
    b.installArtifact(exe);
}
```

Check both directions before pushing:

```bash
zig build -Dci=true --list-steps | grep -c your-step   # expect 0
zig build --list-steps | grep -c your-step             # expect 1
```

**A `createModule` is not a target.** Zig only compiles modules that something
attaches. Three `b.path()` hits for a 0.16 file can still be exactly one real
failure — check which are `addExecutable` + `installArtifact`.

### Touching a file with `pub fn main`?

Guarding it out of CI deletes its only automated check. `zig-0-16-migrated.yml`
exists so that guard *moves* coverage instead of dropping it: it compiles every
file matching `std.process.Init` under a real 0.16 toolchain, with the list
**derived by grep**, so newly migrated files are covered automatically.

If you add a guard, you do not need to touch that workflow. If you change the
0.16 main signature, you do — and its empty-result check will fail loudly rather
than pass green on an empty list.

## Verify the way CI will, not the way your laptop will

**Pin the target.** This is not pedantry; it cost a red CI run:

```bash
zig build-exe src/path/file.zig -target x86_64-linux
```

macOS links libc implicitly, Linux does not. Ten files compiled clean natively
and one (`src/trinet/main.zig`) failed on the runner with
`dependency on libc must be explicitly specified`. Cross-compiling reproduces
it locally in seconds. Files that genuinely need libc get `-lc`.

**Run workflow shell bodies before pushing.** Extract and execute them:

```bash
python3 -c "import yaml,sys;d=yaml.safe_load(open('.github/workflows/W.yml'));\
sys.stdout.write([s for s in d['jobs']['J']['steps'] if s.get('name')=='NAME'][0]['run'])" > /tmp/body.sh
bash /tmp/body.sh
```

The local `/bin/bash` is **3.2** — no `mapfile`, no `${x@Q}`. Anything you
cannot run here is untested until CI says so. Prefer
`while IFS= read -r x; do arr+=("$x"); done < <(...)`.

## Reading a red PR

Four checks are **red on `main`** and are not yours:

- `orphan-artefacts`
- `withdrawn-live`
- `⚡ Brain Health Check`
- `📋 Brain Health Report`

Confirm before blaming your diff:

```bash
gh pr checks <N> --repo gHashTag/trinity-fpga --json name,bucket \
  | jq -r 'group_by(.bucket)[] | "\(.[0].bucket): \([.[].name]|unique|join(", "))"'
```

Anything red beyond those four is yours.

**A compiler error names a position, not a defect class.** `zig build` reports
the first failure only. Before fixing the file it named, enumerate the set that
file belongs to:

```bash
grep -rl 'std\.process\.Init' src/            # the class
for f in $(...); do grep -q "b.path(\"$f\")" build.zig && echo "TARGET $f"; done
```

Two pushes were spent walking a class one member at a time. One grep would have
replaced both.

## Related

- `.github/reachability-baseline` — the ratchet's stored count
- `.github/workflows/tri-build.yml` — header explains why 0.16.0 is pinned,
  and what the old 0.15.2 pin was for
- `.github/workflows/zig-0-16-migrated.yml` — the other half of that trade
- `docs/zig-migration-rules.md` — the API-level 0.15→0.16 notes
