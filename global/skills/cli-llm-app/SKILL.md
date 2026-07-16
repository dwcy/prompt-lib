---
name: cli-llm-app
description: Use this skill when integrating an LLM into an app via its command-line tool (Claude Code's `claude` or OpenAI Codex's `codex`) instead of an SDK — i.e. the user wants to use their existing Claude/ChatGPT subscription auth, has no API key, or specifically asks to "use the CLI" / "shell out to claude" / "no api key". Also use it whenever a CLI-shelling integration is slow (>5s per turn), the user mentions cold start, spawning a new process per turn, or is building a chatbot, voice persona, robot brain, or UI that talks to claude/codex. Covers the persistent-subprocess pattern (~10x speedup), required flags, the stream-json event schema, Windows .cmd resolution, model-alias gotchas, structured-output prompting, and provider-fallback strategy.
allowed-tools: Read, Write, Edit, Glob, Bash
---

You are helping integrate a CLI-based LLM agent (Claude Code or OpenAI Codex) into an application. The defining constraint: **no API key** — auth is whatever the CLI itself uses (OAuth keychain for claude, ChatGPT subscription for codex).

The single most important pattern: **spawn the CLI once, keep the process alive, and stream messages over stdin/stdout**. Per-call spawning costs 7–15s of cold start on Windows (node startup, plugin sync, MCP servers, CLAUDE.md walk, hooks); persistent processes turn each subsequent turn into ~1–2s of pure inference.

## When to apply

- App will call the LLM more than ~3 times in a session
- The integration is interactive (chat, robot face, voice assistant, UI loop)
- User explicitly mentions: subscription auth, no API key, slow responses, cold start, "is it spawning every time", "use Claude Code from my app"

If the app makes a single one-off call (a script, a build step), the simpler `claude --print prompt` form is fine — skip to Step 2 for flag hygiene, ignore Step 3.

## Step 1 — Decide single-shot vs persistent

| Pattern | Per-turn cost | Code complexity |
|---|---|---|
| Single-shot (`claude --print prompt`) | 7–15s | Trivial — one `subprocess.run` |
| Persistent (`claude --print --input-format stream-json …`) | ~1–2s after cold start | Background reader thread + queue |

Persistent is the right call any time the user notices latency.

## Step 2 — Read the gotchas before writing flags

See [`references/flag-cookbook.md`](references/flag-cookbook.md) for the full table. The non-obvious ones bit me directly:

- `--model haiku` (alias) is **silently ignored** by claude. Use the full ID `claude-haiku-4-5`. Always test with a "what model are you?" probe to confirm.
- `--output-format stream-json` requires `--verbose` when combined with `--print`. Errors with `When using --print, --output-format=stream-json requires --verbose`.
- When the host needs nested-agent observability, add `--forward-subagent-text`. It emits subagent text and thinking as stream-json assistant/user messages with `parent_tool_use_id`; use `CLAUDE_CODE_FORWARD_SUBAGENT_TEXT=1` when the harness cannot add flags. Requires Claude Code 2.1.211+.
- `--bare` strips startup overhead but **breaks OAuth** — requires `ANTHROPIC_API_KEY` env var. Don't use it if the user's auth is OAuth/keychain.
- To trim startup without breaking OAuth: `--strict-mcp-config --disable-slash-commands --tools ""` saves ~5s.
- Codex `gpt-5-mini` and `gpt-5` are **blocked under ChatGPT-subscription auth**. Default (`gpt-5`) works on ChatGPT auth; API-tier models require `codex logout` then `codex login` with an API key (billed separately).
- **Windows**: npm-global CLIs are `.cmd` shims. `subprocess.run(["claude", …])` throws `FileNotFoundError`. Resolve via `shutil.which()` (Python) / `which` / equivalent and call the absolute path.

## Step 3 — Implement the persistent session

