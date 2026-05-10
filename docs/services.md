# Services — long-running daemons that extend Claude Code

The `services/` directory holds runtime processes that go beyond what a single Claude Code session can do: cross-agent delegation and autonomous PR review. Both are spec-kit driven — their authoritative design lives under `specs/`, and both ship as `uv`-managed Python packages.

## `services/a2a-bridge`

**Purpose**: bidirectional A2A protocol bridge so Claude Code can delegate work to a peer agent (Gemini CLI in v1) and external clients can drive Claude Code over JSON-RPC + SSE.

**Stack**: Python 3.13, FastAPI ≥0.135 (native `EventSourceResponse`), httpx, uv. Two adapters (`claude` inbound, `gemini` outbound) share one package.

**What it gives you**:

- **Outbound delegation** (US1) — Claude → `DelegationClient` → POSTs an A2A `tasks/send` to a peer agent → streams SSE artifacts back → Claude integrates them. Used by `services/orchestrator` to dispatch each PR to a peer Claude.
- **Inbound reception** (US2) — external A2A client → Claude adapter → drives Claude Code. Lets a daemon, bot, or other LLM trigger Claude as a tool.
- **Agent Card discovery** (US3) — `/.well-known/agent-card.json` advertises capabilities so peers can negotiate.

**Spec sources** (`specs/001-a2a-bridge/`):

- `spec.md` — user stories, requirements, success criteria
- `plan.md` — stack decisions, structure, constitution gates, subagent delegation
- `tasks.md` — Phase 1–6 task breakdown with named owners (`@python-architect` or `@python-tester`)
- `research.md` — six Phase 0 decisions (A2A spec version, FastAPI SSE pattern, CLI flags…)
- `data-model.md` — Task, Artifact, Adapter, AgentCard entity models
- `contracts/` — Agent Card schema, JSON-RPC methods, SSE events, error codes
- `quickstart.md` — 9-step end-to-end walkthrough (~10 min)

**Status**: 199 tests passing / 5 skipped / 0 failed. Phase 1–6 of `tasks.md` complete (40/41). Only deferred item is the Inspector manual pass (T039), which requires a user-driven web tool.

**Run an adapter**:

```powershell
$env:A2A_BEARER_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
uv run a2a-bridge serve gemini --port 8766
uv run a2a-bridge serve claude --port 8765
```

Adapters refuse to start if `A2A_BEARER_TOKEN` is unset or shorter than 32 characters.

## `services/orchestrator`

**Purpose**: long-running daemon that watches a configured GitHub repo, dispatches each opened/updated pull request to a peer Claude Code agent over the A2A bridge, posts the agent's review back via `gh`, persists every state transition to an append-only SQLite event log, and notifies the operator on screen (Textual dashboard) and on phone (ntfy.sh).

**Stack**: Python 3.13, sibling path-dep on `../a2a-bridge`, Typer CLI, pydantic-settings (env-only config), Textual TUI, SQLite WAL.

**Pieces** (`services/orchestrator/src/orchestrator/`):

- `cli.py` — Typer entry: `orchestrator serve` (daemon), `orchestrator dash` (TUI)
- `config.py` — env-only configuration via pydantic-settings
- `daemon.py` — async dispatch loop + orphan recovery on startup
- `eventlog.py` — SQLite WAL append-only event store, runs view, cursor table, orphan-recovery routine
- `notifier.py` — ntfy.sh HTTP publisher with non-fatal failure semantics
- `triggers/` — Trigger Protocol + GitHub poll source
- `agents/` — PR-review agent that calls A2A `DelegationClient`
- `dashboard/` — Textual TUI tailing the event log read-only

**Spec sources** (`specs/002-agent-orchestrator/`):

- `spec.md`, `plan.md`, `quickstart.md`, `research.md`, `data-model.md`, `contracts/`, `tasks.md`

**Status**: v1 feature-complete. Manual real-repo verification (`tasks.md` T035) is operator-driven before tagging the v1 release.

**Test layout**:

```
tests/
├── contract/      ← Constitution Gate 3 — external wire conformance (gh, ntfy, A2A consumer)
├── integration/   ← P1 with real subprocess (INTEGRATION-gated). P2/P3 in-process.
└── unit/          ← config, eventlog, notifier, orphan recovery, pr-review, triggers
```

## How they fit into the wider system

```
GitHub repo
   │
   ▼ (poll every N seconds)
orchestrator daemon
   │
   ├── new PR detected → append event to SQLite WAL
   │                  → dispatch via A2A bridge
   │                       │
   │                       ▼
   │                  peer Claude Code session reviews the PR
   │                       │
   │                       ▼ (SSE artifact back)
   │                  orchestrator collects the review
   │                       │
   │                       ▼
   │                  gh pr review --body <review>
   │                       │
   │                       ▼
   │                  ntfy.sh push to operator's phone
   │
   └── operator opens dashboard ('orchestrator dash')
        Textual TUI tails the event log live
```

This is the single best demonstration of why this repo exists: the spec-kit feature trees, A2A bridge, subagent specialists, hooks, skills, and runtime services all come together to make autonomous PR review a real running daemon — not a prompt.

## When to extend

- **New trigger sources** — implement the `Trigger` protocol in `orchestrator/triggers/` (Linear webhook, Jira poll, file-system watcher).
- **New peer agents** — add an adapter to `a2a-bridge` for any A2A-compliant target.
- **New review agents** — drop into `orchestrator/agents/`. Anything that takes a PR payload and returns a review string composes.
