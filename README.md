# prompt-lib

Versioned source for everything in `~/.claude/` — agents, skills, hooks, rules, output styles, MCP servers, project templates — plus a TUI installer and two services that extend Claude Code into a multi-agent system.

## Functionality

| Need | How this repo handles it |
|---|---|
| Domain expertise on demand | 14 specialist subagents (`@dotnet-architect`, `@python-tester`, `@react-architect`, `@tanstack-architect`, `@frontend-css`, `@unity-architect`, `@code-plan-verifier`, `@gitignore-auditor`, `@secret-auditor`, `@init-project`, `@load-project`, …) auto-invoked when the task matches their description |
| Repetitive workflows (commit, PR, review, scaffold) | 17 slash-command skills under `global/skills/` — `/git`, `/commit`, `/pr`, `/review`, `/react-init`, `/react-review`, `/react-test`, `/react-perf`, `/react-safe`, `/css`, `/lovable-cleanup`, `/skill-create`, `/executing-plans`, `/finishing-a-development-branch`, `/using-git-worktrees`, `/design`, `/ui-component` |
| Loading project context on session start | `SessionStart` hook detects whether the cwd has a `CLAUDE.md`; if yes, invokes `@load-project`; if no, offers to scaffold one from a template (`.NET`, Python, frontend, monorepo, Unity, generic) |
| Always-on context bloat | Conditional rules in `global/rules/` (`csharp.md`, `typescript.md`, `react.md`, `tests.md`) load only when Claude touches a matching file |
| Response-mode switching | Four output styles — `concise`, `technical`, `review`, `architect` — picked per session via `/output-style` |
| External tool integrations | Eight pre-wired MCP servers: `context7`, `github`, `figma`, `playwright`, `azure-devops`, `supabase`, `obsidian`, `docker` (env vars resolved via `${VAR}` substitution) |
| Multi-machine setup / drift detection | Interactive TUI wizard at `setup/apply.py` — deploy, init env vars, doctor (drift report), restore from backup, local project scaffold, optional companion tools |
| Cross-agent delegation (Claude ↔ Gemini) | [`services/a2a-bridge`](services/a2a-bridge/) — A2A protocol v1.0.0 implementation, Python 3.13 + FastAPI, 199 tests passing |
| Autonomous PR review | [`services/orchestrator`](services/orchestrator/) — daemon that watches a GitHub repo, dispatches each PR to a peer Claude agent over the A2A bridge, posts the review back via `gh`, persists state to SQLite, pushes phone notifications via ntfy.sh, ships with a Textual dashboard |
| Spec-driven feature work | `specs/` holds spec-kit feature trees (spec, plan, research, data-model, contracts, tasks, quickstart) — `001-a2a-bridge` and `002-agent-orchestrator` |
| Tool-call safety | `PreToolUse` hooks (`command_guard.py`, `file_write_guard.py`) and `PostToolUse` audit (`write_audit.py`) intercept risky operations |
| Authoring new skills | `/skill-create` — scaffolds, tests, and refines new slash commands |

## Layout

```
prompt-lib/
├── global/              ← deploy target: ~/.claude/
│   ├── settings.json    ← MCP servers, hooks, theme, model
│   ├── CLAUDE.md        ← always-loaded global behaviour
│   ├── agents/          ← @-invocable specialist subagents
│   ├── skills/          ← /-invocable slash commands
│   ├── hooks/           ← SessionStart / PreToolUse / Stop scripts
│   ├── rules/           ← file-pattern-conditional rules
│   ├── output-styles/   ← response formatting profiles
│   └── project-templates/  ← templates used by @init-project
├── setup/               ← TUI installer (apply.py)
├── services/
│   ├── a2a-bridge/      ← A2A protocol bridge
│   └── orchestrator/    ← PR-review daemon
└── specs/               ← spec-kit feature trees
```

## Apply changes

```bash
python setup/apply.py
```

First run auto-installs `rich` + `questionary`. After applying, restart Claude Code.

Fallback (non-interactive): `bash setup/tools/apply-global-claude-settings.sh`.

## Further reading

### Deep documentation (`docs/`)

- [`docs/README.md`](docs/README.md) — index + reading order
- [`docs/architecture.md`](docs/architecture.md) — 5-step session boot; how agents, skills, MCP tools, hooks, and rules fit together
- [`docs/settings.md`](docs/settings.md) — every field in `global/settings.json` explained (model, permissions, MCP servers, hooks)
- [`docs/agents.md`](docs/agents.md) — every subagent: purpose, tools, when triggered, composition partners
- [`docs/skills.md`](docs/skills.md) — every slash command: trigger, behaviour, allowed tools
- [`docs/hooks.md`](docs/hooks.md) — `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop` scripts and what they protect
- [`docs/rules-output-styles.md`](docs/rules-output-styles.md) — file-pattern conditional rules, response styles, project-init templates
- [`docs/workflows.md`](docs/workflows.md) — multi-agent recipes: spec-kit → worktree → plan → implement → verify → review → PR
- [`docs/parallel-isolation.md`](docs/parallel-isolation.md) — when concurrent subagents must run in isolated git worktrees, why, and how
- [`docs/speckit.md`](docs/speckit.md) — spec-kit configuration in this repo: constitution, gates, slash commands, templates, delegation roster, phase-status rule, git-extension override
- [`docs/services.md`](docs/services.md) — `a2a-bridge` and `orchestrator` daemons in detail
- [`docs/learning.md`](docs/learning.md) — 5-day learning path, mental shortcuts, debugging surprises

### Other references

- [`global/README.md`](global/README.md) — full Claude Code behaviour walkthrough (how agents trigger, how skills resolve, how overlapping tools are picked)
- [`global/MCP.md`](global/MCP.md) — MCP server setup and token configuration
- [`setup/README.md`](setup/README.md) — installer modes
- [`services/a2a-bridge/README.md`](services/a2a-bridge/README.md), [`services/orchestrator/README.md`](services/orchestrator/README.md) — service docs
- [`specs/`](specs/) — spec-kit feature trees
