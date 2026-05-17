# Contract: `gh issue list --json` Output Schema

**Surface**: GitHub CLI — `gh issue list --json <fields>` subprocess output  
**Consumer**: `services/orchestrator/src/orchestrator/triggers/github_issues_poll.py`  
**Canonical reference**: <https://cli.github.com/manual/gh_issue_list>  
**Contract test**: `services/orchestrator/tests/contract/test_gh_issue_list_schema.py`

---

## Command

```sh
gh issue list \
  --json number,title,body,labels,author,createdAt,state \
  --repo <owner/repo> \
  --state open \
  --limit 100
```

Exit 0 on success. Exit non-zero + stderr on auth failure, repo not found, rate limit.

---

## Output Format

JSON array (possibly empty `[]`) of issue objects. Each object:

```json
[
  {
    "number":    123,
    "title":     "Login button broken on mobile",
    "body":      "Steps to reproduce: ...",
    "state":     "OPEN",
    "labels":    [
      {"id": "...", "name": "bug", "description": "...", "color": "d73a4a"}
    ],
    "author":    {"login": "octocat", "id": "...", "name": "..."},
    "createdAt": "2026-05-12T08:00:00Z"
  }
]
```

### Field Constraints

| Field | Type | Notes |
|---|---|---|
| `number` | integer | Positive; unique per repo |
| `title` | string | May be empty string on some GHE installs |
| `body` | string | May be empty string; may contain markdown |
| `state` | string | Always `"OPEN"` given `--state open` |
| `labels` | array | May be empty `[]`; each item has at least `name` string |
| `author` | object | Has at least `login` string |
| `createdAt` | string | ISO-8601 UTC, e.g. `"2026-05-12T08:00:00Z"` |

### Extraction Rules

The consumer extracts:
- `issue_number` ← `number`
- `title` ← `title`
- `body` ← `body` (truncated to 4000 chars in triage prompt)
- `labels` ← `[item["name"] for item in labels]`
- `author` ← `author["login"]`
- `created_at` ← `createdAt`

### Error Stderr Patterns

| Pattern | Kind emitted |
|---|---|
| `gh auth login` in stderr | `auth.failed` |
| `API rate limit exceeded` in stderr | `gh.rate_limited` |
| Any other non-zero exit | `gh.transient` |
| Exit 0 but output not valid JSON | `gh.parse.failed` |

---

## Conformance Scope

The orchestrator is a **consumer** of this surface — it parses but does not produce the `gh issue list` JSON format. Wire conformance means: the parser must not assume fields beyond those listed above, must tolerate an empty labels array, must tolerate empty body, and must not crash on additional undocumented fields in each item (use `.get()` or Pydantic `extra='allow'` on the parse model).

Any deviation from this contract (e.g., renaming a field, adding a required field, changing `labels` type) requires an ADR in `specs/003-issue-triage/contracts/`.
