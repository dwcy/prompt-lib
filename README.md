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
| Multi-machine setup / drift detection | Interactive TUI wizard at `setup/settings-configurator-ui.py` — deploy, init env vars, doctor (drift report), restore from backup, local project scaffold, optional companion tools |
| Cross-agent delegation (Claude ↔ Gemini) | [`services/a2a-bridge`](services/a2a-bridge/) — A2A protocol v1.0.0 implementation, Python 3.13 + FastAPI, 199 tests passing |
| Autonomous PR review | [`services/orchestrator`](services/orchestrator/) — daemon that watches a GitHub repo, dispatches each PR to a peer Claude agent over the A2A bridge, posts the review back via `gh`, persists state to SQLite, pushes phone notifications via ntfy.sh, ships with a Textual dashboard |
| Spec-driven feature work | `specs/` holds spec-kit feature trees (spec, plan, research, data-model, contracts, tasks, quickstart) — `001-a2a-bridge` and `002-agent-orchestrator` |
| Tool-call safety | `PreToolUse` hooks (`command_guard.py`, `file_write_guard.py`) and `PostToolUse` audit (`write_audit.py`) intercept risky operations |
| Authoring new skills | `/skill-create` — scaffolds, tests, and refines new slash commands |

## Slash commands

Every command available in this project, grouped by purpose. Source links point at the SKILL/command file; docs links point at the relevant section in [`docs/`](docs/).

### Git workflow

