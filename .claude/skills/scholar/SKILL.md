---
name: scholar
description: Self-Evolving Research Agent — scans web for relevant tech, evaluates findings, proposes improvements. Uses Perplexity Sonar API via MCP.
argument-hint: [scan|eval|apply|full|report|topic:"query"]
allowed-tools: Bash(gh *), Bash(cat *), Bash(grep *), Bash(find *), Bash(python3 *), Bash(echo *), Bash(date *), Bash(wc *), Bash(git *), Bash(test *), Bash(ls *), Read, Edit, Write, mcp__perplexity__perplexity_search, mcp__perplexity__perplexity_ask, mcp__perplexity__perplexity_research, mcp__perplexity__perplexity_reason
model: opus
context: fork
---

For output formatting conventions, follow `.claude/skills/_shared/output_format.md`.

Scholar — autonomous research agent for Trinity.
Scans the web for relevant technologies, evaluates findings against project context,
and proposes improvements via GitHub issues or MU Learning DB entries.

Uses Perplexity Sonar API via MCP (4 tools: search, ask, research, reason).

## Modes

Parse $ARGUMENTS to determine mode:

- `scan` — Run SCAN phase only (search for new findings)
- `eval` — Run EVAL phase on last scan results
- `apply` — Run APPLY phase (create issues / enrich MU)
- `full` — Run all 3 phases sequentially (default if no args)
- `report` — Show last scan results without running new scan (for bridge/Perplexity)
- `topic:"<query>"` — Deep research on a specific topic
- `errors` — Scan for solutions to current broken specs/compilation errors
- `zig` — Scan for Zig 0.15 updates and best practices
- `fpga` — Scan for FPGA/edge AI optimization techniques
- `agents` — Scan for self-evolving agent architectures

## Phase 1: SCAN

### Phase 0: what we already settled (run BEFORE searching outside)

`research/frontier/INDEX.md` indexes the 76 frontier/block documents. Read it
first — four separate sessions have re-derived results that were already on
disk, because a search that does not know the filename finds nothing and an
empty search reads as an open question.

Two traps, both paid for:

- **An index entry is not a verdict.** The grouping is mechanical (it reads
  titles for "closed", "withdrawn", "still"), and all three entries it filed
  under "open ends" were in fact closed — two by documents sitting in another
  section of the same index, with no link between the entries. That section is
  now hand-resolved with supersession links; the other sections are not.
- **Read the prose under the table, not just the table.** For six loop
  iterations "the fan-in 32 pipeline regression, nobody investigated why" was
  carried forward as an open question. `NODE_PIPELINED_2026-08-11.md` answers it
  in the paragraph directly beneath the table that was being quoted: the register
  cost overtakes the frequency gain between sixteen and thirty-two, the cut buys
  30 % frequency for 42 % area at 32, and the quotable configuration is fan-in 8
  or 16. Copying a table out of a document is not reading it.
- **Read to the end before citing a title.** One document of the 76,
  `LADDER_THIRD_MODEL_BREAKS_4BIT`, carries a follow-up appended below a rule
  that withdraws the result its own title announces.

The instrument you navigate by sits inside the failure domain: if the index is
stale, every search that starts from it inherits the staleness. Confirm an entry
against the document's *conclusion* before starting work on it, and when you
discover a stale entry, fix the index in the same pass — otherwise the next
session pays for it again.

### Re-measuring one of our own results

Scope objections to our own conclusions are the highest-value work available,
because they are the ones a reviewer raises and we cannot answer by argument.
`ROTATION_VERDICT_2026-08-11.md` is the pattern:

- **Reuse the original's code, do not reimplement it.** `block_tnf.py` runs its
  driver at module level, so it cannot be imported; the source is split on its
  own first driver line and the helpers executed. A copy would drift and the
  comparison would quietly stop being apples to apples.
### The ruler check earns its keep by refusing to run

