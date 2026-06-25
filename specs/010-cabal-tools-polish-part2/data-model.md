# Phase 1 - Data Model

## ToolDefinition

Represents one visible Tools view entry.

| Field | Type | Notes |
|---|---|---|
| `key` | string | Stable unique identifier used in widget IDs and tests |
| `label` | string | Human display name |
| `category` | string | One of the supported Tools sections |
| `description` | string | Short user-facing description, max 160 characters preferred |
| `source_url` | string or null | Official homepage, docs, package, repository, or release page |
| `source_label` | string | Read-more button/tooltip label |
| `source_status` | enum | `verified`, `manual_required`, `unavailable` |
| `install_channel` | enum | `package`, `desktop_app`, `container_service`, `embedded_engine`, `manual`, `none` |
| `status_probe` | string | Named probe function or probe strategy |
| `installer` | string or null | Named install function when automated install is supported |
| `platforms` | list | `Windows`, `Darwin`, `Linux`, or `all` |
| `version_provider` | string or null | Provider key for version selector |
| `backup_policy` | string or null | Backup policy key for runtime changes |
| `secret_policy` | enum | `redact` for all rows |

Validation rules:

- `key`, `label`, `category`, and `description` are required.
- Every visible entry must have `source_url` unless `source_status` is `manual_required` or `unavailable`.
- Automated installers are blocked when `source_status` is not `verified`.
- Widget IDs derived from `key` must remain stable.

## ToolCategory

Represents a rendered section in Tools view.

| Field | Type | Notes |
|---|---|---|
| `name` | string | Display name |
| `slug` | string | Stable CSS/widget identifier |
| `keys` | list[string] | ToolDefinition keys in category |
| `sort_mode` | enum | `label` by default, `declared` for curated order |

Required categories:

- System & VCS
- Runtimes
- Package Managers
- Container & Cloud
- Databases
- Database Clients
- Azure Local Tools
- AI CLIs
- Local AI
- AI Editors / IDEs
- Developer Tools

## ContainerServiceSpec

Represents a local container-backed database or Azure emulator service.

| Field | Type | Notes |
|---|---|---|
| `key` | string | Tool key |
| `image` | string | Container image reference |
| `container_name` | string | Stable local container name |
| `ports` | list | Host/container port mappings |
| `volumes` | list | Named/local volumes |
| `environment` | dict | Non-secret defaults only |
| `health_command` | list[string] or null | Command used to verify service health |
| `status_command` | list[string] | Container status probe |
| `logs_hint` | string | User guidance for logs |
| `cleanup_hint` | string | User guidance for explicit cleanup |
| `security_notes` | list[string] | Local-only and credential guidance |

Validation rules:

- Host ports must be declared and conflict-checked before install.
- Volumes must be declared before install.
- Health must be checked before reporting success.
- No default secret values may be logged.

## VersionOption

Represents a selectable install/upgrade target.

| Field | Type | Notes |
|---|---|---|
| `tool_key` | string | Runtime key |
| `version` | string | Exact or channel version |
| `label` | string | User-visible dropdown label |
| `channel` | enum | `latest`, `lts`, `stable`, `current`, `installed`, `unknown` |
| `is_latest` | bool | True for newest known version |
| `is_lts` | bool | True only when upstream defines LTS |
| `source_url` | string | Metadata source |
| `fetched_at` | datetime or null | Cache timestamp |

Validation rules:

- Version selectors must show installed/current even when fresh metadata fails.
- LTS markers must not be invented for ecosystems without LTS.

## RuntimeBackupRecord

Represents recovery evidence captured before changing a runtime.

| Field | Type | Notes |
|---|---|---|
| `tool_key` | string | `bun`, `npm`, `pnpm`, `python`, `node`, or `dotnet` |
| `created_at` | datetime | Backup timestamp |
| `before_version` | string or null | Detected previous version |
| `before_path` | string or null | Detected executable path |
| `install_channel` | string | Detected or assumed channel |
| `config_paths` | list[string] | Safe user config paths captured or referenced |
| `restore_hint` | string | Human restore guidance |
| `artifact_path` | string or null | Optional local backup artifact |

Validation rules:

- A backup record must be attempted before supported runtime installs/upgrades.
- Failure to create a backup record must be visible before continuing.
- Restore hints must avoid promising full binary rollback unless that rollback is actually captured.

## ToolStatus

Represents a row state after probing.

| Field | Type | Notes |
|---|---|---|
| `key` | string | ToolDefinition key |
| `state` | enum | `installed`, `missing`, `update_available`, `unsupported`, `source_required`, `error`, `checking` |
| `detail` | string | Version or short explanation |
| `copyable_text` | string | Plain text representation for copy |
| `actions` | list[string] | `install`, `update`, `read_more`, `select_version`, `view_logs` |

Validation rules:

- Visible status text must have a plain-text copy representation.
- Errors must be copyable and redacted.
