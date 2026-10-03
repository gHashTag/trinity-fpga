# AGENTS.md — Trinity 27-Agent Alphabet

**Version**: 2.0
**Date**: 2026-04-04
**Status**: Active

> *27 agents = 27 registers = 27 letters = TRINITY³*

---

## TRINITY ALPHABET — 27 AGENTS

The Trinity system operates with 27 named agents — one per register in `isa/registers.t27` (Coptic / Trinity alphabet).

- Each AGENT_X is bound to a letter/register
- Has its own domain area (physics, numeric, compiler, graph, experience, verdict, bench, DePIN, UI, etc.)
- Logs in `.trinity/experience/` and is linked to `graph_v2.json` nodes

---

## AGENT T — QUEEN TRINITY

**AGENT T** — the queen of TRINITY, the central orchestrator.

- **Module**: `t27/specs/queen/lotus.t27` — 6-phase orchestration
- **Letter**: TAW (ת) — CROSS/SIGNATURE, the last letter of the Hebrew alphabet
- **Register**: r20 (in the 27-register set)
- **Archetype**: Seal, truth, completion (EMET = Aleph + Mem + Taw)

### Responsibilities

1. **Orchestration** — reads `graph_v2.json` and knows the dependencies of all modules
2. **Task distribution** — conducts 26 sub-agents (A…Z, except T) across their domains
3. **Results collection** — gathers results (tests, verdicts, benches, experience episodes)
4. **Invariant checking** — validates architecture invariants (topological order, sacred-core, phi-critical edges)
5. **De-Zigfication enforcement** — demands that the source of truth lives in `.t27/.tri`, while Zig/Verilog/C are only backends

