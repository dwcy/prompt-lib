# Git policy — tags, policy editing & recovery

Reference detail for the `git-identity` wrapper. The behavioral rules live in `~/.claude/CLAUDE.md` (*Git commits*); this file holds the mechanics that don't need to sit in always-loaded context.

All commit-policy values live in `~/.claude/git-policy.json`. If it doesn't exist, the wrapper falls back to `~/.claude/git/git-policy.default.json` (seeded by the apply script) and then to its built-in defaults.

## Tags

`git tag` is gated by policy and **off by default**. Edit `~/.claude/git-policy.json`:

```json
"tags": { "agent_may_tag": false, "auto_push": false }
```

- `agent_may_tag: false` (default) — the wrapper's `tag` subcommand refuses. Don't fall back to raw `git tag`; ask first.
- `agent_may_tag: true` — wrapper creates annotated tags only: `python ~/.claude/scripts/git-identity.py tag v1.0.0 -m "release notes"`.
- `auto_push: false` (default) — tags stay local until pushed manually. Never `git push --tags` automatically.

## Editing the policy

Two equivalent ways to change values:

- Edit `~/.claude/git-policy.json` in your editor.
- `python ~/.claude/scripts/git-identity.py policy set --agent-email "you@example.com"` (or `--agent-name`, `--agent-may-tag true|false`, `--auto-push true|false`).
- `python ~/.claude/scripts/git-identity.py policy add-type wip` / `policy remove-type docs` to change the allowed-type list.
- `python ~/.claude/scripts/git-identity.py policy show` to see current values + source file.

## Recovery

If a commit crashes mid-flight and `.git/config --local` is stuck on agent identity, run `/git-restore-identity` (or `python ~/.claude/scripts/git-identity.py restore`) in the affected repo.
