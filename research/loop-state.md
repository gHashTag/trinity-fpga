# Loop state — autonomous improvement cycle

Journal for the `/loop` cron job (`*/15 * * * *`). **Read this before doing anything.**
Its purpose is that a later iteration does not redo, undo, or contradict an
earlier one. Append; do not rewrite history.

## Invariants — do not violate

1. **Never claim without measuring.** Every assertion here carries either a run
   URL, a commit SHA, or a file:line. If you cannot produce one, write
   "unverified" next to the claim rather than dropping it.
2. **Never fix by guessing at someone else's API.** Read the implementation.
   Three defects this session came from code written against an API that had
   moved; a fourth nearly came from me substituting a plausible signature.
3. **Do not push to `main` without the gate passing**, unless the commit is
   explicitly a diagnosis (say so in the message).
4. **Do not touch the user's main checkout** at `/Users/playom/trinity-fpga` —
   it has uncommitted work on branch `trinet-fleet-truth`. Work in a worktree.
5. **A red gate is information, not an emergency.** Report where it stopped;
   do not disable it, loosen it, or edit the test so it passes.
6. **Board work is the user's.** Anything needing the AX7203 waits for them.

## Current state of the long threads

*Last refreshed at iteration 029. This table decays — check it against the
iteration log before trusting a row, and refresh it when it disagrees.*

| Thread | State | Evidence |
|---|---|---|
| `tri` build | Builds, links, runs; 18/144 smoke-tested | gate `tri builds` |
| `build.zig` under 0.16 | Clean; only vendored raylib still fails | Codegen Validation |
| usage-exit convention | **49 sites fixed, 0 remain, gated** | gate step, iteration 025 |
| unreachable files | 395 of 744 under `src/tri`; **ratcheted, not deleted** | `.github/reachability-baseline` |
| BUFR configuration | **Fixed upstream, merged** | nextpnr-xilinx#151 |
| BUFR from a pin | Blocked on prjxray `047b` (I2IOCLK rows) | issue #149 |
| IDDR / #114 | Site config eliminated; 4 `IFF.ZSRVAL_Q` bits left; **needs the board** | issue #114 |
| Router / #154 | Filed with a control; a35t only, of four parts tested | issue #154 |
| Part-coverage gate | **4 parts green**; Kintex uses IBUFDS | run 32150382712 |
| IOB divergence / #120 | Draft; blast radius measured — 6 of 8 goldens change | `research/benchmark-timing-correction.md` sibling |
| Benchmark timing claim | **Retracted — the correction was itself wrong** | `research/benchmark-timing-correction.md` |
| `zig-golden-float` | **Unpushed commits — clone --recursive fails for everyone** | README |
| Skill `stale-reference` | 12 sections; §11–§12 cover defects in the repair itself | `.claude/skills/` |
| Literature review | **Blocked 6+ iterations** — web tooling returns a model error | not written from memory |

## Iteration log

### 001 — 2026-08-18

**Did.** Resolved the zig-hdc API drift that blocked the `tri` build, by reading
the implementation rather than guessing at it:

* `zig-hdc` turned out to be a thin re-export of `zig-golden-float`, which is
  checked out locally — so the real signatures were readable.
* `bundle2(a, b)` takes two arguments; our callers passed three. The third was
  an allocator the current implementation does not want.
* `getTritChecked` was renamed `getTrit`, and the new one is still
  bounds-checked (`if (pos >= self.trit_len) return 0`), so the substitution
  preserves semantics. Verified before applying, not after.

**Found, worth carrying forward.** `zig-hdc`'s own header records the reason it
became a re-export: two maintained copies of `src/vsa/*` had diverged, so
repairing sixteen defects in one left all sixteen standing in the other. That is
the same failure mode as everything else found today — a reference left pointing
at a thing that moved — and it argues for the general rule in the skills file.

**Left deliberately.** `src/query_cli.zig` and `src/sota_report_demo.zig` still
pass an allocator to `bundle2`. They are not in `tri`'s module graph, so nothing
has compiled them against the current signature. Fixing them now would be a
guess about which `bundle2` they resolve to; the compiler will say when it
reaches them.

**Next.** Whatever the gate reports. Then: the two benchmark corrections, and a
minimal reproducer for the `Invalid global constant node` router failure.

### 002 — 2026-08-18, same evening

**Method change that paid for itself.** Fixing "no module named X" one CI round
at a time was costing a build per defect and finding them in the compiler's
order rather than mine. Enumerated instead: 34 named imports under `src/tri`,
21 wired, 13 missing. All 13 in one commit. Prefer the inventory to the
iteration whenever the defect class is enumerable.

**Defects closed this round.** zig-hdc API drift (`bundle2` arity,
`getTritChecked` → `getTrit`), 13 unwired modules, `golden_chain` bound to the
wrong file of that name, an orphaned parameter, a `{m}` format specifier, 14
C-style `{:.3f}` specifiers, `for` over an `ArrayList` instead of `.items`,
`catch unreachable` on a void, `'●'` assigned into a `u8`, and
`totalVelocity` called with an allocator it no longer takes.

**Two of them were mine**, both caught by the gate rather than by me:
dropping `bundle2`'s allocator orphaned `store()`'s parameter, and a
`grep 'pub const GoldenChain'` matched `GoldenChainAgent` by prefix, so I wired
a module to the wrong file on a fuzzy name match. Both now have a habit
attached: after removing an argument, check the enclosing function still uses
its parameter; and a prefix match is not an identity match.

**The recurring shape, now with six instances.** Every structural defect found
today is the same one: code moved out, a reference stayed behind.
`local_farm.zig` (farm → trinity-training), `src/vsa.zig` (VSA → zig-hdc),
`quantum_gravity_full.zig` (physics → zig-physics), the zig-hdc API drift after
its own dedup, `build.zig` itself, and the submodule gitlink pointing at an
unpushed commit. None was caught at extraction time, because nothing ran the
build.

**Instrument improvement.** Added `-freference-trace=12` to the gate after a
comptime format error reported std's line and hid the call site behind "8
reference(s) hidden". It named the real line on the first run afterwards.

