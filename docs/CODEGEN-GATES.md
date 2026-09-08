# Codegen gates: what each one measures, and what it cannot see

The `.tri` → Zig pipeline is defended by four checks. They overlap deliberately,
because each is blind to something the next one catches. Every gap listed here
let a real defect through at least once.

## The gates

| gate | command | scope | runtime |
|---|---|---|---|
| format | `zig fmt --check src/ tools/` | whole tree | seconds |
| ast-check ratchet | `zig build astcheck` | 2262 source files | ~1 min |
| codegen corpus | `zig build codegen-corpus` | **all 1137 specs** | ~1 min |
| codegen compile | the four specs in `codegen.yml` | 4 specs, compiled | ~15s |

## What ast-check does NOT see

`zig ast-check` parses and resolves names. It does **not** resolve types or
members. Invisible to it:

- a struct literal missing a field
- a call with the wrong **arity**
- a misspelled member on an imported type
- a function whose body does not satisfy its return type

Each of those has reached a commit here. One `.test_cases = .{}` — a Sema error
— made the whole `src/vibeec/codegen/` subtree unimportable while ast-check and
the format gate both called every file in it clean, and 90 tests sat unreachable
behind it.

**A green ast-check run means "nothing got syntactically worse". It does not
mean the tree compiles.**

## Why the corpus gate exists

The compile gate checked **four** specs. Ad-hoc sweeps used `head -80`. The tree
has **1137 specs, 1033 of which produce behaviours** — so every figure quoted
during the generator work ("24 of 49", "34 of 49") described about 5% of the
population, and a regression reached a commit because the failing spec was in
neither slice.

`zig build codegen-corpus` walks all of them:

- **788 of 1033** specs with behaviours generate ast-check-clean output
- a spec dropping out of that set fails the build, **by name**
- a sample is additionally **compiled** with `zig test`, which is the only check
  that sees arity and types

### The sample is a stride, not a prefix

The clean list is sorted by path, so the first N specs all come from one
directory. `specs/tri/sacred_math_agent.vibee` — passes ast-check, does not
compile — was invisible to a 24-spec prefix and found within seconds of
switching to an even stride.

`--compile N` raises the sample; `--compile all` compiles everything, about 40
minutes, which suits a nightly rather than every push.

## Recording a new baseline

```bash
zig build codegen-corpus-update   # after an intended change
zig build astcheck-update         # same, for the ast-check ratchet
```

Both are ratchets rather than zero-demands: 245 specs still generate output that
does not pass ast-check, and 92 source files still fail it. Demanding zero would
mean a permanently red gate, and a permanently red gate reads as a broken
subject rather than a broken check — the harder failure to notice.

## Traps that cost real time here

- **A gate can fail without saying why.** `zig build` swallows a failing run
  step's *stdout*. Diagnostics belong on stderr, or the gate exits 1 with the
  offending filename nowhere in the output.
- **A tool that only works where it was written.** The corpus gate located the
  generator by searching `.zig-cache`, which succeeds only on a machine that
  already built it. It passed locally and could not pass in CI. The build now
  passes the path with `addArtifactArg`.
- **A child `zig` needs both cache dirs.** Running inside `zig build`, the
  parent holds `.zig-cache`; and with no inherited environment the child cannot
  resolve `HOME` for its global cache. Missing either produced
  `AppDataDirUnavailable`, which `catch return false` reported as "does not
  compile" for 24 of 24 sampled specs — every one of which compiled by hand.
- **`generated/` must exist.** The generator writes nothing and reports success
  if the output directory is absent; the failure then looks like a compile
  error in the next step.

## Where the remaining 245 are

First-error causes, from the failing outputs:

| cause | outputs |
|---|---|
| use of undeclared identifier | 109 |
| expected ';' after declaration | 44 |
| expected X, found Y | 37 |
| expected ',' after field | 15 |
| expected type expression | 11 |
| duplicate struct member name | 9 |
| other | 26 |

Measured over all 251 failing generated outputs. That is more than the 245
specs-with-behaviours the gate counts, because specs with no behaviours are
still generated and can still produce a file that fails — the gate ignores
those, this census does not. Two different denominators for two different
questions, stated so neither gets quoted as the other.

The undeclared identifiers split two ways: spelling gaps in `mapType` (a
generator fix) and specs referencing types they neither declare nor import (a
spec fix — the generator now warns about these at generation time).
