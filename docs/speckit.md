# Spec-kit — how it behaves in this repo

Spec-kit is the spec-driven workflow this repo uses for any non-trivial feature: a chain of slash commands that walks from `spec.md` → `plan.md` → `tasks.md` → execution, with a constitution that gates each step. This document covers **the specific configuration shipped here** — not generic spec-kit usage.

## Where it lives

```
.specify/
├── feature.json              ← current feature directory pointer
├── init-options.json         ← spec-kit init choices (ai, scripts, branch numbering)
├── integration.json          ← integration state, settings, version
├── extensions.yml            ← auto-execute hook map (git extension, overridden — see below)
├── memory/
│   ├── constitution.md       ← v1.0.0 — 5 principles + 5 Constitution Check gates
│   └── agents.md             ← subagent roster loaded by /speckit-plan and /speckit-tasks
├── templates/                ← spec, plan, tasks, constitution, checklist templates
├── scripts/powershell/       ← Windows scripts (check-prerequisites, create-new-feature, …)
├── workflows/speckit/        ← workflow.yml
└── extensions/git/           ← speckit-git extension assets (overridden)

specs/
├── 001-a2a-bridge/           ← shipped feature
└── 002-agent-orchestrator/   ← shipped feature
```

## Installed configuration

| Setting | Value | Effect |
|---|---|---|
| `ai` | `claude` | Slash commands target Claude Code's harness |
| `ai_skills` | `true` | Skills are installed as `/speckit-*` |
| `script` | `ps` | Spec-kit ships PowerShell scripts (`.specify/scripts/powershell/`) |
| `branch_numbering` | `sequential` | Features get `001-…`, `002-…`, `003-…` rather than timestamps |
| `context_file` | `CLAUDE.md` | Project context is read from the root `CLAUDE.md` |
| `here` | `true` | The repo itself is the spec-kit workspace |
| `integration` | `claude` | Sole installed integration |
| `speckit_version` | `0.8.8.dev0` | Pinned version |

## Constitution — v1.1.0

`.specify/memory/constitution.md` defines five principles that gate every `/speckit-plan` run. Read the file for the authoritative wording; the table below is a routing summary.

| # | Principle | Status |
|---|---|---|
| I | **Spec-First Conformance** | NON-NEGOTIABLE. External protocols (A2A, MCP, JSON-RPC, OpenAPI) are authoritative. Deviations require an ADR. |
| II | **Subagent Delegation** | Every `tasks.md` line must end with `Owner: @<agent>`. Specialists own their domains; `main` is allowed only when nothing else fits. v1.1.0 extends this with the parallel-isolation clause — concurrent writers require `isolation: "worktree"`. |
| III | **Contract Tests Before Implementation** | Protocol surfaces must have contract tests written and observed failing *before* implementation. |
| IV | **Reversible Config Changes** | Anything under `global/` must be deployable and revertable via `./run` (the cabal wizard) or its `setup/settings-configurator-ui.py` fallback. |
| V | **Minimal Skill & Agent Surface** | Don't add a new skill or agent if an existing one can be extended. Run `/review-conflicts` before adding. |

Amendments require the `/speckit-constitution` slash command, a Sync Impact Report at the top of the file, a semver bump, and propagation to dependent templates.

## Constitution Check gates (every `/speckit-plan` run)

`plan.md`'s "Constitution Check" section must clear all six gates before Phase 0 research can begin (Gate 6 stems from Principle II's parallel-isolation clause, added in v1.1.0 — it's not a standalone 6th principle, but it is a standalone gate):

| Gate | What it checks | If N/A |
|---|---|---|
| 1 | External protocol spec is linked + conformance scope stated | Write `N/A — no external protocol` |
| 2 | Delegation table maps every phase to an owner from `agents.md` | Always required |
| 3 | Contract test tasks appear before impl tasks for each protocol surface | Write `N/A` if no protocol surface |
| 4 | Rollback path documented for any `global/` change | Write `N/A` if no `global/` touch |
| 5 | New skill/agent justified vs extending existing ones | Write `N/A` if no new skill/agent |
| 6 | Concurrent writing subagents listed in Parallel Execution Map; `tasks.md` marks them `Parallel: yes`; dispatcher passes `isolation: "worktree"` | Write `N/A` if no phase runs writers in parallel |

Unresolved gate violations go into a "Complexity Tracking" table in `plan.md` with explicit justification — they don't silently slip.

## Slash commands

The skills harness exposes these `/speckit-*` commands. Each is a thin orchestrator around its template + scripts.

