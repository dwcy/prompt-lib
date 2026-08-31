# Contract: `GET /api/env/sources`

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)
**Constitution Gate 3**: contract tests for this surface MUST be written and observed failing
before the route is implemented. They live in `setup/tests/contract/test_env_sources_contract.py`.

Lists every detected variable source for the currently selected project, **names and metadata
only**. This route never returns a value under any circumstance.

## Request

```http
GET /api/env/sources
Authorization: Bearer <handshake token>
```

No parameters. The project is taken from application state, as the existing project-scoped routes
already do.

## Response

Standard envelope (`webapi/envelope.py`), `source: "environment"`, with `data`:

```jsonc
{
  "sources": [
    {
      "id": "repo_file:apps~web~.env.local",
      "kind": "repo_file",
      "label": ".env.local",
      "state": "ok",
      "hint": null,
      "outside_repository": false,
      "link_confidence": null,
      "link_reason": null,
      "containers": [
        {
          "id": "repo_file:apps~web~.env.local",
          "source_id": "repo_file:apps~web~.env.local",
          "label": ".env.local",
          "qualifier": "apps/web",
          "layer": null,
          "entries": [
            {
              "name": "DATABASE_URL",
              "source_id": "repo_file:apps~web~.env.local",
              "container_id": "repo_file:apps~web~.env.local",
              "description": "",
              "target": null,
              "entry_type": null,
              "updated_at": null,
              "retrievability": "readable",
              "retrievability_reason": null,
              "is_reference": false
            }
          ]
        }
      ]
    }
  ],
  "project": "C:/projects/example",
  "scanned_at": "2026-08-29T09:20:00Z"
}
```

## Invariants the contract tests MUST assert

| # | Assertion | Requirement |
|---|---|---|
| C1 | No object anywhere in the response has a `value` key | FR-008 |
| C2 | Every source with `state: "degraded"` has a non-empty `hint` | FR-034/35/36 |
| C3 | No source has `state: "not_linked"` — undetected sources are absent, not empty | FR-005 |
| C4 | Every entry with `retrievability != "readable"` has a `retrievability_reason` | FR-018 |
| C5 | Every GitHub secret entry has `retrievability: "never"` | FR-019 |
| C6 | Every Vercel entry with `entry_type: "sensitive"` has `retrievability: "never"` | FR-020 |
| C7 | `label` + `qualifier` is unique across every container in the response | data-model rule 4 |
| C8 | An Azure source with `link_confidence: "machine_default"` states so in `link_reason` | FR-032 |
| C9 | Hierarchical entries are fully-qualified leaf paths; no section-only names appear | FR-040/41 |
| C10 | The response is produced within the timeout cap even when a collector hangs | FR-039, SC-010 |

## Degradation matrix

Each row is a required contract test case. None of them is an HTTP error — the envelope stays 200
and the *source* carries the bad news.

| Condition | `state` | `hint` names |
|---|---|---|
| `az` not installed | `degraded` | the missing tool |
| `az` installed, not signed in | `degraded` | that sign-in is required |
| No `VERCEL_TOKEN` and no CLI | `degraded` | the missing credential |
| `gh` not authenticated | `degraded` | that sign-in is required |
| Collector exceeded its timeout | `degraded` | the timeout |
| Provider reachable, holds nothing | `empty` | — |
| Config file unreadable/malformed | `degraded` | the parse failure, on that file's source only |
| Secret store declared, never populated | `empty` | — |

## Error responses

Reserved for failures of the route itself, never of a source:

| Status | Code | When |
|---|---|---|
| 401 | `unauthorized` | Missing/invalid bearer token |
| 404 | `no_project_selected` | No project in application state — 404, not 409, matching every other project-scoped read in this app (`/api/docs`, `/api/security/scan`, `/api/dashboard`) and the action-safety GET sweep that asserts against that set |
