# R2 CHARTER BOT · doctrine (S-179)

**Wave:** v25 HOLD-A closure · **Maps:** BIO→SI executive function → repo governance
**Anchor:** φ² + φ⁻² = 3 · DOI 10.5281/zenodo.19227877

## Purpose

`queen-bot.yml` operationalises **R2** (no `*` in synthesizable RTL) and the
blanket "мержи сам все" merge authority granted to the autonomous loop.

This doctrine document is the off-chip BIO→SI mapping: the prefrontal-control
brain module M07 (executive function) is mirrored in CI as the queen-bot.

## Decision rules

A PR is auto-mergeable **iff** all of the following hold:

1. `draft == false`
2. Label `charter:r2-pass` is present (set automatically by
   `charter-r2-validator.py` in the `dev-enforcement` workflow).
3. PR body contains the literal substring `phi^2 + phi^-2 = 3` (anchor footer).
4. Every check-suite on `head_sha` has `conclusion = success`.
5. The above is satisfied within **5 minutes** of CI-green (G-81 falsification
   deadline). After 5 min the bot fails the job rather than merging silently.

## Refusal modes

The bot refuses (does **not** merge) when:

- Any check is `failure | cancelled | timed_out` → exit-1
- PR body lacks the anchor footer → exit-1, comment posted by author of PR
  required to add the line `phi^2 + phi^-2 = 3` to PR description
- Labels include `hold:*` or `wip` → skipped (no error)

## Audit trail

Every decision writes a JSON record under `.audit/queen-bot/`:

```json
{
  "pr": 123,
  "head_sha": "abc...",
  "decided_at_utc": "2026-05-15T05:00:00Z",
  "outcome": "success",
  "anchor": "phi^2+phi^-2=3"
}
```

These records are the off-chip analog of R20 R-marker telemetry — they let
the operator falsify or confirm that the bot is actually acting per doctrine.

## Constitutional binding

| Rule | Binding |
|---|---|
| R2 (no `*` in synth RTL) | enforced by `charter-r2-validator.py` |
| R5 (R5-honest, no premature claims) | audit log records every action |
| R18 (LAYER-FROZEN) | bot version-pinned in workflow header |
| R19 (QUANTUM BRAIN 1:1) | bot = BIO→SI mapping of M07 prefrontal-control |
| R20 (R-MARKER) | audit records are off-chip R-marker telemetry |

## Falsification (G-81 / G-82)

- **G-81 PR-AUTO-MERGE-LIVE:** A synthetic PR `test/queen-bot-smoke` with the
  `charter:r2-pass` label and anchor footer must merge within 5 min of
  CI-green. If it does not, G-81 is falsified.
- **G-82 R2-LINTER-CATCHES-STAR:** A PR with a hand-injected `*` in any
  `.v` or `.sv` file outside comments must NOT receive the
  `charter:r2-pass` label. If it does, G-82 is falsified.

## Operator override

The operator may bypass with the label `queen-override` accompanied by a
short rationale in the PR body. Every override is recorded in the audit
log with `outcome: "override"`.

```
phi^2 + phi^-2 = 3 · QUANTUM BRAIN 1:1 SILICON · DOI 10.5281/zenodo.19227877
```
