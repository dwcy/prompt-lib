# Contract: OKF Bundle Output

This contract defines the generated file tree and document shape for the prompt-lib OKF bundle.

## Bundle Root

Default output root:

```text
docs/okf/prompt-lib/
```

The exporter may accept an alternate output root for tests, but all generated resource paths inside documents remain repository-relative.

## Required Files

```text
docs/okf/prompt-lib/
|-- index.md
|-- log.md
|-- manifest.json
|-- graph.json
|-- agents/
|-- skills/
|-- hooks/
|-- rules/
|-- tools/
|-- specs/
`-- templates/
```

Empty category directories may be omitted, but `index.md`, `log.md`, `manifest.json`, and `graph.json` are required.

## Markdown Document Shape

Every generated concept document MUST have YAML frontmatter followed by Markdown body:

```markdown
---
type: agent
title: python-architect
description: Designs Python services and package structure.
resource: global/agents/python-architect.md
tags:
  - prompt-lib
  - agent
  - claude-code
timestamp: "2026-06-18T00:00:00Z"
id: agent:python-architect
relations:
  - kind: referenced_by
    target: skill:orchestrate
---

# python-architect

...
```

## Required Frontmatter Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | string | yes | Concept category or OKF-compatible type |
| `title` | string | yes | Human display title |
| `description` | string | yes | Short summary |
| `resource` | string | yes | Repo-relative POSIX source path |
| `tags` | string[] | yes | Must include `prompt-lib` and category |
| `timestamp` | string | yes | ISO-8601 UTC |
| `id` | string | yes | Stable prompt-lib concept id |
| `relations` | object[] | no | Outgoing relation summary |

## Relation Extension

Relation objects are prompt-lib extensions and must remain additive. Consumers that do not understand them may ignore them.

Required fields for each relation object:

| Field | Type | Notes |
|---|---|---|
| `kind` | string | e.g. `routes_to`, `references`, `depends_on` |
| `target` | string | Target concept id when resolved, otherwise raw target ref |
| `confidence` | string | `explicit`, `structured`, or `inferred` |
| `reason` | string | Human-readable explanation |
| `evidence` | object[] | Evidence records with `resource`, optional `line`, `text`, and `extractor` |

## Reserved Documents

### `index.md`

MUST include:

- Bundle title.
- OKF version.
- Generation timestamp.
- Counts by concept type.
- Links to category directories and `graph.json`.

### `log.md`

MUST include:

- Generation timestamp.
- Exporter version when known.
- Source revision when known.
- Summary of skipped files.

## `manifest.json`

MUST be UTF-8 JSON with deterministic key ordering.

Required top-level shape:

```json
{
  "bundle_id": "prompt-lib",
  "okf_version": "0.1",
  "generated_at": "2026-06-18T00:00:00Z",
  "source_revision": null,
  "source_categories": {
    "agent": 24,
    "skill": 12
  },
  "generated_files": [
    "index.md",
    "agents/python-architect.md"
  ],
  "skipped": [],
  "tool_version": "unknown"
}
```

## Determinism Requirements

- Source traversal order MUST be stable.
- Generated file order in `manifest.json` MUST be stable.
- Concept ids MUST be stable across OS path separators.
- Tests MAY inject a fixed timestamp to make generated output byte-stable.
- Regeneration MUST overwrite generated files under the selected output root and MUST NOT modify source artifacts.

## Security Requirements

- Generated output MUST NOT include secret values, OAuth tokens, API keys, local credentials, or private runtime state.
- Environment variable names may appear only when they are already documented as configuration keys.
- The exporter MUST skip files matching future secret/private skip patterns and record the skip reason in `manifest.json`.
