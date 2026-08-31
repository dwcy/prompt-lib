# Phase 1 Data Model: Environment Variables — Multi-Source Browser

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-29

Backend dataclasses live in `setup/src/cabal/models/envsources.py`; the frontend mirrors them as
Zod schemas in `apps/cabal-desktop/src/api/envSources.ts`. The wire shape is defined in
[`contracts/`](./contracts/).

---

## Enumerations

### `SourceKind`

`repo_file` · `dotnet_secrets` · `dotnet_launch_profile` · `azure_keyvault` ·
`azure_app_settings` · `vercel` · `github`

Drives the tab's icon and grouping. `curated` and `system` remain the existing built-in views and
are deliberately *not* part of this enum — they predate the feature and are unchanged (FR-002).

### `AvailabilityState`

**Amended during implementation.** Planned as a reuse of `models/dashboard.py`'s enum; built as
its own enum in `models/envsources.py` with exactly the four values below. Two reasons: the
dashboard enum's six failure values (`no_cli`, `not_authed`, `token_missing`, `token_rejected`,
`timeout`, `error`) are all collapsed into `degraded` + a hint here, so widening the shared enum
would have obliged every existing dashboard consumer to handle two values it can never receive;
and `models/dashboard.py` was already carrying another feature's uncommitted work, which this
change must not entangle itself with. The wire values are unchanged, so the contract is unaffected.

The four values:

| Value | Meaning | Requirement |
|---|---|---|
| `not_linked` | No link signal for this project; the tab does not render | FR-005 |
| `ok` | Loaded successfully, entries present | FR-037 |
| `empty` | Reachable and authenticated, but the source holds nothing | FR-037 |
| `degraded` | Detected but not fully readable; `hint` states why | FR-034/35/36 |

`empty` must be visibly distinct from `not_linked` and from `degraded` — that distinction is the
whole point of FR-037.

### `Retrievability`

| Value | Meaning | Example |
|---|---|---|
| `readable` | The value can be fetched now | repo file, GitHub variable |
| `permission_gated` | Fetchable only if the caller holds the right | Key Vault secret, Vercel encrypted |
| `never` | The platform will never return it | GitHub secret, Vercel `sensitive` |

`never` renders a permanently disabled eye with a reason and is **not** an error state (FR-018).

### `LinkConfidence`

`explicit` · `azd` · `iac` · `machine_default`

Ordered highest to lowest. `machine_default` MUST be rendered as a machine default rather than a
project link (FR-032).

---

## Entities

### `VariableSource`

One origin of configuration for the selected project.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Stable within a response; addresses the source on the reveal route |
| `kind` | `SourceKind` | |
| `label` | `str` | Tab group label, e.g. `appsettings.Development.json`, `GitHub`, `Key Vault` |
| `state` | `AvailabilityState` | |
| `hint` | `str \| None` | Required whenever `state` is `degraded`; explains what is missing |
| `outside_repository` | `bool` | True for the .NET secret store and every cloud source (FR-045) |
| `link_confidence` | `LinkConfidence \| None` | Azure only; drives the "machine default" badge |
| `link_reason` | `str \| None` | Which signal established the link (FR-031) |
| `containers` | `list[VariableContainer]` | Empty when `state` is `not_linked` or `degraded` |

**Rules**: a source with `state = not_linked` is omitted from the response entirely rather than
sent with an empty body — the frontend must never decide whether a tab is worth rendering.

### `VariableContainer`

The grouping that becomes one tab.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Unique within its source |
| `source_id` | `str` | |
| `label` | `str` | Tab caption |
| `qualifier` | `str \| None` | Disambiguates same-named files across a monorepo (edge case) |
| `layer` | `ConfigLayer \| None` | Set only for framework stacks with a defined precedence |
| `entries` | `list[VariableEntry]` | |

**Rules**: `label` alone is not required to be unique across the response; `label` + `qualifier`
is. Three services each holding an `appsettings.json` must stay tellable apart.

### `VariableEntry`

