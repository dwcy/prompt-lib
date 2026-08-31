# Contract: `POST /api/env/reveal`

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)
**Constitution Gate 3**: contract tests for this surface MUST be written and observed failing
before the route is implemented. They live in `setup/tests/contract/test_env_sources_contract.py`.

Fetches exactly one value, on explicit user action, and audits the attempt.

## Why POST for a read

The value must not appear in a URL, and therefore not in browser history, proxy logs, server
access logs, or any query cache. A GET would put it in all of them. This is the one place in the
module where a read is deliberately modelled as a POST.

## Request

```http
POST /api/env/reveal
Authorization: Bearer <handshake token>
Content-Type: application/json

{
  "source_id": "github:env:production",
  "container_id": "github:env:production",
  "name": "DATABASE_URL"
}
```

All three fields are required. Exactly one entry per call — there is no array form, by design
(FR-012).

## Response

Standard envelope, `source: "environment"`, with `data`:

```jsonc
{ "status": "revealed",    "value": "postgres://…", "reason": null,                              "is_reference": false }
{ "status": "revealed",    "value": "@Microsoft.KeyVault(SecretUri=…)", "reason": null,          "is_reference": true  }
{ "status": "denied",      "value": null, "reason": "Key Vault access requires the Key Vault Secrets User role", "is_reference": false }
{ "status": "unavailable", "value": null, "reason": "GitHub never returns secret values",        "is_reference": false }
```

## Invariants the contract tests MUST assert

| # | Assertion | Requirement |
|---|---|---|
| R1 | `value` is non-null **only** when `status: "revealed"` | FR-012 |
| R2 | `status != "revealed"` always carries a non-empty `reason` | FR-018/21 |
| R3 | An entry classified `never` returns `unavailable` **without contacting the provider** | data-model rule 8 |
| R4 | Every call — success, denial, or unavailable — writes exactly one audit record | FR-016 |
| R5 | No audit record contains the revealed value | FR-016 |
| R6 | A permission refusal returns `denied` and names the access required, not a 5xx | FR-021 |
| R7 | A Key Vault reference returns `is_reference: true` and is not resolved further | FR-022 |
| R8 | The response sets no cache-permitting headers | FR-015 |
| R9 | Requesting an unknown `source_id`/`name` returns 404, not a partial reveal | — |
| R10 | The value is never written to any file on disk during the call | FR-015 |

## Audit record

Written through the existing `webapi/audit.py`:

| Field | Value |
|---|---|
| `action` | `env.reveal` |
| `source_id`, `container_id`, `name` | echoed from the request |
| `status` | `revealed` / `denied` / `unavailable` |
| `at` | ISO-8601 |

The value is **absent by construction** — the audit payload has no field capable of holding it,
so it cannot be added by accident.

## Error responses

| Status | Code | When |
|---|---|---|
| 401 | `unauthorized` | Missing/invalid bearer token |
| 404 | `entry_not_found` | The triple does not match a known entry |
| 404 | `no_project_selected` | No project in application state — 404, not 409, matching every other project-scoped read in this app (`/api/docs`, `/api/security/scan`, `/api/dashboard`) and the action-safety GET sweep that asserts against that set |
| 422 | `params_invalid` | Missing field, or an array where one entry is required |

A provider being slow, refusing, or unreachable is **not** an error response — it is a `denied` or
`unavailable` body with a 200 envelope, so the row can explain itself in place.
