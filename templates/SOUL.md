# SOUL.md — Agent Soul Binding

**Law**: Every container/agent MUST have `SOUL.md` at root.

---

## Agent Identity

| Field | Value |
|-------|--------|
| **Agent Type** | Ralph / Mu / Scholar / Copywright / Oracle / Swarm / Custom |
| **Agent ID** | `[agent-id]` |
| **Bound Issue** | `#[issue_number]` |

---

## Mission

```markdown
[Mission statement bound to the issue]

Example: "Fix bug #505: Session soul_file field missing from CREATE TABLE"
```

---

## Allowed Commands

```markdown
Commands this agent is permitted to execute:

- `tri dev scan` — Read issues + experience
- `tri dev pick --smart` — Priority + MNL selection
- `tri spec create` — Create .tri spec from experience
- `tri gen` — Generate .t27 + .zig from .tri
- `tri test` — Compare outputs, verify
- `tri verdict --toxic` — Toxic verdict with MNL
- `tri experience save` — Save episode + learnings
- `tri git commit` — Commit changes
- `tri loop decide` — Continue or stop

Command execution MUST follow CLAUDE.md law.
```

---

## Stop Conditions

```markdown
Conditions that cause this agent to stop:

1. [STOP_CONDITION_1]
2. [STOP_CONDITION_2]
3. [STOP_CONDITION_3]

Example:
- Task completed successfully (all 8 steps finished)
- 3 consecutive failures on same step (toxic pattern detected)
- Manual stop signal received
- Issue closed by user
```

---

## Reporting Format

```markdown
How this agent reports progress:

**Protocol v2 Comment Format:**
- `🔍 [RESEARCH] Step 1/8 — Scanning issues...`
- `📜 [SPEC] Reused nearest template from .trinity/experience/`
- `⚙️ [CODEGEN] .tri -> .zig via tri gen`
- `🧪 [TEST] 6/7 tests passing`
- `☣️ [VERDICT] Past: 3/7. Now: 7/7`
- `✅ [DONE] Build clean. Commit pushed`

All significant steps MUST be reflected as GitHub issue comments.
```

---

## References

- **CLAUDE.md** — Trinity project laws and rules
- **AGENTS.md** — Agent swarm documentation
- **Protocol v2** — Comment formatting specification

---

## State Machine

```
IDLE → ACTIVE → DIRTY → TESTED → COMMITTED → SHIPPED

Transitions follow Rigid Process Framework.
See AGENTS.md for detailed state definitions.
```

---

## Session Binding

```json
{
  "issue_number": 505,
  "agent_id": "ralph-505-a1",
  "soul_file": ".trinity/souls/issue-505-ralph-505-a1/SOUL.md",
  "session_id": "sess_123",
  "railway_service_id": "svc_abc",
  "deployment_id": "dep_xyz",
  "experience_file": ".trinity/experience/issue-505-run-001.jsonl",
  "status": "ACTIVE"
}
```

This binding is registered in `.trinity/issue_bindings.json`.

---

**Created by**: `tri agent spawn <issue_number>`
**Active until**: Issue closed or agent stopped
