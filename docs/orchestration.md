# Multi-Agent Orchestration

This document describes how the main Claude Code session routes tasks to specialist subagents using the `/orchestrate` skill.

## Architecture overview

```
User / main session
        │
        ▼
  /orchestrate skill
        │
   ┌────┴────────────────────────────┐
   │  Routing table (domain + phase) │
   └────┬────────────────────────────┘
        │
   ┌────┴──────────────────────────────────────────┐
   │                                               │
   ▼ sequential                          parallel ▼
Agent(subagent_type, isolation="worktree")    Agent × N
        │                                        │
   result                              merge worktrees
        │                                        │
        └──────────────────┬────────────────────┘
                           ▼
                    aggregated result
                    → main session
```

## Agent registry

| Agent | Speciality | Writes files? |
|---|---|---|
| `dotnet-architect` | .NET Clean Architecture, CQRS, DI, domain modelling | Yes |
| `dotnet-tester` | xUnit, TestContainers, NSubstitute, Moq | Yes |
| `react-architect` | Vite + TypeScript + Zustand + Biome + TanStack stack | Yes |
| `frontend-architect` | Vue 3, Next.js, React (non-Vite+Zustand) | Yes |
| `tanstack-architect` | TanStack Router / Query / Form / Table / Virtual | Yes |
| `frontend-css` | CSS modules, design tokens, globals.css | Yes |
| `frontend-designer` | UI/UX design, design system, DESIGN.md | Yes |
| `ux-analyst` | Behaviour/best-practice questioning + a11y gate for new UI (advisory, non-deciding) | Yes (UX briefs) |
| `python-architect` | FastAPI, Django, SQLAlchemy, async patterns | Yes |
| `python-tester` | pytest, pytest-asyncio, fixtures, integration tests | Yes |
| `unity-architect` | MonoBehaviour, ScriptableObject, scene architecture | Yes |
| `pi-arduino-architect` | Raspberry Pi (Python), Arduino (C++), GPIO, sensors | Yes |
| `github-config-manager` | Branch protection, secret scanning, Dependabot | No (runs `gh api`) |
| `gitignore-auditor` | Pre-commit .gitignore audit | No (read-only) |
| `secret-auditor` | Pre-commit secret / credential scan | No (read-only) |
| `owasp-security-reviewer` | OWASP Top 10 security review of code, APIs, auth flows | No (read-only) |
| `code-cleaner` | Dead code / dead CSS / unused asset & dependency removal | Yes (edits + deletions) |
| `code-plan-verifier` | Verify implementation matches plan and conventions | No (read-only) |
| `init-project` | New project scaffolding, CLAUDE.md creation | Yes |
| `load-project` | Load existing project context at session start | No |
| `requirements-analyst` | Elicit + document requirements, user stories, acceptance criteria | Yes (REQUIREMENTS.md / spec) |
| `data-analyst` | Profile + analyse datasets, compute metrics, findings reports | Yes (analysis scripts + reports) |
| `api-designer` | REST / GraphQL contract design, OpenAPI / SDL | Yes (openapi.yaml / schema.graphql) |
| `db-architect` | Schema design, indexing, migrations, data modelling | Yes (DDL / migrations) |
| `website-content-analyst` | Fetch + distil web pages from URLs into cited findings | Yes (research reports) |
| `git-repo-analyst` | Two-stage repo analysis: feature map → code/idea extraction | Yes (analysis reports; clones to scratch) |
| `solution-architect` | Cross-cutting system design: service boundaries, integration style, caching, scalability, ADRs | Yes (design docs / ADRs) |
| `devops-engineer` | Dockerfiles, docker-compose, GitHub Actions pipelines, release engineering | Yes |
| `frontend-tester` | Vitest + React Testing Library, MSW, Playwright, frontend test strategy | Yes |

> `load-project` is NOT routed via `/orchestrate` — it runs at session start only.

## Routing logic

The skill matches **domain signals** (technology keywords) against **phase signals** (what kind of work) and selects the highest-priority matching agent. Full routing table: [`global/skills/orchestrate/SKILL.md`](../global/skills/orchestrate/SKILL.md).

Priority rules:
- More specific beats more general (e.g. `dotnet-tester` over `dotnet-architect` when test keywords present)
- TanStack-specific beats generic React
- Vite+Zustand React beats generic React/frontend

## Parallel isolation

When multiple writing agents run concurrently, each gets its own git worktree via `isolation: "worktree"`. This prevents silent file overwrites. The harness:
1. Creates a temporary worktree per agent on a unique branch
2. Auto-cleans the worktree if the agent makes no changes
3. Returns the worktree path + branch when changes are made
4. The main session merges each branch back sequentially and reports conflicts

Read-only agents (`gitignore-auditor`, `secret-auditor`, `code-plan-verifier`, `owasp-security-reviewer`) are exempt — they can run in parallel without isolation.

**Concurrency cap:** at most 4 subagents run at the same time, regardless of isolation. Larger selections are dispatched in waves of ≤4, with the next agent launched only as a running one finishes — this bounds CPU/RAM pressure on the machine, not just token spend.

See [`docs/parallel-isolation.md`](parallel-isolation.md) for the full isolation rules.

## When routing fires

The main session handles tasks itself by default. `global/CLAUDE.md` gates delegation on what it buys — **scale** (roughly >5 files or context-dominating work), **independence** (fresh-eyes review or audit), or **parallelism** (independent isolated workstreams) — never on domain match alone. `/orchestrate` runs its full routing table when explicitly invoked; auto-routing fires only when the gate passes, and the session announces which agent was selected and what the dispatch buys. Multi-agent pipelines run only on explicit `/orchestrate` or Spec Kit invocation.

## Inter-agent communication (mcp-bus)

Dispatched agents are otherwise blind to each other. The `mcp-bus` MCP server (`services/mcp-bus/`) gives them a shared channel-based message bus, a namespaced key-value memory, and an agent registry — all durable in SQLite and callable as MCP tools.

When `/orchestrate` runs parallel agents that depend on a shared artifact (e.g. an API contract), the agents coordinate through the bus:

1. The lead agent posts the contract to a channel (`bus_post`)
2. Each worker reads the channel before starting (`bus_read`)
3. Workers record decisions to shared memory under a feature namespace (`mem_set`)
4. The verifier reads channel + memory to confirm consistency

Setup and tool reference: [`specs/007-mcp-bus/quickstart.md`](../specs/007-mcp-bus/quickstart.md). Registration is documented in [`global/MCP.md`](../global/MCP.md).

## Roadmap

| Feature | Spec |
|---|---|
| `/orchestrate` skill — subagent routing (this doc) | `specs/006-orchestrate-skill/` |
| MCP message bus — inter-agent comms + shared memory | `specs/007-mcp-bus/` (implemented in `services/mcp-bus/`) |
| Autonomous pollers — git/GitHub watching via CronCreate | `specs/002-agent-orchestrator/` (partial) |
| Full daemon + Textual dashboard | `specs/002-agent-orchestrator/` (implemented in `services/orchestrator/`) |
| A2A bridge — Claude ↔ Gemini ↔ Codex | `specs/001-a2a-bridge/` (redesign planned) |
