# prompt-lib

Versioned source for everything in `~/.claude/` — agents, skills, hooks, rules, output styles, MCP servers, project templates — plus a TUI installer and two services that extend Claude Code into a multi-agent system.

> **Visual tour:** open [`docs/infographic.html`](docs/infographic.html) in a browser — single A4 landscape sheet, no scrolling, every feature at a glance. The longer scrollable variant is at [`docs/infographic-v1.html`](docs/infographic-v1.html).

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
| Install without cloning | `/plugin marketplace add dwcy/prompt-lib` + `/plugin install prompt-lib@prompt-lib` ships skills, agents, hooks, MCP servers, and output styles as a Claude Code plugin. The apply-script path remains the way to get the full setup (global `CLAUDE.md`, rules, permissions, theme). See [`docs/plugin-install.md`](docs/plugin-install.md). |
| Cross-agent delegation (Claude ↔ Gemini) | [`services/a2a-bridge`](services/a2a-bridge/) — A2A protocol v1.0.0 implementation, Python 3.13 + FastAPI, 199 tests passing |
| Autonomous PR review | [`services/orchestrator`](services/orchestrator/) — daemon that watches a GitHub repo, dispatches each PR to a peer Claude agent over the A2A bridge, posts the review back via `gh`, persists state to SQLite, pushes phone notifications via ntfy.sh, ships with a Textual dashboard |
| Spec-driven feature work | `specs/` holds spec-kit feature trees (spec, plan, research, data-model, contracts, tasks, quickstart) — `001-a2a-bridge`, `002-agent-orchestrator`, `003-issue-triage`, `004-github-plugin` |
| Tool-call safety | `PreToolUse` hooks (`command_guard.py`, `file_write_guard.py`) and `PostToolUse` audit (`write_audit.py`) intercept risky operations |
| Authoring new skills | `/skill-create` — scaffolds, tests, and refines new slash commands |

## Statusline

The "tile bar" Claude Code renders at the bottom of the terminal. Script: [`global/statusline.py`](global/statusline.py). Wired up via `statusLine` in [`global/settings.json`](global/settings.json). Two rows — row 1 is session state from the stdin JSON snapshot Claude Code passes per turn, row 2 is workspace state from cheap git + filesystem probes.

```
✦ Opus 4.7  │  ◐ 34%  │  💰 $0.42 · 12m  │  Δ +142 -38  │  📝 explanatory  │  ⏳ 5h:78%  │  ⊙ C:/projects/prompt-lib
⎇ 005-cabal-tools-polish  │  ↑3 ↓1  │  ±5f  │  ⚑ 2  │  🐳 docker  │  ✓ 47  │  🎯 P3 8/14  │  🤖 3 · 🛠 14
```

### Row 1 — session state (from stdin JSON, zero I/O)

| Segment | Source | What it shows | Hides when | Color logic |
|---|---|---|---|---|
| `✦ <model>` | `model.display_name` | Active model name (e.g. Opus 4.7) | never | cyan |
| `◐ <pct>%` / `⚠ 200k+` | `context_window.used_percentage`, `exceeds_200k_tokens` | % of the 200k context window used; red warning replaces it when the model has exceeded 200k input tokens | never | green <50% → yellow <75% → orange <90% → red ≥90%; red flash when over 200k |
| `💰 $<usd> · <duration>` | `total_cost_usd`, `total_duration_ms` | Session cost so far + wall-clock duration | cost field missing | green <$1 → yellow <$3 → orange <$10 → red ≥$10 |
| `Δ +<a> -<r>` | `total_lines_added`, `total_lines_removed` | Lines added / removed across all edits this session | both counters 0 | adds green, removes red |
| `📝 <style>` | `output_style.name` | Active output style — reminds you a non-default style is biasing responses | style is `default` | cyan |
| `⏳ 5h:<%>` `7d:<%>` | `five_hour`, `seven_day` | % quota remaining before 5-hour / 7-day rate limits hit | both quotas have >90% headroom (nothing to worry about) | green >50% → yellow >25% → red ≤25% |
| `⊙ <cwd>` | `workspace.current_dir` | Project path rendered as a clickable VS Code link (OSC 8 hyperlink → `vscode://file/<path>`). **Ctrl+Click to open** in Windows Terminal | cwd missing | violet |

### Row 2 — workspace state (git + filesystem, 1s timeout-guarded)

