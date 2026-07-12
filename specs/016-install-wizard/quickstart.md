# Quickstart: Installable Distribution with Installation Wizard

**Date**: 2026-07-11 | **Plan**: [plan.md](plan.md)

## For a user installing on a fresh machine (after the first release ships)

```bash
# 1. Install the tool (one command; needs Python >= 3.14 via uv)
uv tool install <distribution-name>        # name pending R1 decision; command is `cabal`

# 2. Run the wizard
cabal
#    → prerequisite/env panel → component selection → dry-run preview →
#      confirm → deploy with backups → verification summary

# 3. Later: health check, upgrade, uninstall
cabal doctor
uv tool upgrade <distribution-name> && cabal apply --yes
cabal uninstall --restore-backups
```

No repo clone, no `core.hooksPath`, no identity-filter setup — those are contributor steps, not installer steps. Windows-without-Python alternative: download `cabal.exe` from the GitHub Release.

## Non-interactive provisioning

```bash
cabal apply --yes --json          # full deploy, machine-readable result
cabal apply --dry-run             # preview only, exit 0
cabal doctor --json               # health as JSON; exit 1 on errors
```

Exit codes and JSON schemas: [contracts/cli-contract.md](contracts/cli-contract.md).

## For the developer (this feature's verification path)

```bash
# Run the affected suites
python -m pytest setup/tests/test_install_manifest.py setup/tests/test_headless_cli.py setup/tests/test_uninstall_service.py -q

# Full orchestrated run (release gate)
python scripts/test-all.py --strict-missing

# Wheel build + required-content inspection
python -m build
python -m zipfile -l dist/*.whl | grep -E "_data/global|_data/setup/env|mcp-templates.json|__main__.py"

# Headless smoke against a sandbox HOME (never your real ~/.claude)
HOME=$(mktemp -d) python -m cabal apply --dry-run   # POSIX
```

## First-release procedure (user-owned)

Ordered steps live in `docs/release-runbook.md` (created by this feature):

1. Decide the distribution name — **`cabal` is taken on PyPI** (verified 2026-07-11); recommendation `cabal-panel`, command stays `cabal`.
2. Update `pyproject.toml` `[project] name`, `release.yml` PyPI URL + wheel globs if renamed.
3. Create the PyPI project and configure Trusted Publishing (repo → workflow `release.yml` → environment `pypi`); create the matching GitHub `pypi` environment.
4. `python scripts/test-all.py --strict-missing` green.
5. Local wheel build + content inspection (step above).
6. Windows exe smoke test (`python setup/build/build_exe.py`, run `dist/cabal.exe`, apply dry-run in a sandbox HOME).
7. Tag `v0.1.0` and push the tag — the workflow does the rest.

This feature implements everything up to (but not including) the tag.