| Command | What it produces | Reads |
|---|---|---|
| `/speckit-constitution` | Creates or amends `.specify/memory/constitution.md` | Constitution template + interactive input |
| `/speckit-specify` | Creates `specs/<NNN>-<slug>/spec.md` | `spec-template.md` + user description |
| `/speckit-clarify` | Resolves `NEEDS CLARIFICATION` markers in `spec.md` | Asks up to 5 targeted questions, encodes answers back |
| `/speckit-plan` | Creates `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` | `plan-template.md`, `constitution.md`, `agents.md` |
| `/speckit-tasks` | Creates `tasks.md` with `Owner: @<agent>` lines and per-phase Status lines | `tasks-template.md`, `plan.md`, `agents.md` |
| `/speckit-analyze` | Cross-artifact consistency check (spec ↔ plan ↔ tasks) — non-destructive | All three docs |
| `/speckit-checklist` | Generates a feature-specific QA checklist | `checklist-template.md` + feature context |
| `/speckit-implement` | Executes `tasks.md` task-by-task, dispatching to named owners | `tasks.md` + the `Agent` tool with `subagent_type` |
| `/speckit-taskstoissues` | Converts `tasks.md` into ordered GitHub issues | `tasks.md` + `gh` CLI |

## Templates — what fills the boilerplate

`.specify/templates/` holds five fill-in-the-blank templates. Customising one customises every future feature.

| Template | Used by | Key local customisations |
|---|---|---|
| `constitution-template.md` | `/speckit-constitution` | (default — generic) |
| `spec-template.md` | `/speckit-specify` | User stories prioritised P1/P2/P3, each independently testable |
| `plan-template.md` | `/speckit-plan` | **Has the 5-gate Constitution Check section** + Subagent Delegation table referencing `agents.md` |
| `tasks-template.md` | `/speckit-tasks` | **Phase-status convention** (see below) + **Owner field mandatory** + Contract-test ordering rule |
| `checklist-template.md` | `/speckit-checklist` | (default — generic) |

## Subagent roster — `.specify/memory/agents.md`

This file is loaded by `/speckit-plan` and `/speckit-tasks` to decide ownership of each task. The roster has eight specialists (`@dotnet-architect`, `@dotnet-tester`, `@python-architect`, `@python-tester`, `@react-architect`, `@frontend-architect`, `@frontend-css`, `@unity-architect`), two orchestrators (`@init-project`, `@load-project`), and one verifier (`@code-plan-verifier`).

Decision matrix (excerpt from the file):

| Task touches… | Owner |
|---|---|
| `.csproj`, `.cs`, EF Core, MediatR | `@dotnet-architect` (impl) + `@dotnet-tester` (tests) |
| `pyproject.toml`, FastAPI, SQLAlchemy | `@python-architect` (impl) + `@python-tester` (tests) |
| Vite + Zustand + TanStack | `@react-architect` |
| Vue 3, Next.js, plain React | `@frontend-architect` |
| `*.css`, design tokens | `@frontend-css` |
| `*.unity`, MonoBehaviour | `@unity-architect` |
| Cross-cutting orchestration, ADRs | `main` |
| Read-only plan-vs-code verification | `@code-plan-verifier` |

Anti-patterns the file calls out: never let a frontend architect write CSS; never let an architect write tests; never use `@react-architect` for Next.js; never spawn `@init-project` on an existing repo.

## Phase-status convention (local override)

This repo enforces a **stricter** tasks.md convention than stock spec-kit. Every `## Phase X: …` heading must be followed immediately by a status line in one of three exact forms:

```
**Status**: ⬜ Pending (0/N — T###–T###)
**Status**: 🟡 In progress (M/N — T###–T###)
**Status**: ✅ Complete (N/N — T###–T###)
```

`/speckit-tasks` initialises every phase as ⬜ Pending. During `/speckit-implement`, whenever `[X]` checkboxes flip, the status line on every affected phase must be rewritten in the **same edit**. The per-task checkboxes are the source of truth; the status line is the at-a-glance view that must agree.

This is encoded in `tasks-template.md` and codified as durable memory — don't drop it.

## Git extension — installed but overridden

`.specify/extensions.yml` registers an auto-execute git extension that wires `before_*` and `after_*` git-commit hooks around every spec-kit command. The full hook table is in `extensions.yml`.

**This repo overrides the extension at the user-rule level.** The durable rule:

> Never invoke `speckit-git-*` skills; always drive commits, branches, and pushes from the `/git` skill / global commit rules.