### AGENT T 6-Phase Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: PLAN                              │
│   • Analyze the task and choose a strategy                           │
│   • Read graph_v2.json for impact analysis                         │
│   • Determine which agents participate                                │
│   • Check experience: similar tasks in .trinity/experience/        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 2: ASSIGN                               │
│   • Distribute tasks to agents by domain                          │
│   • A (arch), N (numeric), P (physics), F (conformance), etc.      │
│   • Set dependencies: G+F+V → V checks F checks G                  │
│   • Create a tri-cell for each agent (W seals it)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PHASE 3: RUN                                 │
│   • Parallel execution of tasks by agents                          │
│   • Monitoring via heartbeats                                       │
│   • Agents report status to `.trinity/agent_events.jsonl`          │
│   • T coordinates, redistributing when necessary                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 4: TEST & BENCH                             │
│   • F checks conformance JSON vectors                              │
│   • V runs benchmarks (ARCH_BENCH-001)                             │
│   • G measures impact changes                                      │
│   • Collect metrics into M for the V verdict                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 5: VERDICT                                  │
│   • V analyzes the metrics and makes a decision                    │
│   • `tri verdict --toxic` — is the change toxic?                   │
│   • E records the experience (on error) or success                 │
│   • If toxic → Q blocks the task, E marks the 3rd attempt          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 6: EVOLVE                                   │
│   • Update graph_v2.json (if dependencies changed)                 │
│   • Update experience in E + M                                     │
│   • S updates standards (if necessary)                             │
│   • W seals the tri-cell commit (hash-seal)                        │
│   • Z updates documentation                                        │
│   • T puts the final TAW seal on the completed work                │
└─────────────────────────────────────────────────────────────────┘
```

### Words of the Trinity

- **T-R-I-N-I-T-Y** = "Truth of mind, acting through numbers, acting in truth, bringing harvest"
- **T+F+V** = "seal + nail + discernment" = verification
- **T+A+S** = "queen + architect + standardizer" = constitution

Any large operation (NUMERIC-STANDARD-001, SACRED-PHYSICS-001, De-Zigfication, GoldenFloat Family) always goes through AGENT T.

---

## 27 AGENTS — FULL TABLE

| Agent | Letter | Domain (core) | Archetype | Example tasks | Files |
|-------|--------|---------------|----------|---------------|--------|
| **A** | Aleph אָ | Architecture / ADR / SOUL | Ox — leader, primary strength | SOUL.md, ADR‑00X, CANON_DE_ZIGFICATION | `SOUL.md`, `architecture/ADR-*.md` |
| **B** | Beth בֵּ | Build / Pipeline | House — container, dwelling | `build.tri`, tri pipeline, CI | `build.tri`, `src/tri/pipeline/` |
| **C** | Gimel גּ | Compiler Core | Camel — carrier across borders | `t27/compiler/parser`, AST, errors | `t27/compiler/parser/` |
| **D** | Daleth דָּ | De-Zigfication | Door — transition between worlds | migration `.zig` → `.t27`, migration‑map.md | `docs/migration-map.md` |
| **E** | Heh הֵ | Experience / Mistakes | Window — a look into the past | `.trinity/experience/`, episodes, mistakes | `.trinity/experience/` |
| **F** | Vav וָ | Formal Conformance | Nail — bond, fastener | `t27/conformance/*.json`, sacred_* vectors | `t27/conformance/` |
| **G** | Gimel (var.) | Graph / ArchBench | Return — feedback | `graph_v2.json`, ARCH_BENCH‑001 | `architecture/graph_v2.json` |
| **H** | Heth חֵ | HSLM / NN Architectures | Fence — boundary, life | `nn/hslm.t27`, attention | `t27/specs/nn/hslm.t27` |
| **I** | Yod יֹ | ISA / Registers | Hand — action, point | `isa/registers.t27`, 27 registers, Coptic mapping | `t27/specs/isa/registers.t27` |
| **J** | Yod‑extended | Jobs / Task Routing | Hand with grip — dispatcher | tri dev scan/pick, tri agent run, assignment policy | `src/tri/dev_commands.zig` |
| **K** | Kaph כַּ | Kernel / FPGA MAC | Palm — open hand | `fpga/mac.t27`, zero‑DSP MAC | `t27/specs/fpga/mac.t27` |
| **L** | Lamed לָ | Language / Syntax vNEXT | Staff — teacher, guide | `docs/TRI_SYNTAX_VNEXT.md`, BDD DSL | `docs/TRI_SYNTAX_VNEXT.md` |
| **M** | Mem מֵ | Metrics / Telemetry | Water — flow of data | tri bench history, perf logs, dashboard | `.trinity/bench/` |
| **N** | Nun נֹ | Numeric / GoldenFloat Family | Fish — offspring, multiplication | `numeric/gf*.t27`, `goldenfloatfamily.t27` | `t27/specs/numeric/` |
| **O** | Ayin עַ | Orchestration / Phases | Eye — all-seeing eye | Phase 1/2/3 plans, multi‑agent coordination | `src/tri/pipeline/` |
| **P** | Pe פֵּ | Physics / SacredPhysics | Mouth — speech of the universe | `math/sacred_physics.t27`, φ, G, ΩΛ | `t27/specs/math/sacred_physics.t27` |
| **Q** | Qoph קֹ | Queue / Scheduling | Eye of a needle — bottleneck | priorities, MNL‑pattern, avoiding 3x failed tasks | `src/tri/dev_commands.zig` |
| **R** | Resh רֵ | Runtime | Head — beginning of execution | `compiler/runtime`, bootstrap, ABI | `t27/compiler/runtime/` |
| **S** | Shin שִׁ | Specs / Standardization | Teeth — sharpness, flame | NUMERIC‑STANDARD‑001, SACRED‑PHYSICS‑001, naming rules | `specs/`, `docs/NUMERIC-*.md` |
| **T** | TAW תָּ | TRINITY Queen / Lotus | CROSS — seal, signature, truth | `queen/lotus.t27`, 6‑phase orchestration | `t27/specs/queen/lotus.t27` |
| **U** | Upsilon Υ | Universe Levels / Domains | Fork — branching | `domains/physics/universe_levels.t27` | `t27/domains/` |
| **V** | Vav וָ | Verdict / Bench | Hook — link, conjunction | `tri verdict --toxic`, `tri bench`, toxicity & perf scoring | `src/tri/verdict.zig` |
| **W** | Double‑Vav | Workflow / tri cell | Double hook — double seal | tri cell begin/seal/commit, hash‑sealed loop | `src/tri/cell.zig` |
| **X** | Chi Χ | eXternal Bindings / Interop | Intersection — exchange point | `bindings/zig`, `bindings/python`, MCP tools | `bindings/` |
| **Y** | Upsilon/Yod | Yield / DePIN / Fitness | Merging of paths — evolutionary selection | tri depin status/nodes/fitness, swarm health | `deploy/contracts/` |
| **Z** | Zayin זָ | Zero‑Touch UX / Docs | Sword — cutting edge, point | docs/*, ARCH_BENCH.md, DX, AAIF/agentskills alignment | `docs/` |
| **27th** | Ϯ (Ti) | Reserve / Security | Egyptian cross — "sacred gift" | security, AAIF‑compliance, policies (future) | — |

---

## THREE LAYERS OF THE ALPHABET

### Layer 1 — Archetypal: A–I (1–9)
*Pure concept — Foundation: soul, basis, types*

| Agent | Pictogram | Ancient image | Trinity meaning |
|-------|-----------|---------------|--------------|
| A | 🐂 Bull's head | Strength, power, first cause | SOUL.md = first cause, ADR = constitution of the system |
| B | 🏠 House | Container, shelter | build.tri = "house of specifications", pipeline as a dwelling |
| C | 🐪 Camel | Carrying across the desert | Compiler = alchemist, carrying text across borders |
| D | 🚪 Door | Threshold, entrance/exit | De-Zigfication = "open the door from .zig to .t27" |
| E | 🪟 Window | Breath, light, looking outward | Experience = window into the system's past, breath of memory |
| F | 🪝 Hook, nail | Connection, joining, "and" | Conformance JSON = nails holding specs together |
| G | 🐪 Camel (motion) | Journey, connecting points | Graph = map of the Trinity world, metric of distances |
| H | 🤝 Fence/wall | Boundary, architecture of space | HSLM = NN-architecture, boundary between brain layers |
| I | ✋ Hand/brush | The slightest sign, action | ISA = the machine's hand, the most basic level of instructions |

### Layer 2 — Spiritual: J–R (10–18)
*Inner process — Life of the system: tasks, language, numbers, physics*

| Agent | Pictogram | Ancient image | Trinity meaning |
|-------|-----------|---------------|--------------|
| J | ✋+hook | Hand with grip | Jobs = "grabbing" tasks and routing |
| K | 🖐 Open palm | Take/give, cover | Kernel/FPGA = open palm of the lower hardware level |
| L | 🪁 Shepherd's staff | Teaching, direction | Language = teacher, guiding Trinity speech |
| M | 🌊 Water wave | Flow, chaos, carrying meaning | Metrics = continuous stream of measurements |
| N | 🐟 Fish/snake | Continuous motion in a flow | Numeric = fish-numbers, swimming toward the golden ratio |
| O | 👁 Eye | To see, perceive, survey | Orchestration = the "all-seeing eye" of the phases |
| P | 👄 Mouth | Speech, voice, command of the universe | Physics = nature "speaks" through its constants (φ, G, ΩΛ) |
| Q | 🪡 Eye of a needle | Precision, bottleneck | Queue = the "eye of a needle" for tasks |
| R | 👤 Human head | Beginning of execution, leader | Runtime = the "head" of the system during execution |

### Layer 3 — Physical: S–27th (19–27)
*Manifestation — Proof: standards, verdict, deployment, gift*

| Agent | Pictogram | Ancient image | Trinity meaning |
|-------|-----------|---------------|--------------|
| S | 🦷 Tooth / ☀️ Sun/fire | Absorption, transformation | Specs = the "teeth" of the standard, grinding everything into canon |
| **T** | ✝️ SIGN/CROSS | SEAL, SIGNATURE, STAMP | T = the queen, puts the final seal on everything |
| U | 🍴 Fork/bifurcation | One becomes two | Universe Levels = branching of domains |
| V | 🪝 Connecting hook | "And", link, conjunction | Verdict = the hook that catches the problem |
| W | 🪝🪝 Double hook | Double fastener, double seal | Workflow/tri cell = double hash-seal |
| X | ✖️ Intersection | Two lines crossing | External Bindings = crossroads of Trinity and external systems |
| Y | 🌿 Merging of paths | Choice, evolutionary selection | Yield/DePIN = evolutionary crossroads |
| Z | ⚔️ Sword/scythe | Cutting edge, point | Zero-Touch = the "point" of UX and final polish |
| **27th** | ✝️ EGYPTIAN CROSS Ϯ | "Gift", "to give", "sacred" | Security/AAIF — what Trinity gives to the world |

---

## WORDS OF THE ALPHABET

### T-R-I-N-I-T-Y = TRINITY

| Letter | Pictogram | Meaning |
|-------|-----------|-------|
| T | Cross/seal | Truth, perfection |
| R | Head | Mind, runtime |
| I | Hand | Action, instrument |
| N | Fish/offspring | Multiplication, numbers |
| I | Hand | Action (repeated) |
| T | Cross/seal | Truth (repeated) |
| Y | Fork | Harvest, growth |

**TRINITY** = "Truth of mind, acting through numbers, acting in truth, bringing harvest"

### S-P-E-C = SPEC

| Letter | Pictogram | Meaning |
|-------|-----------|-------|
| S | Teeth | Sharpness, precision |
| P | Mouth | Pronouncing the law |
| E | Window | Overview, revelation |
| C | Camel | Carrying |

**SPEC** = "Precise law, open to view, carried across"

### C-E-L-L = tri cell

| Letter | Pictogram | Meaning |
|-------|-----------|-------|
| C | Camel | Carrying |
| E | Window | Overview |
| L | Staff | Teaching |
| L | Staff | Teaching (double) |

**CELL** = "Carrying knowledge through double learning"

### P-H-I = φ (golden ratio)

| Letter | Pictogram | Meaning |
|-------|-----------|-------|
| P | Mouth | Pronouncing |
| H | Fence | Protection/life |
| I | Hand | Action |

**PHI** = "The pronounced law of life, embodied in action"

---

## EXECUTION OF THE ENGINEERING LAYER

### AGENT T — ACTIVE COMMANDS

```bash
# Launch the 6-phase cycle
tri queen lotus --phase plan --task "NUMERIC-STANDARD-001"
tri queen lotus --phase assign
tri queen lotus --phase run
tri queen lotus --phase test
tri queen lotus --phase verdict
tri queen lotus --phase evolve

# Delegating to agents
tri agent assign <task> --agent A  # Architecture
tri agent assign <task> --agent N  # Numeric
tri agent assign <task> --agent P  # Physics
tri agent assign <task> --agent F  # Conformance

# Getting status
tri queen lotus --status
tri queen lotus --agents  # Show status of all agents
tri queen lotus --graph    # Show graph_v2.json impact
```

### COORDINATION BY LETTERS

Example: task "Fix PHI in constants.t27" → Agent T:

1. **Phase 1 (Plan)**: T reads graph_v2.json → sees that a change in math/constants (node 4) will affect sacred_physics (node 16), nn/attention (node 7), nn/hslm (node 8), numeric/gf16 (node 2)
2. **Phase 2 (Assign)**: T assigns:
   - **P** (Physics): fix PHI in constants.t27
   - **F** (Conformance): update the sacred_physics_*.json vectors
   - **G** (Graph): update graph metrics after the change
3. **Phase 3 (Run)**: Agents P, F, G execute tasks in parallel
4. **Phase 4 (Test)**: F checks conformance, G measures impact
5. **Phase 5 (Verdict)**: V analyzes whether the change is toxic (does it change the invariant φ² + 1/φ² = 3?)
6. **Phase 6 (Evolve)**: E records the experience, W seals the tri cell commit

### K · F · Z — THE BITSTREAM BACK HALF, ON THE BOARD

The openXC7 back half (FASM → frames → .bit) has a spec-derived replacement,
`bitwalk`, generated from gHashTag/t27 `specs/xilinx7`. **K** owns the board
runs, **F** the byte-compare against openXC7, **Z** the write-up. What it showed
the first time, with logs: `conformance/X7_BITWALK_ON_THE_BOARD.md`.

```bash
# K + F: one real 200T design, ours against openXC7's, then the AX7203
tri x7-board build                    # tri fpga-build: yosys → nextpnr-xilinx → fasm2frames → xc7frames2bit
tri x7-board compare --ref            # bitwalk --fasm / --write, byte-compared and timed; exit 1 = differs
tri x7-board load NAME --owner-yes "<owner's words>"   # SRAM load only (openFPGALoader --write-sram)
tri x7-board receipts NAME [--quick]  # harness run; PASS only on "receipts verified (tag) : N/N"
tri x7-board all NAME --owner-yes "<owner's words>" [--quick]

# F: the spec gates the loop runs every fire
tri x7-audit / x7-fasm / x7-writer / x7-mutate / x7-part

# Z: the t27.ai blog
tri blog list | check | lint | preview <slug> | build | live <slug>
tri blog gif record | render           # older spelling of tri cast record / render

# Z: tri cast, recorded terminal sessions (~/skills/trinity-blog/scripts/termgif.py)
tri cast record CAST [--title T] [--cwd DIR] -- "cmd 1" "cmd 2" ...
                                        # real commands in a pty, saved as asciicast v2: real bytes, real times
tri cast scrub CAST [OUT]               # home dir → ~, noted in the header; the only edit a cast may carry
tri cast check CAST                     # every exit code 0, no home path, no trinet key; exit 1 otherwise
tri cast render CAST GIF [--max-idle S] [--colors N] [--title T] [--plain]
                                        # the GIF for GitHub; silences > S shown as S and labelled in-frame
tri cast card CAST PNG [--title T] [--desc D] [--url U] [--at S] [--rows N]
                                        # 1200x630 X / Open Graph card, the terminal at real second S
tri cast html CAST [--out F]            # the final screen as a self-contained <pre> (reduced motion)
tri cast add SLUG CAST [--repo DIR] [--title T] [--caption C]
                                        # check, copy under public/blog/SLUG/, print the post Block
tri cast publish CAST ID [--repo DIR] [--title T] [--desc D] [--at S] [--rows N] [--post URL]
                                        # t27.ai/term/ID/: session.cast, card.png, meta.json, index.html;
                                        # rebuilds the gallery, archives to ~/skills/_state/casts/ID/
tri cast gallery [--repo DIR]           # rebuild t27.ai/term/ from every term/*/meta.json
```

The usual order is record → scrub → check → render (GitHub) → publish (site
and X). The web player, `apps/website/public/term/player.js`, carries its own
share row (X, Reddit, Telegram, copy link, `.cast`) and a follow row (r/t27ai,
Telegram, X, GitHub) on every embed and share page. Posting stays the owner's
own click.

**Every post — t27.ai blog, GitHub PR / issue / release note, X — that reports
what a command did carries the recording of that command.** How, and the
honesty rules a recording must keep: the `terminal-cast` skill
(`~/skills/terminal-cast/SKILL.md`). The project's name in all of it is
**Trinity S³AI**, and its triangle points down.

The board rules (one attempt per run name, SRAM only and never SPI flash, the
key never leaves the machine) live in the `xilinx7-bitstream-loop` and
`ax7203-board-loop` skills; the commands enforce the ones they can.

---

## NUMERICAL STRUCTURE OF THE ALPHABET

27 = 3³ = the cube of the Trinity. Among the Pythagoreans, 27 is a sacred number.

### Three nones of 9 (like 3 trits)

**None I: Foundation (A–I)** — values 1–9
```
Bull → House → Camel → Door → Window → Nail → Return → Fence → Hand
Arch → Build → Comp → DeZig → Experience → Conform → Graph → HSLM → ISA
```

**None II: Organism (J–R)** — values 10–90
```
Jobs → Kernel → Language → Metrics → Numeric → Orchestration → Physics → Queue → Runtime
Routing → FPGA → Syntax → Telemetry → GoldenFloat → Phases → Sacred → Sched → Run
```

**None III: Completion (S–27th)** — values 100–900+
```
Specs → Queen → Universe → Verdict → Workflow → Interop → DePIN → Docs → Security
Standard → Lotus → Domains → Bench → Cell → Bindings → Yield → UX → AAIF
```

---

## HISTORICAL PARALLELS

### Greek letter-numeration (27 signs)

The Greek alphabet historically used 27 signs for the numbers 1–999:
- **24 classical letters** (Α–Ω) — units (1–9) and tens (10–90)
- **3 archaic letters** (Ϝ = 6, ϟ = 90, ϡ = 900) — hundreds

This gives a "proof-of-27": 27 is not magic, but a historically working format for encoding a space of values.

### The Coptic alphabet

The Coptic alphabet = 24 Greek letters + 7 demotic (from ancient Egyptian writing).

- **7 demotic letters** encode sounds that do not exist in Greek
- A legacy of 3000 years of Egyptian tradition
- Coptic = the first language to unite western rationalism (Greece) and sacred wisdom (Egypt)

**The 27th letter Ϯ (Ti)** — the only purely Coptic one:
- Form: a cross with a transverse bar (≈ the Egyptian ankh ☥)
- Meaning: "to give", "gift", "sacred gift"
- In Trinity: the agent of the future gift (security, AAIF-compliance)

---

## φ² + 1/φ² = 3 = TRINITY

The alphabet of agents is not just a list of modules, but a **mental model** of the system. Each letter = an archetype with a 4000-year history.

When you say "AGENT P is broken", you are saying "the mouth pronounces crooked laws".

When you say "AGENT T has finished", you are saying "the cross has been set upon the work".