Making a script reproduce the published table *before* it does anything else is
not ceremony. On 2026-08-11 that gate stopped a codebook search dead: the fp32
baseline and Lloyd-Max matched to four decimals and MXFP4 came back 21.9397
against a published 22.4998. Neither number was wrong — E2M1's top magnitude is
6.0, not a power of two, so dividing the block maximum by it does not commute
with rounding the E8M0 scale up, and three defensible rules span **21.94 to
23.54, a 7.3 % spread** on comparisons whose margins are under 3 %.

Without the gate the search would have run, found something, and reported it
against whichever MXFP4 number the script happened to compute.

**When a ruler check fails, suspect the ruler first.** The failure above was
written up as two documents disagreeing. Re-measuring both codebooks under both
rules showed the published pair was internally consistent and the *check* was
not: it had normalised one codebook to a top of 1.0 and left the other
un-normalised, so it measured one arm under each rule. The correction went into
the document that made the claim, the same day.

The instrument still earned its keep, because what it actually found was
sharper: under one rule the squared-error optimum beats MXFP4 by 0.90 %, under
the other MXFP4 beats it by 4.45 %. **The convention decides which codebook
wins**, which is a stronger statement than either number.

- **A convention is part of a number.** Any figure that depends on an alignment,
  a rounding direction or a normaliser must carry it, or two correct
  measurements read as a contradiction — which is what shipped to the site and
  to `COMPETITIVE_LANDSCAPE` before this was found.
- **Check which way the ambiguity cuts.** Here the specification's own rule was
  the least favourable to the competitor, so every claim held with more room
  than reported. Saying so is worth more than the claim itself.
- **Do not restate published tables to fit a new convention.** They are correct
  and internally consistent; re-deriving trades a documented convention for an
  undocumented re-run.

- **The reproduction is the real instrument check.** Before reading any new
  number, the unrotated arms had to return 21.9397 / 36.7214 / 14.7269 /
  18.0275 — the published figures, to four decimals. That is what proves the new
  script and the old document measure the same thing; a baseline in a plausible
  band does not.
- **Check that the intervention is an involution.** Rotate-then-unrotate with no
  quantisation had to return the weights (2.4e-07) and leave perplexity
  unchanged. Without that, every rotated number measures a broken transform.
- **Expect the answer to be unwelcome and report it anyway.** It widened the gap.
  That is a better outcome than leaving the objection open, and it is the version
  a reviewer cannot use against us.
- **State what the measurement isolates.** This measured rotation alone; the
  published method is rotation plus GPTQ error compensation. Say so in the
  document, the commit and the page, or the result will be over-read.

Model weights for this line live under a *previous session's* scratchpad
(`/private/tmp/claude-501/.../0e868af8-.../scratchpad/weights`, 2.3 GB: SmolLM2,
Qwen, Pythia, GPT-2, OPT, and wikitext-2). Check there before downloading
anything — it survives across sessions but not forever.

### Run the baselines before building the alternative

The single most expensive omission of 2026-08-11, and it cost three sessions.

`BLOCK_AXIS_CLOSED` concluded no eight-level element format takes the block axis
from MXFP4. Three codebooks were then designed and searched here to test it. The
thing that actually falsified it was **NF4** — the 4-bit NormalFloat from QLoRA,
published in 2023, sixteen constants in `bitsandbytes`, fitted to a Gaussian
prior and to nothing in this repository. It beats MXFP4 in this harness by
**−6.50 % pooled out of sample**, `t = −15.60`, `p = 2e-28`, at strictly equal
budget. **Nobody had ever run it.**

A day of searching produced a codebook five times weaker than that.

- **Every "we beat X by Y %" is meaningless until the field's own leader is in
  the same table.** Beating a *deployed hardware format* is not the same as
  beating the *research* in the class your work belongs to, and the second is the
  one a reviewer will ask about.
- **The strongest opponent is usually free.** Published constants, a pip install,
  an afternoon. That is cheaper than any search, and it bounds what a search is
  worth before the search is run.
- **A conclusion of the form "nothing can do X" needs a literature check, not
  just an argument.** The argument in `BLOCK_AXIS_CLOSED` was wrong *and* the
  counterexample predated it by three years.

