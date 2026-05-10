# ADR — `cwd` extension on `tasks/sendSubscribe` task payload

**Status**: Accepted (v1, scaffolding)
**Date**: 2026-05-10
**Owner**: `@worktree-feature-architect` (003-worktree-manager, future)
**Affects**: `services/a2a-bridge/src/a2a_bridge/client/delegation.py`, `specs/001-a2a-bridge/contracts/jsonrpc-methods.md`, `specs/002-agent-orchestrator/contracts/a2a-delegation.contract.md`

## Context

A2A v1.0.0 §9 (JSON-RPC binding) defines the `tasks/sendSubscribe` task payload as `{ messages: [...] }`. Spec is silent on workspace / working-directory hints — the underlying agent picks its own cwd.

The 003-worktree-manager feature (PR-fix agent, follow-up to orchestrator v1) needs to direct the peer agent into a per-PR git worktree so concurrent runs don't race on `.git/index.lock`. The orchestrator computes the path; the peer adapter has no way to know it without a wire-level signal.

Per Constitution Principle I, "silent deviation [from a wire spec] is forbidden". This ADR records the deviation explicitly.

## Decision

Extend `tasks/sendSubscribe`'s `params.task` payload with an optional `cwd: string` field:

```json
{
  "method": "tasks/sendSubscribe",
  "params": {
    "task": {
      "messages": [...],
      "cwd": "/abs/path/to/worktree"
    }
  }
}
```

Semantics:

- **Optional**. Default `None` / absent — peer adapter behaves as v1.0.0 spec.
- **Type**: absolute filesystem path string. The receiving adapter MUST validate it exists and is a directory before spawning the CLI subprocess.
- **Direction**: client → server only. Echoed in `tasks/get` responses is OUT OF SCOPE for this ADR.
- **Failure mode**: an adapter that does not understand `cwd` MUST ignore the field (forward-compatible). An adapter that understands it but receives an invalid path MUST raise JSON-RPC error `-32602 Invalid params`.

## Why this shape

- **Additive** — `cwd: None` produces the exact v1.0.0 wire bytes. No existing client breaks.
- **Optional, not required** — keeps the orchestrator-v1 (PR-review) path completely untouched. Only the worktree-enabled deployment exercises this field.
- **Server-side validation** — fail-loudly on bad paths rather than letting the CLI subprocess die with a confusing error.

## Alternatives considered

1. **Pass `cwd` via a custom HTTP header.** Rejected — invisible to JSON-RPC envelope inspectors; not recoverable from a captured request body.
2. **Encode `cwd` inside the prompt text.** Rejected — couples agent prompt rendering to adapter cwd-resolution. The agent should not need to parse its own prompt for runtime hints.
3. **Add a brand-new method (`tasks/sendSubscribeAt`).** Rejected — duplicates 90 % of the existing method's semantics for one optional field.

## Conformance impact

- A2A v1.0.0 wire spec is unchanged in the absence of `cwd`. With `cwd` present, the orchestrator is a non-conformant client by the strictest reading. Acceptable per Constitution Principle I because (a) this ADR exists, (b) the deviation is documented in both contract files, (c) the feature is gated behind `ORCHESTRATOR_WORKTREE_ENABLED=false` by default.
- The 003-worktree-manager feature spec (TBD) is the long-term home for adapter-side validation and tests for this field.

## Reversal plan

If A2A v1.1+ adopts a different mechanism (e.g. a `workspace` capability descriptor on the Agent Card), drop the `cwd` field and migrate the worktree manager to populate the new field via the same opt-in flag. Backward compatibility break is acceptable because no client outside the worktree-enabled orchestrator deployment ever sets `cwd`.
