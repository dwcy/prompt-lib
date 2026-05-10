# Contract — ntfy.sh HTTP publish (OUTBOUND POST)

**Surface**: ntfy.sh public push service publish API.
**Direction**: OUTBOUND. The orchestrator **POSTs** notification messages to ntfy.
**Canonical reference**: <https://docs.ntfy.sh/publish/>
**Contract test**: `services/orchestrator/tests/contract/test_ntfy_publish_request.py`

---

## Request shape

```http
POST /<topic> HTTP/1.1
Host: ntfy.sh
Content-Type: text/plain; charset=utf-8
Title: <UTF-8, ≤200 chars, no CR/LF>
Priority: <"3"|"4"|"5">
Tags: <comma-separated emoji or short slug>
Click: <absolute https URL or omitted>
User-Agent: orchestrator/0.1.0 (+services/orchestrator)

<UTF-8 plain-text body, ≤1024 chars>
```

- Base URL is `ORCHESTRATOR_NTFY_BASE` (default `https://ntfy.sh`); self-host friendly.
- Topic is a path segment, URL-encoded.
- No bearer / no API key in v1 (public ntfy.sh requires none).
- No JSON publish endpoint — we use the simple `POST /<topic>` form documented at the top of <https://docs.ntfy.sh/publish/>.

---

## Header requirements

| Header | Required | Format | Source |
|---|---|---|---|
| `Title` | YES | UTF-8, no CR/LF, ≤200 chars | `Notification.title` |
| `Priority` | YES | `"3"`, `"4"`, or `"5"` | level → priority map (below) |
| `Tags` | YES | comma-separated, single-token | level → tags map (below) |
| `Click` | optional | absolute `https://` URL | `Notification.click_url` if set |
| `Content-Type` | YES | `text/plain; charset=utf-8` | constant |
| `User-Agent` | YES | `orchestrator/<version>` | constant |

We do NOT use:
- `Actions` (interactive buttons) — out of scope for v1 push (one-way).
- `Attach` / `Filename` / `Icon` — none of our messages need attachments.
- `Email` — phone push only; email is a different transport.
- `Delay` — events fire when they happen.
- `X-Forwarded-For` and other proxy headers — not relevant for direct POST.

---

## Body

UTF-8 plain text. Truncated to 1024 chars at the construction layer; if the source string is longer, it is truncated with a trailing `…` marker (and the full text is in the SQLite event log payload).

No HTML, no markdown formatting expected on the receiver. ntfy renders the body as plain text in the mobile app.

---

## Level → ntfy mapping (locked)

| Notification level | `Priority` header | `Tags` header | Notes |
|---|---|---|---|
| `info` | `3` | `🔵` | Default behavior; no vibration override. |
| `warn` | `4` | `⚠️` | High priority; phone vibrates. |
| `error` | `5` | `🛑` | Max priority; phone vibrates with the urgent pattern. |
| `needs_input` | `5` | `❓` | Same priority as error but a different visible tag. |

This mapping is the contract: changing it requires a contract update + a notifier-test update.

---

## Response handling

| ntfy response | Orchestrator action |
|---|---|
| `200 OK` | Success. No event written (would be too chatty). |
| `4xx` (any) | Emit `push.failed` warn event with `status_code`, `topic`, response-body snippet. **Do not retry.** Per FR-009, push failures are non-fatal — they MUST NOT abort the underlying run. |
| `5xx` (any) | Same as 4xx for v1. (v2 may add bounded retry with backoff.) |
| Network error / timeout | Emit `push.failed` warn event with `error=<exception class name>`. Same non-fatal policy. |

`push.failed` itself is NEVER pushed (we cannot push that we couldn't push). It is only logged to SQLite and visible in the dashboard.

---

## Timing & concurrency

- Each `Notifier.send()` call is a single async POST with a 5 s timeout.
- The Notifier maintains one `httpx.AsyncClient` for the daemon's lifetime.
- Concurrent calls are safe (httpx connection pooling). The daemon does not deduplicate or batch.

---

## What we deliberately do NOT depend on

- ntfy server's persistence behavior — messages may or may not be cached on the server; we don't poll back.
- ntfy's `Authorization` header — public server doesn't require it; self-hosting may add it later.
- `subscribe` GET endpoints — the dashboard does NOT subscribe to ntfy; it tails the local SQLite event log.
- Push delivery latency guarantees — we treat ntfy as best-effort. The dashboard is the source of truth; ntfy is a convenience.

---

## Contract test outline

```python
# tests/contract/test_ntfy_publish_request.py

def test_post_url_uses_configured_base(): ...
def test_post_url_uses_configured_topic(): ...
def test_info_level_sets_priority_3_and_blue_tag(): ...
def test_warn_level_sets_priority_4_and_warning_tag(): ...
def test_error_level_sets_priority_5_and_stop_tag(): ...
def test_needs_input_level_sets_priority_5_and_question_tag(): ...
def test_title_header_set_from_notification_title(): ...
def test_click_header_set_when_url_present(): ...
def test_click_header_omitted_when_url_none(): ...
def test_body_is_utf8_plain_text(): ...
def test_body_truncated_at_1024_chars_with_ellipsis(): ...
def test_user_agent_includes_orchestrator_and_version(): ...
def test_4xx_response_emits_push_failed_event_and_does_not_raise(): ...
def test_5xx_response_emits_push_failed_event_and_does_not_raise(): ...
def test_network_timeout_emits_push_failed_event_and_does_not_raise(): ...
```

Tests use `httpx.MockTransport` to intercept requests in-process — no real network calls. Each test asserts on the exact request shape (URL, headers, body) the notifier produced.

Implementation tasks for `notifier.py` MUST be ordered AFTER these contract tests in `tasks.md`.
