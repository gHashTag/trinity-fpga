---
name: stale-reference
description: Repairing a build, tree, or dependency that rotted silently — why extraction leaves dangling references, why a gate that answers two questions hides the interesting one, and the habits that separate a real fix from one that compiles. Use when something has not been built or run in a long time, when a refactor moved code between repositories, or before writing a CI gate.
---

# Stale references, and gates that hide their own news

Distilled from one evening that took a CLI from "no build definition exists" to a
running binary — about twenty defects, **nine of them introduced by the repair
itself** (§11). Every rule below is a specific failure that happened.

The single sentence, if you read nothing else:

> **Code moves out; references stay behind; nothing reports it, because nothing
> runs the build.**

Six independent instances in one tree, all the same shape:

| What moved | Where to | What was left pointing at it |
|---|---|---|
| farm subsystem | `trinity-training` | 20 references to a deleted `local_farm.zig` |
| VSA core | `zig-hdc` | `src/vsa.zig` gone, build still named it |
| physics | `zig-physics` | `quantum_gravity_full` imported by name |
| `src/vsa/*` inside zig-hdc | deduplicated to one copy | callers on the old API arity |
| `build.zig` | renamed to `.tri`, then deleted | every named module unresolvable |
| numerical core commit | never pushed | gitlink to an unfetchable SHA |

None was noticed at the time. All six were found in one evening — by running the
build.

---

## 1. A gate that answers two questions with one exit code hides the interesting one

The build gate ran `zig build tri`. That is a **run** step. So "compiled, linked,
then crashed at startup" and "ninety compile errors" produced the same red.

The first successful link in four months arrived looking exactly like every
failure before it, and was read past once:

```
Build Summary: 1/3 steps succeeded
tri
+- run exe tri failure          <- this is a SUCCESS being reported as a failure
```

**Rule.** One question per gate step, named in the step title. *Does it parse?*
is not *does the graph load?* is not *does it compile?* is not *does it run?*
When a step covers two questions, the one it hides is the one you needed.

Corollary: a run check belongs in the pipeline, but as its own step with
`continue-on-error`, reporting the exit code. A crash is information, not a
build failure.

---

## 2. Fix the instrument before you look harder at the same output

Twice in one evening the right move was to make the tool speak more precisely,
not to stare at what it already said.

* A comptime format error reported `std/Io/Writer.zig:1355` and hid the real
  call site behind `8 reference(s) hidden`. Adding `-freference-trace=12` named
  the line on the very next run. **A log that points at the standard library for
  a defect in your repository is sending the reader to the wrong place.**
* Separating build from run (above) named a success that had been invisible.

**Rule.** When a diagnostic is unhelpful, the first fix is the diagnostic.

---

## 3. Enumerate the defect class; do not iterate one per CI round

Fixing `no module named X` one round at a time costs a full build per defect and
finds them in the compiler's order rather than yours. Enumerating instead:

```
34 named imports under src/tri  →  21 already wired  →  13 missing
```

All thirteen in one commit. Roughly ten CI rounds saved.

**Rule.** If the defect class is enumerable by a script, enumerate it. Iteration
is for classes you cannot list.

---

## 4. The correct form is usually already next door

Four times in one file, the right usage sat a few lines from the wrong one:

* `results.items` used in three places, `for (results)` in a fourth
* `RESET` formatted `{s}` eleven times, `{m}` once
* `totalVelocity` called with seven arguments in `fitting.zig`, eight in `cli.zig`
* `std.json.Array.append` correct everywhere but one call

**Rule.** Before inventing a fix, grep the same file for the same call. Defects
accumulate where the compiler has not looked, and they accumulate *beside*
correct code, which is why they look plausible.

---

## 5. Two mistakes the repair itself made

Recorded because they are the ones a careful person still makes. Two more
followed later in the same session; §11 collects all four and names what they
have in common.

**A prefix match is not an identity match.** `grep 'pub const GoldenChain'`
matched `GoldenChainAgent`, so a module was wired to the wrong file of a
duplicated name. Two files were called `golden_chain.zig`; only one exported the
type. **Grep for the terminator** — `pub const GoldenChain =` or `\b` — when the
name could be a prefix.

**Removing an argument can orphan a parameter.** Dropping an allocator from
`bundle2(...)` left the enclosing function's `allocator` parameter unread, and
the next build failed on that. **After removing an argument, check the enclosing
function still uses its own parameters** — before committing, not one round
later.