**Judgement worth keeping.** `'●'` in a `u8` would also have compiled if I had
swapped it for ASCII — and would have silently downgraded the plot. The print
loop already emitted the glyph as a literal and only used the buffer as a
marker, so markers were the correct fix. The cheaper repair is not always the
smaller change.

**Next.** Whatever the gate says. Then the two benchmark corrections, and a
reduced test case for the `Invalid global constant node` router failure.

### 003 — 2026-08-18, later

**`tri` builds, links, and runs.** First time since 2026-03-20. `tri --help`
prints its full command surface: **144 commands**. Gate: run 32116484331.

Two findings closed it, and both were disguised as something else.

**The gate was answering two questions with one exit code.** `zig build tri` is
a RUN step, so "compiled and then crashed" reported identically to "ninety
compile errors". The first successful link in four months arrived looking like
a failure, and I read past it once. build.zig now has a `tri-compile` step that
installs without running; starting the binary is a separate, non-fatal step.
Whenever a gate covers two questions, the answer to the interesting one is the
one it hides.

**The startup allocation was understated by ~80x.** `CLIState.init` allocated
the TVC corpus unconditionally under the note "~26MB, must be on heap".
`TVCCorpus` is `[10000]TVCEntry`; each entry holds three `HybridBigInt`, each
carrying `unpacked_cache: [59049]Trit` plus an 11810-byte packed buffer —
~213 KB per entry, **~2.1 GB** for the array. The write to `self.count` lands
past it, so every `tri` command, `--help` included, segfaulted before `main()`
did anything. Moved to `ensureCorpus()`, which allocates on first read and
returns null on failure: a machine short of 2.1 GB should lose self-learning,
not the CLI.

**Where the whole repair landed.** From "no build definition exists" to a
running binary: ~20 defects. Thirteen unwired modules, the zig-hdc API drift,
eight separate faults in `sparc/cli.zig`, a `{m}` format specifier, `'●'` in a
`u8`, a module bound to the wrong file of that name, and the 2.1 GB startup
allocation. **Two were mine**, both caught by the gate rather than by me.

**Instrument lesson, twice over.** `-freference-trace=12` named a call site that
had been hidden behind "8 reference(s) hidden"; separating build from run named
a success that had been hidden behind a failure. Both times the fix was to make
the instrument report more precisely, not to look harder at the same output.

**Next.** Verify individual commands actually work (144 of them; `--help`
running proves startup, not function). Then the two benchmark corrections, and
a reduced case for the `Invalid global constant node` router failure.

### 004 — 2026-08-18, night

**Skill written.** `.claude/skills/stale-reference/SKILL.md` — the transferable
half of this repair, in the register of `measurement-discipline`: every rule a
failure that happened. Six instances of "code moved out, reference stayed
behind" tabulated, plus the two mistakes the repair itself made.

**The gate now runs commands, not just builds them.** `--help` proves `main()`
starts and nothing more. Fourteen of the 144 advertised commands are sampled
each build. It found something on the first run:

| | before | after |
|---|---|---|
| `stats` | exit 0, "TODO - not implemented yet" | exit 1 |
| `doctor` | exit 0, "TODO - not implemented yet" | exit 1 |

**Twenty sites** in `tri_commands.zig` printed "not implemented" and returned
normally. A caller could not distinguish work done from work never written —
the same defect as everything else this session, one layer up. They now return
`error.NotImplemented`; the message is unchanged, only the exit code stopped
lying.

**Unexplained, recorded rather than claimed.** `verify` went from exit 124 (a
20-second timeout) to exit 0 between runs, with nothing touching it. Either a
side effect of the lazy corpus, or the command is flaky. Do not attribute this
to the fix without evidence; re-check it next iteration and treat a second
timeout as the real state.

**Still open from the same table.** `fib` and `lucas` print usage and exit 0,
while `phi` in the same situation exits 2 — two conventions in one binary. Not
fixed here because which is correct is a decision, not a repair.

**Third self-inflicted defect.** The mass edit that added the returns put two of
them *before* a trailing print, producing unreachable code. Same shape as the
other two: a uniform edit applied to sites that were not uniform. The parse
check that would have caught it was skipped because the local toolchain had
been cleaned up and CI was "good enough" — it cost a full round.

**Running score: ~20 defects closed, 3 introduced, all 3 caught by the gate
within one cycle.** That ratio is the argument for the gate, not for care.

**Next.** Re-check `verify`. Decide the usage-exit convention. Then the two
benchmark corrections and the router-failure reducer, both untouched since 001.

### 005 — 2026-08-19, night

**I corrected a correction, and the original correction was wrong.**

I told @cavearr by mail, and repeated in commit messages, that the benchmark's
timing column needed fixing because "every openXC7 PASS was against nextpnr's
12 MHz default rather than a real target". Two greps show that is wrong twice
over:

* `--freq` has been passed explicitly since `1437ed5cc`, the commit that
  introduced the workflow. No build here ran on the 12 MHz default.
* The harness emits `synth_ms, pnr_ms, bit_ms, total_ms, cores` and nothing
  else. **There is no timing verdict field**, and the invocation carries
  `--timing-allow-fail`. This half of the benchmark never produced a timing
  column at all.

Written up in `research/benchmark-timing-correction.md`, with what *is* wrong:
the GF designs' XDC (`ax7203_corona.xdc`) contains **no `create_clock`**, so
their only target is `--freq 5.0`; and for blinky the XDC asks 200 MHz while the
flag asks 100 MHz — a 2× disagreement nobody has resolved.

**The lesson, and it is the sharpest of the session.** A correction is a claim,
and it inherits no credibility from being self-critical. Saying "I was wrong
about X" does not establish that X was wrong. I carried a specific-sounding
figure — a named default, a named unit — across three artefacts without opening
the file, because specificity felt like evidence.

Add to the invariants: **before publishing a correction, verify the thing being
corrected, not only the correction.**

**Wall-clock numbers are unaffected.** The harness times three subprocesses;
none of this touches that. What it constrains is what may be said around them.

**Next.** Send the correction to @cavearr and @hansfbaier — it revises something
they were told. Then the router-failure reducer, still untouched since 001.

### 006 — 2026-08-19, night

**Filed openXC7/nextpnr-xilinx#154.** The router failure promised on #114 in
iteration 001 is reduced, controlled and reported.