| Segment | Source | What it shows | Hides when | Color logic |
|---|---|---|---|---|
| `⎇ <branch>` (with `🌳 worktree:` prefix) | `git branch --show-current` + `git rev-parse --git-dir --git-common-dir` | Current branch; worktree prefix appears when this checkout is a git worktree (not the main checkout) | not a git repo | gold; worktree prefix green |
| `↑<a> ↓<b>` or `↕ sync` | `git rev-list --count --left-right @{u}...HEAD` | Commits ahead of / behind upstream — `↕ sync` when both are 0 | branch has no upstream | ahead green, behind orange |
| `±<n>f` | `git status --porcelain` | Number of dirty files (staged + unstaged) | working tree is clean | yellow |
| `⚑ <n>` | `git stash list` | Stash count | zero stashes | violet |
| `🐳 docker` | filesystem probe — `Dockerfile`, `docker-compose.{yml,yaml}`, `compose.{yml,yaml}` | Whether the project is dockerized | never (shows `🐳 N/A` when absent) | bright cyan when present, gray when absent |
| `✓ <n>` / `✗ <f>/<n>` / `◑ <pct>%cov` | First detector that matches: .NET `TestResults/*.trx` → pytest `.pytest_cache/v/cache/lastfailed`+`nodeids` → Jest/Vitest `coverage/coverage-summary.json` → Playwright `test-results/results.json` or `playwright-report/results.json` | Pass count, failure ratio, or coverage % from the most recent test run | no detector matches (shows `✓ N/A`) | green pass, red fail, yellow low coverage |
| `🎯 P<n> <m>/<t>` or `🎯 ✓ all` | Parses `specs/<branch>/tasks.md` for the first non-`✅` `**Status**: …(M/N — T###–T###)` line | Active speckit phase + M/N task progress; `✓ all` when every phase is complete | not on a `NNN-feature-name` branch, or no `tasks.md` | gold mid-flow, green when complete |
| `🤖 <a> · 🛠 <t>` | `~/.claude/.session_state.json` written by the `PostToolUse` hook | Agents dispatched · tools called this session — proves work is happening even when output is quiet | hook hasn't fired yet, or `session_id` doesn't match | agents violet, tools gray |

### How it works

- **Snapshot, not live.** Claude Code invokes the statusline command once per turn boundary and passes session state on stdin per the [statusline contract](https://docs.claude.com/en/docs/claude-code/statusline). There is no streaming or refresh — segments update on the next turn.
- **Multi-row layout.** Every `\n` printed becomes a new row; vertical spacing comes from `settings.json → padding`.
- **Cheap reads only.** Every git / filesystem call is timeout-guarded (1s) and falls back silently on error — the statusline never blocks the prompt.
- **Activity counters.** The `🤖 · 🛠` segment is driven by [`global/hooks/post_tool_use.py`](global/hooks/post_tool_use.py), a `PostToolUse` hook that increments per-session counters in `~/.claude/.session_state.json`. Counters reset automatically when `session_id` changes.
- **OSC 8 hyperlink.** The cwd segment uses an ANSI OSC 8 escape with the SGR color codes wrapping the hyperlink (not nested inside it) so Windows Terminal hit-tests the link region correctly. If clicking does nothing, verify the URI handler with `start vscode://file/C:/projects/prompt-lib` in PowerShell.

### Customize / disable

- **Disable entirely:** delete the `statusLine` block from `global/settings.json` and reapply.
- **Hide a segment:** comment out its entry in the `row1` or `row2` list at the bottom of `global/statusline.py`.
- **Add a segment:** write a `seg_*` function returning a colored string (or `None` to hide), and append to `row1` / `row2`. Falsy returns are filtered before the `SEP.join`.
- **Change colors:** every segment passes RGB tuples through the `rgb()` helper — no theme indirection, just edit the literal tuples.
- **Change thresholds:** color bands live in `ctx_color()`, `cost_color()`, `headroom_color()` near the top of the file.

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
| `/react-init` | Scaffold a full current-stable React project — Vite + TS + Zustand + TanStack + Biome + Tailwind + Zod + MUI Icons | [src](global/skills/react-init.md) · [docs](docs/skills.md#react-init) |
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

### Alternative: install as a Claude Code plugin

You can install skills/agents/hooks/MCP servers without cloning the repo:

```text
/plugin marketplace add dwcy/prompt-lib
/plugin install prompt-lib@prompt-lib
```

Plugin install ships the shareable surface (skills become `/prompt-lib:*`, agents become `prompt-lib:*`). Items the plugin model can't carry — global `CLAUDE.md`, `global/rules/`, `global/project-templates/`, permissions, theme, statusLine — stay on the apply path. Both paths coexist. Full guide at [`docs/plugin-install.md`](docs/plugin-install.md); design at [`specs/004-github-plugin/`](specs/004-github-plugin/).

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
- [`docs/plugin-install.md`](docs/plugin-install.md) — install prompt-lib as a Claude Code plugin (no clone), scope split with the apply path
- [`docs/learning.md`](docs/learning.md) — 5-day learning path, mental shortcuts, debugging surprises

### Other references

- [`global/README.md`](global/README.md) — full Claude Code behaviour walkthrough (how agents trigger, how skills resolve, how overlapping tools are picked)
- [`global/MCP.md`](global/MCP.md) — MCP server setup and token configuration
- [`setup/README.md`](setup/README.md) — installer modes
- [`services/a2a-bridge/README.md`](services/a2a-bridge/README.md), [`services/orchestrator/README.md`](services/orchestrator/README.md) — service docs
- [`specs/`](specs/) — spec-kit feature trees
