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

## When the exit code IS the measurement, never pipe

```bash
python3 tools/check_x.py 2>&1 | tail -4; echo "exit=$?"   # WRONG: reads tail
```

`$?` after a pipeline is the last command's status. This reported a working gate
as vacuous — *"prints FAIL and exits 0"* — when its last line was
`sys.exit(0 if ok else 1)` and it exits 1 correctly. Nothing errors; you just get
a plausible number for the wrong process.

The failure mode is asymmetric and therefore dangerous: it turns **failures into
successes**, so it always reads as reassuring.

```bash
cmd >/tmp/out.log 2>&1; rc=$?          # RIGHT
tail -4 /tmp/out.log; echo "exit=$rc"
```

This is the same defect as the `measurer | tee` one in the workflows above,
committed at the shell instead of in YAML. Knowing the bug does not prevent
typing it — before publishing "this gate is broken", re-measure without the pipe.

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

Four checks are red on `main` and are not caused by your diff. **They are not
"ignore these" — every one has a diagnosed cause.** An earlier version of this
skill listed them as background noise, and that sentence did the work of a green
gate for a whole session: it made a red signal safe to skip without looking.

| check | cause | who fixes it |
|---|---|---|
| `⚡ Brain Health Check` | `zig build tri` **runs** the CLI; it never installs it, so `zig-out/bin/tri` does not exist and the health step has nothing to measure. `tri_step.dependOn(&run_tri.step)`, while `installArtifact` hangs off the *install* step. | candidate fix open in #739 — needs a rebase to retest |
| `📋 Brain Health Report` | downstream of the above | same |
| `withdrawn-live` | **2 flags, and they are not alike.** `0.1797` sits in a `\textbf{}` cell of a live results table — a real assertion of a withdrawn number. `0.92` appears in *"The ratios an earlier draft reported … were the unfilled M=9 rung"*, which reads as a withdrawal but does not match the gate's sentence pattern (`is/are/was/were withdrawn\|retracted`). | paper author — one is a content fix, one is a classification call |
| `orphan-artefacts` | 13 measurement JSONs under `research/arxiv_tnf/measurements/` with no generator script. The gate's own output says the count "has stood for weeks". | paper author — provenance, not infrastructure |

The distinction that matters: the Brain Health pair is **infrastructure** and
fixable by anyone; the other two are **claims about the paper** and are the
author's to settle. Neither category is background noise.

Confirm which checks are actually failing before blaming your diff:

```bash
gh pr checks <N> --repo gHashTag/trinity-fpga --json name,bucket \
  | jq -r 'group_by(.bucket)[] | "\(.[0].bucket): \([.[].name]|unique|join(", "))"'
```

Anything red beyond those four is yours.

**And check whether your diff woke something.** A workflow that watches itself
fires when you edit it, and a job that has not run in months may be broken
independently of your change. `fpga-docker.yml` had run twice in its life and
failed both times; removing one dead `paths:` entry made it fire and revealed a
Dockerfile broken since April. Read the run history before assuming a new red is
a regression:

```bash
gh run list --repo gHashTag/trinity-fpga --workflow <name>.yml --limit 5 \
  --json createdAt,headBranch,conclusion \
  --jq '.[] | "\(.createdAt[0:10])  \(.headBranch)  \(.conclusion)"'
```

Two runs in five months, both failed, means you did not break it — you woke it.

**A compiler error names a position, not a defect class.** `zig build` reports
the first failure only. Before fixing the file it named, enumerate the set that
file belongs to:

```bash
grep -rl 'std\.process\.Init' src/            # the class
for f in $(...); do grep -q "b.path(\"$f\")" build.zig && echo "TARGET $f"; done
```

Two pushes were spent walking a class one member at a time. One grep would have
replaced both.

## Counting red checks: the denominator is workflows, not runs

This query is **wrong**, and it produced a published claim that main had one red
check when it had five:

```bash
gh run list --branch main --limit 40 --json name,conclusion,createdAt \
  | jq 'group_by(.name)[] | max_by(.createdAt) | select(.conclusion=="failure")'
```

Forty *runs* does not contain one run of every *workflow*. A workflow that last
fired hours ago falls out of the window, contributes nothing to the group-by, and
reads as **absent rather than as red**. Use `--limit 200`, or query per workflow,
and say which you did.

A count that shrinks because the instrument could not see far enough looks
exactly like progress.

## 50 workflows can only be tested by merging

`push:` without `pull_request:` — 50 of 118, including every `ax7203-*` synthesis
job. `ax7203-format-cost.yml` is `push: branches: [main]`, so a change to it runs
**only after it lands**.

That is probably deliberate: these are 240-minute FPGA jobs and running them per
PR would be prohibitive. But the consequence is real — for those 50, "verify
before merging" is not available through the normal path, which is part of why
`fpga-bitstream`, `fpga-docker` and `format-cost` all sat broken for months.

The escape hatch is `workflow_dispatch`, which most of them declare:

```bash
gh workflow run <file>.yml --repo gHashTag/trinity-fpga --ref <your-branch>
```

Use it before merging a change to one of these. Do not add `pull_request:` to
them casually — that is a cost decision, not yours to flip in passing.

## Read the file before contradicting it

Diagnosing `ax7203-format-cost.yml`'s routing failure, the external evidence was
strong and entirely outside the file: three sibling GF-mul workflows pass
`-nodsp`, this one does not, this one has never routed. The fix and a confident
comment were written on that basis.

