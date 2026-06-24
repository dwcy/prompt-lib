# Contract: OKF Doctor

This contract defines validation behavior for the OKF doctor.

## Inputs

| Input | Type | Required | Notes |
|---|---|---|---|
| `bundle_root` | path | yes | Generated OKF bundle root |
| `repo_root` | path | yes | Repository root for resource validation |
| `format` | string | no | `human` or `json`; default `human` |

## Exit Semantics

| Condition | Exit code |
|---|---|
| No errors | 0 |
| One or more errors | 1 |
| Bundle root missing or unreadable | 2 |

Warnings do not fail the doctor unless a future strict mode is enabled.

## Machine-Readable Output

JSON output MUST follow this shape:

```json
{
  "ok": false,
  "bundle_root": "docs/okf/prompt-lib",
  "summary": {
    "documents": 42,
    "relations": 87,
    "errors": 1,
    "warnings": 2,
    "infos": 0
  },
  "findings": [
    {
      "severity": "error",
      "code": "OKF003",
      "message": "Resource path does not exist: global/agents/missing.md",
      "resource": "agents/missing.md",
      "concept_id": "agent:missing",
      "relation_id": null,
      "remediation": "Regenerate the bundle or restore the referenced source file."
    }
  ]
}
```

## Human Output

Human output MUST include:

- Overall status: `OKF doctor passed` or `OKF doctor failed`.
- Counts for documents, relations, errors, and warnings.
- One line per finding with severity, code, resource, and message.
- No stack traces for expected validation failures.

## Finding Codes

| Code | Severity | Meaning |
|---|---|---|
| `OKF001` | error | Required generated file missing |
| `OKF002` | error | Required frontmatter field missing or empty |
| `OKF003` | error | Source resource path missing or unsafe |
| `OKF004` | error | Duplicate concept id |
| `OKF005` | error | Graph node/document mismatch |
| `OKF006` | error | Graph edge/relation mismatch |
| `OKF101` | warning | Relation target unresolved |
| `OKF102` | warning | Concept has no incoming or outgoing relations |
| `OKF103` | warning | Source category is configured but empty |
| `OKF201` | info | File skipped by documented skip pattern |

## Validation Rules

The doctor MUST validate:

- Bundle root exists.
- `index.md`, `log.md`, `manifest.json`, and `graph.json` exist.
- Every generated Markdown document has frontmatter.
- Required frontmatter fields are present and non-empty.
- `resource` paths are repo-relative POSIX paths and do not contain `..`.
- Referenced `resource` files exist under repo root unless the concept type explicitly allows virtual resources.
- Concept ids are unique.
- Relation sources exist.
- Resolved relation targets exist.
- Graph nodes match generated concept ids.
- Graph edges match generated relation ids.
- Manifest file list matches generated files.

## Non-Goals

- The doctor does not validate arbitrary third-party OKF bundles in MVP.
- The doctor does not repair output in MVP.
- The doctor does not make network calls.
- The doctor does not parse or expose secret values.
