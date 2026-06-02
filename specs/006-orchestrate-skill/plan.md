# Implementation Plan: /orchestrate Skill — Automatic Subagent Routing (v1)

**Branch**: `feat/006-orchestrate-skill` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)

## Summary

Implement a `/orchestrate` skill (`global/skills/orchestrate.md`) that routes tasks to the correct specialist subagent(s). Add proactive routing guidance to `global/CLAUDE.md` so the main session delegates automatically without being asked. Write user-facing docs.

No new Python services, no external dependencies, no database. Everything is markdown + the existing `Agent` tool.

## Subagent Delegation

| Task | Owner |
|---|---|
| Skill file implementation | main session |
| CLAUDE.md routing rules | main session |
| Documentation | main session |
| Plan conformance audit | `@code-plan-verifier` |

## Routing Table (authoritative)

This table is embedded verbatim in the skill file. It is the single source of truth — update both when adding agents.

### Domain + phase → agent

| Priority | Domain signals | Phase signals | Agent |
|---|---|---|---|
| 1 | `.cs`, `csproj`, `.NET`, `C#`, `CQRS`, `MediatR`, Clean Architecture | test, xUnit, NUnit, NSubstitute, Moq, TestContainers | `dotnet-tester` |
| 2 | `.cs`, `csproj`, `.NET`, `C#`, `CQRS`, `MediatR`, Clean Architecture | architect, design, structure, review, DI, domain | `dotnet-architect` |
| 3 | `TanStack Router`, `TanStack Query`, `TanStack Form`, `TanStack Table`, typed routes, route loaders | any | `tanstack-architect` |
| 4 | React + (`Vite`, `Zustand`, `Biome`, `Zod`, `MUI Icons`) | architect, design, component, state | `react-architect` |
| 5 | React (Vue/Next.js/Nuxt/Angular — not Vite+Zustand) | architect, design, component, state | `frontend-architect` |
| 6 | CSS, `globals.css`, design tokens, theming, CSS modules | implement, scaffold, audit | `frontend-css` |
| 7 | UI design, UX, wireframe, design system, colors, typography, mockup | design, plan, vision | `frontend-designer` |
| 8 | Python, FastAPI, Django, SQLAlchemy, `pyproject.toml` | test, pytest, fixture, async test | `python-tester` |
| 9 | Python, FastAPI, Django, SQLAlchemy, `pyproject.toml` | architect, design, structure, async, service layer | `python-architect` |
| 10 | Unity, MonoBehaviour, ScriptableObject, scene, prefab, `Assets/` | architect, design, review | `unity-architect` |
| 11 | Raspberry Pi, Arduino, GPIO, I2C, SPI, UART, sensor, motor, servo | any | `pi-arduino-architect` |
| 12 | GitHub settings, branch protection, secret scanning, Dependabot, Copilot review | configure, set up, audit | `github-config-manager` |
| 13 | `.gitignore`, staged files, pre-commit, `git add` | audit, check | `gitignore-auditor` |
| 14 | API keys, secrets, credentials, tokens, passwords, high-entropy | scan, audit, pre-commit | `secret-auditor` |
| 15 | new project, `CLAUDE.md` missing, init, scaffold | setup, initialise | `init-project` |
| 16 | verify, plan conformance, "does the code match", architecture review | verify, check, audit | `code-plan-verifier` |

### Dispatch mode

| Condition | Mode | Isolation |
|---|---|---|
| Single agent selected | Sequential (trivially) | `isolation: "worktree"` if agent writes files |
| Multiple independent domains | Parallel | `isolation: "worktree"` per writing agent |
| Read-only agents only (`gitignore-auditor`, `secret-auditor`, `code-plan-verifier`) | Parallel | No isolation needed |
| Sequential pipeline (design → implement → verify) | Sequential | `isolation: "worktree"` per writing agent |

## File Changes

```
global/
├── skills/
│   └── orchestrate.md          ← new skill file
└── CLAUDE.md                   ← add "Subagent routing" section

specs/006-orchestrate-skill/
├── spec.md                     ← done
├── plan.md                     ← this file
└── quickstart.md               ← user guide + how to extend routing table

docs/
└── orchestration.md            ← architecture overview
```

## Implementation Notes

- The skill operates entirely through Claude's reasoning + `Agent` tool calls — no Python, no subprocess
- Worktree branch names: `orchestrate/<agent-name>/<short-task-slug>` — keeps them identifiable
- When parallel agents return, merge each worktree sequentially; report conflicts per-file rather than aborting
- The skill must NOT silently deviate from the routing table — if ambiguous, pick the highest-priority match and tell the user which was chosen and why
- The `load-project` agent is NOT in the routing table — it is invoked separately at session start, not via orchestrate

## Validation

Run `/orchestrate` against these reference tasks and confirm agent selection:

| Task prompt | Expected agent(s) | Mode |
|---|---|---|
| "Refactor PaymentService to use Clean Architecture" | `dotnet-architect` | Sequential |
| "Write xUnit tests for OrderRepository" | `dotnet-tester` | Sequential |
| "Add a React checkout page with Zustand cart state" | `react-architect` | Sequential |
| "Add FastAPI endpoint + React form for user login" | `python-architect` + `react-architect` | Parallel |
| "Design the onboarding UX flow" | `frontend-designer` | Sequential |
| "Audit staged files before committing" | `gitignore-auditor` + `secret-auditor` | Parallel (no isolation) |
| "Verify the implementation matches the plan" | `code-plan-verifier` | Sequential (no isolation) |
| "Write TanStack Router routes for the dashboard" | `tanstack-architect` | Sequential |
