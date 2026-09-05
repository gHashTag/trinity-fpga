---
name: ci-gates
description: How trinity-fpga's CI gates actually behave — which checks are pre-existing failures, why adding a build.zig target can break the build, and how to verify a Zig change the way CI will. Use before pushing anything that touches build.zig, .github/workflows/, or a file with a pub fn main.
allowed-tools: Bash(gh *), Bash(zig *), Bash(grep *), Bash(python3 *), Read, Grep, Glob
---

# CI gates in trinity-fpga

Written after an iteration that burned two CI cycles rediscovering all of this.

## The single most important fact

**Neither Zig toolchain builds this tree.** The repo is mid-migration:

| Toolchain | Builds | Fails on |
|---|---|---|
| **0.15.2** (what CI runs) | everything else | files migrated to `main(init: std.process.Init)` |
| **0.16.0** (what's installed locally) | the migrated files | ~20 targets still on 0.15 `std.fs` / `std.process` APIs |

So "just bump CI to 0.16" is **not available** as a fix and won't be until the
migration finishes. Measured, not assumed: `zig build -Dci=true` under 0.16
locally fails on ~20 targets.

## Before you push

### Touching `build.zig`?

Adding an executable target is the highest-risk edit in this repo, because two
gates pull in opposite directions:

- **`ratchet`** (reachability) wants every entry point declared, and reads
  `build.zig` **as text** — `re.findall(r'b\.path\("([^"]+)"\)')` plus an
  `@import` walk. It never runs the build.
- **`Validate VIBEE Codegen`** runs `zig build -Dci=true` under **0.15.2** and
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

**Pin the ABI, not just the OS.** `-target x86_64-linux` means **musl** — Zig
defaults a Linux target with no ABI suffix. Measured, compiling with `-lc`:

| target | result |
|---|---|
| `x86_64-linux` | statically linked — musl |
| `x86_64-linux-gnu` | dynamically linked, `/lib64/ld-linux` — glibc |

The runner is glibc, and `std.c` carries ~12 `isGnu()`/`isMusl()` switches. A
gate pinned to the bare form compiles against a libc no real build uses.

## A green gate is not a working gate

Eight gates in this repo have been found reporting success while measuring
nothing. Before trusting one, ask whether it has ever emitted its own
measurement line.

- **`overfull.yml`: 298 green runs, zero measurements.** `cargo install tectonic
  || true` fails on the runner; `check_overfull.py` turns the resulting
  `FileNotFoundError` into `sys.exit(0)`. The string `overfull boxes over` has
  never appeared in any run log.
- **Six glob-scoped `tools/check_*.py` print OK on an empty scope.**
  `check_script_rot.py` scans `fpga/**/*.sh` — files this repo's own rules mark
  for deletion, so the roadmap ends with it scanning zero files and passing.
- **`reachability-ratchet.yml` reports `No change.` green when its own
  measurement crashes** — no `pipefail` anywhere in this repo's workflows, so
  `python3 … | tee` discards the exit status.

**The instrument already exists: `tools/check_gates_can_fail.py`.** It injects,
per gate, the defect that gate exists to catch and requires red. Run it before
trusting any gate:

```bash
python3 tools/check_gates_can_fail.py
```

It reports `UNTESTABLE` for gates already red on a clean tree, and **still exits
0** — correct on its own terms, but it means the check degrades silently as the
tree worsens. `gates-can-fail.yml` therefore enforces a floor on the *tested
count*, not just the exit code. When you add a gate of this shape, gate the
denominator too: **a derived scope that shrinks to zero passes green.**

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
- `.github/workflows/tri-build.yml` — header explains why 0.15.2 is pinned
- `.github/workflows/zig-0-16-migrated.yml` — the other half of that trade
- `docs/zig-migration-rules.md` — the API-level 0.15→0.16 notes
