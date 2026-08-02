# `fpga-ci` and `fpga-regression`: why they have been red since July

Diagnosis only. Both workflows belong to other workstreams, and this campaign does not
edit another line's CI — a silent change there is worse than a red badge. What follows
is what the logs say, checked to the line.

Pass 173 measured that these are the longest-standing failures in the repository:
`fpga-ci` and `fpga-regression` have failed on **all thirty** of their most recent runs,
back to **2026-07-23**.

---

## `fpga-ci` — a guard applied to the producer and not the consumer

```
./zig-out/bin/vibee: No such file or directory
##[error]Process completed with exit code 127
```

The step before it already handles the cause:

```yaml
- name: Build
  run: |
    if [ -f build.zig ]; then
      zig build -Dci=true
    else
      echo "::warning::build.zig not present at repo root — legacy VIBEE build skipped"
    fi
```

There **is** no root `build.zig`. `CLAUDE.md` says it was removed on purpose and
converted to a `.tri` spec. So the build is skipped, correctly and deliberately — and
then the next step runs `./zig-out/bin/vibee` **unconditionally**.

The guard was written for the producer and not for the consumer. That is the whole
defect, and it has cost thirty runs.

### Why the obvious fix is not obvious

Making the job *work* rather than skip needs a decision this campaign cannot make:

- `src/vibeec/build.zig` builds an executable named **`vibeec`**, not `vibee`.
- No `gen` subcommand is visible in its `cli_main.zig`.
- `tools/bin/` holds shell scripts, not a prebuilt binary — `CLAUDE.md`'s note about
  prebuilt binaries there does not hold for this one.

So wiring the subproject in would be a guess about an interface. **Whoever owns the
VIBEE pipeline should decide what replaces the old root binary.**

### What a minimal fix would look like

Guard the consumer the way the producer is guarded, and say what is missing:

```yaml
if [ ! -x ./zig-out/bin/vibee ]; then
  echo "::warning::./zig-out/bin/vibee absent — nothing rebuilds it since the root
  build.zig was removed. Generation SKIPPED; this job verifies nothing until the
  VIBEE entry point is decided."
  exit 0
fi
```

**Skipping is honest; passing silently is not.** A job that green-lights without doing
its work is the exact failure the `research/` checks were rebuilt to avoid — exit 2 with
a reason, never exit 0 on a missing input.

---

## `fpga-regression` — a different cause

```
🔬 Regression (transcendent) — φ-Threshold Validation
##[error]Process completed with exit code 1
env: CONSCIOUSNESS_THRESHOLD: 61.8
```

Not a missing binary: a validation step that runs and fails its threshold. Diagnosing
it means knowing what the φ-threshold is measured against and whether 61.8 is still the
intended bar, which is a question for that workstream rather than a defect visible from
the log.

---

## The number that matters

Not how many are red, but for how long. Thirty consecutive failures is not a check —
it is a habit, and it trains everyone to stop reading the badge next to it, including
the eleven that are green and mean something.

`research/audit_ci_health.py` reports this state on demand and does not fix it, for the
same reason this file does not.
