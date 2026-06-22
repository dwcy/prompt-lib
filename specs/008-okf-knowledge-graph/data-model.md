# Data Model: OKF Knowledge Graph

**Feature**: 008-okf-knowledge-graph  
**Date**: 2026-06-18

## Entity Relationship Overview

```text
OkfBundle
  contains ConceptDocument*
  contains GraphSnapshot
  contains ExportManifest
  reports DoctorFinding*

ConceptDocument
  derived_from SourceArtifact
  has Relation*
  has Backlink*

Relation
  connects source ConceptDocument to target ConceptDocument or unresolved target
  has EdgeEvidence*

GraphSnapshot
  contains GraphNode* from ConceptDocument
  contains GraphEdge* from Relation
  overlays DoctorFinding*
```

## Entities

### OkfBundle

Represents one generated OKF catalog rooted at `docs/okf/prompt-lib/`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `bundle_id` | string | yes | Stable value, initially `prompt-lib` |
| `root` | path | yes | Repository-relative output root |
| `generated_at` | string | yes | ISO-8601 UTC, configurable for deterministic tests |
| `okf_version` | string | yes | Draft target, initially `0.1` |
| `source_revision` | string/null | no | Git SHA when available, null when git unavailable |
| `documents` | ConceptDocument[] | yes | Deterministic order |
| `relations` | Relation[] | yes | Flattened relation list |
| `manifest` | ExportManifest | yes | Export metadata |

### SourceArtifact

Represents a repository file or directory that produced a concept.

| Field | Type | Required | Notes |
|---|---|---|---|
| `resource` | string | yes | POSIX-style repo-relative path |
| `category` | string | yes | `agent`, `skill`, `hook`, `rule`, `tool`, `template`, `spec`, `codex`, `output_style`, `statusline`, `other` |
| `name` | string | yes | Normalized display/source name |
| `exists` | bool | yes | Doctor validates this |
| `sha256` | string/null | no | Optional content hash for future drift checks |

### ConceptDocument

Represents one generated OKF Markdown document.

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Stable concept id, e.g. `agent:python-architect` |
| `type` | string | yes | OKF/frontmatter type, e.g. `agent` or `skill` |
| `title` | string | yes | Human display title |
| `description` | string | yes | Short summary |
| `resource` | string | yes | SourceArtifact path |
| `tags` | string[] | yes | Includes category and compatibility tags |
| `timestamp` | string | yes | ISO-8601 UTC or stable configured timestamp |
| `path` | string | yes | Generated Markdown path |
| `body` | string | yes | Generated body after frontmatter |
| `relations` | Relation[] | yes | Outgoing relations |
| `backlinks` | Backlink[] | yes | Incoming relation summaries |

### Relation

Represents a typed edge.

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Stable id from source id, kind, target id, and evidence hash |
| `kind` | string | yes | `routes_to`, `references`, `depends_on`, `documents`, `configured_by`, `deploys`, `extends`, `uses` |
| `source_id` | string | yes | Concept id |
| `target_id` | string/null | no | Concept id when resolved |
| `target_ref` | string | yes | Raw reference, preserved even unresolved |
| `target_resource` | string/null | no | Source path when resolved |
| `confidence` | string | yes | `explicit`, `structured`, `inferred` |
| `reason` | string | yes | Short explanation for humans |
| `evidence` | EdgeEvidence[] | yes | One or more evidence records |

### EdgeEvidence

Explains why a relation exists.

| Field | Type | Required | Notes |
|---|---|---|---|
| `resource` | string | yes | Source file path |
| `line` | int/null | no | 1-based line when available |
| `text` | string | yes | Short excerpt or normalized routing condition |
| `extractor` | string | yes | Extractor name, e.g. `agent_token`, `routing_table` |

### Backlink

Represents an incoming relation summary embedded in a concept document.

| Field | Type | Required | Notes |
|---|---|---|---|
| `source_id` | string | yes | Referencing concept |
| `source_title` | string | yes | Human title |
| `kind` | string | yes | Relation kind |
| `reason` | string | yes | Short relation reason |
| `evidence` | EdgeEvidence[] | yes | Evidence from source relation |

### GraphSnapshot

Machine-readable visualization and recommendation input.

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Initially `1` |
| `bundle_id` | string | yes | Matches OkfBundle |
| `generated_at` | string | yes | Matches bundle timestamp |
| `nodes` | GraphNode[] | yes | One per ConceptDocument |
| `edges` | GraphEdge[] | yes | One per Relation |
| `counts` | object | yes | Counts by type, kind, and severity |
| `findings` | DoctorFinding[] | yes | Optional diagnostic overlay |

### GraphNode

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Concept id |
| `label` | string | yes | Short display label |
| `type` | string | yes | Concept type |
| `resource` | string | yes | Source resource |
| `doc` | string | yes | Generated Markdown path |
| `tags` | string[] | yes | Frontmatter tags |
| `metrics` | object | yes | `incoming`, `outgoing`, `warnings`, `errors` |

### GraphEdge

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Relation id |
| `source` | string | yes | Source concept id |
| `target` | string/null | no | Target concept id when resolved |
| `target_ref` | string | yes | Raw reference for unresolved edges |
| `kind` | string | yes | Relation kind |
| `confidence` | string | yes | `explicit`, `structured`, `inferred` |
| `reason` | string | yes | Human explanation |
| `evidence` | EdgeEvidence[] | yes | Evidence records |

### DoctorFinding

| Field | Type | Required | Notes |
|---|---|---|---|
| `severity` | string | yes | `error`, `warning`, `info` |
| `code` | string | yes | Stable code, e.g. `OKF001` |
| `message` | string | yes | Human-readable summary |
| `resource` | string/null | no | Source or generated file path |
| `concept_id` | string/null | no | Related concept |
| `relation_id` | string/null | no | Related edge |
| `remediation` | string/null | no | Suggested fix |

### ExportManifest

| Field | Type | Required | Notes |
|---|---|---|---|
| `bundle_id` | string | yes | `prompt-lib` |
| `okf_version` | string | yes | `0.1` |
| `source_categories` | object | yes | Category to count |
| `generated_files` | string[] | yes | Deterministic order |
| `skipped` | object[] | yes | Skipped files and reason |
| `tool_version` | string | yes | Cabal package version or `unknown` |

## Validation Rules

- Concept ids must be unique.
- Generated Markdown paths must be unique and must stay under the bundle root.
- Resource paths must be repo-relative POSIX paths and must not contain `..`.
- Required frontmatter fields must be present and non-empty.
- Relations must have an existing source concept.
- Resolved relation targets must point to existing concept ids.
- Unresolved relation targets are allowed in export but must produce doctor warnings or errors depending on relation kind.
- Backlinks must be derived from relations, never hand-authored separately.
- Graph nodes must match concept documents one-to-one.
- Graph edges must match exported relations one-to-one.
- Secret-like values must not appear in generated frontmatter, graph JSON, manifest JSON, or document bodies.

## State Transitions

```text
discover sources
  -> generate concepts
  -> extract relations
  -> resolve targets
  -> derive backlinks
  -> write OKF docs and manifest
  -> build graph snapshot
  -> run doctor
  -> report success or findings
```

## MVP vs Beyond-MVP Fields

MVP fields are all fields listed above except:

- `sha256` content hashes: optional.
- `confidence = inferred`: beyond MVP.
- Import/merge provenance: beyond MVP.
- Visual layout coordinates: beyond MVP and should be generated by visualizer, not stored in the core graph contract unless needed later.
