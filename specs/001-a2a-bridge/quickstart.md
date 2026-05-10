# A2A Bridge v1 — Quickstart

**Feature**: A2A Bridge for Multi-Agent CLI Delegation (v1)
**Audience**: A developer with this repo cloned who wants to verify the bridge works end-to-end on their laptop.
**Scope**: P1 (outbound Claude → Gemini delegation) and P2 (inbound Claude adapter receives a curl task). P3 (Agent Card fetch) is exercised as part of P2 verification.

Time budget: 10 minutes from clone-with-deps-installed to a successful delegation.

---

## Prerequisites

- This repo cloned and on branch `001-a2a-bridge`
- Python 3.13 on PATH
- `uv` on PATH (`pip install uv` if missing)
- Claude Code CLI (`claude`) on PATH
- Gemini CLI (`gemini`) on PATH
- A free TCP port at 8765 and 8766 on `127.0.0.1`

---

## Step 1 — Install dependencies

```bash
cd services/a2a-bridge
uv sync
```

This creates `.venv/` inside `services/a2a-bridge/` and installs `fastapi`, `httpx`, `uvicorn`, `pydantic`, `a2a` (the official `a2a-python` SDK, used in tests), and the dev dependencies.

---

## Step 2 — Configure the shared bearer token

The token is read from `A2A_BEARER_TOKEN`. Generate a strong one:

```bash
# bash
export A2A_BEARER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

# PowerShell
$env:A2A_BEARER_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
```

For the v1 demo we use the same token for both peers (set the variable in every shell that runs an adapter or the delegation CLI). The adapters compare with constant-time HMAC and reject any mismatch with HTTP 401.

> Adapters refuse to start if `A2A_BEARER_TOKEN` is unset or shorter than 32 chars.

---

## Step 3 — Start the Claude Code adapter

In a dedicated terminal:

```bash
cd services/a2a-bridge
uv run a2a-bridge serve claude --port 8765
```

You should see:

```
[2026-05-10T14:00:00Z] adapter=claude-code listen=127.0.0.1:8765 cli=/usr/bin/claude timeout=300s
[2026-05-10T14:00:00Z] agent-card published at /.well-known/agent-card.json
[2026-05-10T14:00:00Z] ready
```

---

## Step 4 — Start the Gemini adapter

In a second terminal:

```bash
cd services/a2a-bridge
uv run a2a-bridge serve gemini --port 8766
```

You should see the same `ready` line for `adapter=gemini`.

---

## Step 5 — Verify the Agent Card (P3)

In a third terminal:

```bash
curl -s http://127.0.0.1:8765/.well-known/agent-card.json | python -m json.tool
```

Expected: a JSON document with `name`, `version`, `protocols: ["json-rpc-2.0"]`, `capabilities.streaming: true`, `authentication.schemes: ["bearer"]`. Repeat for port 8766 to confirm Gemini's card.

This satisfies SC-004 (Agent Card validates against schema).

---

## Step 6 — Send a task to the Claude adapter via curl (P2)

```bash
curl -N -H "Authorization: Bearer $A2A_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST http://127.0.0.1:8765/jsonrpc \
     -d '{
           "jsonrpc": "2.0",
           "id": "demo-1",
           "method": "tasks/sendSubscribe",
           "params": {
             "task": {
               "messages": [{"role": "user", "content": "Reply with the single word: pong"}]
             }
           }
         }'
```

`-N` disables curl's response buffering so SSE events appear as they arrive. Expected event sequence:

```
event: task.state
data: {"task_id":"...","state":"submitted","ts":"..."}

event: task.state
data: {"task_id":"...","state":"working","ts":"..."}

event: task.artifact
data: {"task_id":"...","artifact":{"kind":"text","mime_type":"text/plain","content":"pong"}}

event: task.state
data: {"task_id":"...","state":"completed","ts":"..."}
```

This satisfies SC-003 (curl can drive the adapter without ad-hoc protocol knowledge).

---

## Step 7 — Delegate from Claude → Gemini (P1, headline demo)

Without leaving the third terminal:

```bash
uv run a2a-bridge delegate gemini "Summarise the contents of this directory in one sentence" \
    --peer http://127.0.0.1:8766
```

This invokes the DelegationClient. It reads `A2A_PEER_BEARER_TOKEN` (or falls back to `A2A_BEARER_TOKEN`), opens an SSE stream to `http://127.0.0.1:8766/jsonrpc`, sends `tasks/sendSubscribe`, prints streamed task updates as they arrive, and exits 0 on `completed`.

Expected: the Gemini adapter spawns `gemini -p "..." --output-format stream-json`, the response streams back, and you see the final summary in your terminal within 30 seconds (matches SC-001).

Failure modes you can deliberately trigger to verify SC-006:
- Stop the Gemini adapter (Ctrl-C in its terminal), re-run the delegate command — should fail within 5 seconds with `connect refused`.
- Set `A2A_PEER_BEARER_TOKEN=wrong` and re-run — should fail within 5 seconds with `auth failed (401)`.

---

## Step 8 — Run the contract test suite

```bash
cd services/a2a-bridge
uv run pytest -m contract
```

Expected: every contract test (Agent Card schema, JSON-RPC envelope, `tasks/sendSubscribe` event sequence, error codes for malformed input) passes. These are the tests that satisfy Constitution Principle III (contract tests for protocol surfaces).

---

## Step 9 — (Optional) Open the Inspector for manual conformance check

```bash
git clone https://github.com/a2aproject/a2a-inspector ~/tools/a2a-inspector
cd ~/tools/a2a-inspector
uv sync
( cd frontend && npm install )
# follow inspector's README to start backend + frontend
```

Open `http://127.0.0.1:5001`, point it at `http://127.0.0.1:8765`, fetch the Agent Card, send a chat message. Confirm the validation panel reports zero violations. This is the manual verification step for SC-002 — record the result in the v1 release notes.