The corollary for reporting: once a real baseline is in the table, restate old
margins against it. "−1.31 % against MXFP4" and "five times weaker than NF4" are
the same measurement, and only the second tells the reader where the work stands.

### Hold out the unit the parameters were fitted against

The most expensive lesson of 2026-08-11. A codebook with six free parameters was
fitted against one model's logits and beat MXFP4 by 7.66 %. It was checked on
held-out **windows** — disjoint text, a paired per-window test, `t(39) = −12.51`,
better in 39 of 40, `p = 7.5e-11`, and the two leaked windows deleted for a
0.12 pp change. Every part of that check was sound, and it certified an overfit.

Run on two models it had never seen, the codebook **lost** to MXFP4 by 1.98 % and
8.63 %, worse on 17 of 20 and 37 of 40 windows. First of three where it was
fitted; second of three where it was not.

The check varied text. The parameters were fitted to a *model*. A test that
varies the wrong axis measures generalisation across an axis nobody was
overfitting to, and passes with an impressive p-value.

- **Name the fitted unit before designing the check.** Model, layer, dataset,
  seed, board — whichever the parameters saw is the one to hold out.
- **A strong statistic on the wrong axis is worse than no check**, because it
  buys confidence. `p = 7.5e-11` was true and irrelevant.
- **Look for the ranking inversion.** Best on the fitting unit, middle of the
  pack elsewhere, is the signature. Compare against *both* neighbours, not just
  the headline opponent — here the weaker claim (beats the squared-error optimum
  on all three models) transferred and was worth keeping.

### The graceful failure is the dangerous one

Two codebooks were fitted to the same model with the same search and the same six
free parameters, differing only in what they were fitted *against*. Both failed
out of sample, and the two failures do not look alike:

| fitted against | in sample | on two unseen models |
|---|---:|---|
| the model's **logits** | −7.66 % | **loses**, +1.98 % and +8.63 % — ranking inverts |
| the model's **weight statistics** | −5.24 % | −0.10 %, −0.19 % — ranking holds, `t = −0.22`, `p = 0.83` |

The logit fit goes **actively wrong**: first of three where fitted, second of
three everywhere else. The weight-statistics fit merely **stops helping**: the
sign never flips, the magnitude collapses 30–50× into a tie.

- **Fitting against a static property of a system degrades gracefully; fitting
  against its behaviour can reverse.** Weight distributions are more alike across
  checkpoints than logit distributions are.
- **The graceful one is easier to mistake for a result**, precisely because the
  sign holds. `−0.19 %` reads like a small win and is a tie: `t = −0.181`,
  `p = 0.858`, 22 windows better and 18 worse. A point estimate without its
  paired statistic beside it is noise with a decimal point.
- **Report the confidence interval when a margin shrinks**, not just the new
  point estimate. The pooled CI here was `[−1.56 %, +1.27 %]`, which settles the
  question in one line where three perplexity figures did not.

### Before calling a result new, read what it would be new against

A measured win over a *deployed* format says nothing about the *research* it
belongs to. The KL-optimised codebook beat MXFP4 by 7.66 %, which sounds like a
result until you notice MXFP4 is a hardware standard and the thing being claimed
is a learned codebook — a class with its own literature and its own leader.

Read on 2026-08-11: **every learned 4-bit codebook in the field minimises squared
error.** BOF4 via EM on Lloyd's, any4 via k-means, QAM-W via Lloyd-Max on a
circular Gaussian, LO-BCQ via clustering. The strongest of them, BOF4, improves
NF4 by ≈1.2 %. Their contribution is always a better *estimator* of the same
objective; none questions the objective.

That is what made the finding worth having rather than deflating it — this
repository has *measured* that objective pointing the wrong way. But it also
means:

- **Name the right opponent.** For an element-codebook claim that is NF4/BOF4,
  not MXFP4. Beating a hardware format says nothing about beating the research
  leader, and that comparison has not been run.
