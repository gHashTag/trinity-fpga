# Git Workflow

## Commit Format
- `feat(<module>): <description>` — new feature
- `fix(<module>): <description>` — bug fix
- `refactor(<module>): <description>` — refactoring
- `docs(<module>): <description>` — documentation
- `chore(<module>): <description>` — maintenance

**IMPORTANT**: All commits MUST be bilingual — English + Russian. Use format:
```
<English description>

Русский перевод описания изменений.
```

## Rules
- Pipeline auto-commits generated code via Link 18 (git)
- Manual commits for: specs, config, pipeline infra, rules, core library
- Always push after commit
- Never force-push to main without user approval
- Large files (>1MB) must be in .gitignore — check before committing
