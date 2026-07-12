# Data Model: Installable Distribution with Installation Wizard

**Date**: 2026-07-11 | **Plan**: [plan.md](plan.md)

All entities are plain dataclasses persisted as JSON on the local filesystem. No database.

## InstallManifest

The on-machine record of what cabal deployed. Location: `~/.claude/.cabal/install-manifest.json`. One current manifest; each apply rewrites it (the previous one is copied to `~/.claude/.cabal/history/<timestamp>.json` before overwrite, capped to the last 10).

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Manifest format version, starts at 1 |
| `tool_version` | str | `cabal.__version__` that performed the apply (FR-015) |
| `source_mode` | `"source" \| "wheel" \| "frozen"` | From `_paths` detection |
| `applied_at` | str (ISO 8601) | Timestamp of the apply |
| `status` | `"in_progress" \| "complete"` | Journal field for interrupted-apply detection (FR-017) |
| `components` | list[str] | Component keys selected for this apply (FR-005) |
| `backup_dir` | str \| null | Timestamped backup directory used by this apply, if any overwrites occurred (FR-007) |
| `files` | list[ManagedFile] | Every file this apply deployed or verified |

**Validation rules**: `status` must be `complete` for doctor/uninstall to trust the file list; an `in_progress` manifest forces the recovery flow. Unknown `schema_version` → treat as absent (legacy fallback). Component keys must exist in `COMPONENTS`.

**State transitions**: *(absent)* → `in_progress` (written with planned file list before first write) → `complete` (flipped after last write). Any run observing `in_progress` offers resume (re-apply) or rollback (restore `backup_dir`), never proceeds silently.

## ManagedFile

One deployed file inside `~/.claude/`, embedded in `InstallManifest.files`.

| Field | Type | Notes |
|---|---|---|
| `component` | str | Owning component key (e.g. `agents`, `hooks`, `settings`) |
| `rel` | str | Path relative to the component destination |
| `sha256` | str | Content hash of the deployed file at apply time (doctor: hand-modified vs stale) |
| `action` | `"created" \| "updated" \| "unchanged"` | What this apply did (FR-006 preview maps 1:1) |
| `backup` | str \| null | Path (inside `backup_dir`) of the pre-overwrite copy, when `action == "updated"` and a prior file existed |

**Validation rules**: `rel` must not contain `..` or be absolute (path-traversal guard on load). A file whose on-disk hash matches neither `sha256` nor the current source hash is classified **user-modified** and is never removed or overwritten without an explicit per-file confirmation (FR-010).

## BackupSnapshot

Already exists (timestamped backup dirs + `cleanup_service` manifest). This feature links to it, not reimplements it.

| Field | Type | Notes |
|---|---|---|
| `dir` | str | Timestamped directory under the existing backup root |
| `created_at` | str (ISO 8601) | From directory timestamp |
| `entries` | list[str] | Relative paths restorable from this snapshot |

**Relationship**: `InstallManifest.backup_dir` → one BackupSnapshot; `ManagedFile.backup` → one entry. Uninstall (FR-013) offers restoration of the snapshot(s) referenced by manifests it removes.

## ComponentGroup

Already exists as `Component` in `setup/src/cabal/components.py` (key, label, type, src, dst, glob, recursive). This feature adds one derived attribute, not a schema change:

| Field | Type | Notes |
|---|---|---|
| `required` | bool (derived) | `settings` and `claude_md` are the required core (FR-005); all others optional. Encoded as a constant set in the headless layer, not a Component field change |

## ApplySession (transient, not persisted)

In-memory aggregate driving one apply run (wizard or headless), producing the post-install verification summary (US1 acceptance 1).

| Field | Type | Notes |
|---|---|---|
| `plan` | list[FileStatus] | Existing `diff_apply.diff_component` output across selected components |
| `confirmed` | bool | Preview accepted (interactive) or `--yes` (headless) |
| `result` | counts: created / updated / unchanged / backed_up / skipped | Rendered as the final report and exit-code source |

## Entity relationships

```text
InstallManifest 1 ── * ManagedFile
InstallManifest * ── 1 BackupSnapshot   (via backup_dir; optional)
ManagedFile     * ── 1 ComponentGroup   (via component key)
ApplySession    ──> writes ──> InstallManifest (in_progress → complete)
Doctor          ──> reads  ──> InstallManifest + disk + bundled source
Uninstall       ──> reads  ──> InstallManifest; offers BackupSnapshot restore
```