- **List what is not comparable, in the document.** Different model, different
  block size, different *kind* of scale — BOF4 uses a real-valued absmax, which
  by T38 has no headroom phase at all, so its setup is free of an effect ours has
  to control for.
- **Read the full text, not the abstract.** BOF4's abstract does not say what it
  optimises; the body says MSE and MAE. The abstract would have left the whole
  comparison unresolved.

### Testing a mechanism you proposed yourself

A measured result attracts an explanation, and the explanation is where the next
error goes in — it is written while the number is fresh and nobody checks it,
because the number is right. `WHY_ROTATION_HURTS_2026-08-11.md` is what happened
when one was checked: the mechanism attached to the rotation result was **wrong
by sign**, and finding that out was worth more than the original result.

- **Test it against several mechanisms, not just yours.** Three predictors were
  correlated against the same per-block error change. One candidate cannot lose.
- **Correlate against a shuffled target as well.** All three controls came back
  at |r| < 0.001. Without that column the winner is not evidence, it is a number.
- **Say what "no answer" would look like before running.** The script prints
  "no candidate explains the variation" and "the top two are not separated" as
  first-class outcomes, so an inconclusive run cannot be quietly read as a win.
- **Withdraw in the original document, not just the new one.** The refuted
  hypothesis was published; it is struck through where it was published, with a
  pointer, rather than tidied away.

**And the finding itself is a standing warning.** Rotation reduced total weight
MSE by 3.31 % while perplexity worsened by 8.24 % — the cheap proxy and the real
axis moved in opposite directions on the same weights in the same run. Before
reporting any quantisation comparison in squared error, remember there is a
measured case in this repository where it points the wrong way.

### The metric, once it was chased down

Three mechanisms were proposed for that anomaly and all three were wrong. The
answer, in `METRIC_DISAGREEMENT_2026-08-11.md`, was that nothing was wrong inside
the network:

| instrument | change under rotation |
|---|---:|
| weight L2 | −3.31 % |
| layer-output L2 | −19.94 % |
| final-logit L2 | −46.11 % |
| KL(fp32 ‖ quantised) | **+15.47 %** |
| perplexity | **+7.96 %** |

Every Euclidean instrument said the quantised model was closer to fp32; KL said
it was further away, and `exp(ΔKL)` accounts for 85 % of the perplexity change.
An error costs nothing on tokens that had no probability and a great deal on the
few that did.

Two rules follow, and they are cheap to apply:

- **Report quantisation quality in KL or perplexity, never in squared error.**
  Lloyd-Max minimises squared error, which is why the block line kept finding
  MSE-optimal codebooks that lost — the objective was wrong every time.
- **When a proxy and the real axis disagree, measure the ladder between them.**
  Weights, layer outputs, logits and KL took four short runs and turned an
  unexplained anomaly into a located one. Guessing the mechanism failed three
  times in a row first.

### Context Collection (ALWAYS run first)
```bash
# Current project state — feeds into search queries
OPEN_ISSUES=$(gh issue list --state open --json number,title,labels --limit 20 2>/dev/null || echo "[]")
BROKEN_SPECS=$(grep -c "❌" specs/REGENERATION_REPORT.md 2>/dev/null || echo "0")
TOTAL_SPECS=$(grep -c "✅\|❌" specs/REGENERATION_REPORT.md 2>/dev/null || echo "0")
COMPILE_RATE=$((TOTAL_SPECS > 0 ? (TOTAL_SPECS - BROKEN_SPECS) * 100 / TOTAL_SPECS : 0))
RECENT_ERRORS=$(grep -r "TODO\|FIXME\|HACK" src/ --include="*.zig" 2>/dev/null | head -10)
LAST_COMMITS=$(git log --oneline -5)
ZIG_VERSION=$(zig version 2>/dev/null || echo "0.15.x")

# MU patterns — what errors keep recurring?
MU_PATTERNS=$(cat .ralph/memory/REGRESSION_PATTERNS.md 2>/dev/null | head -30 || echo "none")

# Current priorities from issues
P0_ISSUES=$(echo "$OPEN_ISSUES" | python3 -c "import json,sys; issues=json.load(sys.stdin); p0=[i for i in issues if any('P0' in l.get('name','') for l in i.get('labels',[]))]; [print(f'#{i[\"number\"]}: {i[\"title\"]}') for i in p0]" 2>/dev/null || echo "none")
```

