# Feature Specification: A2A Bridge for Multi-Agent CLI Delegation (v1)

**Feature Branch**: `001-a2a-bridge`
**Created**: 2026-05-10
**Status**: Draft
**Input**: User description: "Multi-agent A2A bridge so Claude Code, Gemini CLI, and Codex CLI can delegate tasks to each other"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Outbound Delegation: Claude → Gemini (Priority: P1) 🎯 MVP

A developer working inside Claude Code asks Claude to delegate a task to a peer Gemini agent (for example, "have Gemini summarise this codebase for the architecture review"). Claude packages the task as an A2A request, sends it to a locally running Gemini A2A adapter, streams progress updates back to the developer, and surfaces the final artifact in the Claude Code session.

**Why this priority**: This is the headline capability of the bridge. Without it, no value is delivered. Every other story exists to support, validate, or extend this flow.

**Independent Test**: With the Gemini-side A2A adapter running on localhost and a valid bearer token configured, a developer triggers a delegation from Claude Code with a one-line prompt. The developer sees streamed progress and a final artifact within the configured per-task timeout.

**Acceptance Scenarios**:

1. **Given** the Gemini A2A adapter is running and reachable on localhost, **When** the developer triggers a delegation with a prompt, **Then** Claude posts a spec-compliant JSON-RPC 2.0 task and begins receiving streaming updates over the A2A wire.
2. **Given** the peer adapter has produced an artifact and reported task completion, **When** the stream closes, **Then** the developer sees the artifact rendered in the Claude Code session along with a clear completion indicator.
3. **Given** the peer adapter is unreachable (process not running, port refused, or bearer token mismatch), **When** the developer triggers a delegation, **Then** Claude surfaces an actionable error containing the failed endpoint, the failure mode (connect / auth / parse), and the underlying status code or exception within 5 seconds.

---

### User Story 2 — Inbound Task Reception by Claude Code Adapter (Priority: P2)

A developer starts the Claude Code A2A adapter locally. An external client (initially `curl` during development, eventually a peer agent such as Gemini) sends a JSON-RPC task to the adapter. The adapter authenticates the request, executes the task by invoking the Claude Code CLI locally, streams progress as A2A task updates over Server-Sent Events, and returns the final artifact.

**Why this priority**: Claude Code must be a peer in the mesh, not only a caller. Once Story 1 proves the wire format works for one direction, Story 2 makes the bridge bidirectional and enables every future peer to invoke Claude Code symmetrically.

**Independent Test**: Start the Claude Code adapter on localhost with a known bearer token. Use `curl` to POST a JSON-RPC task with a trivial prompt. Verify the SSE event stream contains spec-compliant task lifecycle events and a final artifact event matching the A2A spec.

**Acceptance Scenarios**:

1. **Given** the Claude Code adapter is running and a valid bearer token is supplied, **When** a JSON-RPC task arrives, **Then** the adapter responds with a task id and begins streaming SSE updates that pass A2A schema validation.
2. **Given** the task completes successfully, **When** the underlying CLI emits final output, **Then** the adapter emits a spec-compliant artifact event and closes the SSE stream cleanly.
3. **Given** the request lacks a bearer token or supplies the wrong one, **When** it arrives, **Then** the adapter rejects with HTTP 401 and emits no task lifecycle events.
4. **Given** the underlying CLI exits non-zero or hangs past the configured per-task timeout, **When** the adapter detects the failure, **Then** the adapter emits a spec-compliant `failed` or `cancelled` task state with the captured stderr or timeout reason, and closes the stream.

---

### User Story 3 — Agent Card Discovery (Priority: P3)

A developer or peer agent fetches the Agent Card from a running adapter via HTTP GET to discover what tasks the agent supports, what authentication scheme it expects, and what URLs to call.

**Why this priority**: Discovery is part of the A2A protocol and is essential for any non-trivial mesh. v1 callers can hardcode the peer endpoint, so this is not strictly required for the headline P1 demo — but the cost is low and the discovery surface must be in place before v2 can add a third peer.

**Independent Test**: Start any adapter. GET the canonical discovery path with no auth required. Verify the response is a JSON Agent Card that validates against the published A2A Agent Card schema.

**Acceptance Scenarios**:

1. **Given** an adapter is running, **When** the canonical discovery URL is fetched via HTTP GET, **Then** the adapter returns a JSON Agent Card containing the agent's display name, supported task types, capability flags, and the endpoint URLs for task submission.
2. **Given** the Agent Card is returned, **When** validated against the A2A Agent Card schema, **Then** validation passes with zero errors.

---

### Edge Cases

