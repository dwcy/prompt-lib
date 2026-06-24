# orchestrator

Agent-orchestration daemon. Watches a configured GitHub repository, dispatches each opened or updated pull request to a peer Claude Code agent over the existing [A2A bridge](../a2a-bridge/), posts the agent's review back to the PR via the `gh` CLI, persists every state transition to an append-only SQLite event log, and notifies the operator on screen (Textual dashboard) and on phone ([ntfy.sh](https://ntfy.sh) push).

## Status

**v1 feature-complete and manually verified** — see [`specs/002-agent-orchestrator/tasks.md`](../../specs/002-agent-orchestrator/tasks.md) for the per-phase status. The real-repo verification pass (`tasks.md` T035) is complete; the remaining cross-service manual validation is the A2A Inspector pass tracked in [`specs/001-a2a-bridge/tasks.md`](../../specs/001-a2a-bridge/tasks.md) T039.

## Documentation

- **Spec**: [`specs/002-agent-orchestrator/spec.md`](../../specs/002-agent-orchestrator/spec.md) — user stories, requirements, success criteria
- **Plan**: [`specs/002-agent-orchestrator/plan.md`](../../specs/002-agent-orchestrator/plan.md) — tech stack, structure, constitution gate status
- **Quickstart**: [`specs/002-agent-orchestrator/quickstart.md`](../../specs/002-agent-orchestrator/quickstart.md) — operator setup walkthrough, end-to-end verification
- **Research**: [`specs/002-agent-orchestrator/research.md`](../../specs/002-agent-orchestrator/research.md) — locked tech decisions (R1–R10) with rationale
- **Data model**: [`specs/002-agent-orchestrator/data-model.md`](../../specs/002-agent-orchestrator/data-model.md) — entities, state machine, SQLite DDL
- **Contracts**: [`specs/002-agent-orchestrator/contracts/`](../../specs/002-agent-orchestrator/contracts/) — external surface conformance (gh CLI, ntfy, A2A consumer)
- **Tasks**: [`specs/002-agent-orchestrator/tasks.md`](../../specs/002-agent-orchestrator/tasks.md) — implementation breakdown

## What's in this directory

```
services/orchestrator/
├── pyproject.toml          # uv-managed; sibling path dep on ../a2a-bridge
├── .python-version         # 3.13
├── uv.lock
├── src/orchestrator/
│   ├── cli.py              # Typer entry: `orchestrator serve` / `orchestrator dash`
│   ├── config.py           # pydantic-settings; env-only
│   ├── daemon.py           # async dispatch loop + orphan recovery on startup
│   ├── eventlog.py         # SQLite WAL append-only event store; runs view; cursor table; orphan-recovery routine
│   ├── notifier.py         # ntfy.sh HTTP publisher; non-fatal failure semantics
│   ├── triggers/           # Trigger Protocol + GitHub poll source
│   ├── agents/             # PR-review agent (calls A2A DelegationClient)
│   └── dashboard/          # Textual TUI tailing the event log (read-only)
└── tests/
    ├── conftest.py         # tmp_db, fake_gh PATH-shim, fake_delegation_client factory
    ├── contract/           # Constitution Gate 3 — external wire conformance
    │   ├── test_gh_pr_list_schema.py
    │   ├── test_a2a_delegation_consumer.py
    │   └── test_ntfy_publish_request.py
    ├── integration/        # P1: real subprocess + ephemeral repo (INTEGRATION-gated). P2/P3: in-process.
    │   ├── test_p1_pr_review_end_to_end.py     # INTEGRATION=1
    │   ├── test_p2_dashboard_tail.py           # default
    │   ├── test_p3_phone_notification.py       # default
    │   └── test_p4_replayable_history.py       # INTEGRATION=1
    └── unit/
        ├── test_config.py
        ├── test_eventlog.py
        ├── test_notifier.py
        ├── test_orphan_recovery.py
        ├── test_pr_review.py
        ├── test_trigger_base.py
        └── test_github_poll.py
```

## Prerequisites

Install on the operator's machine, BEFORE first run:

- **Python 3.13+** with `uv` on PATH
- **`gh` CLI** authenticated (`gh auth status` shows logged in) with permission to post review comments on the watched repo
- **A peer Claude Code A2A adapter** running locally (started separately — see step 1 below)
- **A phone with the [ntfy app](https://ntfy.sh/app)** installed (iOS or Android), subscribed to your chosen topic

## How to run

Three terminals:

### Terminal 1 — A2A bridge

```bash
cd ../a2a-bridge
uv run a2a-bridge serve claude
```

Leave it running on `127.0.0.1:8765`.

### Terminal 2 — orchestrator daemon

Set the env vars in this shell only — the orchestrator NEVER reads or writes `.env` files.

**PowerShell:**

```powershell
$env:ORCHESTRATOR_REPO         = 'YOUR_GITHUB_USER/your-test-repo'
$env:ORCHESTRATOR_NTFY_TOPIC   = '<your-random-topic>'
$env:ORCHESTRATOR_POLL_SECONDS = '30'
$env:A2A_PEER_URL              = 'http://127.0.0.1:8765'
$env:A2A_BEARER_TOKEN          = '<token-matching-the-bridge>'

cd ../orchestrator
uv run orchestrator serve
```

**bash / zsh:**

```bash
export ORCHESTRATOR_REPO='YOUR_GITHUB_USER/your-test-repo'
export ORCHESTRATOR_NTFY_TOPIC='<your-random-topic>'
export ORCHESTRATOR_POLL_SECONDS=30
export A2A_PEER_URL='http://127.0.0.1:8765'
export A2A_BEARER_TOKEN='<token-matching-the-bridge>'

cd ../orchestrator
uv run orchestrator serve
```

### Terminal 3 — live dashboard

```bash
cd ../orchestrator
uv run orchestrator dash
```

The dashboard is read-only — it tails the SQLite event log written by the daemon. Safe to launch / close / relaunch any number of times without affecting the daemon.

### Trigger a review

In a fourth terminal, on the watched repo: push a branch and `gh pr create`. Within ~35 s the daemon dispatches the diff to the peer agent, the dashboard fills in, the phone buzzes "Reviewing PR #N", and once the agent finishes a review comment lands on the PR + the phone buzzes "Review posted on PR #N" with a clickable link.

See [`specs/002-agent-orchestrator/quickstart.md`](../../specs/002-agent-orchestrator/quickstart.md) for the full walkthrough including failure-path verification (peer down, daemon kill mid-run, dashboard auto-update).

## Development

```bash
cd services/orchestrator

uv sync                              # install + lock deps
uv run ruff check src tests          # lint
uv run pytest                        # contract + unit + non-gated integration tests
INTEGRATION=1 uv run pytest          # adds real-subprocess tests (P1 PR-review end-to-end, P4 replayable history); needs a real test repo, gh auth, A2A bridge running
```

`uv run pytest` baseline: ~168 passed, ~7 skipped (the skipped ones are `INTEGRATION`-gated).

## License

Same as the parent repository.