Why: the `/git` skill enforces branch safety, conventional commit type, category tagging, agent authorship (`my@agent.commit`), and a refuse-on-main check. The spec-kit git extension does none of that. Letting auto-execute fire would bypass every commit-time safety rule.

When you see a spec-kit prompt like "Execute speckit.git.commit?" — say no. Run `/git commit` yourself.

## Per-feature spec tree

Every feature directory under `specs/<NNN>-<slug>/` follows the same layout:

```
specs/002-agent-orchestrator/
├── spec.md           ← user stories, requirements, success criteria
├── plan.md           ← stack, structure, constitution check, delegation table
├── research.md       ← Phase 0 decisions (R1–RN) with rationale
├── data-model.md     ← entities, state machine, schemas
├── contracts/        ← external wire-format contracts
├── tasks.md          ← phase-by-phase tasks, Owner-tagged, Status-tracked
├── quickstart.md     ← end-to-end walkthrough
└── checklists/       ← QA checklists from /speckit-checklist
```

`specs/001-a2a-bridge/` and `specs/002-agent-orchestrator/` are reference examples — both have full trees with the constitution-gate output, delegation tables, and contract test directories.

## How it behaves end-to-end

```
1. /speckit-constitution        ← (once, or to amend) writes .specify/memory/constitution.md
2. /speckit-specify             ← writes specs/NNN-slug/spec.md
3. /speckit-clarify (optional)  ← resolves NEEDS CLARIFICATION markers
4. /speckit-plan                ← writes plan.md + Phase 0 artifacts
                                  Constitution Check gates must pass before Phase 0
5. /speckit-tasks               ← writes tasks.md
                                  Every task line gets Owner: @<agent>
                                  Every Phase heading gets ⬜/🟡/✅ Status line
6. /speckit-analyze (optional)  ← cross-artifact consistency check
7. /speckit-implement           ← dispatches each task to its owner via Agent tool
                                  Tasks marked `Parallel: yes` are dispatched with
                                    isolation: "worktree" (see parallel-isolation.md)
                                  Updates checkboxes + Phase Status as it goes
                                  Phase status convention is rewritten in the same edit
8. @code-plan-verifier          ← read-only audit of code vs plan before commit
9. /git commit                  ← NOT a speckit-git-* hook — driven by /git skill
```

For the broader multi-agent flow (worktrees, parallel sessions, end-of-branch finishing), see [`workflows.md`](workflows.md).

## Pitfalls / anti-patterns

- **Accepting speckit-git-* auto-execute prompts.** They bypass the `/git` skill's safety. Always decline; run `/git commit` afterwards.
- **Forgetting to rewrite Phase Status when flipping checkboxes.** The Status line is the at-a-glance view; if it diverges from the checkboxes, future sessions read stale state.
- **Dispatching `Parallel: yes` tasks without `isolation: "worktree"`.** Constitution Gate 6 violation. The two agents will silently overwrite each other. See [`parallel-isolation.md`](parallel-isolation.md).
- **Setting `Owner: main` without a one-line justification.** The constitution requires it. Auditors will catch the omission.
- **Skipping `/speckit-clarify` when `spec.md` has `NEEDS CLARIFICATION` markers.** `/speckit-plan` will inherit the ambiguity and bake it into design decisions.
- **Writing implementation tasks before contract test tasks for a protocol surface.** Constitution Gate 3 violation; reorder in `tasks.md`.
- **Adding a new skill/agent without justifying why an existing one can't be extended.** Constitution Gate 5 violation; document it in `plan.md` or merge into an existing surface.
- **Letting an architect write tests in `/speckit-implement`.** Override the dispatch — testers own test tasks, architects own implementation. The `agents.md` decision matrix is binding.

## Amending the workflow

| Want to change… | Edit |
|---|---|
| A principle or a gate | `.specify/memory/constitution.md` via `/speckit-constitution` (bump version, propagate to templates) |
| The delegation roster | `.specify/memory/agents.md` (no version bump; it's a routing table) |
| The shape of `spec.md` / `plan.md` / `tasks.md` | `.specify/templates/<which>.md` |
| The PowerShell helpers | `.specify/scripts/powershell/*.ps1` |
| Whether git auto-execute fires | `.specify/extensions.yml` (or just keep declining the prompts) |

Every change here propagates to **every future feature** — there is no per-feature override. If you need a one-off exception, record it in that feature's `plan.md` Complexity Tracking section with explicit justification.