---

## 6. The cheaper repair is not always the smaller change

`row_buffer[x] = '●'` fails because U+25CF does not fit a `u8`. Swapping it for
`'*'` compiles immediately — and silently downgrades the output.

Reading further showed the print loop already emitted the glyph as a string
literal and only used the buffer as a marker. So markers were the correct fix,
the rendering was untouched, and nothing was lost.

**Rule.** When a type error has an obvious narrowing fix, check what the value is
actually *for* first. A compile error converted into a silent behaviour change is
worse than the compile error.

---

## 7. Comments about size and cost drift; measure them

```zig
// Heap-allocate TVC corpus for self-learning (~26MB, must be on heap)
```

It was **~2.1 GB** — `[10000]TVCEntry`, each holding three `HybridBigInt` with
`[59049]Trit` caches. Understated by about eighty times. Allocated
unconditionally at startup, so every command including `--help` segfaulted
before `main()` did anything.

**Rule.** A comment stating a size is a claim with no test attached. If the
number matters, compute it from the type — `@sizeOf` is available at comptime —
or do the arithmetic explicitly in the commit that relies on it.

---

## 8. Restoring from history: pick the last version that *parsed*

`build.zig` had been unparseable since a specific commit, then edited by **73
further commits**, then renamed away and deleted. Two executable declarations
had lost their opening lines.

Restoring the newest version means reconstructing code nobody ever ran.
Restoring the last version that parsed loses only edits that were never
validated — because a file that does not parse cannot have been.

**Rule.** `git log --all -- <file>` plus a parse check on each revision finds the
last good one in seconds. Prefer it to repairing damage of unknown provenance.

---

## 9. Dependency pins to a branch are not pins

```
.zodd = .{ .url = "git+https://github.com/CogitatorTech/zodd#main", ... }
```

`#main` moved from alpha.3 to alpha.6, the new version required a different
compiler, and the build broke with no change in the repository. A sibling
dependency's hash was the literal placeholder `????????????????????????????????????????`
— it could never have resolved.

**Rule.** Pin dependencies to commits. A hash that has never been filled in is a
dependency that has never been fetched, and something else is quietly supplying
those symbols — or nothing is, and the code using them has never been compiled.

Also: **check whether the dependency is used at all.** Three of four declared
here were referenced nowhere in the build and were breaking it for nothing.

---

## 10. What to do first, in order

1. Run the build. Not "read the build" — run it.
2. Ask what the failure actually says. If it names the standard library, improve
   the trace before theorising.
3. Split any gate that covers more than one question.
4. Enumerate the defect class before fixing an instance of it.
5. For each fix: does the correct form exist nearby? does removing this argument
   orphan something? is the cheap fix a silent downgrade?
6. Record what was left deliberately unfixed and why. "Not in the module graph,
   so nothing has compiled it against this signature" is a reason; "looked fine"
   is not.

---

## 11. The uniform edit is the repair's own failure mode

Nine defects were introduced by the repair in one session. All nine are the
same mistake, and with a sample that size it can be stated precisely:

> **A rule that holds for every case you looked at, applied to a set containing
> a case you did not.**

| the edit | what it assumed | what bit |
|---|---|---|
| dropped an argument from every `bundle2` call | the callers were alike | one enclosing function stopped using its parameter |
| `grep 'pub const GoldenChain'` | the name was unique | it matched `GoldenChainAgent` by prefix |
| appended `return` after every stub print | the stubs were alike | two had a second print after it, now unreachable |
| one XDC for five reducer variants | the variants had the same ports | four had extra ports and never reached the router |
| rewrote calls on anything not ending `_mod` | modules follow that naming | `wasm_root` is a module and does not |
| one `--db-root .../artix7` for every part | the parts share a family | a spartan7 part is not in the artix7 database |
| widened a classifier to catch assembler errors | a missing FASM means a harness fault | after a failed P&R it means the failure the gate exists to detect |
| took a part's speed grade from the board supplying its pins | one source is one source | the database that answers about it ships a different grade |

Not seven accidents. One habit, and note where the exceptions live: never in
the sites that motivated the edit, always in the ones adjacent to them. The
`_mod` heuristic was derived from every module I had read; `wasm_root` was the
one I had not. The `artix7` db-root was right for both parts in the matrix at
the time it was written.

