# Subagent Roster — Spec-Kit Delegation Guide

This file is loaded by `/speckit-plan` and `/speckit-tasks` to decide which existing Claude Code subagent should own each task. Every task in `tasks.md` MUST have an `Owner: @<agent>` field naming an agent listed below (or `Owner: main` if the work belongs in the main thread).

## How to delegate

When generating `plan.md` or `tasks.md`:

1. Match the task's domain (language / framework / concern) to an agent below.
2. Write `Owner: @<agent>` on the task line.
3. If two or more writing tasks will be dispatched concurrently, mark each `Parallel: yes` (see "Parallel isolation" below).
4. During `/speckit-implement`, dispatch via the `Agent` tool with `subagent_type: "<agent>"` — never inline implementation work that has a specialist owner.
5. If no specialist matches, set `Owner: main` and explain why in one line.

## Parallel isolation (Constitution Principle II + Gate 6)

When `/speckit-implement` (or any dispatcher) spawns **two or more writing subagents that operate concurrently on the same repository**, every concurrent writer MUST run in an isolated git worktree. Reason: parallel writers on a shared working tree silently overwrite each other; isolation forces conflicts to surface at merge time.

### How it appears in `tasks.md`

Every task line ends with `— Owner: @<agent>` plus, when applicable, `Parallel: yes`. Example:

```
T012 [P] [US1] Implement POST /api/orders handler — src/api/orders.py — Owner: @python-architect — Parallel: yes
T013 [P] [US1] Implement OrdersForm component — web/src/features/orders/OrdersForm.tsx — Owner: @react-architect — Parallel: yes
T014     [US1] Wire orders feature module — web/src/features/orders/index.ts — Owner: @react-architect
```

T012 and T013 are dispatched concurrently — each gets its own worktree. T014 runs sequentially and uses the shared tree.

### How `/speckit-implement` honours it

For every task marked `Parallel: yes`, dispatch via the Agent tool with `isolation: "worktree"`. The harness auto-cleans the worktree if the agent makes no changes; on changes, the path + branch are returned and must be merged back. For tasks without the marker, dispatch normally.

### Exemptions

- **Read-only auditors** — `@code-plan-verifier`, `@gitignore-auditor`, `@secret-auditor`, or any agent whose `tools:` line excludes Write/Edit. They cannot overwrite anything; worktrees would only add cleanup cost.
- **Sequential single-agent dispatch** — even if the task touches many files, one writer at a time can't race itself.

See [`docs/parallel-isolation.md`](../../docs/parallel-isolation.md) for the canonical explainer.

## Agent roster

### Backend / language specialists

- **@dotnet-architect** — .NET Clean Architecture, CQRS, domain modelling, DI, service design, architectural review. Use for any structural decision in `*.csproj` projects.
- **@dotnet-tester** — xUnit, TestContainers integration tests, NSubstitute / Moq, .NET test strategy. Use for every .NET test task.
- **@python-architect** — FastAPI / Django structure, async design, service layer, DI, DB session management. Use for any structural decision in Python projects.
- **@python-tester** — pytest, async test patterns, fixture design, real-DB integration tests. Use for every Python test task.

### Frontend specialists

- **@react-architect** — React 2025 stack ONLY (Vite + TypeScript + Zustand + TanStack Query/Router/Forms + Tailwind v4 + Biome + Zod). Use when the project matches this stack.
- **@frontend-architect** — Vue 3, Next.js, or React projects NOT on the 2025 stack. Component design, state, performance, accessibility.
- **@frontend-css** — Modular CSS (globals.css + CSS Modules pattern). Use for any CSS-only task — never let a frontend agent do CSS architecture work.

### Game

- **@unity-architect** — Unity3D scene architecture, ScriptableObjects, MonoBehaviour patterns, performance.

### Project-level orchestrators

- **@init-project** — New project bootstrap (stack detection, CLAUDE.md authoring, agent spawning). Use ONLY for greenfield init.
- **@load-project** — Reads existing CLAUDE.md and announces available specialists. Use at session start for existing projects.

### Verification (read-only)

- **@code-plan-verifier** — Read-only audit of an implementation against the agreed plan, project architecture, existing patterns, coding guidelines, and version-specific docs. Flags shortcuts, mock data, hardcoded fakes, TODOs, unplanned-file changes, outdated APIs, and architectural boundary violations. NEVER edits files. Use after `/speckit-implement` (or any major implementation push) to gate a commit. Outputs verdict (PASS / PASS WITH WARNINGS / FAIL) plus Plan Compliance checklist, findings with severity, and a Final Recommendation.

## Stack → agent decision matrix

| If the task touches… | Owner |
|---|---|
| `.csproj`, `.cs`, NuGet, EF Core, MediatR | `@dotnet-architect` (impl) + `@dotnet-tester` (tests) |
| `pyproject.toml`, FastAPI, Django, SQLAlchemy, Pydantic | `@python-architect` (impl) + `@python-tester` (tests) |
| Vite + Zustand + TanStack | `@react-architect` |
| Vue 3, Next.js, plain React | `@frontend-architect` |
| `*.css`, design tokens, theming | `@frontend-css` |
| `*.unity`, MonoBehaviour, ScriptableObject | `@unity-architect` |
| Cross-cutting orchestration, ADRs, scripts that span domains | `main` |
| Read-only verification of an implementation against its plan | `@code-plan-verifier` |

## Anti-patterns

- Do NOT have `@frontend-architect` write CSS — delegate to `@frontend-css`.
- Do NOT have an architect write tests — delegate to the matching `*-tester`.
- Do NOT use `@react-architect` for Next.js — that is `@frontend-architect`.
- Do NOT spawn `@init-project` on an existing repo — use `@load-project`.
- Do NOT bundle multi-stack work onto one agent — split the task by stack.
