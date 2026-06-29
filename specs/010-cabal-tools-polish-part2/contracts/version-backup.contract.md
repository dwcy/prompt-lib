# Contract: Runtime Version Selection and Backup

## Purpose

Make runtime upgrades deliberate and recoverable for Bun, npm, pnpm, Python, Node, and dotnet.

## Version provider contract

Every provider must return:

- installed/current version if detectable
- latest known version or channel when metadata is available
- LTS/support markers only when upstream defines them
- source URL for metadata
- stale/unavailable status when fresh lookup fails

## Runtime coverage

| Runtime | LTS behavior |
|---|---|
| `node` | Use upstream LTS release metadata |
| `dotnet` | Use upstream LTS/STS support policy |
| `python` | Use upstream supported branch status; label bugfix/security rather than fake LTS |
| `bun` | Latest/stable only unless upstream defines LTS |
| `npm` | Latest/stable only unless upstream defines LTS |
| `pnpm` | Latest/stable only unless upstream defines LTS |

## Backup contract

Before install/update for each covered runtime:

- Capture previous version.
- Capture executable path.
- Capture detected install channel when possible.
- Capture safe config paths or note why none were captured.
- Write restore guidance.
- Surface backup failure before continuing.

## Expected contract tests

- `test_version_options_include_installed_when_metadata_unavailable`
- `test_node_versions_mark_lts_from_upstream_status`
- `test_dotnet_versions_mark_lts_and_sts`
- `test_python_versions_do_not_fake_lts`
- `test_runtime_backup_record_created_before_install`
- `test_backup_failure_blocks_or_requires_confirmation`
- `test_restore_hint_is_present_for_each_runtime`
