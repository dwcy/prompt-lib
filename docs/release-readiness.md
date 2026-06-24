# Release Readiness

This repo is intended to publish the Cabal control panel as an installable Python
package, but publishing is not treated as ready just because the release workflow
exists. Use this page as the checklist before creating any `v*.*.*` tag.

## Current State

- Package metadata lives in `pyproject.toml`.
- The console entry point is `cabal`.
- `.github/workflows/release.yml` builds a wheel, sdist, and Windows executable
  from version tags.
- Publishing to PyPI requires a configured PyPI project and Trusted Publishing
  environment. Do not assume a tag is safe until that is verified.

## Decisions Before Publishing

1. Confirm the package and command name.
   The current name is `cabal`. If the project is renamed to `prompto` or
   another name for product-positioning reasons, do it before the first real
   package release.
2. Confirm the release channel.
   Decide whether the first public artifact is PyPI, GitHub Releases, the
   standalone executable, or all three.
3. Confirm package ownership.
   Create or claim the PyPI project and configure GitHub Trusted Publishing for
   this repository/environment before tagging.

## Required Checks

Run the repository test orchestrator:

```bash
python scripts/test-all.py --strict-missing
```

For release candidates that depend on real services, also run:

```bash
python scripts/test-all.py --include-integration --strict-missing
```

Then build and inspect the package locally:

```bash
python -m build
python -m zipfile -l dist/cabal-*.whl
```

The wheel must include:

- `cabal/_data/global`
- `cabal/_data/setup/env`
- `cabal/_data/setup/mcp-templates.json`
- `cabal/__main__.py`

## Tagging Rule

Only create a `v*.*.*` tag after the name decision, PyPI Trusted Publishing
setup, root test orchestration, local package inspection, and Windows executable
smoke test are all complete. Until then, use normal branch commits and PRs only.
