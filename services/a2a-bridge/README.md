# a2a-bridge

A v1 multi-agent A2A bridge so Claude Code can delegate tasks to a peer Gemini CLI, and so external clients can drive Claude Code, over the official [A2A v1.0.0](https://a2a-protocol.org/latest/specification/) JSON-RPC 2.0 binding.

Two adapters (Claude inbound, Gemini outbound target) share one Python package. Built on Python 3.13, FastAPI ≥0.135 (native `EventSourceResponse`), httpx, and uv.

## Status

Phases 1–6 of `specs/001-a2a-bridge/tasks.md` complete (40/41 tasks). All three user stories functional, all polish landed except T039 (Inspector manual pass — requires user-driven web tool).

- **US1 (P1)** — Outbound delegation Claude → Gemini ✅
- **US2 (P2)** — Inbound reception via Claude adapter ✅
- **US3 (P3)** — Agent Card discovery ✅
- **Polish** — Concurrency test ✅, end-to-end quickstart walkthrough ✅, README ✅, ADR audit ✅ (zero deviations); Inspector manual pass ⏸ deferred

Test suite: **199 passing / 5 skipped / 0 failed**.

## Spec-driven sources

This package is spec-driven. The authoritative documents live in [`specs/001-a2a-bridge/`](../../specs/001-a2a-bridge/):

- [`spec.md`](../../specs/001-a2a-bridge/spec.md) — What it does and why; user stories, requirements, success criteria
- [`plan.md`](../../specs/001-a2a-bridge/plan.md) — Stack, project structure, constitution gates, subagent delegation
- [`tasks.md`](../../specs/001-a2a-bridge/tasks.md) — Phase-by-phase task breakdown with named owners
- [`research.md`](../../specs/001-a2a-bridge/research.md) — Six Phase 0 decisions (A2A spec version, FastAPI SSE pattern, CLI flags, etc.)
- [`data-model.md`](../../specs/001-a2a-bridge/data-model.md) — Task, Artifact, Adapter, AgentCard entity models
- [`quickstart.md`](../../specs/001-a2a-bridge/quickstart.md) — 9-step end-to-end walkthrough (≈10 min)
- [`contracts/`](../../specs/001-a2a-bridge/contracts/) — Authoritative wire-format contracts (Agent Card schema, JSON-RPC methods, SSE events, error codes)

Read `plan.md` first if you're implementing, then `tasks.md`. Every implementation task lists its file paths and its owning subagent (`@python-architect` or `@python-tester`).

## Install

Requires Python 3.13 and `uv`.

```bash
cd services/a2a-bridge
uv sync
```

## Run an adapter

```bash
# Bash
export A2A_BEARER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run a2a-bridge serve gemini --port 8766
# In another terminal:
uv run a2a-bridge serve claude --port 8765
```

```powershell
# PowerShell
$env:A2A_BEARER_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
uv run a2a-bridge serve gemini --port 8766
uv run a2a-bridge serve claude --port 8765
```

Adapters refuse to start if `A2A_BEARER_TOKEN` is unset or shorter than 32 characters.

## Delegate from Claude → Gemini

```bash
uv run a2a-bridge delegate gemini "Reply with the single word: pong"
```

Exit codes: `0` completed, `1` connect refused, `2` auth fail, `3` protocol error, `4` cancelled / failed task. Streamed events print to stdout as one JSON object per line.

See [`quickstart.md`](../../specs/001-a2a-bridge/quickstart.md) for the full 9-step verification walkthrough including `curl`-driven inbound testing and Agent Card discovery.

### Manual Inspector conformance

The only deferred validation is the A2A Inspector pass. Start both adapters,
then follow [quickstart Step 9](../../specs/001-a2a-bridge/quickstart.md#step-9--open-the-inspector-for-manual-conformance-check)
against `http://127.0.0.1:8765` and `http://127.0.0.1:8766`. The expected
result is zero Agent Card violations and zero message-flow violations for both
adapters.

## Tests

```bash
uv run pytest                      # full suite
uv run pytest -m contract          # protocol-surface contract tests only
uv run pytest tests/integration    # real-uvicorn integration tests
```

Current count: **199 tests** across `tests/contract/`, `tests/integration/`, `tests/unit/`, plus shared `tests/fixtures/fake_cli.py`.

### Real-CLI test gating

Two integration tests exercise the real CLI binaries when configured:

| Test | Gate | How to enable |
|---|---|---|
| `test_p1_real_gemini_delegation_completes_within_budget` | `gemini` on PATH AND `GEMINI_API_KEY` set | `npm install -g @google/gemini-cli`, get key at <https://aistudio.google.com/app/apikey>, `export GEMINI_API_KEY=...` |
| `test_p2_curl_real_claude_completes` | `claude` on PATH AND `A2A_REAL_CLI_TESTS=1` set | Install Claude Code CLI, `claude /login` interactively, `export A2A_REAL_CLI_TESTS=1` |

When unset, both tests skip cleanly with a clear reason. The bridge mechanics themselves are fully covered by deterministic fake-CLI tests (`tests/fixtures/fake_cli.py`).

## Architecture overview

```
src/a2a_bridge/
├── protocol/              # CLI-agnostic protocol primitives (no I/O)
│   ├── auth.py            # bearer-token compare (constant-time HMAC)
│   ├── logging.py         # structured stdout JSON logger
│   ├── jsonrpc.py         # envelopes, ErrorCode IntEnum, parse_request
│   ├── tasks.py           # Task entity + state machine, Artifact
│   ├── agent_card.py      # AgentCard model + jsonschema validator
│   ├── sse.py             # SSE event types + framer + OrderingEnforcer
│   └── cli_runner.py      # Generic CLI subprocess runner (factory + parser pluggable)
├── adapters/
│   ├── base.py            # build_app: auth + content-type middleware + dispatcher + discovery
│   ├── claude/            # Claude-specific runner shim + server (port 8765)
│   └── gemini/            # Gemini-specific runner shim + server (port 8766)
├── client/
│   └── delegation.py      # DelegationClient (httpx async + SSE consumer)
└── cli.py                 # Typer entry — `serve <agent>` and `delegate <peer> <prompt>`
```

The runner abstraction (`protocol/cli_runner.py`) is intentionally CLI-agnostic — adapters provide their `cli_command_factory(prompt) -> argv` and `parse_event(dict) -> Artifact | None`. Adding a third peer (e.g. Codex) is a new `adapters/codex/` shim with two functions; no changes to the runner or dispatcher.

## Constitution gates

This package is governed by [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) v1.0.0. Every `/speckit-plan` run must satisfy:

1. **Spec-First Conformance** — A2A v1.0.0 wire format is authoritative; deviations require an ADR.
2. **Subagent Delegation** — every task in `tasks.md` has a named `@python-architect` / `@python-tester` / `main` owner.
3. **Contract Tests Before Implementation** — test files for any protocol surface land before the implementation.
4. **Reversible Config Changes** — v1 makes zero edits to `global/`.
5. **Minimal Skill & Agent Surface** — no new global skills/agents; `a2a-bridge` CLI is the only developer surface.

Zero spec deviations have been recorded in v1 implementation.

## Troubleshooting

- **`Adapter refuses to start: A2A_BEARER_TOKEN must be at least 32 characters`** — Generate a longer token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- **`fastapi.sse import fails`** — You're on FastAPI < 0.135. Run `uv sync --upgrade-package fastapi` to pull ≥0.135.
- **Real Gemini delegation returns "auth method not configured"** — Set `GEMINI_API_KEY` (see real-CLI test gating above).
- **Real Claude returns "Not logged in · Please run /login"** — Run `claude /login` interactively in a separate shell, then re-run.
- **Port 8765 / 8766 already in use** — Pass `--port <free-port>` to `a2a-bridge serve`.

## License

Internal personal-use repo. No license declared.
