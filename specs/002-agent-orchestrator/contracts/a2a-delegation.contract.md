# Contract — A2A delegation (CONSUMER side)

**Surface**: A2A v1.0.0 wire protocol, consumed via `a2a_bridge.client.delegation.DelegationClient`.
**Direction**: OUTBOUND. The orchestrator **calls** the bridge client; the bridge client posts the actual A2A wire to a peer adapter.
**Canonical wire spec**: <https://a2a-protocol.org/latest/specification/> v1.0.0 (released 2026-03-12)
**Owning contract**: [`specs/001-a2a-bridge/contracts/`](../../001-a2a-bridge/contracts/) (Agent Card, JSON-RPC envelope, SSE event ordering, error codes)
**Contract test**: `services/orchestrator/tests/contract/test_a2a_delegation_consumer.py`

This contract pins ONLY the consumer-side shape: what the orchestrator passes into `DelegationClient` and what it expects out. Wire-format conformance for A2A v1.0.0 itself is owned by feature `001-a2a-bridge` and is NOT re-tested here.

---

## Construction

```python
from a2a_bridge.client.delegation import DelegationClient

client = DelegationClient(
    peer_url=config.a2a_peer_url,            # e.g. "http://127.0.0.1:8765"
    bearer_token=config.a2a_bearer_token,    # required, validated by the peer adapter
    request_timeout=120.0,                   # seconds; per-task timeout, locks v1
)
```

The orchestrator constructs ONE `DelegationClient` per running daemon and reuses it for every PR-review run. The client is async-context-managed in `daemon.py`.

---

## `delegate(prompt)` invocation

```python
async with client:
    async for event in client.delegate(prompt=built_prompt):
        await handle_event(event)
```

**Optional `cwd` keyword (worktree-enabled deployments only)**: When `ORCHESTRATOR_WORKTREE_ENABLED=true`, `agents/pr_review.py` passes `cwd=<worktree path>` so the peer adapter spawns its CLI subprocess inside the per-PR worktree. v1 PR-review path always passes `cwd=None`, preserving wire conformance with A2A v1.0.0. See [`../../001-a2a-bridge/contracts/adr-cwd-extension.md`](../../001-a2a-bridge/contracts/adr-cwd-extension.md).

**Built prompt** (from `agents/pr_review.py`):

```text
You are reviewing a pull request on `<owner/repo>`.

PR number: #<n>
PR title: <title>
Branch: <headRefName> → <baseRefName>
Author: @<author.login>
URL: <pr.url>

Diff:
```
<output of `gh pr diff <n>`>
```

Use the existing `/review` skill to produce a review comment. Output ONLY the
review comment text — no preamble, no metadata, no markdown code-fences around
the entire response. The orchestrator will pass your output verbatim to
`gh pr review --comment -F -`.

If the diff is empty or unreviewable (binary-only, etc.), output a single line:
"NO_REVIEW: <one-line reason>"
```

The orchestrator detects the `NO_REVIEW:` sentinel and emits `run.skipped` with `reason="agent_declined"` instead of posting.

---

## Expected event stream (v1 consumer-side shape)

`client.delegate()` yields a sequence of events. The orchestrator handles these kinds (others are passed through to the eventlog as-is, level=info):

| Event kind (consumer view) | Required? | Orchestrator action |
|---|---|---|
| `state` with `state="submitted"` | YES — exactly once | Emit `agent.state` event with payload. |
| `state` with `state="working"` | optional, ≥0 | Emit `agent.state` event. |
| `message` (partial or final) | ≥1 | Append `text` chunk to the running review buffer; emit `agent.message`. |
| `state` with `state="completed"` | YES — exactly once on success | Treated as the run-complete signal. The accumulated message buffer is the review text. |
| `state` with `state="failed"` | terminal on failure | Emit `run.failed` with the failure reason from the event payload; do NOT post a comment. |
| `state` with `state="cancelled"` | terminal on cancel | Emit `run.failed` with `error="cancelled by peer"`; do NOT post. |
| Any other event kind | optional | Emit `agent.<kind>` event with raw payload, level=info. |

If `delegate()` raises (network error, bearer mismatch, peer unreachable):
- Emit `run.failed` with `stage="delegate"` and the exception message (truncated to 200 chars).
- Do NOT post a comment.

Stream MUST close cleanly — the orchestrator consumes via `async for` and expects the iterator to terminate after the terminal `state` event.

---

## What we deliberately do NOT depend on

- The exact JSON-RPC method names on the wire (`tasks/sendSubscribe`, etc.) — those are the bridge's contract, not ours.
- The SSE framing format (event-id, retry, etc.) — also the bridge's contract.
- The Agent Card discovery flow — v1 hardcodes the peer URL via env var; we don't fetch the Agent Card. (v2 may.)
- Streaming token deltas being byte-aligned — `message` events may arrive as partial chunks; we concatenate.
- Any specific upper bound on the number of `state="working"` events — agents may emit many, none, or one.

---

## What we depend on (locked v1 invariants)

The orchestrator's correctness assumes:

1. The bridge raises a typed exception (or a clearly-shaped error) on auth failure rather than silently producing an empty stream.
2. The terminal `state` event is the LAST event yielded by the iterator (no events after `completed`/`failed`/`cancelled`).
3. `message` events emit `text` strings encoded as UTF-8.
4. The bridge client respects `request_timeout` and raises (or yields a `failed` state) when the peer hangs past it.

If any of these change, this contract — and the consumer test — must be updated.

---

## Contract test outline

```python
# tests/contract/test_a2a_delegation_consumer.py

# Uses a FakeDelegationClient (in-test stub) that yields canned event sequences.
# Does NOT spin up a real A2A adapter — wire-format conformance lives in 001-a2a-bridge.

def test_consumer_handles_minimal_success_sequence(): ...           # submitted → message → completed
def test_consumer_concatenates_partial_message_chunks(): ...
def test_consumer_emits_agent_state_for_each_state_event(): ...
def test_consumer_treats_failed_state_as_terminal(): ...
def test_consumer_treats_cancelled_state_as_terminal(): ...
def test_consumer_propagates_unknown_event_kinds_with_agent_prefix(): ...
def test_consumer_emits_run_failed_when_delegate_raises(): ...
def test_consumer_truncates_exception_message_in_failure_payload(): ...
def test_consumer_handles_no_review_sentinel_as_skipped(): ...
def test_consumer_does_not_post_when_terminal_state_is_failed(): ...
def test_consumer_does_not_post_when_terminal_state_is_cancelled(): ...
```

Implementation tasks for `agents/pr_review.py` MUST be ordered AFTER these contract tests in `tasks.md`.