- Peer adapter is not running when delegation is triggered (TCP refused).
- Bearer token is missing or wrong on inbound or outbound traffic.
- Local CLI invocation hangs past the configured per-task timeout.
- Local CLI invocation exits non-zero mid-task or produces malformed output.
- Streaming HTTP / SSE connection drops mid-task on either side.
- Malformed JSON-RPC payload arrives (parse error, invalid method, missing required params).
- Two inbound tasks arrive simultaneously — each must get its own isolated CLI session and stream.
- Developer's prompt exceeds the peer agent's context window — the developer must see a clear, attributable error from the peer rather than a generic timeout.
- The CLI for the peer agent is not installed on the peer's host machine — the adapter must fail fast with a clear "CLI not available" diagnostic.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a JSON-RPC 2.0 over HTTP endpoint that conforms to the published A2A protocol specification, for each adapter shipped in v1.
- **FR-002**: System MUST publish an A2A Agent Card at the canonical discovery path for each running adapter, returning valid Agent Card JSON without authentication.
- **FR-003**: System MUST translate inbound A2A task requests into local Claude Code CLI invocations and emit spec-compliant streaming task lifecycle events (`submitted`, `working`, `completed` / `failed` / `cancelled`) and artifact events as the CLI produces output.
- **FR-004**: System MUST allow Claude Code to send an A2A task to a configured peer endpoint, receive streamed updates, and surface the resulting artifact in the developer's Claude Code session.
- **FR-005**: System MUST authenticate every inbound and outbound A2A request via a shared bearer token configured out-of-band (per-adapter); requests without a valid token MUST be rejected before any task lifecycle event is emitted.
- **FR-006**: System MUST log every inbound task receipt, every outbound delegation, every authentication failure, and every CLI exit (zero or non-zero) to stdout in a structured form that includes task id, peer identity, timestamp, and outcome.
- **FR-007**: System MUST reject malformed JSON-RPC payloads with the error codes defined in the JSON-RPC 2.0 spec, surfaced through the A2A response envelope.
- **FR-008**: System MUST cancel and report long-running CLI invocations that exceed a configurable per-task timeout, surfacing a spec-compliant `cancelled` task state with the timeout reason.
- **FR-009**: System MUST run as one or more standalone local processes on a developer's machine, requiring only localhost network access in v1; no cloud deployment, no LAN binding, no TLS termination.
- **FR-010**: System MUST NOT persist task state between restarts in v1 — task tracking is in-memory only and any in-flight task is lost on adapter restart.
- **FR-011**: System MUST handle concurrent inbound tasks by giving each its own isolated CLI process and streaming session; tasks must not share state.
- **FR-012**: Every deviation from the published A2A specification (extension, omission, reinterpretation) MUST be recorded as an ADR per Constitution Principle I — silent deviation is forbidden.

### Key Entities *(include if feature involves data)*

- **Agent Card**: JSON document describing an agent's identity, capabilities, supported task types, authentication requirements, and endpoint URLs. Fetched by other agents via the canonical well-known discovery path.
- **Task**: A unit of work submitted to an agent over the A2A wire. Has a unique id, request parameters, a lifecycle state (`submitted`, `working`, `completed`, `failed`, `cancelled`), and produces zero or more artifacts.
- **Artifact**: A structured output produced by a task — text content, a file reference, or structured data — emitted as part of the task event stream and surfaced to the calling agent.
- **Adapter**: The HTTP server wrapping a CLI agent. Receives A2A task requests, authenticates them, dispatches to the local CLI, and streams responses back over SSE.
- **Delegation Client**: The host-side component (within Claude Code's adapter or skill surface) that constructs an A2A task, sends it to a peer adapter's endpoint, reconciles streamed updates with the developer's session, and renders the final artifact.
- **Bearer Token**: Shared secret configured per adapter via out-of-band channel (environment variable). Used to authenticate every adapter-to-adapter request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer in Claude Code can delegate a task to a Gemini peer and receive the final artifact within 30 seconds for prompts under 1000 tokens.
- **SC-002**: The A2A surface exposed by every shipped adapter passes the official A2A test client / inspector with zero spec violations, OR each violation is recorded as an ADR per Constitution Principle I.
- **SC-003**: An external client using only `curl` and the published A2A spec can submit a task to Claude Code's adapter, receive a streaming response, and parse the final artifact without ad-hoc protocol knowledge.
- **SC-004**: An Agent Card fetched from any shipped adapter validates against the published A2A Agent Card schema without errors.
- **SC-005**: A developer can install and start an adapter on a clean machine that already has the underlying CLI installed in under 2 minutes from cloning the repo.
- **SC-006**: When the peer adapter is unreachable, returns a non-2xx, or rejects authentication, the developer sees a clear, attributable error in Claude Code within 5 seconds — no silent hangs, no opaque generic errors.
- **SC-007**: Concurrent inbound tasks (at least 3 in flight) complete independently, each producing its own correct artifact, with no cross-contamination of CLI state.

## Assumptions

- v1 ships only the Claude Code → Gemini direction for delegation, plus the Claude Code adapter for inbound traffic. Codex CLI support and a full mesh (Gemini → Claude, Codex ↔ either) are explicitly deferred to v2+.
- The bridge code lives within this repo under `services/a2a-bridge/`, not in a separate repository. Deploy story for the adapters is "developer starts a local process" — no cloud deployment, no daemonisation, no service manager integration in v1.
- Both peers run on the same developer machine (localhost) for v1 — no LAN, no public internet exposure, no TLS termination, no reverse proxy.
- Authentication is a shared bearer token, configured per adapter via environment variable. PKI / mTLS / OAuth are explicitly out of scope for v1.
- Each adapter wraps a single CLI agent. Concurrent inbound tasks each spawn their own CLI process — no pooling, no in-process reuse, no warm caches in v1.
- The runtime stack for the adapters (language, web framework, async model) is a planning-phase decision and is intentionally not specified here. The spec is runtime-agnostic.
- The developer ergonomics for *triggering* a delegation from Claude Code (slash command vs subagent vs hook vs skill) is a planning-phase decision and is intentionally not specified here.
- Logging is to stdout only. Structured log shipping, dashboards, distributed tracing, and persistent log storage are explicitly out of scope for v1.
- Persistent task storage, retries, durable queues, and at-least-once delivery are explicitly out of scope for v1. Tasks are best-effort, in-memory, single-attempt.
- The published A2A protocol specification is the authoritative reference; the canonical version and source URL will be recorded in `plan.md` research artifacts (Phase 0).
- The Gemini CLI and Codex CLI installed on the peer machine are recent enough to support headless invocation with a prompt argument. Validating CLI compatibility is part of the adapter's startup checks.
