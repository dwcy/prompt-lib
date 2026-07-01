# RAG Integration Options: Preprocess Hook vs MCP

**Date**: 2026-06-30
**Branch**: `task/rag-preprocess-options`
**Feature**: `009-okf-analytics-rag`

## Context

The 009 plan already chooses SQLite as the local OKF runtime index and context packs as the first RAG deliverable. The remaining architecture question is how agents should use that retrieval layer:

- run a pre-process automatically through Claude hooks
- expose retrieval through an MCP server
- keep it as Cabal/CLI only
- combine the above with clear ownership boundaries

Updated requirement from product discussion:

- Primary human user is the Cabal user.
- Claude and Cursor should both be able to use the retrieval layer.
- Cabal should make usage visible, so the user can see whether preflight/RAG actually ran and what it contributed.
- The feature is not driven by a current failure; the goals are token optimization, scope/complexity definition, and reducing hidden context sprawl.

Current code is partway there:

- `setup/src/cabal/okf/index.py` builds a SQLite index and FTS search helper.
- `setup/src/cabal/okf/analytics.py` implements graph/text analytics.
- `setup/src/cabal/okf/recommendations.py` has a lightweight graph-only recommender.
- `setup/src/cabal/okf/context.py` does not exist yet.
- `setup/src/cabal/okf/__main__.py` still exposes only `export`, `doctor`, `graph`, and `recommend`, while the 009 quickstart/contracts expect `index`, `search`, `analytics`, and `context`.
- `default_index_path()` currently returns `docs/okf/prompt-lib/index.sqlite`; the 009 plan/research say the mutable cache should default to `.cabal/okf/index.sqlite`.

Those gaps should be fixed before any hook or MCP integration becomes default behavior.

## Re-evaluation After Merging `main`

Merged local `main` (`9d564b8`) into this branch on 2026-07-01. The merge adds two relevant Cabal surfaces:

- **Claude Sessions dashboard** (`setup/src/cabal/views/sessions.py`, `session_reader.py`, `models/session.py`): Cabal can now parse Claude Code JSONL transcripts, show token/cost/tool/agent/hook activity, and correlate write-audit events.
- **Local Agent Services view** (`setup/src/cabal/views/services.py`, `service_catalog.py`, `service_supervisor.py`): Cabal can now present and supervise local runnable services such as `a2a-bridge` and `orchestrator`.

The OKF/RAG core did **not** materially change in the merge:

- `cabal.okf.context` is still absent.
- `python -m cabal.okf` still lacks `index`, `search`, `analytics`, and `context` commands.
- `default_index_path()` still points inside the OKF bundle instead of `.cabal/okf/index.sqlite`.

Impact on the recommendation:

- `okf-rag` should be treated like a **client-launched MCP server**, not a standalone daemon, unless it later grows into a long-running service. The merged Services spec explicitly keeps mcp-bus out of Local Agent Services because it already belongs in MCP tooling. `okf-rag` should follow that pattern.
- Cabal's MCP manager / `setup/mcp-templates.json` should own Claude/Cursor registration.
- Cabal's OKF Knowledge area should own preflight, context-pack inspection, and index freshness.
- The new Sessions dashboard can provide a Claude-specific proof-of-use cross-check by detecting `okf_*` MCP/tool calls in Claude transcripts.
- Cursor will not appear in Claude transcripts, so the MCP server must write its own local usage ledger for cross-client visibility.

## Decision Criteria

Any integration should:

- keep OKF Markdown/JSON as source of truth
- keep SQLite and analytics local/offline by default
- avoid injecting large context into every session
- be fast enough not to make Claude startup feel broken
- be opt-in when it adds a protocol surface or long-running work
- support query-specific retrieval with evidence and source paths
- be testable without a live Claude session
- work from more than one AI client, especially Claude and Cursor
- expose usage telemetry clearly enough that the Cabal user can verify adoption

## Option A: CLI/Cabal Only

Expose the planned commands:

```bash
python -m cabal.okf index docs/okf/prompt-lib --db .cabal/okf/index.sqlite
python -m cabal.okf search .cabal/okf/index.sqlite "query"
python -m cabal.okf analytics docs/okf/prompt-lib --db .cabal/okf/index.sqlite
python -m cabal.okf context .cabal/okf/index.sqlite "query" --format json
```

Pros:

- Lowest complexity and easiest to test.
- Matches the current 009 contracts.
- No Claude lifecycle coupling.
- No MCP protocol obligation.

Cons:

- Agents must know to call shell commands.
- Not naturally discoverable as a tool.
- Does not give a clean, typed retrieval interface to Claude.

Use this as the foundation regardless of the final integration choice.