Fifty lines below the edit sat the maintainer's own diagnosis — a nextpnr-xilinx
constant pseudo-net bug on `$PACKER_GND_NET`, explicitly *not* congestion — with
the P&R cascade that exists because of it.

**The stronger the outside evidence, the less the inside seems worth checking.**
When a file already carries a diagnosis, argue with it explicitly and say what
would settle it. Replacing it silently destroys the only record of why the
surrounding workaround exists.

## "Flaky" is a diagnosis, and usually the wrong one

A gate that fails on some branches and passes on others is almost never a timing
problem you can tune away. Before touching a timeout, establish **what the gate
is measuring**.

`qa/browser-audit.mjs` failed the RU language audit on `/dashboard` on some
branches and not others while nothing about `/dashboard` changed. It navigated
with `Page.navigate` to a **hash-only** URL — which does not reload, it fires
`hashchange` and the SPA re-renders asynchronously — then waited a flat `700ms`.
On a heavy route the budget expired while the **previous route's DOM was still
mounted**, so the harness stored route A's text under route B's key.

That is not slowness, it is **misattribution**, and it fails both ways: a
translated page captured under an untranslated route's name passes it; an English
page captured under a translated route's name fails the wrong route.

**A fixed sleep after an async navigation is not a wait, it is a bet** — and when
it loses, the harness does not error, it silently reports the wrong subject. Wait
for the *thing*: require the app to commit the route, then require the DOM to stop
changing across two samples, with a budget to fall through.

Cost is real — the EN audit went 23s → 198s. Waiting for a settled DOM is not
free; guessing was.

And note what this does to history: every green run of that gate before the fix is
weaker evidence than it looked, because the gate was not checking the routes it
named.

## The PASS that had nothing to do with your change

Same session, one step earlier. I found the genuine defect under that flaky gate
(`ProductionDashboard.tsx` had zero `useI18n` calls while sitting in the audit's
ROUTES list from the start), translated the page, rebuilt, ran the audit, got
**PASS** — and nearly committed on it.

Then I checked *which strings the capture actually contained*: neither my new
Russian ones nor the original English ones. The PASS was the harness handing me
another route's DOM. My fix was real; the evidence for it was not.

**Before believing a green that follows your change, confirm the check saw your
change.** One probe — does the captured artifact contain a string only my version
has? — separates a fix from a story. Then close it with a negative control:
revert *only* your file, rebuild, and require the gate to go red.

## Run the control before believing the result — and twice if it fails

A gate that passes on its first run and has never been shown to fail is
decoration. Build the control at the same time as the gate.

Auditing whether any t27.ai route scrolls sideways at 375px, the gate returned a
clean 28 of 28. Injecting a 900px div into `dist/index.html` and requiring it to
go red failed **twice, for two unrelated reasons**:

1. `Emulation.setDeviceMetricsOverride` silently did not apply — the page laid
   out at **980px**, the no-viewport-meta fallback, so nothing overflowed.
2. After switching to a real `--window-size`, still green — because port 4173 was
   held by a `python3 -m http.server` from an **earlier worktree I had already
   deleted**. `git worktree remove --force` does not kill a server started inside
   it. The process kept the port, my new server failed to bind, and every
   measurement described the old branch's build.

Neither was visible in the tool's output; both looked exactly like "the site is
fine".

**How to apply:** when a control fails, do not fix it once and trust the next
green — find out how many independent lies are stacked. And before any audit of a
served artifact, ask what is holding the port:

    lsof -nP -iTCP:4173 -sTCP:LISTEN          # which pid
    lsof -a -p <pid> -d cwd -Fn               # which directory it thinks it is in

Kill a worktree's server before removing the worktree.

**Report the width you measured, not the one you asked for.** Headless Chrome will
not go below **500px** via `--window-size`; the metrics override must be applied
on top of it. Measured `clientWidth` was 375 with both and 500 with the window
size alone.

## A baseline is a claim, so verify it like one

A baseline entry says "this is broken and we are not fixing it today". It then
sits there looking like known debt, indefinitely, and nobody re-checks it.

I put `/queen` and `/tree` into a mobile gate's baseline because their buttons
measured at left 850px and 912px on a 375px screen. I never asked whether a
reader could reach them. They could: both sit in a header with
`overflow-x: auto` carrying **619px of real scroll** — `scrollWidth 976` vs
`clientWidth 357` — so a swipe brings them into view. A scrollable toolbar is a
normal mobile pattern. **The defect was in my gate, not the pages.**

The distinction the check was missing:

- clipped by an ancestor that **cannot** scroll → genuinely lost
- inside a scroller → merely not yet in view

**How to apply:** before adding anything to a baseline, reproduce the defect the
way a user would experience it, not the way your instrument reports it. A number
that looks wrong is a hypothesis; a baseline is where hypotheses become
permanent.

And note the near-miss that should have warned me: a flaky run had earlier
reported those two routes as *clean*, I declined to remove them, and I recorded
that as the baseline working. The entries survived for the right reason applied
to the wrong fact.

**Prove a classifier in both directions in one run.** Two buttons, 600px off the
left margin of two identical 375px containers:

    overflow: hidden   -> reported on all 28 routes
    overflow-x: auto   -> reported on none

Two minutes, and it is the check that would have prevented the wrong baseline.

## Related

- `.github/reachability-baseline` — the ratchet's stored count
- `.github/workflows/tri-build.yml` — header explains why 0.15.2 is pinned
- `.github/workflows/zig-0-16-migrated.yml` — the other half of that trade
- `docs/zig-migration-rules.md` — the API-level 0.15→0.16 notes
