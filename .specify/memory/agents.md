# Subagent Roster — Spec-Kit Delegation Guide

This file is loaded by `/speckit-plan` and `/speckit-tasks` to decide which existing Claude Code subagent should own each task. Every task in `tasks.md` MUST have an `Owner: @<agent>` field naming an agent listed below (or `Owner: main` if the work belongs in the main thread).

## How to delegate

When generating `plan.md` or `tasks.md`:

1. Match the task's domain (language / framework / concern) to an agent below.
2. Write `Owner: @<agent>` on the task line.
3. During `/speckit-implement`, dispatch via the `Agent` tool with `subagent_type: "<agent>"` — never inline implementation work that has a specialist owner.
4. If no specialist matches, set `Owner: main` and explain why in one line.

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
