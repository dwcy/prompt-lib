# Contract — `gh pr list --json` output (INBOUND parse)

**Surface**: GitHub CLI (`gh`) JSON output for the `pr list` and `pr view` subcommands.
**Direction**: INBOUND. The orchestrator **parses** the output of `gh`.
**Canonical reference**: <https://cli.github.com/manual/gh_pr_list> · <https://cli.github.com/manual/gh_pr_view>
**Contract test**: `services/orchestrator/tests/contract/test_gh_pr_list_schema.py`

---

## Invocation

```text
gh pr list \
    --repo <owner/repo> \
    --state open \
    --json number,headRefOid,updatedAt,title,url,headRefName,baseRefName,author \
    --limit 100
```

The orchestrator pins the `--json` field list explicitly. Adding a field requires a contract update; we do not rely on `gh`'s default field set.

---

## Expected response shape (top level)

A JSON **array** of PR objects. Each element matches the schema below.

```jsonc
[
  {
    "number": 42,
    "headRefOid": "0123456789abcdef0123456789abcdef01234567",
    "updatedAt": "2026-05-10T12:34:56Z",
    "title": "Add the thing",
    "url": "https://github.com/owner/repo/pull/42",
    "headRefName": "feature/the-thing",
    "baseRefName": "main",
    "author": {
      "id": "MDQ6VXNlcjEyMzQ1",
      "is_bot": false,
      "login": "octocat",
      "name": "Octo Cat"
    }
  }
]
```

---

## Field requirements (parser strictness)

| Field | Type | Required | Validation | Used for |
|---|---|---|---|---|
| `number` | integer | YES | `> 0` | `TriggerEvent.pr_number` |
| `headRefOid` | string | YES | matches `^[0-9a-f]{40}$` | `TriggerEvent.head_sha`, cursor diff |
| `updatedAt` | string (ISO 8601) | YES | parseable by `datetime.fromisoformat` | Tie-breaker for log ordering |
| `title` | string | YES | length 1–256 | Notification body |
| `url` | string | YES | starts with `https://github.com/` | Notification `Click` header |
| `headRefName` | string | YES | non-empty | `agent.prompt` enrichment |
| `baseRefName` | string | YES | non-empty | `agent.prompt` enrichment |
| `author.login` | string | YES | non-empty | `agent.prompt` enrichment |
| `author.is_bot` | boolean | YES | — | Optional skip filter (deferred to v2) |

Unknown fields at any nesting level are accepted and ignored (forward-compatible).

Missing required fields cause the orchestrator to:
1. Skip that PR (do NOT crash the polling loop).
2. Emit a `gh.parse.failed` event with the raw element JSON in `payload_json`.
3. Continue polling.

---

## Error paths

| Condition | `gh` exit code | Stderr signature | Orchestrator behavior |
|---|---|---|---|
| Auth expired / not logged in | non-zero | contains `not authenticated` (case-insensitive) | Emit `auth.failed` event, send error notification, **pause polling loop** until daemon restart. |
| Repo not found | non-zero | contains `not found` (case-insensitive) | Emit `auth.failed` (mis-named — really a config failure) with `which="gh"`, error notification, pause. |
| Rate limited | non-zero | contains `rate limit` | Emit `gh.rate_limited` warning event, sleep `60s` and retry; do not pause. |
| Network blip | non-zero | other | Emit `gh.transient` warn event, retry on next normal poll tick. |
| Empty result (no open PRs) | 0 | — | `[]`. Normal — no events emitted. |

---

## What we deliberately do NOT depend on

- `gh`'s human-readable terminal output (`--json` is the contract; the terminal output is for humans).
- The order of elements in the returned array (we don't assume newest-first; we sort by `(number, updatedAt)` ourselves before diffing).
- Any field NOT in the `--json` list above. If we add a use case (e.g., labels-based filtering in v2), we add the field to the `--json` invocation AND to this contract AND to the test.
- `gh pr view <n> --comments` JSON shape — used only by the operator manually for verification, not by the daemon.

---

## Contract test outline

```python
# tests/contract/test_gh_pr_list_schema.py

def test_parser_accepts_minimal_required_fields(): ...
def test_parser_accepts_unknown_extra_fields(): ...
def test_parser_skips_pr_missing_headRefOid(): ...
def test_parser_skips_pr_with_invalid_sha_format(): ...
def test_parser_skips_pr_with_unparseable_updatedAt(): ...
def test_parser_returns_empty_for_empty_array(): ...
def test_runner_emits_auth_failed_on_not_authenticated_stderr(): ...
def test_runner_emits_auth_failed_on_repo_not_found_stderr(): ...
def test_runner_emits_rate_limited_on_rate_limit_stderr(): ...
```

Tests use a **fake `gh` script** placed on PATH via `monkeypatch.setenv` — a tiny Python file that emits a fixture JSON to stdout (or fails with a fixture stderr) based on `argv`. No real `gh` invocation occurs in contract tests.

Implementation tasks for `triggers/github_poll.py` MUST be ordered AFTER these contract tests in `tasks.md`.