| Command | When to use | Links |
|---|---|---|
| `/git` | Full git workflow — branch safety, conventional commits, agent authorship, push guard | [src](global/skills/git.md) · [docs](docs/skills.md#git) |
| `/commit` | Quick conventional commit without the full safety machinery — fixups inside a feature branch | [src](global/skills/commit.md) · [docs](docs/skills.md#commit) |
| `/pr` | Draft a PR title + description from branch diffs, then create it with `gh pr create` | [src](global/skills/pr.md) · [docs](docs/skills.md#pr) |
| `/review` | Structured branch review against `main` — Critical / Warning / Suggestion findings | [src](global/skills/review.md) · [docs](docs/skills.md#review) |
| `/finishing-a-development-branch` | End-of-feature checklist — runs tests, builds, commits, offers PR/push | [src](global/skills/finishing-a-development-branch.md) · [docs](docs/skills.md#finishing-a-development-branch) |
| `/using-git-worktrees` | Create/list/remove/prune git worktrees for parallel Claude Code sessions | [src](global/skills/using-git-worktrees.md) · [docs](docs/parallel-isolation.md) |
| `/standup` | Generate a standup summary from recent git log | [src](.claude/skills/standup.md) · [docs](docs/skills.md) |

### Planning & implementation

| Command | When to use | Links |
|---|---|---|
| `/plan` | Plan a non-trivial feature — classify, scope, contract (full-stack), task breakdown, spawn parallel agents with worktree isolation | [src](.claude/commands/plan.md) · [docs](docs/workflows.md) |
| `/executing-plans` | Execute a written `tasks.md` plan with review checkpoints between phases | [src](global/skills/executing-plans.md) · [docs](docs/workflows.md#workflow-1--spec-kit-feature-single-session) |
| `/adr` | Create a numbered Architecture Decision Record under `docs/adr/` | [src](.claude/commands/adr.md) · [docs](docs/adr/) |

### Spec-kit feature flow

| Command | When to use | Links |
|---|---|---|
| `/speckit-constitution` | Create or amend `.specify/memory/constitution.md` (principles, gates) | [docs](docs/speckit.md#constitution--v110) |
| `/speckit-specify` | Generate `spec.md` from a natural-language feature description | [docs](docs/speckit.md#slash-commands) |
| `/speckit-clarify` | Resolve `NEEDS CLARIFICATION` markers in `spec.md` via up-to-5 targeted questions | [docs](docs/speckit.md#slash-commands) |
| `/speckit-plan` | Produce `plan.md` + Phase 0 design artifacts; must clear Constitution Check gates | [docs](docs/speckit.md#constitution-check-gates-every-speckit-plan-run) |
| `/speckit-tasks` | Generate `tasks.md` with `Owner: @<agent>` + Phase Status + `Parallel: yes` markers | [docs](docs/speckit.md#phase-status-convention-local-override) |
| `/speckit-analyze` | Non-destructive cross-artifact consistency check across spec/plan/tasks | [docs](docs/speckit.md#slash-commands) |
| `/speckit-checklist` | Generate a feature-specific QA checklist | [docs](docs/speckit.md#slash-commands) |
| `/speckit-implement` | Execute `tasks.md` task-by-task, dispatching to named owners (with worktree isolation for `Parallel: yes`) | [docs](docs/speckit.md#how-it-behaves-end-to-end) |
| `/speckit-taskstoissues` | Convert `tasks.md` into ordered GitHub issues via `gh` | [docs](docs/speckit.md#slash-commands) |
| `/speckit-git-*` | **Do not use** — these auto-execute git commands without the `/git` safety machinery. Driven from the `/git` skill instead per global rules | [docs](docs/speckit.md#git-extension--installed-but-overridden) |

### Frontend / React

| Command | When to use | Links |
|---|---|---|
| `/react-init` | Scaffold a full React 2025 project — Vite + TS + Zustand + TanStack + Biome + Tailwind v4 + Zod + MUI Icons | [src](global/skills/react-init.md) · [docs](docs/skills.md#react-init) |
| `/react-review` | Code-quality review of a React file/feature — Critical / Warning / Suggestion | [src](global/skills/react-review.md) · [docs](docs/skills.md#react-review) |
| `/react-test` | Scaffold or review Vitest + RTL tests for a component, hook, or feature | [src](global/skills/react-test.md) · [docs](docs/skills.md#react-test) |
| `/react-safe` | Audit a React file for async correctness, error handling, security gaps | [src](global/skills/react-safe.md) · [docs](docs/skills.md#react-safe) |
| `/react-perf` | Performance audit — re-renders, memoisation, bundle size, lazy-load opportunities | [src](global/skills/react-perf.md) · [docs](docs/skills.md#react-perf) |
| `/css` | `scaffold` for `globals.css`, or `<ComponentName>` for `<Name>.module.css` next to the component | [src](global/skills/css.md) · [docs](docs/skills.md#css) |
| `/ui-component` | Build a UI component on demand — design-language compliance, Preview, semantic HTML, Zustand+Zod forms | [src](global/skills/ui-component.md) · [docs](docs/skills.md#ui-component) |
| `/design` | Load the Premium Digital Agency 2.0 design system into context before styling decisions | [src](global/skills/design.md) · [docs](docs/skills.md#design) |
| `/lovable-cleanup` | Strip all Lovable / GPTEngineer scaffolding from a project | [src](global/skills/lovable-cleanup.md) · [docs](docs/skills.md#lovable-cleanup) |

### .NET

| Command | When to use | Links |
|---|---|---|
| `/dotnet-class` | Create or refactor a .NET class following Clean Architecture conventions | [src](.claude/commands/dotnet-class.md) · [docs](docs/agents.md#dotnet-architect) |
| `/dotnet-test` | Create or refactor a .NET integration test with TestContainers | [src](.claude/commands/dotnet-test.md) · [docs](docs/agents.md#dotnet-tester) |

### Documentation & memory

| Command | When to use | Links |
|---|---|---|
| `/docs` | Generate a `/docs` folder for a project — index + architecture + per-component reference + workflows + learning path | [src](global/skills/docs.md) · [docs](docs/README.md) |
| `/self-improvement` | Maintain project memory (lessons / mistakes / preferences / evals); stale-detect and remove obsolete entries | [src](.claude/skills/self-improvement/SKILL.md) · [docs](docs/skills.md#self-improvement-project-local) |
| `/skill-create` | Design, write, test, and refine a new skill — scaffolds the Agent Skill folder with `scripts/`, `references/`, `assets/` | [src](global/skills/skill-create.md) · [docs](docs/skills.md#skill-create) |

### Meta / safety

| Command | When to use | Links |
|---|---|---|
| `/review-conflicts` | Detect overlapping agent / skill descriptions that would cause routing collisions | [src](.claude/commands/review-conflicts.md) · [docs](docs/architecture.md#5-ready--how-claude-picks-a-tool) |
| `/prompt-injection-guard` | Scan staged content for prompt-injection patterns before commit | [src](.claude/commands/prompt-injection-guard.md) · [docs](docs/hooks.md) |
| `/xlsx` | Read, edit, and recalculate Excel workbooks via LibreOffice + python-openpyxl | [src](.claude/skills/xlsx.md) · [docs](docs/skills.md) |

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
├── setup/               ← TUI installer (settings-configurator-ui.py)
├── services/
│   ├── a2a-bridge/      ← A2A protocol bridge
│   └── orchestrator/    ← PR-review daemon
└── specs/               ← spec-kit feature trees
```

## Apply changes

```bash
python setup/settings-configurator-ui.py
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