### Search Queries

Based on mode and context, call Perplexity MCP tools.

#### Default scan domains (mode: `scan` or `full`):

1. **Zig ecosystem** — use `perplexity_search`:
   Query: "Zig 0.15 {ZIG_VERSION} new features best practices memory allocator patterns 2025 2026"

2. **FPGA + edge AI** — use `perplexity_search`:
   Query: "FPGA edge AI optimization ternary computing open source synthesis 2025 2026"

3. **Agent architectures** — use `perplexity_research` (deep):
   Query: "self-evolving AI agent architectures autonomous code generation self-improvement loop 2025 2026"

4. **Error-specific** (only if BROKEN_SPECS > 0) — use `perplexity_ask`:
   Query: "Zig {ZIG_VERSION} compilation error {first error from REGRESSION_PATTERNS} fix solution"

5. **MCP extensions** — use `perplexity_search`:
   Query: "Model Context Protocol MCP new servers tools 2025 anthropic"

#### Mode-specific queries:

- `errors` — Focus all queries on current broken specs and compilation errors.
  Read REGENERATION_REPORT.md, extract error messages, search for fixes.
- `zig` — Deep research on Zig language updates.
- `fpga` — Deep research on FPGA synthesis techniques.
- `agents` — Deep research on agent architectures.
- `topic:"<query>"` — Use `perplexity_research` with the exact user query.

### Store scan results

Save raw findings to `.trinity/scholar/`:
```bash
mkdir -p .trinity/scholar
```

Write findings to `.trinity/scholar/scan_YYYYMMDD.json`:
```json
{
  "date": "2026-03-11",
  "mode": "full",
  "context": {
    "compile_rate": 85,
    "broken_specs": 3,
    "open_issues": 8,
    "p0_count": 1
  },
  "findings": [
    {
      "id": 1,
      "domain": "zig",
      "query": "...",
      "summary": "...",
      "citations": ["url1", "url2"],
      "raw_response": "..."
    }
  ]
}
```

## Phase 2: EVAL

Read the latest scan file from `.trinity/scholar/`.

For each finding, evaluate relevance to Trinity:

### Scoring Criteria (0.0 - 1.0):

| Factor | Weight | How to measure |
|--------|--------|----------------|
| **Addresses open issue** | 0.3 | Finding matches an open issue title/description |
| **Fixes broken spec** | 0.3 | Finding addresses a known compilation error |
| **Novel technique** | 0.2 | Not already known in project (check REGRESSION_PATTERNS) |
| **Actionable** | 0.2 | Contains specific code/command/approach to implement |

Use `perplexity_reason` to evaluate complex findings:
Query: "Given this Trinity project context: {context}. Rate the relevance of this finding: {summary}. Score 0-1 and explain."

### Classification:

| Score | Action | Label |
|-------|--------|-------|
| > 0.8 | Create GitHub issue | `research:high` |
| 0.5 - 0.8 | Add to MU Learning DB | `research:medium` |
| < 0.5 | Archive (log only) | `research:low` |

Update scan file with scores:
```json
{
  "findings": [
    {
      "id": 1,
      "relevance": 0.85,
      "classification": "high",
      "reason": "Directly addresses broken specs issue...",
      "action": "create_issue"
    }
  ]
}
```

## Phase 3: APPLY

Read evaluated scan file. For each finding based on classification:

### HIGH (> 0.8) — Create GitHub Issue

