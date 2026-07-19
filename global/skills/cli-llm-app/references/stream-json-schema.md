# Claude Code stream-json event schema

Reference for the NDJSON event format used when running:

```
claude --print --verbose --input-format stream-json --output-format stream-json …
```

Each line of stdin and stdout is a single JSON object. `--verbose` is required when combining `--print` with `--output-format stream-json` — the CLI errors out without it.

## Input events (you write to stdin)

### `user` — the only event the host ever needs to send

```json
{"type":"user","message":{"role":"user","content":"hello, who are you?"}}
```

- `content` can be a plain string. The richer block format (`[{type:"text",text:"…"}]`) also works but is unnecessary for text-only chat.
- One event per turn. Write the JSON + a trailing newline, then `flush()`. Do not close stdin between turns — the process exits when stdin closes.

## Output events (you read from stdout)

A typical turn produces roughly this sequence:

1. `system/hook_started` — internal hooks firing at session boot (first turn only).
2. `system/hook_response` — hook results (first turn only).
3. `system/init` — session metadata: cwd, session_id, model, tools, mcp_servers, plugins, memory_paths. Useful for confirming the model actually selected.
4. `assistant` — one or more events as the model generates. With `--include-partial-messages` you also get incremental chunks; without it, you get the final assembled assistant turn.
5. `rate_limit_event` — usage / limits update. Ignore for control flow.
6. `result` — the turn is complete. **This is the only event the host needs to wait for.**

### `result` — turn completion

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "api_error_status": null,
  "duration_ms": 2310,
  "duration_api_ms": 1880,
  "num_turns": 1,
  "result": "Hello! I'm a helpful assistant.",
  "stop_reason": "end_turn",
  "session_id": "…",
  "total_cost_usd": 0.0,
  "usage": { … },
  "modelUsage": { … },
  "permission_denials": [],
  "terminal_reason": "ok",
  "uuid": "…"
}
```

- `subtype` is `"success"` on a normal turn; other values indicate an error.
- `is_error` is the canonical failure flag.
- `result` is the plain-text assistant reply — what you'd get from `--output-format text`.
- `num_turns` increments each turn — proof that the session is multi-turn.
- `session_id` is stable across all turns of the same process.

### `assistant` — intermediate generation events

```json
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "Hello!"}
    ],
    …
  },
  "session_id": "…",
  "uuid": "…"
}
```

- Multiple `assistant` events per turn when the model thinks/streams.
- For non-streaming UIs: ignore these and read `result.result` instead — simpler and less error-prone.
- For streaming UIs: consume the `text` fields in order. Combined with `--include-partial-messages` you get token-by-token.

### Forwarded subagent messages (Claude Code 2.1.211+)

Add `--forward-subagent-text` when a stream-json host must expose nested-agent progress. If the harness cannot change argv, set `CLAUDE_CODE_FORWARD_SUBAGENT_TEXT=1`. Forwarded assistant/user messages carry a non-empty `parent_tool_use_id`, which distinguishes them from the parent conversation:

```json
{
  "type": "assistant",
  "parent_tool_use_id": "toolu_...",
  "message": {
    "role": "assistant",
    "content": [
      {"type": "thinking", "thinking": "Inspect the shared launcher first."},
      {"type": "text", "text": "The launcher is the common integration point."}
    ]
  }
}
```

- Preserve block order if the UI displays both text and thinking.
- Keep forwarded messages visually distinct from the parent assistant's answer.
- Continue using the top-level `result` event as the turn-completion signal.
- The reference persistent-session implementation disables all tools, so it cannot spawn subagents and does not need this opt-in.

### `system/init` — useful for verification

The init event lists the resolved `model`. After spawning, the first turn will trigger an init event whose `model` field tells you what the CLI actually picked. Log it. This is how to catch silent alias fallbacks (e.g. `--model haiku` resolving to Sonnet without complaint).

## Minimum host implementation

The reader thread needs only one line of logic:

```python
if event.get("type") == "result":
    result_queue.put(event)
```

Everything else can be discarded.

`ask(message)`:

```python
stdin.write(json.dumps({"type":"user","message":{"role":"user","content":message}}) + "\n")
stdin.flush()
result = result_queue.get(timeout=120)
if result.get("subtype") != "success" or result.get("is_error"):
    raise SessionError(result.get("result") or "unknown error")
return result["result"]
```

## Process lifecycle

- The subprocess stays alive as long as stdin is open and the process isn't externally killed.
- Closing stdin makes the CLI exit gracefully after flushing.
- A second `--verbose` is harmless; omitting it with `--print + stream-json` fails fast.
- `--no-session-persistence` means the conversation isn't written to disk — but the in-memory history within the live process IS preserved across turns. This is the property the persistent-session pattern relies on.
