# Feature Specification: /orchestrate Skill — Automatic Subagent Routing (v1)

**Feature Branch**: `feat/006-orchestrate-skill`
**Created**: 2026-06-01
**Status**: Implemented — active skill lives at `global/skills/orchestrate.md`; proactive routing guidance lives in `global/CLAUDE.md`. Manual validation depends on a Claude Code runtime with subagent support.
**Input**: Build a skill that allows the main Claude Code session to automatically route tasks to the right specialist subagent(s) without the user having to know which agent exists or how to invoke it.

---

## Problem

The main Claude Code session has a growing roster of specialist subagents available but uses them only when the user or a skill explicitly calls `Agent(subagent_type=...)`. This means:

- Users must know agent names and when to use them
- Complex tasks that span multiple domains (e.g. Python backend + React frontend) require manual multi-agent coordination
- There is no systematic routing — delegation is ad-hoc

## Goal

A single `/orchestrate <task>` skill that:
1. Analyses the task
2. Selects the right subagent(s) from the registry
3. Dispatches them (with worktree isolation when parallel)
4. Aggregates and returns results

The main session should also proactively invoke `/orchestrate` without being asked when the task clearly matches a specialist domain.

---

## User Scenarios

### Scenario 1 — Single-domain routing (P1) 🎯 MVP

The user says "refactor the auth service to use dependency injection". The main session detects this is a Python architecture concern, invokes `/orchestrate`, which dispatches `@python-architect`. The user gets the architect's analysis without knowing the agent exists.

**Acceptance**: correct single agent selected; result returned to main session; no user intervention needed.

### Scenario 2 — Multi-domain parallel dispatch (P1) 🎯 MVP

The user says "add a React frontend and FastAPI backend for user management". The skill identifies two independent domains, dispatches `@react-architect` and `@python-architect` in parallel with `isolation: "worktree"`, and merges results.

**Acceptance**: both agents run in parallel; each in its own worktree; conflicts reported rather than auto-resolved.

### Scenario 3 — Sequential pipeline (P2)

The user says "design, implement, and verify a new checkout flow". The skill dispatches agents in sequence: `@frontend-designer` → `@react-architect` → `@code-plan-verifier`. Each agent's output seeds the next.

**Acceptance**: agents run in order; output of each is passed to the next as context.

### Scenario 4 — Pre-commit audit (P2)

The user runs `/orchestrate` before committing. The skill dispatches `@gitignore-auditor` and `@secret-auditor` in parallel (both read-only, no isolation needed). Results are presented together.

**Acceptance**: both auditors run; combined report shown; no false positives for already-.gitignored paths.

### Scenario 5 — Proactive routing (P2)

The user asks "write xUnit tests for the PaymentService". The main session recognises this as a .NET testing task and proactively invokes `/orchestrate` without being asked.

**Acceptance**: `global/CLAUDE.md` routing rules cause automatic delegation; user is informed which agent was selected.

---

## Routing Table

The skill selects agents using keyword + context matching. Priority: more specific beats more general.

| Domain signals | Phase signals | Selected agent(s) |
|---|---|---|
| `.cs`, `csproj`, `.NET`, `C#`, `CQRS`, `MediatR`, `DI`, `Clean Architecture` | architect, design, structure, review | `dotnet-architect` |
| `.cs`, `csproj`, `.NET`, `C#` | test, xUnit, NUnit, NSubstitute, Moq, TestContainers | `dotnet-tester` |
| `React` (non-Vite+Zustand), `Vue`, `Next.js`, `Nuxt`, `Angular` | architect, design, component, state | `frontend-architect` |
| `React` + (`Vite`, `Zustand`, `Biome`, `TanStack`, `Zod`) | architect, design, component, state | `react-architect` |
| `TanStack Router`, `TanStack Query`, `TanStack Form`, `TanStack Table`, `routes/` | any | `tanstack-architect` |
| CSS, styling, `globals.css`, design tokens, theme | implement, scaffold, audit | `frontend-css` |
| UI design, UX, wireframe, design system, colors, typography, mockup | design, plan | `frontend-designer` |
| Python, FastAPI, Django, SQLAlchemy, `pyproject.toml` | architect, design, structure, review | `python-architect` |
| Python, pytest, `conftest`, async test, fixture | test, write tests | `python-tester` |
| Unity, MonoBehaviour, ScriptableObject, scene, prefab | architect, design, review | `unity-architect` |
| Raspberry Pi, Arduino, GPIO, I2C, SPI, sensor, motor | any | `pi-arduino-architect` |
| GitHub, branch protection, secret scanning, Dependabot | configure, set up, audit | `github-config-manager` |
| `.gitignore`, staged files, `git add`, pre-commit | audit, check | `gitignore-auditor` |
| API keys, secrets, credentials, tokens, passwords | audit, scan, pre-commit | `secret-auditor` |
| new project, init, scaffold, `CLAUDE.md` missing | setup, init | `init-project` |
| verify, plan conformance, architecture review, matches plan | verify, check | `code-plan-verifier` |

### Parallel vs sequential

**Run in parallel** (with `isolation: "worktree"` for writers):
- Independent domains (frontend + backend)
- Multiple auditors (read-only agents are exempt from isolation)
- Multiple architects on unrelated subsystems

**Run sequentially** (output of each seeds next):
- Design → implement → verify pipelines
- When one agent's output is required input for the next

---

## Skill Behaviour

### Inputs
- `<task>` — free-text description of what needs to be done

### Steps
1. **Analyse** — read the task, identify domain signals and phase signals
2. **Select** — match routing table; if ambiguous, pick the most specific agent; if none match, stay in main session
3. **Plan dispatch** — decide parallel vs sequential based on dependency check
4. **Dispatch** — call `Agent(subagent_type=..., isolation="worktree")` for writers; omit isolation for read-only agents
5. **Aggregate** — collect results; for parallel runs merge worktree branches; report conflicts to user
6. **Report** — present which agents were used and why; surface results clearly

### No-match behaviour
If no agent matches, the skill reports "no specialist matched — handling in main session" and continues without delegation.

### Error handling
- Agent failure: report error + which agent failed; continue with remaining agents if parallel
- Worktree conflict: surface conflict; do not auto-resolve

---

## Out of scope (v1)

- Dynamic agent registration at runtime (routing table is static in the skill file)
- Cross-session shared memory (tracked in spec 007 — MCP message bus)
- Autonomous / unattended invocation (tracked in spec 002 daemon)
- A2A bridge to non-Claude agents (Gemini, Codex) — tracked in spec 001 redesign
