export const meta = {
  name: 'loop-periodic-self-audit',
  description: 'Periodic self-audit for the trinity-fpga/t27 autonomous loop: infra health, code/data freshness, external-collaboration drift, synthesized into concrete backlog items',
  whenToUse: 'Invoke every few hours during an active /loop run (not every 15-minute cron tick -- that would be wasteful), or on demand when the operator asks for a fresh self-critique. Reads .trinity/loop/STATE.json directly; run from the trinity-fpga repo root.',
  phases: [
    { title: 'Audit', detail: '3 parallel finders: loop-infra health, code/data freshness, external-collaboration drift' },
    { title: 'Synthesize', detail: 'merge findings into concrete backlog items and anomaly entries, or an honest "nothing new"' },
  ],
}

const CONTEXT = `
You are auditing an unattended, cron-driven autonomous loop (trinity-fpga
repo, t27 companion repo) that repairs a Rust-to-Zig compiler and verifies
openXC7 FPGA clock-buffer behavior on real hardware. Its state lives in
.trinity/loop/STATE.json (backlog[], done[], anomalies[], loop{status,halt,
continuity_protocol}), narrated in .trinity/loop/JOURNAL.md, and shown on
.trinity/loop/dashboard.html. A companion tool (src/tri/tri_loopstate_main.zig,
built via 'zig build-exe src/tri/tri_loopstate_main.zig -femit-bin=/tmp/tri-loopstate')
exposes 'status'/'check'/'tripwire' subcommands for mechanical status checks.

This is NOT the loop's first audit -- a prior audit already found and fixed:
untracked loop state, uncommitted compiler patches, a stale/self-contradictory
dashboard, no measure.py tests, a stale cron-job-ID belief, and a self-
referential bug in the tripwire mechanism's own banner-vs-readout parsing.
Your job is to find what's drifted or gone wrong SINCE, not to repeat that
work -- read the current state fresh and report only genuinely new findings.
A clean "nothing new" result is a valid and useful answer; do not manufacture
findings to justify the audit's own existence.
`

phase('Audit')
const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          evidence: { type: 'string', description: 'the exact command output or file content that supports this' },
          severity: { type: 'string', enum: ['info', 'low', 'medium', 'high'] },
          recommended_action: { type: 'string' },
        },
        required: ['title', 'evidence', 'severity', 'recommended_action'],
      },
    },
    nothing_notable: { type: 'boolean', description: 'true if this angle found nothing worth reporting -- do not pad findings to avoid saying so' },
  },
  required: ['findings', 'nothing_notable'],
}