**It is not an IDDR bug.** Five variants separated the hypotheses; `v4` — a
three-line flip-flop with no IDDR, no I/O primitive and no constant tie —
fails identically:

    ERROR: Invalid global constant node 'INT_L_X0Y98/VCC_WIRE'

**The control is what makes it publishable.** The same design on
`xc7a200tfbg484-2` builds, rc=0. Same `.v`, same image, same commit. So:
part-specific, not a general router defect — and the claim "openXC7 cannot
route a flip-flop", which is what the a35t result alone would have supported,
is false and would have been embarrassing to publish.

**A second defect fell out.** `v2`/`v3` abort rather than error:
`assertion_failure: user.cell->ports.at(user.port).net == ni` at
`common/nextpnr.cc:466`, triggered by IDDR with `CE` from a port. Reported in
the same issue with an offer to split it.

**Fourth self-inflicted defect of the session.** The reducer's first run reused
one XDC across variants that add ports, so four of five died on a missing
IOSTANDARD and never reached the router — reported indistinguishably from a
result. I had guarded against a yosys failure (`rc=20`) and not against a
constraint failure, one commit after writing "a reducer that cannot tell those
apart produces confident nonsense".

**All four of my defects this session have the same shape:** a uniform edit or
a uniform harness applied to sites that were not uniform. Orphaned parameter,
prefix grep, unreachable return, shared XDC. That is a pattern, not four
accidents, and it belongs in the skill rather than the journal.

**One correction to iteration 005.** The 12 MHz figure is real —
`Annotating ports with timing budgets for target frequency 12.00 MHz` appears
in these logs, because this reducer passes no `--freq`. My error was
attributing it to the benchmark harness, which does pass one. The retraction
letter should say the claim was misattributed rather than invented.

**Next.** Add the uniform-edit rule to `stale-reference`. Then `verify`'s
unexplained timeout→0, and the `fib`/`lucas` exit-code convention.

### 007 — 2026-08-19, night

**The re-check instruction paid for itself.** Iteration 004 recorded `verify`
going from exit 124 to exit 0 without being touched, and said explicitly: do not
attribute this to the fix, re-check next iteration, treat a second timeout as
the real state. Third observation: **124 again**.