One named key. **Never carries a value.**

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Fully-qualified leaf path for hierarchical documents (FR-040) |
| `source_id` / `container_id` | `str` | Attribution (FR-010) |
| `description` | `str` | May be empty |
| `target` | `str \| None` | Deployment target / environment / launch profile (FR-009) |
| `entry_type` | `str \| None` | Provider's own classification, e.g. Vercel `sensitive` |
| `updated_at` | `str \| None` | ISO-8601 where the provider reports it |
| `retrievability` | `Retrievability` | |
| `retrievability_reason` | `str \| None` | Required when not `readable` |
| `is_reference` | `bool` | True for a Key Vault reference rather than a literal (FR-022) |

**Rules**: there is no `value` field on this type at all — the omission is structural, not a
convention, so a listing response cannot leak one by accident.

### `ConfigLayer`

Position in a framework's own precedence order.

| Field | Type | Notes |
|---|---|---|
| `stack` | `str` | e.g. `dotnet` |
| `name` | `str` | e.g. `appsettings.Development.json` |
| `rank` | `int` | Lower wins; matches the confirmed .NET ordering in research R3 |
| `wins` | `bool` | True when this layer holds the winning definition of that key among the layers discovered |

**Rules**: `wins` is computed only across layers this module actually discovered. It never claims
to account for command-line arguments or process environment variables, which the module cannot
observe (FR-043).

### `AzureProjectLink`

| Field | Type | Notes |
|---|---|---|
| `subscription_id` | `str \| None` | |
| `resource_group` | `str \| None` | |
| `confidence` | `LinkConfidence` | |
| `reason` | `str` | Human-readable signal description (FR-031) |
| `is_explicit` | `bool` | True only for a user-recorded link |

The only persisted state this feature writes (FR-025). Stored in the app's platform data
directory, keyed by project path. Clearable (FR-033).

### `RevealResult`

Returned by the reveal route; never stored.

| Field | Type | Notes |
|---|---|---|
| `status` | `"revealed" \| "denied" \| "unavailable"` | |
| `value` | `str \| None` | Present only when `status = revealed` |
| `reason` | `str \| None` | Required when not `revealed` |
| `is_reference` | `bool` | True when the value is a store reference, not a literal (FR-022) |

**Rules**: `unavailable` covers `never`-classified entries that were requested anyway (a stale
UI, or a direct API call); `denied` covers a permission refusal. They are different states and
the copy differs.

---

## Relationships

```text
VariableSource 1 ── * VariableContainer 1 ── * VariableEntry
       │                      │
       │                      └── 0..1 ConfigLayer
       └── 0..1 AzureProjectLink        (azure sources only)

VariableEntry ──(source_id, container_id, name)──> RevealResult   (on demand, one at a time)
```

---

## Validation rules

1. A source with `state = degraded` MUST carry a non-empty `hint`. (FR-034/35/36)
2. An entry whose `retrievability` is not `readable` MUST carry a `retrievability_reason`. (FR-018)
3. `VariableEntry` MUST NOT define a `value` field in any serialisation. (FR-008)
4. `label` + `qualifier` MUST be unique across all containers in one response.
5. A GitHub secret entry MUST be `never`; a Vercel entry typed `sensitive` MUST be `never`. (FR-019/20)
6. `link_confidence = machine_default` MUST NOT set `is_explicit`, and the UI MUST badge it as a
   machine default. (FR-032)
7. Sources with `state = not_linked` MUST be absent from the response. (FR-005)
8. A reveal for an entry classified `never` MUST return `unavailable` without contacting the
   provider — the classification is authoritative and the round trip is pointless.

---

## State transitions

Sources and entries are re-derived per request; there is no stored lifecycle. The only stateful
object is `AzureProjectLink`:

```text
absent ──record──> explicit ──clear──> absent
   │                                      │
   └──── automatic detection (azd | iac | machine_default) ────┘
        (recomputed each request; never persisted)
```

Reveal is stateless by construction. A revealed value exists only in the response and in the
component holding it, and is dropped on tab change or project change (FR-014).
