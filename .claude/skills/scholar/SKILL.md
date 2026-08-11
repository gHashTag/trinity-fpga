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