## Option B: SessionStart Preprocess Hook

Add a `SessionStart` hook that detects prompt-lib/OKF and refreshes the local cache.

Possible behavior:

- if `docs/okf/prompt-lib/manifest.json` or `graph.json` is missing, emit a short hint to run Cabal export
- if source/bundle hashes changed, rebuild `.cabal/okf/index.sqlite`
- optionally write `.cabal/okf/analytics.json`
- emit concise additional context such as "OKF index is ready; use `/okf context <query>` or MCP tool"

Pros:

- Cache is likely warm before a retrieval request.
- Fits "pre-process" as index preparation, not as answer generation.
- Can reuse the existing hook gating pattern: `PROMPTLIB_HOOK_PROFILE=off` and `PROMPTLIB_DISABLED_HOOKS`.

Cons:

- Startup hooks must stay fast and non-disruptive.
- The query is not known at session start, so automatic context injection will be generic or noisy.
- Heavy export/index work inside hooks risks making every session feel slow.
- Hook output is not an interactive retrieval API.

Verdict:

Use a hook only as a lightweight freshness check or opt-in cache warmer. Do not use it as the primary RAG interface.

## Option C: PostToolUse or PreToolUse RAG Hook

Use a tool lifecycle hook to infer task intent, retrieve context, or refresh after file changes.

Pros:

- Can react to writes that change OKF sources.
- Could invalidate or refresh the cache after relevant edits.

Cons:

- PreToolUse hooks are for guarding, not enriching every request.
- PostToolUse hooks run frequently; indexing there would add hidden overhead.
- Query-specific RAG still has no clean user/tool invocation path.
- Higher risk of confusing side effects.

Verdict:

Avoid this for retrieval. At most, use PostToolUse to mark OKF cache stale after writes to `global/`, `setup/src/cabal/okf/`, or `specs/`, then rebuild lazily when a CLI/MCP request asks for retrieval.

## Option D: OKF RAG MCP Server

Add an opt-in local MCP server, for example `okf-rag`, exposing tools such as:

- `okf_prepare`: export/check/index the OKF bundle
- `okf_search`: FTS search concepts/chunks
- `okf_context_pack`: query plus graph expansion and evidence
- `okf_analytics`: graph health/overlap report
- `okf_explain_route`: explain why a skill routes to an agent
- `okf_usage`: recent tool calls, token estimates, cache hits, and included concepts

Pros:

- Best user/agent experience: retrieval is an explicit typed tool.
- Query-specific, so it avoids startup token bloat.
- Can return structured JSON with evidence paths and inclusion reasons.
- Discoverable through Cabal MCP manager and project `.mcp.json`.
- Works beyond Claude if other MCP clients are used later.
- Gives Claude and Cursor the same retrieval contract instead of separate integrations.

Cons:

- MCP is a protocol surface; per constitution, contract tests are mandatory.
- Adds implementation and packaging decisions.
- If built in Python, likely needs an MCP SDK dependency or a carefully tested stdio JSON-RPC implementation.
- Should remain opt-in until stable, because global MCP tools affect every session where enabled.

Verdict:

Best primary interface after the CLI/context service exists. Make it opt-in (`default_enabled: false`) and register through `setup/mcp-templates.json` rather than hard-wiring it into `global/settings.json`. For Claude + Cursor usage, MCP should be the shared integration surface; Cabal should own install/registration and the visible usage ledger.

After the 2026-07-01 merge, do not place `okf-rag` in Local Agent Services by default. That screen is now for runnable local services. Client-launched stdio MCP servers belong in MCP tooling, with OKF-specific status and usage shown from Knowledge/OKF panels.

## Option D2: Client-Specific Rules or Hooks

Configure Claude and Cursor separately through their own rule/hook systems, asking each client to run Cabal commands or read OKF context.

Pros:

- Faster to prototype for one client.
- Can express client-specific prompting conventions.

Cons:

- Duplicates behavior across Claude and Cursor.
- Harder to prove both clients used the same retrieval logic.
- Harder to collect comparable usage telemetry.
- Risks token-heavy auto-injection through prompt rules instead of explicit retrieval.

Verdict:

Use client-specific rules only as thin installation hints: "the `okf-rag` MCP server is available; prefer `okf_context_pack` for prompt-lib context." Do not implement core retrieval separately per client.

## Option E: Hybrid

Recommended architecture:

1. Build the core service and CLI first.
2. Add lazy freshness logic shared by CLI and MCP.
3. Add an opt-in MCP server for query-time retrieval.
4. Add a lightweight hook only for stale detection or warm-cache hints.

Ownership split:

- `cabal.okf.index`: SQLite schema, rebuild, FTS search.
- `cabal.okf.context`: context-pack construction from FTS hits, graph neighbors, and evidence.
- `cabal.okf.prepare`: freshness checks, source/bundle hashes, cache paths, optional analytics JSON.
- `cabal.okf.preflight`: task scope/complexity classification and tiny context plan.
- `cabal.okf.usage`: append-only local usage ledger for CLI/MCP/preflight calls.
- `python -m cabal.okf`: stable testable CLI.
- `okf-rag` MCP server: thin adapter over the service layer.
- Cabal MCP manager / `setup/mcp-templates.json`: registration and configured/unconfigured status for Claude and Cursor.
- Cabal Knowledge / OKF panels: preflight, context pack inspection, index freshness, and usage summaries.
- Cabal Sessions: Claude-specific verification that `okf_*` calls appeared in Claude transcripts.
- `global/hooks/okf_cache_hint.py`: optional lightweight hint/stale marker, not retrieval.

This keeps the implementation testable and prevents hooks from becoming a hidden RAG runtime.

## Visibility and Proof of Use

Cabal should show a small "RAG / Preflight Usage" panel so the user can verify whether Claude or Cursor actually used the system.

Use two evidence sources:

- **Local OKF usage ledger**: written by CLI/preflight/MCP paths for all clients, including Cursor.
- **Claude Sessions parser**: cross-check Claude Code transcripts for `okf_*` tool calls, token usage, and surrounding session context.

Suggested ledger fields:

- timestamp
- client: `cabal`, `claude`, `cursor`, or `unknown`
- entrypoint: `preflight`, `cli`, `mcp`
- tool/action: `okf_prepare`, `okf_search`, `okf_context_pack`, `okf_analytics`
- query/task summary hash plus short redacted preview
- selected budget: `tiny`, `focused`, `full`
- included concept ids
- evidence edge count
- estimated output tokens
- cache state: `fresh`, `rebuilt`, `stale`, `missing`
- duration milliseconds

Suggested Cabal views:

- **Preflight card**: scope tier, risk flags, recommended context budget, and "used OKF index: yes/no".
- **Usage timeline**: recent Claude/Cursor/Cabal retrieval calls.
- **Context pack inspector**: which concepts were included, why, and how many tokens were emitted.
- **Adoption health**: "Cursor configured", "Claude configured", "last successful MCP call", "last Claude transcript match", "index freshness".

The existing Claude Sessions screen should not become the primary RAG dashboard. It should link to or annotate OKF usage when it sees `okf_*` calls. The OKF Knowledge area should remain the primary place for RAG setup, preflight, context-pack inspection, and cross-client usage.

This matters because "automatic" behavior without visible proof will feel untrustworthy. If usage is visible, auto can stay conservative while explicit context packs stay inspectable.

## Recommended Implementation Order

1. Fix the 009 CLI gap: expose `index`, `search`, `analytics`, and `context` in `setup/src/cabal/okf/__main__.py`.
2. Move the default mutable index path to `.cabal/okf/index.sqlite`, while still allowing `--db`.
3. Implement `cabal.okf.context` to satisfy `contracts/context-pack.contract.md`.
4. Add `prepare`/freshness logic with a manifest hash and clear stale/ready states.
5. Add `preflight` logic for scope/complexity classification and tiny context plans.
6. Add `usage` ledger writes for CLI/preflight calls.
7. Add tests for cache path policy, stale detection, context-pack JSON, preflight tiers, usage ledger shape, and CLI behavior.
8. Add an opt-in `okf-rag` MCP server with contract tests for each tool schema.
9. Add `setup/mcp-templates.json` entry with `default_enabled: false`.
10. Add Cabal MCP/Known Tools visibility for `okf-rag` registration status; do not duplicate it in Local Agent Services unless it becomes a daemon.
11. Expand the OKF Knowledge area with preflight, index freshness, context pack inspector, and cross-client usage timeline.
12. Extend Claude Sessions parsing/display only enough to flag `okf_*` calls and link back to the OKF usage view.
13. Only then consider a hook that emits a concise freshness hint or marks the cache stale after OKF-relevant writes.

## Recommendation

Use the hybrid design.

The pre-process should mean "prepare or refresh the local OKF cache," not "inject RAG context into every session." The RAG interface should be MCP once the core CLI/context service is stable, because retrieval is query-specific and should be an explicit tool call. Hooks are still useful, but only around freshness and ergonomics.

Short version:

- CLI/service is the foundation.
- MCP is the primary retrieval interface for Claude and Cursor.
- Cabal is the control plane and usage dashboard.
- Hook is optional cache hygiene.
- Usage telemetry is mandatory for trust.
- Embeddings remain later and optional.
