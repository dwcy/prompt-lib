# Contracts — Agent Orchestrator (002)

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md) | **Research**: [../research.md](../research.md)
**Date**: 2026-05-10

Per Constitution Principle III, every external protocol surface this feature consumes or produces gets a contract document here, and a contract test in `tests/contract/` is written and observed failing before the implementing code is written.

The orchestrator is a **consumer** of every external surface in v1 — it does not implement any wire protocol as a server. The contracts below pin our parser/builder against the documented external schemas.

| Surface | Direction | Contract document | Contract test |
|---|---|---|---|
| `gh pr list --json …` output | INBOUND (we parse) | [`gh-pr-list.contract.md`](./gh-pr-list.contract.md) | `tests/contract/test_gh_pr_list_schema.py` |
| ntfy.sh HTTP publish | OUTBOUND (we POST) | [`ntfy-publish.contract.md`](./ntfy-publish.contract.md) | `tests/contract/test_ntfy_publish_request.py` |
| A2A v1.0.0 delegation client | OUTBOUND (we call `DelegationClient`) | [`a2a-delegation.contract.md`](./a2a-delegation.contract.md) | `tests/contract/test_a2a_delegation_consumer.py` |

---

## Conformance scope per surface

### `gh pr list --json …`

We depend on the documented `--json` field schema for `gh pr list` and `gh pr view`. We do NOT depend on the human-readable terminal output of either command. Our parser accepts unknown fields (forward-compatible) and rejects missing required fields (loud failure). When `gh` adds new fields, our test stays green; when `gh` renames or removes a field we depend on, the contract test fails before the daemon is dispatched.

### ntfy.sh HTTP publish

We conform to the publish API at `POST https://ntfy.sh/<topic>` per <https://docs.ntfy.sh/publish/>. We use only the documented headers (`Title`, `Priority`, `Tags`, `Click`) and a UTF-8 plain-text body — no JSON publish endpoint, no email forwarding, no actions, no attachments. Self-hosted ntfy with the same publish API is supported by changing `ORCHESTRATOR_NTFY_BASE`.

### A2A delegation (consumer side)

The orchestrator imports `a2a_bridge.client.delegation.DelegationClient` from the sibling package and consumes its async iterator of typed events (`message`, `state`, `complete`). Wire-format conformance for A2A v1.0.0 is owned by `001-a2a-bridge`'s contracts (see `specs/001-a2a-bridge/contracts/`); our contract here pins only the consumer-side shape — what we pass in, what we expect out, and how we reconcile failure modes.

---

## What is NOT a Gate-3 contract surface (and why)

These are internal Python interfaces, NOT external protocol surfaces. They are tested by ordinary unit tests, not contract tests:

- **The `Trigger` Protocol** (`triggers/base.py`) — typing.Protocol, in-process Python. No wire format.
- **The `eventlog` read API** (`eventlog.tail_since`, `eventlog.runs_summary`) — Python function signatures, no wire format. The SQLite schema is internal data storage, not an external surface.
- **The `Notifier` class API** — internal Python.
- **Inter-process IPC between daemon and dashboard** — there isn't any: they share the SQLite database file. The "contract" between them is the SQLite schema documented in `data-model.md`.

If any of these are ever exposed across a process boundary in a future version (e.g., the dashboard talks to the daemon over JSON-RPC instead of via SQLite), they get promoted to Gate 3 and a contract document gets added here.