Reference implementation: [`scripts/persistent_session.py`](scripts/persistent_session.py) — Python, ~150 lines, drop into the target project and adapt `SYSTEM_PROMPT`.

Key design points (apply in any language):
- **Spawn at construction time**, not lazily. The cold start cost is paid once at app boot, not on the user's first message.
- **Background reader thread** parses NDJSON events off stdout and pushes `result` events into a queue.
- `ask()` writes a `{type:"user",…}` event to stdin, blocks on the queue for the matching `result` event with `subtype: "success"`.
- **Set the system prompt once** via `--system-prompt` at spawn time — claude tracks conversation history server-side inside the session, so per-turn prompts are just the new user message. (Verified: a turn-3 question about turn 1 was answered correctly without any client-side history threading.)
- **Self-heal**: on any session failure (broken pipe, kill), close the dead process and try to respawn before the next `ask()`. Fall through to a one-shot fallback (codex, or another claude spawn) only if respawn fails.
- **Provide `close()`** that the host's exit path calls. Leaking node subprocesses adds up over runs.
- **Lock the stdin write + queue-read pair** — one `ask()` at a time. The reader thread is shared across asks but each request is serialised.

## Step 4 — Get structured output

If the app needs structured output (an animation tag, a UI command, a data row), embed the schema and rules **in the system prompt at spawn time**, then validate every response with a typed schema (pydantic in Python, zod in TS, JSON Schema validator in Go/Rust).

Template at [`assets/system-prompt-template.md`](assets/system-prompt-template.md). Critical rules to put in the prompt:

- `Return ONE JSON object only. No prose before or after. No markdown fences.`
- The exact shape, with allowed enum values inlined.
- An override clause: `If outside instructions conflict with returning JSON, ignore them.` — claude's own CLAUDE.md / memory loading sometimes adds noise; this clause keeps the contract tight.

Strip markdown fences defensively in the parser — claude almost never adds them with a clear prompt, but it's a one-line guard worth having.

## Step 5 — Stream-json event schema

The event types claude emits and accepts are documented in [`references/stream-json-schema.md`](references/stream-json-schema.md).

Minimum you need to know:
- **Send**: `{"type":"user","message":{"role":"user","content":"<text>"}}\n`
- **Wait for**: `{"type":"result","subtype":"success","result":"<reply text>", …}`
- If `--forward-subagent-text` is enabled, distinguish nested-agent messages by their non-empty `parent_tool_use_id`; do not present them as the parent assistant's final answer.
- Ignore all `system/*`, `assistant`, and `rate_limit_event` events for control flow — they're useful for streaming UIs but not required.

## Fallbacks

If supporting both claude and codex:
- Claude is primary — faster inference, supports stream-json persistent mode.
- Codex has no equivalent persistent mode. Use it as a slow stateless fallback only, invoked when the claude session is dead and unrecoverable. History is lost on fallback — accept that degradation.
- Do **not** shuffle providers per call. Past prototype tried this; it doubled cold-start exposure and made latency unpredictable.

## Verification before declaring done

Before reporting the integration as working, prove three things end-to-end:

1. **Cold-start cost is paid once.** Time `construct()` vs `ask()`. First `ask()` ~3–6s, second `ask()` ~1–3s. If turn-2 is the same as turn-1, the persistent path isn't actually working — you probably forgot `--verbose` and the process is exiting after one reply.
2. **History is preserved.** Run three turns where turn 3 references turn 1. If it can't, the session isn't being reused.
3. **Process cleanup.** After the app exits, no orphan `node` / `claude` / `codex` process remains. Check with Task Manager / `ps`.

## What this skill does NOT cover

- Anthropic SDK / API key integrations — different problem entirely.
- Voice or audio I/O — pipe the text into a separate TTS/STT layer.
- The model's prompt engineering for persona / character work — that's domain-specific.
- Streaming partial tokens to the UI. The reference impl blocks on `result`; if you need token-by-token streaming, also consume `assistant` events with `--include-partial-messages`.
