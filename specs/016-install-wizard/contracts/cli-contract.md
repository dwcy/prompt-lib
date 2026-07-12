# CLI Contract: `cabal` command surface

**Date**: 2026-07-11 | **Plan**: [../plan.md](../plan.md)

Not a wire protocol (Constitution Gate 1/3: N/A) — this documents the tool contract that `tests/test_headless_cli.py` locks down before the argparse implementation lands.

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `cabal` | Launch the Textual wizard (unchanged default; FR-003) |
| `cabal --version` | Print `cabal <version> (<source_mode>)` and exit 0 (FR-015) |
| `cabal apply [...]` | Headless deploy of `global/` payload → `~/.claude/` (FR-014) |
| `cabal doctor [...]` | Headless health check (FR-012) |
| `cabal uninstall [...]` | Headless uninstall of managed files (FR-013) |

`python -m cabal` is equivalent to `cabal` in every mode. Unknown subcommands/flags → usage message on stderr, exit 2 (argparse default).

## `cabal apply`

```
cabal apply [--components KEY[,KEY...]] [--dry-run] [--yes] [--json]
```

- `--components`: comma-separated component keys (from the component registry). Omitted → all components. Unknown key → error, exit 2, nothing written. Required core (`settings`, `claude_md`) is always included; requesting their exclusion is an error.
- `--dry-run`: print the plan (NEW / CHANGED / UNCHANGED counts and file list), write nothing, exit 0.
- `--yes`: proceed without confirmation. Without `--yes` and with pending changes: print the plan and exit **3** (confirmation required) — never prompt on a non-TTY path.
- `--json`: machine-readable output (see schema below).
- An `in_progress` manifest from a previous run: with `--yes`, resume (re-apply); without, report the interrupted state and exit **4**.

**Exit codes**: `0` success (including "already up to date"), `1` failure mid-apply (manifest left `in_progress`), `2` usage error, `3` confirmation required, `4` interrupted previous apply detected.

**`--json` output schema (apply)**:

```json
{
  "status": "applied | up-to-date | dry-run | confirmation-required | interrupted-detected | error",
  "tool_version": "0.1.0",
  "components": ["settings", "agents"],
  "counts": {"created": 0, "updated": 0, "unchanged": 0, "backed_up": 0, "skipped": 0},
  "backup_dir": null,
  "manifest": "C:/Users/x/.claude/.cabal/install-manifest.json"
}
```

## `cabal doctor`

```
cabal doctor [--json]
```

Runs the existing config health checks plus the new manifest checks (missing managed file, hash-mismatch managed file, `in_progress` manifest, tool/manifest version skew).

**Exit codes**: `0` healthy, `1` findings with severity `error`, `5` no manifest found (legacy install — findings still reported from diff fallback).

**`--json` output schema (doctor)**: list of findings `{severity, category, path, message, hint}` (existing `Finding` dataclass) plus `{"manifest": {"present": bool, "status": str, "tool_version": str}}`.

## `cabal uninstall`

```
cabal uninstall [--restore-backups] [--dry-run] [--yes] [--json]
```

- Removes exactly the files recorded in the latest `complete` manifest; user-modified files (hash matches neither manifest nor source) are skipped and listed unless individually confirmed in the wizard flow (headless: always skipped, reported).
- `--restore-backups`: after removal, restore the pre-install backups referenced by the manifest.
- `--dry-run` / `--yes` / exit code `3`: same semantics as `apply`.
- No manifest → legacy fallback (component-diff file list) is **only** available with an explicit extra flag `--legacy` to prevent surprises; without it, exit **5**.

**Exit codes**: `0` success, `1` failure mid-uninstall, `2` usage error, `3` confirmation required, `5` no manifest (and `--legacy` not given).

## Global guarantees (all modes)

- Never creates or edits env/secret files (FR-011) — env instructions print as copy-paste blocks only.
- Never writes outside `~/.claude/` (plus `~/.codex/` for the existing Codex flows) and never removes files absent from the manifest/component registry (FR-010).
- Every overwrite is preceded by a backup into the timestamped backup dir recorded in the manifest (FR-007).
- Identical service layer under wizard and headless modes — same inputs produce byte-identical deployments (SC-007).