```bash
gh issue create \
  --title "research: {concise finding title}" \
  --label "research:high,agent:scholar" \
  --body "## Scholar Finding

**Source:** {citations}
**Relevance:** {score}/1.0
**Domain:** {domain}

### Summary
{finding summary}

### Proposed Action
{specific steps to apply this finding to Trinity}

### Context
- Compile rate: {rate}%
- Related issues: {matching issues}

---
*Auto-generated by Scholar Agent via Perplexity Sonar API*"
```

Add to project board:
```bash
gh project item-add 6 --owner gHashTag --url "https://github.com/gHashTag/trinity/issues/$ISSUE_NUM"
```

### MEDIUM (0.5-0.8) — Enrich MU Learning DB

Append to `.trinity/mu/learning_db.json`:
```bash
python3 -c "
import json, time
db_path = '.trinity/mu/learning_db.json'
try:
    db = json.load(open(db_path))
except: db = {'entries': []}
db['entries'].append({
    'timestamp': int(time.time()),
    'source': 'scholar',
    'domain': '${DOMAIN}',
    'summary': '${SUMMARY}',
    'relevance': ${SCORE},
    'citations': ${CITATIONS},
    'applied': False
})
with open(db_path, 'w') as f:
    json.dump(db, f, indent=2)
print(f'Added to MU Learning DB: {len(db[\"entries\"])} entries')
"
```

### LOW (< 0.5) — Archive

Just log to `.trinity/scholar/archive.log`:
```bash
echo "$(date -Iseconds) | score=${SCORE} | ${DOMAIN} | ${SUMMARY}" >> .trinity/scholar/archive.log
```

## Output Format

Render a report after each run:

```
═══════════════════════════════════════════════════
  🔍 SCHOLAR RESEARCH REPORT — {date}
═══════════════════════════════════════════════════

  📡 SCAN CONTEXT
  ┌──────────────────┬───────────────┐
  │ Compile rate     │ {rate}%       │
  │ Broken specs     │ {N}           │
  │ Open issues      │ {N}           │
  │ MU patterns      │ {N}           │
  │ Mode             │ {mode}        │
  └──────────────────┴───────────────┘

  🔬 FINDINGS ({N} total)
  ┌────┬─────────┬───────┬────────────────────────────────────┐
  │ #  │ Domain  │ Score │ Summary                            │
  ├────┼─────────┼───────┼────────────────────────────────────┤
  │ 1  │ {dom}   │ {S}   │ {one-line summary}                 │
  │ 2  │ {dom}   │ {S}   │ {one-line summary}                 │
  └────┴─────────┴───────┴────────────────────────────────────┘

  📋 ACTIONS TAKEN
  ┌────────────┬─────────────────────────────────────────────┐
  │ Action     │ Details                                     │
  ├────────────┼─────────────────────────────────────────────┤
  │ Issues     │ Created #{N}: {title}                       │
  │ MU entries │ {N} findings added to Learning DB           │
  │ Archived   │ {N} low-relevance findings logged           │
  └────────────┴─────────────────────────────────────────────┘

  📚 CITATIONS
  1. {url} — {what it's about}
  2. {url} — {what it's about}

  ✨ Scholar says: "{contextual insight about findings}"
```

## Mode: report

If $ARGUMENTS is `report`, do NOT run any scan. Instead:

1. Read the latest scan file from `.trinity/scholar/` (most recent `scan_*.json`)
2. Render the Output Format report above using cached data
3. If no scan file exists, output: "No scan data. Run: /scholar scan"

This mode is optimized for bridge-agent / Perplexity queries — fast, no API calls.

## Cron Integration

Scholar can be triggered remotely via bridge-agent:
```
claude:Run /scholar full
claude:Run /scholar errors
claude:Run /scholar report
claude:Run /scholar topic:"ternary neural network quantization"
```

### Automated 24h cycle (via bridge-agent cron):
- **06:00 UTC** — `claude:Run /scholar full` (morning: full scan + eval + apply)
- **18:00 UTC** — `claude:Run /scholar errors` (evening: fix broken specs)

The bridge-agent checks UTC hour and auto-submits scholar jobs.

## Language

For language detection and translations, follow `.claude/skills/_shared/language.md`.