The script that edits N places is the fastest tool available and the one most
likely to be wrong, because its speed comes precisely from not looking at the
places. Three cheap defences, in order of value:

1. **Print what you are about to change, with context, and read it.** All four
   would have been visible in a diff of the matched lines.
2. **Assert the count.** If the change should touch twenty sites, say twenty and
   fail if it is nineteen or twenty-one.
3. **Parse-check before committing.** Available every time; skipped once because
   the local toolchain had been cleaned up and CI was "good enough". That saved
   a minute and cost a full round.

The general form, which is the same rule as §4 seen from the other side: the
sites that look alike enough to edit mechanically are exactly the sites nobody
has read recently.

### The matrix corollary

A CI matrix is the same trap wearing different clothes. One workflow in this
repository baked in a per-part value **three separate times** — the IOSTANDARD
(`LVCMOS33`), the database root (`artix7`), and the part's speed grade — and
each was correct for every row present on the day it was written.

> **A matrix with N rows teaches you nothing about the N+1th, and the values
> most likely to be hardcoded are exactly the ones the current rows happen to
> agree on.**

The defence is cheap and worth applying before adding any row: for each literal
in the shared code path, ask which row would have to change for this to be
wrong — and if you cannot name one, that is because you have only looked at the
rows that agree.

And when a row is added, one more habit: **take every field of an identifier
from the same source.** The speed-grade defect came from reading a part's pins
off a board file and its name off the same file, when the database that would
be asked about it ships a different grade.

---

## 12. Test the classifier on answers you already know

A script that decides something about many sites — which are safe, which are
dead, which need the fix — is itself a claim, and it is the least examined thing
in the room. Its output looks like data.

**The case.** Deciding which of 144 CLI commands were safe for CI to execute.
Three revisions in one sitting:

| revision | verdict | why it was wrong |
|---|---|---|
| scan the handler body for risky calls | 180 of 208 safe | handlers delegate; the risk is one call deeper |
| reject any handler calling project code | 87 safe | still cleared `git` |
| — | — | `runGitCommand` does `std.process.Child.init` and `spawn()` |

The third row is the diagnosis: the allow-list contained `std.` wholesale, and
`std.process.Child` lives inside `std.`. A handler that spawns a subprocess read
as print-only. A second hole: unqualified calls — `showRailwayHelp(...)`, no dot
— were skipped entirely.

**Every revision erred toward "safe".** Feeding revision 1 or 2 into CI would
have run `deploy`, `serve` and `git` on every build.

**The rule.** Before believing a classifier, run it against cases whose answer
you already know — and choose them from *both* classes. `git` obviously spawns;
`clean` is obviously a stub. Checking those two took one command and invalidated
the whole direction.

**The corollary that matters more.** Ask which way the classifier's errors run.
One that occasionally misses a dead file wastes a little disk. One that
occasionally calls a subprocess-spawning command "safe" executes `deploy` in CI.
**When the error direction is asymmetric, a classifier that cannot be made sound
should be abandoned, not tuned** — the fourth revision would have produced the
number I wanted and no more truth than the third.

Coverage that matters grows by reading. The smoke list here stayed at 18 of 144,
each read individually, because that is the only figure anyone can defend.

---

## 13. A baseline generated from a broken gate freezes the bug as known state

A ratchet needs a baseline: the debt that exists today, which you fail only on
top of. The baseline is produced by running the gate — so **if the gate is
wrong, `--update-baseline` launders its defect into a file that reads like
history.** Nobody re-derives a baseline. It looks like a record of the tree; it
is a record of the checker.

**The case.** A gate asked whether a number the paper *withdraws* is still
asserted live elsewhere. It failed on `0.1173` — a current value, printed in two
results tables, withdrawn by nobody.

The withdrawal zone ran blank-line to blank-line. A LaTeX float has no blank
line inside it, so a withdrawal sentence in the `\caption` — where a paper
naturally puts one — made the zone span `\begin{table}` to `\end{table}` and
swallow the **tabular body**. Every live number in that table became
"withdrawn", and every legitimate appearance of one became a violation.

Three things worth separating:

1. **One zone of nine did it, and produced 14 of the 15 baseline entries.** The
   baseline was 93% artefact.