**And then the explanation removed the defect entirely.** `tri verify` shells out
to `zig build test`:

    const test_result = std.process.Child.run(.{
        .argv = &[_][]const u8{ "zig", "build", "test" },

That legitimately takes minutes. My smoke list gives 20 seconds. So there was no
hang and no flakiness — **my measurement was wrong**: a sample of "pure,
side-effect-free commands" containing one that builds the whole project measures
the build cache, not the command. `verify` is now out of that list, with the
reason written where the list is.

I was one step from filing "verify hangs". The thing that stopped me was the
journal's own instruction to re-check before attributing.

**Skill §11 added.** All four self-inflicted defects share one habit: a uniform
edit applied to non-uniform sites. Three defences, cheapest first: print the
matched lines and read them, assert the expected count, parse-check before
committing.

**Literature review blocked, and left blocked.** Both web tools returned a model
error all iteration. Writing a prior-art section from memory is the exact failure
this project documents, so it is not written. Recorded as blocked-with-reason.

**A repository survey instead**, `research/where-this-work-sits.md`, with its
method bounded in the first paragraph. Two findings worth carrying:

* `f4pga/prjxray` has not been pushed since **2025-06-05** — fourteen months.
  The database the whole ecosystem rests on is dormant, which is why fixes go to
  openXC7's fork and why missing rows need a campaign rather than a request.
* `openXC7/nextpnr-xilinx` is pushed daily and has **one** CI workflow, which
  builds demos. `bit2fasm` appears nowhere in the tree: **no comparison against
  a vendor bitstream runs in its CI at all.**

Four of this month's five defects produced a bitstream that a build-only gate
would pass. That is the gap, stated with sources.

**Next.** The `fib`/`lucas` exit convention (they print usage and exit 0 while
`phi` exits 2). Then propose the part-coverage gate upstream — a three-line flop
across the supported part list would have caught #154 on the day it appeared.

### 008 — 2026-08-19, night

**`fib` and `lucas` stopped reporting a missing argument as success.**
`runPhiCommand`, forty lines above them in the same file, already returned
`exitWithCode(.validation_error)` for the identical situation. Fourth instance
this session of the correct form sitting beside the incorrect one — that is
skill §4, and at four occurrences it is a location rule rather than an anecdote:
**defects live next to working code, in files nothing has exercised.**

**Proposed a part-coverage gate on openXC7#154.** The structural reading of that
defect is that no CI job builds anything on `xc7a35t`, so a part can regress to
totally broken without one red run. One three-line design across the supported
part list, through `fasm2frames` rather than stopping at P&R — because #149
showed a design that places and routes cleanly and then has no bitstream.

Offered to write and test it here before opening a PR, with an explicit
acceptance test for the gate itself: **it must fail on `xc7a35t` and pass on
`xc7a200t` before it is worth anything.** A new gate that cannot reproduce the
defect that motivated it is not evidence.

Asked two questions that are theirs rather than mine — which parts they consider
supported, and per-push versus nightly — and offered the worse fallback of
keeping it here if they would rather not carry another workflow.

**Next.** Build that gate here and demonstrate the acceptance test. Then the
remaining smoke-table anomalies, if any survive.

### 009 — 2026-08-19, night

**The part-coverage gate exists and passes its own acceptance test.**
Run 32122683650:

| part | nextpnr | fasm2frames | result | expected |
|---|---|---|---|---|
| `xc7a35tcsg324-1` | 255 | 1 | fail — `Invalid global constant node X0Y98/VCC_WIRE` | fail |
| `xc7a200tfbg484-2` | 0 | 0 | pass | pass |

Both jobs end "Matches the recorded expectation — gate is sound". It reproduces
openXC7#154 and does not false-positive on a working part, which was the
condition set in iteration 008 before it was worth proposing. Demonstrated on
the issue with an offer to open it as a PR.

**Three properties it was given deliberately**, each from a failure earlier in
this session:

* **It checks itself.** Expectations are pinned per part; a mismatch in either
  direction fails with a different message. A gate that cannot demonstrate it
  still detects something should not be able to report green — the build gate
  spent four months doing exactly that.
* **chipdb/yosys failures are INCONCLUSIVE, not part results.** The first #154
  reducer lacked this and reported four of my own broken XDC files as findings.
* **It runs to `fasm2frames`.** #149 places and routes cleanly and has no
  bitstream; stopping at P&R would call that fine.

**Two parts, not four, and the reason is written in the file.** Verified pins
exist for exactly these two. Guessing pins for the Kintex, Spartan and Zynq
parts would manufacture failures that are mine — the same mistake as the shared
XDC, which is now skill §11. Asked upstream for working pin assignments rather
than inventing them.

**Next.** Whatever upstream answers. Meanwhile: the smoke table is clean apart
from documented stubs, and `verify` is out of it for cause.

### 010 — 2026-08-19, night

**Queue empty, so the deferred item got done.** Upstream has not replied to #154
(every recent comment is mine), and web search still returns a model error — the
literature review stays blocked rather than written from memory, for the second
iteration running.

**`tri journal` added**, the one repeatedly-requested thing that only became
possible tonight. It prints a section of `research/loop-state.md`: latest entry,
invariants, or all. It deliberately parses nothing — a command that *summarised*
the journal would create a second version of the truth, which is the defect
class this session exists to repair.

**Two collisions caught before committing, for once**, rather than by the gate:

* `tri_loop` is already bound to `heartbeat.zig` at main.zig:29, and Zig forbids
  shadowing.
* **`loop` is already a command.** Bare `tri loop` routes to `dev_workflow`
  (main.zig:1532) and CLAUDE.md documents it as pipeline step ten, `tri loop
  decide`. An early dispatch on that name would have stolen it silently — still
  present, still documented, quietly doing something else. Renamed to `journal`.

That is §11 working on the first attempt. Not entirely: the rename's `sed`
matched one usage line of three and I read only the line I aimed at, leaving two
stale references inside the file about stale references. Fixed in a follow-up.

**Exit conventions are now consistent.** `phi`, `fib`, `lucas` all exit 2 on a
missing argument; `stats` and `doctor` exit 1 as unimplemented stubs; the other
seven exit 0 with real output. The smoke summary said "of 13 sampled" while
listing 12 — removing `verify` never decremented the count. Corrected.

**Next.** Nothing queued that does not depend on someone else. If upstream
answers #154, adapt the gate to their part list. Otherwise the honest options
are: extend part coverage once pins are confirmed, or stop adding and let the
gates run.

### 011 — 2026-08-19, night

**The empty queue was wrong: two gates were failing on my commits.** Checked
ownership of each rather than assuming either way.

**`Codegen Validation` — mine.** It builds with Zig **0.16**, and the `build.zig`
I restored is the March file, where `linkLibC()` is a method 0.16 removed. Eight
call sites, all one shape, converted to `root_module.link_libc` — the form this
same file already uses **fifteen times**, so its own idiom rather than a new
one, and one that works under 0.15 too. One file, two toolchains, one spelling.

The edit asserted its own scope: exactly eight sites expected, zero survivors
required, abort otherwise. **§11 applied rather than recalled** — and the
assertion means a ninth site of a different shape would have stopped the script
instead of being silently skipped.

**Verified no regression**: `tri builds` (0.15) still passes on the same commit.

**`Withdrawn numbers` — not mine.** It fails on `0.1173` in
`research/arxiv_tnf/tnf_paper.tex`, a document I have not touched this session.
Left alone.

**Three more paper gates fail** — Document references, Orphaned artefacts,
Undefined outputs — all on work another session is actively doing. Not touched:
interfering with live parallel work is worse than leaving a red gate that
belongs to someone else.

**Worth noting about this repository**: it has a gate whose entire job is to
catch withdrawn claims reappearing in the text. Given that this session
retracted one of its own corrections and then qualified the retraction, that is
not an ornament.

**Next.** Whether `Codegen Validation` gets past line 69 under 0.16 — if it does,
the next error is the real state of the 0.15→0.16 gap rather than a method name.

### 012 — 2026-08-19, night

**build.zig is 0.16-clean, confirmed in CI rather than only locally.** On
`c58b52e7d` the Codegen Validation run shows **zero** remaining errors in this
repository's build definition; the only two are inside the vendored raylib
package (`std.mem.trimLeft`, `std.process.getEnvVarOwned`, both removed in
0.16). Nine Compile-to-Module sites converted after enumerating the class out of
the 0.16 standard library rather than fixing one per round.

**Two of my own errors on that change**, both caught before they landed:
`-Dci=true` cannot help because build.zig's body compiles whole regardless of
runtime branches (a local pre-commit hook caught it), and the conversion
identified modules by a `_mod` suffix that `wasm_root` does not follow.

**Wrote to Hans and Carlos** — option B of the three offered. It carries #154
with its control, the working part-coverage gate offered as a PR, the state of
#149 and #114, the withdrawn timing correction, and three questions that block
further progress: which parts they consider supported, per-push or nightly, and
pin assignments for the three parts I cannot verify.

**Running score for the session: ~20 defects closed in other people's code, 5
introduced by me, all 5 caught by automation within one cycle, none noticed by
me first.** All five share one shape — a uniform edit applied to sites that were
not uniform.

**Next.** Nothing here is unblocked. #114 needs the AX7203, #149 needs `047b`,
the coverage gate needs their part list, and raylib needs a version that
supports 0.16 or the GUI targets dropped. If the loop fires again with no reply,
the honest report is "no change" rather than invented work.

### 013 — 2026-08-19, night

**Upstream replied — the first response on any of these threads.**
@hansfbaier on #154: litex-hub/litex-boards has pin assignments for a great many
boards, *"or am I misunderstanding something?"*

He was not misunderstanding, and my hesitation was unnecessary.
`litex-boards/litex_boards/platforms/digilent_arty_s7.py` names
`xc7s50csga324-1` exactly, so `clk12 F14`,
`user_sw0 H14`, `user_led0 E18` were a search away, not a research project.

**Part coverage extended to three parts.** The Spartan expectation is recorded
as `pass` and marked in the file as a **prediction, not a measurement** — that
part has never been built by this gate. If it fails like a35t, the pinned
expectation makes it a finding rather than a line to edit away afterwards.
Recording a guess as a guess is the only thing that makes the next result mean
anything.

**Kintex still absent, for a stated reason.** The board carrying exactly
`xc7k325t-ffg676-2` (`sitlinv_stlv7325_v1`) has only differential clock inputs,
marked TODO in its own file. The ffg676 boards with clean single-ended pins
(`berkeleylab_marble`) are a different die, `xc7k160t`. Package-level pins are
*probably* transferable — and "probably" is what produced four self-inflicted
failures in the first #154 reducer. Question goes back to Hans rather than a
guess going into the matrix.

**Process slip worth recording.** The first dispatch of the extended gate never
ran: `gh workflow run` sat at the end of an `&&` chain and was never reached. I
reported it as started. Third time this session I have taken the absence of an
error for confirmation of an action — the fix is to check the thing happened,
not that nothing complained.

**Next.** The three-part result. If Spartan passes, propose the PR to upstream
with two parts of evidence and one open question; if it fails, that is a second
part-specific defect and a bigger finding than the gate itself.

### 014 — 2026-08-19, night

**Three-part coverage green, all matching their recorded expectations.**
Run 32132592070:

| part | result | expected |
|---|---|---|
| `xc7a35tcsg324-1` | fail — the #154 error | fail |
| `xc7s50csga324-1` | pass | pass |
| `xc7a200tfbg484-2` | pass | pass |

So #154 is narrower than "some parts are broken": of three tested, **only a35t
cannot route a flip-flop**. Reported to Hans on the issue.

**Two more self-inflicted defects, sixth and seventh, both caught by the gate
within one run each.**

* The Spartan run first reported `fail`. nextpnr had finished with 0 errors;
  `fasm2frames` refused because the db-root was hardcoded to `artix7` and
  Spartan is `spartan7`. Family now lives in the matrix.
* Fixing that broke the other direction: I widened the INCONCLUSIVE classifier
  to treat assembler errors as harness faults, and a35t's genuine failure then
  reported as inconclusive — a failed P&R leaves no FASM, so `fasm2frames` says
  "No such file". The guard now applies only when nextpnr succeeded.

**All seven of my defects this session are one shape**, and it is worth naming
precisely now that the sample is large: *a rule that holds for the cases I was
looking at, applied to a set containing a case I was not.* Orphaned parameter,
prefix grep, unreachable return, shared XDC, `_mod` suffix heuristic, shared
db-root, widened classifier.

**The strongest evidence of the session, for the record.** The pinned
expectation was wrong about Spartan — I predicted pass, the first run said fail
— and being wrong is exactly what made it useful: the mismatch sent me to the
logs instead of accepting a plausible result. **A gate that only confirms its
author would have recorded a second part-specific defect that does not exist,
and then hidden the real one.** The value of a written expectation is not that
it is correct but that it is checkable.

**Next.** Kintex needs one answer from Hans (differential clock acceptable, or a
board with a single-ended one). `xc7z035` unexamined. Otherwise unchanged: #114
needs the board, #149 needs 047b.

### 015 — 2026-08-19, night

Recorded late; iteration 015 did the work and skipped the journal entry, which
is the same omission this journal exists to prevent.

**`xc7z035` cannot be added, and upstream's own `nextpnr-xilinx/.github/workflows/demos.yml` says why:**

    Known-failing projects (BRAM/LUTFF legaliser spiral on artix7,
    missing xc7z035 tilegrid) are intentionally not part of the subset.

No tilegrid means chipdb cannot be generated, so the gate would report
INCONCLUSIVE forever. Reason recorded in the workflow header rather than as a
permanently red row.

**That line also supports openXC7#154 from their side rather than mine.** Their
single gate is scoped to what passes, with known-failing cases excluded by
hand. A part nothing exercises cannot fail — which is how a35t reached "cannot
route a three-line flip-flop" without one red run.

**Skill §11 grew from four instances to seven** and got a statement rather than
a gesture: *a rule that holds for every case you looked at, applied to a set
containing a case you did not.* The larger sample added something the first four
did not show — the exceptions are never in the sites that motivated the edit,
always in the adjacent ones. Each rule was true when written and false when
extended.

### 016 — 2026-08-19, night

**Refreshed the state table at the top of this file**, which had not been touched
since iteration 001 and was wrong in three rows: `tri` was listed as "compiling
further each round" when it builds and runs; the benchmark corrections were
listed as owed when one had been retracted as wrong; and #154 and the coverage
gate were absent entirely, being younger than the table.

A stale summary at the top of the memory is worse than none — a later iteration
reads it first and trusts it. Added a line saying it decays and to check it
against the log.

**No upstream reply since Hans's pin pointer.** Kintex still waits on one answer.

**Nothing else is unblocked**, and the honest list of who holds what is: Hans
(differential clock question), Carlos (`047b`), the user (board A/B for #114,
pushing `zig-golden-float`), and whoever owns the GUI targets (raylib under
0.16).

### 017 — 2026-08-19, night

**No external change.** No upstream replies; the failing gates are the same four
belonging to the paper session plus Codegen Validation on vendored raylib.

**Widened the stub search and found nine sites outside the earlier fix.** The
first pass matched `"TODO - not implemented yet"`; searching every phrasing
finds **29 print sites announcing non-implementation**, so nine were missed —
eighth instance of the §11 shape this session.

**Five of the nine are not defects**, and reading them individually is what
established that:

    tri fpga gen not implemented - use zig build vibee instead   redirect
    Not implemented: use .tri specs instead                      redirect
    Detailed trends analysis coming soon  (x2)                   analysis prints
    Run with --write ... (coming soon)                           flag hint

Each sits inside a command that works. Changing their exit codes would turn a
working command into a failing one — **the distinction a blanket pattern edit
destroys**, and the reason this fix was made by reading nine sites rather than
by matching a string.

**Two were real** and now return `error.NotImplemented`: `runBenchCommandAsync`
(every path prints a TODO and returns void) and `runRepair` in
`cytoplasm_registry.zig`. A third, `serve`, was already correct. Build green.

**Method note worth keeping.** I predicted the §11 failure before making this
edit and therefore inspected each site by hand. That is the first time this
session the pattern was anticipated rather than discovered afterwards — the
skill entry earning its keep rather than just recording history.

**Next.** Still nothing unblocked from outside. Command coverage remains 12
tested of 144 advertised; extending it means deciding which commands are safe to
execute, since the list includes `clean`, `deploy`, `spawn` and `serve`.

### 018 — 2026-08-19, night

**Four parts green. Only a35t fails.** Run 32138267197:

| part | result | expected |
|---|---|---|
| `xc7a35tcsg324-1` | fail — the #154 error | fail |
| `xc7a200tfbg484-2` | pass | pass |
| `xc7s50csga324-1` | pass | pass |
| `xc7k325tffg676-1` | pass | pass |

Kintex added with `IBUFDS` on a differential clock, as promised to Hans on the
issue rather than waiting for his answer. It builds through `fasm2frames`.

**Two corrections to things I had told him**, both now on the issue:

* The `# TODO verify / test` comment in
  `litex-boards/litex_boards/platforms/sitlinv_stlv7325_v1.py` is on `clk156`
  and `clk150`, **not** on `clk200`, which is the one I used. I generalised from
  two lines to all of them.
* The Kintex part id is `-1`, not `-2`. I took the speed grade from the board
  that supplied the pins rather than from the database that would be asked
  about it.

**Ninth self-inflicted defect**, and a new angle on the same shape: taking one
field from one source and the rest from another without checking they agree.

**What the gate got right, which is the whole design.** It reported the Kintex
misconfiguration as **INCONCLUSIVE**, not as "Kintex cannot route" — the
distinction added two iterations earlier after the spartan7/artix7 database
mix-up. Two of four rows produced a harness fault before settling, and neither
became a false finding.

**A property worth stating for §11**: this file has now baked in a per-part
value three times — `LVCMOS33`, the `artix7` db-root, and the speed grade — each
correct for every row present when written. *A matrix with N rows teaches you
nothing about the N+1th, and the properties most likely to be hardcoded are the
ones the current rows happen to agree on.*

**Next.** Nothing unblocked. `xc7z035` stays out (upstream: missing tilegrid).
Awaiting Hans on the part list and cadence; #114 needs the board; #149 needs
`047b`.

### 019 — 2026-08-19, night

**Found an open draft of mine I had lost track of: PR #120**, two IOB bits that
diverge from Vivado on essentially every 7-series design. Not stale — updated
2026-08-18 — and held not by doubt but by coordination: the patch changes the
bitstream of any design with an LVCMOS33 pad, so `demo-projects` goldens stop
matching.

**Measured what "the goldens no longer match" actually costs**, since it had
never been stated. Eight committed goldens; **six change, two must not**:

| golden | standard | changes |
|---|---|---|
| arty, basys-3, zybo, genesys2, qmtech, litex-arty-s7 | LVCMOS33 | yes |
| `blinky-kc705` | no LVCMOS33 | **no** |
| `blinky-stlv7325` | LVCMOS15 | **no** |

**The two that must not change are the valuable half.** They turn a bulk
regeneration into something falsifiable: six diffs that should touch only the
two named IOB bits, and two files that must come out byte-identical. If either
of those moves, the patch reaches further than its description claims.

*A regeneration that cannot fail is not evidence the patch is right.* Same
principle as the coverage gate's pinned expectations, applied to an artefact
update rather than a test.

Offered to produce that table as a PR against `demo-projects`, and said plainly
I will not touch their reference artefacts uninvited.

**Skill §11 now at nine instances**, with the matrix corollary: *a matrix with N
rows teaches you nothing about the N+1th, and the values most likely to be
hardcoded are the ones the current rows happen to agree on.* Plus the habit from
the ninth: take every field of an identifier from one source.

**Next.** Still waiting on Hans (part list, cadence, and now the goldens offer),
Carlos (`047b`), and the board for #114.

### 020 — 2026-08-19, night

Hypothesis tested and refuted:
`prjxray-db/artix7/harness/arty-a7/swbut/design.json` and its three siblings
bitstreams is not a yosys netlist (`info`, `ports`, `required_features` only),
so no whole-design differential build is available from them. They support a
**per-feature** reference — `required_features` publishes 433/199/431/864 FASM
features per harness — not a per-design one. Correction appended to
`research/where-this-work-sits.md`, where I had implied more.

### 021 — 2026-08-19, night

**No external change** — no replies on #154, #149 or #120.

**Nearly edited a dead file, and that turned into a measurement.** Scanning for
command handlers safe to add to the smoke test, the scan returned
`runFibCommand`, `runLucasCommand` and `runPhiCommand` in
`src/tri/tri_math_backup.zig` — **imported by nothing**. I had fixed those three
earlier in `src/tri/math/commands.zig`. Two copies exist; the live one is the
one I edited, but only because I checked.

**395 of 744 files under `src/tri` are reached by neither `build.zig` nor any
relative import** — 3.13 MB. Written up in `research/src-tri-reachability.md`
with the method and its weakness stated: dead files importing each other keep
each other "reached", so the true figure is **larger**, not smaller. Nothing
deleted — that is the user's call, and a one-pass analysis is not grounds for it.

**Method correction worth recording.** The first count was 407. Adding
`b.path()` from `build.zig` as a reachability source brought it to 395. I nearly
published the larger figure; twelve files is a small error but a striking number
deserves the check before it is quoted, not after.

**What the orphan actually costs**, since "dead code" sounds harmless: a 228 KB
file answers `grep` with plausible, editable, unreachable code. A defect repair
landing in it would look correct, pass review, and change nothing. That is the
same failure `zig-hdc`'s header records from the other side — two maintained
copies of `src/vsa/*` diverged, and fixing sixteen defects in one left all
sixteen standing in the other.

**Next.** Unchanged: Hans (part list, cadence, goldens offer), Carlos (`047b`),
the board for #114. A reachability gate is proposed in the note but not built —
it needs a decision about what to do with 395 files first.

### 022 — 2026-08-19, night

**Built the reachability ratchet.** I had deferred it as needing a decision
about the 395 unreachable files; that was wrong — a ratchet needs no decision.
It counts, compares against `.github/reachability-baseline` (395), and fails
only on an *increase*. A decrease asks for the baseline to be lowered in the
same commit. Nothing is deleted. Green: 744 files, 395 unreachable, delta 0.

**Smoke list 12 → 18**, the six added by reading each handler rather than
guessing. It found two defects on its first run:

* **`spiral` aborted** — `for (args[1..])` where `args[0]` was guarded a line
  above and `args[1..]` was not. `n` defaults to 12, so a no-argument call is
  *supported* and used to panic. Now conditional.
* **`formula` reported a usage error as success** — third command in that file
  after `phi`, `fib` and `lucas`. Unlike `spiral` it has no default, so a
  missing argument really is an error. Now exits 2.

**The distinction between those two is the point.** One command must work with
no arguments; the other must refuse. A uniform edit would have made them alike
and broken one. Reading both is what separated them.

**Instrument fixed first, and it paid immediately.** The smoke step recorded one
line per command, so a panic's backtrace went in the bin — the case it exists to
catch. Failing commands now keep full output as an artefact. The retained trace
pointed at `math/commands.zig:504`, while `grep` for that handler returns
`tri_math.zig` and `tri_math_backup.zig` as well: **three copies, and I would
have edited a dead one.** Second near-miss of that kind in two iterations, and
the reason the ratchet exists.

Third time this session the right move was to make the instrument speak rather
than stare harder at its output. The others: `-freference-trace=12`, and
splitting "does it build" from "does it run".

**Next.** Unchanged externally. `formula`/`fib`/`lucas`/`phi` now agree on exit
2; whether the other 126 commands do is unmeasured.

### 023 — 2026-08-20, night

**Measured the usage-exit convention across the tree instead of sampling it.**
Handlers printing a `Usage:` line: 15 exit honestly, 29 return normally.
Narrowing to the unambiguous shape — `if (args.len == 0) { print("Usage: …");
return; }`, a required argument missing reported as success — gives **49 sites
in 15 files**.

**Eleven fixed, 38 measured and left.** The boundary: only files already
importing `tri_exit_codes`. The other 38 sit in 13 files that would each need an
import added, and a mass edit that also performs import surgery across thirteen
files is a different risk from one that changes a return statement.

**Three of the eleven were in `math/commands.zig`** — a file I had already been
through this session for `phi`, `fib`, `lucas` and `formula`. Fixing the four a
smoke test happened to exercise left three of the same defect in the same file.
*The difference between fixing what a test reports and fixing what the code
contains.*

**Tenth self-inflicted defect, and it is the first one repeated.** My "already
imports" test was `'tri_exit_codes' in source` — a substring match. In
`cytoplasm.zig` that string occurred once, at line ~2480, inside a
function-local import bound to the name `exit_codes`. So the match was on the
module **path in a string literal**, not on a declared identifier, and eight
sites referenced a name not in scope.

That is precisely iteration 006's defect — `grep 'pub const GoldenChain'`
matching `GoldenChainAgent` — which was written into skill §5 at the time. **A
substring is not an identifier**, known and violated again in a new disguise.
Caught by CI in one round.

**Process note.** The rebase hit vendored `zig-pkg` packages another session had
committed while mine existed untracked from a local build. Removed with
`git clean -fdq zig-pkg` rather than by deleting paths one at a time as the
error listed them.

**Next.** 38 usage sites remain, each needing an import. Externally unchanged.

### 024 — 2026-08-20, night

**The usage-exit convention is closed.** 38 remaining sites across 13 files
converted; a re-scan now reports **0** sites printing a usage message and
returning success. Build green.

**The import path was not uniform, which is why this was deferred rather than
swept in with the first eleven.** Ten files take `tri_exit_codes.zig`; three,
one directory deeper, take `../tri_exit_codes.zig` —
`commands/multi_cluster.zig`, `geometry/non_euclidean.zig`,
`geometry/sacred_bridge.zig`. A single hardcoded path breaks exactly those
three. **Eleventh instance of this session's one mistake, and the first
prevented rather than discovered** — by computing the value per file instead of
assuming the rows agree.

Two defences from the skill applied together, both earned earlier tonight:

* the edit asserts its plan — 13 files, 38 sites, abort otherwise;
* files already holding the binding are skipped by matching the **declaration
  at line start**, not the string anywhere in the file. The substring test is
  what put an undeclared identifier into `cytoplasm.zig` one commit earlier.

**Distribution is worth noting**: 17 of the 38 sit in `github_commands.zig`
alone. The defect is not spread evenly — it clusters where many commands were
written together from one template, which is also where a single wrong template
does the most damage.

**Running totals for the session**: ~20 defects closed in existing code plus 49
usage sites, 10 introduced by me, all 10 caught by automation within one cycle,
none noticed by me first.

**Next.** Externally unchanged — Hans on the part list, Carlos on `047b`, the
board for #114. The 395 unreachable files are ratcheted but untouched.

### 025 — 2026-08-20, night

**Gated the usage-exit convention.** Reports `sites: 0`; all steps green.

Two iterations went into finding and fixing 49 sites. Nothing stopped a
fiftieth appearing tomorrow, and the next person would have measured 49 again.
The repair without the gate is a deferred recurrence — which is the argument
this whole session keeps making, now applied to my own work rather than
someone else's.

**Static, not sampled.** It covers all 144 commands; the smoke test runs 18. The
first four instances were found only because the smoke list happened to include
them, and three more sat in the same file untouched until a tree-wide scan.

**It matches one shape on purpose.** A command asked for help explicitly must
print usage and exit 0, so matching the word would fail working commands. That
distinction cost a careful reading of 29 handlers; it is now encoded rather than
remembered.

**The error message names the fix and the precedent** — `exitWithCode`, as
`phi`, `fib`, `lucas` and `formula` do. A gate that says only "you broke it"
sends the reader to find out how, and in this tree they might find out from one
of the 395 unreachable files.

**Three instruments now exist, each grown from a specific miss:**

| instrument | the miss it came from |
|---|---|
| reachability ratchet | nearly editing a dead copy of a handler |
| failure-output retention | a panic backtrace discarded by the smoke step |
| usage-convention gate | 49 sites found twice, once by accident |

**Next.** Externally unchanged. Nothing self-contained left that does not need a
decision — the 395 files need one, and the remaining `tri` coverage needs a
judgement about which commands are safe to execute.

### 026 — 2026-08-20, night

**Attempted the recommended option — extend the smoke list from 18 to every
safe command — and stopped, because the classifier could not be made sound.**

Three revisions in one iteration, each unsound in the *dangerous* direction:

1. **Body-only scan for risky calls.** Reported 180 of 208 handlers safe —
   including `clean`, `deploy`, `serve`, `swarm`. Wrong because those handlers
   delegate; the risk sits one call deeper.
2. **Stricter: reject any handler calling project code.** Reported 87. Still
   included `git`.
3. **Spot-check against known answers**, which is what settled it:
   `runGitCommand` does `std.process.Child.init(argv, allocator)` and
   `child.spawn()`. My allow-list contained `std.` wholesale, and
   `std.process.Child` is inside `std.`. A second hole: unqualified calls
   (`showRailwayHelp(...)`, no dot) were skipped entirely.

**So the answer to "which commands are safe to execute" is not reliably
computable this way**, and feeding revision 1 or 2 into CI would have run
`deploy`, `serve` and `git` on every build. Recorded rather than iterated
toward a fourth revision that produces a number I wanted.

**What actually saved it** was testing the instrument on cases where the answer
was already known — `git` obviously spawns, `clean` is obviously a stub. That
check cost one command and invalidated two hours of direction.

**Consequence:** the smoke list stays hand-verified and small. 18 of 144, each
read individually. Coverage grows by reading, not by classification.

**Next.** Externally unchanged. The remaining paths all need a decision that is
not mine: the 395 unreachable files, and which risky commands may run in CI.

### 027 — 2026-08-20, night

**Wrote iteration 026's lesson into the skill as §12** — *test the classifier on
answers you already know*, with the corollary that decides what to do when it
fails: **ask which way its errors run.** A classifier that occasionally misses a
dead file wastes disk; one that occasionally calls a subprocess-spawning command
safe runs `deploy` in CI. Asymmetric error direction means abandon, not tune.

That distinction is what stopped a fourth revision. The fourth would have
produced the number I wanted and no more truth than the third.

**The skill now carries twelve sections**, and the arc across them is worth
naming: §1–§10 are about defects in other people's code, §11 and §12 are about
defects in the repair itself. The second half was not planned; it accumulated
because ten of my own defects landed in one session and every one shared a
shape.

**No external change.** #154 still one reply, #120 and #149 none.

### 028 — 2026-08-20, night

**Verification iteration. No external change, and all three gates green on
current `main` — checked rather than remembered.**

| gate | jobs |
|---|---|
| `tri builds` | build ✓ |
| `reachability ratchet` | ratchet ✓ (395, delta 0) |
| `part coverage` | a35t ✓ s50c ✓ a200t ✓ k325t ✓ |

None had run for several iterations, because nothing touched their trigger
paths. **"Was green" and "is green" are different claims**, and this session has
spent itself on that distinction — a gate that has not run lately guarantees
nothing, it only remembers.

**Still quiet**: #154 one reply, #120 and #149 none. Web search has failed with
the same model error for six iterations; the literature review stays unwritten
rather than written from memory.

**Nothing self-contained remains.** Every open path needs a person:

| waiting on | what |
|---|---|
| Hans | differential-clock question; whether to take the coverage gate as a PR |
| Carlos | `047b` — without those rows a BUFR from a pin has no bitstream |
| the user | board A/B for #114's four `ZSRVAL` bits; pushing `zig-golden-float` |
| a decision | the 395 unreachable files; whether risky commands may run in CI |

**Next.** Short iterations: check the four signals above, run the gates if
anything landed, report no change otherwise. That is the correct mode for a loop
that has run out of unblocked work, and it is preferable to inventing some.

### 029 — 2026-08-20, night

**No change on any of the four signals.** #154 one reply, #120 and #149 none,
`main` carries only my commits, `zig-golden-float` still unpushed.

Refreshed the state table above, which had not been touched since iteration 016
and predated the usage-convention work, the ratchet, the fourth coverage part
and six sections of the skill. **A stale summary at the head of the memory is
the failure this journal documents**, so it gets refreshed when it drifts rather
than when someone trips over it.

**Consecutive no-change iterations: 1.** Recording the count so the pattern is
visible. If it grows, that is the signal to pause the loop rather than let it
tick — the work is not stalled, it is finished pending other people.

### 030 — 2026-08-20, night

**No external change.** Signals unchanged for the second consecutive iteration.

**Tried to grow smoke coverage by reading, per iteration 026's conclusion, and
stopped one step short of a useless change.** Read five candidate handlers —
`groups`, `evidence`, `nuclear`, `particles`, `identities` — and verified all
five side-effect free, including one hop deeper for `identities`, whose
`printAllIdentities` is also pure. `particles` is pure arithmetic over inline
constants.

Then checked whether they are dispatched at top level. **None is.** All five are
subcommands, presumably of `math`. `tri groups` would land in the
unknown-command path, so adding them would have measured the dispatcher's error
handling and reported it as command coverage.

**So the smoke list stays at 18**, and the useful finding is about what remains:
the reachable top-level commands are largely covered, and the rest of the 144
are subcommands needing a two-token invocation with a valid argument. Testing
`tri math evidence` without a name now correctly exits 2 — which is the
convention working, and not a test of the command.

Meaningful coverage beyond this means supplying real arguments per subcommand.
That is a different and larger piece of work, and it needs someone who knows
what a valid argument is for each.

**Consecutive no-change iterations: 2.**

### 031 — 2026-08-20, night

**Third consecutive no-change iteration.** All signals flat: #154 one reply,
#120 and #149 none, submodule unpushed, no commits on `main` but mine.

At iteration 029 I wrote that a growing no-change count is the signal to pause
the loop deliberately rather than let it tick. It has reached three. **I am not
stopping it unilaterally** — a continuous loop is what was asked for, and the
user is asleep and cannot be consulted — but the recommendation belongs on the
record, and it is in the report.

**Wrote `research/HANDOFF-morning.md`** instead: the things that need a person,
in one file, with the commands to run. Five minutes for the submodule push,
the FASM-level A/B for #114 with both outcomes stated in advance, the two
decisions that are the user's, who is waiting on what, and the two unsent
letters — noting that the retraction matters more than the status letter,
because a wrong claim of mine may already have been acted on.

That is the last thing the loop can produce without new input. Further
iterations should check the four signals and stop.

**Consecutive no-change iterations: 3.**
