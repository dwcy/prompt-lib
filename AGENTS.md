# AGENTS.md

Cross-tool agent guidance for this repo. Authoritative project rules live in [`CLAUDE.md`](./CLAUDE.md) — read it first.

## What this repo is

Personal Claude Code configuration library. Source of truth for everything in `~/.claude/`. Edit here, deploy, restart Claude Code.

Deploy with the TUI wizard (preferred) or the bash script:

```bash
python setup/settings-configurator-ui.py          # interactive wizard
bash setup/tools/apply-global-claude-settings.sh   # non-interactive fallback
```

This is **not** an application. It is a library of agents, hooks, skills, rules, settings, and project templates for Claude Code (and, going forward, other compatible harnesses).

## Where agent-relevant files live

| Path | Purpose |
|------|---------|
| [`CLAUDE.md`](./CLAUDE.md) | Project-level instructions (always loaded by Claude Code). |
| [`global/CLAUDE.md`](./global/CLAUDE.md) | Deployed to `~/.claude/CLAUDE.md` — global behavioral rules. |
| [`global/agents/`](./global/agents/) | Subagent definitions — 24 specialists (`@dotnet-architect`, `@python-architect`, `@requirements-analyst`, `@api-designer`, `@db-architect`, `@ux-analyst`, `@git-repo-analyst`, …). Roster: [`docs/agents.md`](./docs/agents.md). |
| [`global/skills/`](./global/skills/) | Slash command definitions (`/git`, `/review`, `/orchestrate`, etc.). |
| [`global/hooks/`](./global/hooks/) | SessionStart / PreToolUse / PostToolUse / Stop / SessionEnd scripts. Honor `PROMPTLIB_DISABLED_HOOKS` and `PROMPTLIB_HOOK_PROFILE=off` for runtime gating (see `_gate.py`). |
| [`global/rules/`](./global/rules/) | File-pattern-conditional rules (loaded only when matching paths are touched). |
| [`global/output-styles/`](./global/output-styles/) | Response formatting profiles. |
| [`global/project-templates/`](./global/project-templates/) | CLAUDE.md scaffolds + the cross-platform `run` launcher used by `@init-project`. |
| [`global/statusline.py`](./global/statusline.py) | Terminal statusline; segments configured in `global/statusline-segments.json`. |
| [`global/codex/`](./global/codex/) | Curated Codex-compatible skills, references, project templates, and conversion manifest. |
| [`.specify/memory/agents.md`](./.specify/memory/agents.md) | Spec-kit subagent roster — drives `/speckit-plan` and `/speckit-tasks` delegation. |
| [`specs/`](./specs/) | Feature specifications (Spec Kit format). |
| [`setup/`](./setup/) | Deploy wizard (`settings-configurator-ui.py`), the cabal TUI package (`setup/src/cabal/`), and tests. |

## Tool-specific notes

- **Claude Code**: reads `CLAUDE.md` automatically. The deploy wizard installs everything from `global/` into `~/.claude/`.
- **Codex / Cursor / OpenCode** (future): start from `CLAUDE.md`. Hooks and skills under `global/` are Claude-Code-specific; treat them as data, not instructions.

## Conventions worth knowing

- Branches use `<type>/<topic>` naming. Never commit on `main` / `master` (commits are driven through the `git-identity` wrapper per `CLAUDE.md`).
- Commits use `<type>: <subject>` where type ∈ `feat | task | fix | refactor | test | docs`. Imperative mood, ≤72 chars.
- Hooks are stdlib-only Python scripts that read JSON from stdin; exit 0 = allow, exit 2 = block.
- New env vars use the `PROMPTLIB_` prefix.