2. **The gate simultaneously missed everything it was aimed at.** The numbers
   that caption actually withdraws are `440`, `895`, `5.1` — and the value
   regex required two decimal places, so none of them matched. It flagged the
   neighbours of its targets while seeing none of the targets.
3. **The stale entries were not inert.** After the zone fix those 14 could never
   fire again — so if the paper ever *did* withdraw one of those values, the
   baseline would have silently excused it. A dead exclusion is a live hole.

**Rules.**

* When a ratchet fires on something that looks correct, **suspect the ratchet
  before the content** — and read its baseline as evidence about the checker,
  not about the tree. A baseline that is mostly one shape is a defect with a
  shape.
* After fixing a gate, **regenerate the baseline rather than editing the failing
  line out of it.** Here it went from 15 entries to zero: the debt had never
  been real.
* **An empty baseline plus a blind checker is permanently green.** Emptying it
  raises the stakes on §12: prove the gate still catches, from both classes,
  *after* the baseline is empty. Injecting each genuinely-withdrawn value as a
  live assertion — three of them — and confirming each is caught took one
  command.
* **A test that patches a file by string replacement must assert the file
  changed.** A replace whose target is absent is a no-op, and the gate then
  reports OK because nothing was injected — indistinguishable from a gate that
  has gone blind. Check by checksum before trusting the result, and restore
  byte-identically after.

### The generalisation

Both defects here were one mistake wearing two costumes: **a withdrawal
withdraws a claim, not every number sharing its paragraph.** The zone was a
proxy — "same paragraph" standing in for "same claim" — and proxies fail at
their edges, which is exactly where a float boundary or a second sentence lives.

That is §1 from the other side. A gate that answers *"is this number near a
retraction"* while claiming to answer *"is this number retracted"* will be
wrong in both directions at once: false on the neighbours, silent on the
targets. When a gate fires, ask which question it actually asked.

---

## 14. A handoff note rots faster than the thing it describes

The hand-off file said the next step on a hardware bug was "an A/B on four
`IFF.ZSRVAL_Q` bits — the last standing hypothesis". I repeated that in three
status reports and a dashboard across one day, and offered it as the highest-value
remaining work.

It had been answered weeks earlier. Those four bits **were** the real
discrepancy; emitting them was the fix, it shipped as its own PR, and the thread
had moved on to a different failure — the block is now correctly initialised and
still never clocks. The experiment I kept promising would have re-tested a
question whose answer was already merged.

Nothing about the note looked stale. It was specific, it named real bits, and it
was written by someone who had read the thread — which is exactly why it survived
three re-readings of *itself* without anyone re-reading the *source*.

**Rule.** A summary of a live thread is a cache with no invalidation. Before
acting on one, open the thread. The cost is a minute; the cost of not doing it
is running an experiment to confirm something already known, and telling
collaborators you are about to.

The tell is temporal, not textual: **ask when the note was written and what has
happened in that thread since.** Not "does this still look right" — a stale note
looks exactly as right as it did the day it was written.

### The same shape, one layer up

The blocker the thread actually names is a reference dump only vendor tools can
produce. That had been sitting in plain sight in my own comment for weeks, under
a sentence beginning "I still can't say what is wrong without…". A stated
blocker is not a request until someone who can act on it is asked directly —
and I had been carrying it as a fact about the world rather than as an ask with
an owner.

---

## 15. When you cannot execute, say which part is reading

Three JIT tests failed. The fix was found by decoding the emitted machine code
by hand — the ModRM and SIB bytes, the `F6 /5` form of `IMUL`, the rel32
displacements measured from the end of the instruction — and confirming the
emitter was correct, then finding the defect one level up: the function pointer
was handed out with no `callconv`, so Zig's unspecified `.auto` convention was
being asked to agree with hand-written System V.

**The tests skip unless `cpu.arch == .x86_64`, and the machine doing the fixing
is arm64.** Every one of them has always skipped locally. The reading is the
entire evidence; CI is the only executor.

**Rule.** When the environment cannot run the thing being fixed, say so in the
commit, in those words, before the fix is reviewed. Not as a hedge — as the
scope of the claim. "The emitter decodes correctly and the convention was never
declared" is a claim about source that reading can support. "This fixes the
tests" is a claim about execution, and belongs to whoever ran them.

A skipped test reports success exactly like a passing one — §12 again, arriving
this time through the target architecture rather than through a classifier.