const angles = [
  {
    key: 'infra-health',
    prompt: CONTEXT + `
Angle: LOOP INFRASTRUCTURE HEALTH. This loop's working tree location is NOT
fixed -- it has run from different git worktrees of trinity-fpga across its
lifetime, and a worktree that hosted it before has already been pruned once
(found live by a prior self-audit: this exact file used to hardcode a path
that no longer exists by the time you read this). Do not hardcode a path.
First locate the live working tree yourself: run
'find /Users/playom -maxdepth 5 -path "*/.trinity/loop/STATE.json" 2>/dev/null'
and treat the directory three levels up from whichever STATE.json that finds
(there should be exactly one) as the root for every command below. If more
than one turns up, prefer the one whose STATE.json has the most recent mtime.
Run and inspect (all paths relative to that discovered root):
- 'zig test src/tri/tri_loopstate.zig' -- must be all-green; a failing test here is the highest-severity finding possible.
- jq '.loop, .backlog | length, .anomalies | length' on STATE.json -- does loop.status match what dashboard.html's masthead/banner claims? Read the dashboard's <!-- LOOP_HALT_BANNER_START/END --> region and its readout numbers directly and compare to a fresh 'tripwire' run.
- Do backlog rows' 'blocked_by' reasons still hold, or has something they depend on quietly resolved (check git log / gh pr view / gh issue view for anything a blocked_by reason names)?
- Is JOURNAL.md's most recent entry consistent with STATE.json's current iteration/done count, or has one been updated without the other?
Report concretely, with the actual command output as evidence, not general impressions.`,
  },
  {
    key: 'code-data-freshness',
    prompt: CONTEXT + `
Angle: CODE AND DATA FRESHNESS. Check:
- git log -5 on both trinity-fpga and /Users/playom/t27 (fix/struct-field-brace-nesting branch) -- any commits NOT authored by this loop's own iterations (i.e. by another session/agent) that touch files the loop's backlog also references? That's a collision risk worth flagging.
- git status --short in /Users/playom/t27 -- how many dirty tracked files, and does the count match what STATE.json's B18 (or whichever item tracks this) currently claims?
- df -h / on this machine -- is free space trending toward either tripwire threshold (2 GiB halt, 5 GiB warn) again?
- Any TODO, FIXME, or explicitly "not attempted" note in recent JOURNAL.md entries or docs/COMPILER_BUGS.md (t27) that names a concrete next step nobody has picked up?
Report concretely, with real command output as evidence.`,
  },
  {
    key: 'external-collaboration',
    prompt: CONTEXT + `
Angle: EXTERNAL COLLABORATION DRIFT. For each of these, run 'gh api repos/openXC7/nextpnr-xilinx/issues/<n>/comments' or 'gh pr view <n> --repo <owner>/<repo> --json state,updatedAt,reviewDecision,statusCheckRollup,comments' and report anything NEWER than the timestamp already recorded in STATE.json for it:
- openXC7/nextpnr-xilinx issues #149, #172
- openXC7/nextpnr-xilinx PRs #120, #171
- gHashTag/trinity PR #877
Also check 'gh issue list --repo gHashTag/t27 --search "is:open" --limit 5 --json number,title,createdAt' for anything opened recently that looks related to this loop's own work (compiler bugs, measure.py, loop infra) that the loop did not itself create.
Report exact timestamps and whether each is newer than what's on file -- do not just say "checked, no change" without showing the comparison.`,
  },
]

const results = await parallel(angles.map(a => () =>
  agent(a.prompt, { label: `audit:${a.key}`, phase: 'Audit', schema: FINDING_SCHEMA })
))
const valid = results.filter(Boolean)
log(`${valid.length}/3 audit angles reported back`)

const allFindings = valid.flatMap((r, i) => (r.findings || []).map(f => ({ ...f, angle: angles[i].key })))
log(`${allFindings.length} raw findings before synthesis`)

phase('Synthesize')
let synthesis = { new_backlog_items: [], new_anomalies: [], summary: 'No findings to synthesize -- all three audit angles reported nothing notable.' }
if (allFindings.length > 0) {
  synthesis = await agent(
    CONTEXT + `\n\nThree audit angles reported these findings:\n\n${JSON.stringify(allFindings, null, 2)}\n\nSynthesize into: (a) concrete new backlog items STATE.json's backlog[] array should gain (id left blank, a human/agent will assign the next Bnn), each with a one-line 'what', a priority hint (lower = more urgent, relative to the fact that this loop's existing backlog runs roughly 6-30), and whether it needs an operator decision; (b) new anomalies[] entries for anything that represents a genuine self-correction or drift, not just routine backlog work; (c) a short summary. Merge duplicate/overlapping findings from different angles into one item rather than listing both. If a finding is low-severity and already has an obvious one-line fix, you may say so as the recommended action rather than inventing a backlog item for something trivial.`,
    {
      label: 'synthesize-findings',
      phase: 'Synthesize',
      schema: {
        type: 'object',
        properties: {
          new_backlog_items: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                what: { type: 'string' },
                prio_hint: { type: 'number' },
                needs_operator_decision: { type: 'boolean' },
              },
              required: ['what', 'prio_hint', 'needs_operator_decision'],
            },
          },
          new_anomalies: {
            type: 'array',
            items: {
              type: 'object',
              properties: { what: { type: 'string' }, impact: { type: 'string' } },
              required: ['what', 'impact'],
            },
          },
          summary: { type: 'string' },
        },
        required: ['new_backlog_items', 'new_anomalies', 'summary'],
      },
    }
  )
}

return { raw_findings: allFindings, synthesis }
