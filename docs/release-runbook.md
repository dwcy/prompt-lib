# Release Runbook — first `cabal` package release

Ordered, user-owned procedure for shipping the first real release. Complements
[`release-readiness.md`](release-readiness.md) (the gate) — this is the *how*.
Nothing here is automated by the repo tooling on purpose: tagging and PyPI
ownership are deliberate manual acts.

## 0. Current blocker: the PyPI name

**`cabal` is taken on PyPI** — verified 2026-07-11 via
`https://pypi.org/pypi/cabal/json`: an unrelated, actively maintained package
(exact computable real numbers, v0.2.1 uploaded 2026-06-15). PEP 541 name
transfer does not apply to active projects, so the first release cannot ship
under `cabal`.

**Recommendation**: distribution name **`cabal-panel`**, keeping `cabal` as the
import package and console command — PyPI distribution name, import name, and
console-script name are independent, so `uv tool install cabal-panel` still
installs the `cabal` command and every internal path stays unchanged.

Known trade-off: the `cabal` *command* collides with Haskell's `cabal` binary
on machines with a Haskell toolchain. Acceptable for the primary audience
(your machines, no Haskell); if it ever bites, add a second console-script
alias (e.g. `cabal-panel = "cabal.__main__:main"`) rather than renaming.

Alternative on the table: full product rename (e.g. `prompto`), floated in
`release-readiness.md`. Larger blast radius (package dir, exe name, docs,
muscle memory) for no functional gain — can still be done later.

## 1. Decide and apply the name

1. Pick the distribution name (recommendation above).
2. If it is not `cabal`, edit:
   - `pyproject.toml` → `[project] name = "<new-name>"`
   - `.github/workflows/release.yml` → the `environment.url`
     (`https://pypi.org/project/<new-name>/`) and the wheel-inspection glob
     (`dist/cabal-*.whl` → `dist/<new_name_with_underscores>-*.whl`)
   - `setup/README.md` install command (`uv tool install <new-name>`)
   - `docs/release-readiness.md` name decision line
3. The import package (`setup/src/cabal/`), console command, and exe name stay
   `cabal` unless you chose the full rename.

## 2. Create the PyPI project + Trusted Publishing

1. On pypi.org (logged in as the owning account): **Add a pending publisher**
   under *Publishing* → GitHub:
   - Project name: the chosen distribution name
   - Owner/repo: this repository
   - Workflow: `release.yml`
   - Environment: `pypi`
2. In the GitHub repo settings: create an environment named **`pypi`**
   (Settings → Environments). Optionally add yourself as a required reviewer —
   that makes every PyPI publish a manual approval click.
3. No API tokens anywhere — the workflow uses OIDC (`id-token: write`).

## 3. Pre-tag gates (all must pass)

```bash
# 1. Full test orchestration
python scripts/test-all.py --strict-missing

# 2. Build + wheel content inspection
python -m build          # or: uv build
python -m zipfile -l dist/*.whl
```

The wheel MUST contain:

- `cabal/_data/global`
- `cabal/_data/setup/env`
- `cabal/_data/setup/mcp-templates.json`
- `cabal/__main__.py`

```bash
# 3. Version sanity (single-sourced from setup/src/cabal/__init__.py)
python -m cabal --version

# 4. Windows exe smoke test
python setup/build/build_exe.py
setup/build/dist/cabal.exe --version
# then, in a sandbox HOME, run: cabal.exe apply --dry-run
```

Record pass/fail for each gate here (or in the PR) before tagging.

- 2026-07-12 — wheel gate: PASS after a fix. First build failed on duplicate
  `cabal/assets/*` entries — the `force-include` table re-added asset dirs the
  `packages = ["setup/src/cabal"]` entry already ships; removed the two
  redundant force-include lines from `pyproject.toml`. Rebuilt wheel inspected:
  all four required paths present (`cabal/_data/global`, `cabal/_data/setup/env`,
  `cabal/_data/setup/mcp-templates.json`, `cabal/__main__.py`), assets included
  exactly once, version resolved dynamically from `cabal/__init__.py`.

## 4. Tag and ship

```bash
# version bump first: setup/src/cabal/__init__.py __version__
git tag v0.1.0
git push origin v0.1.0
```

The `release.yml` workflow then: builds wheel + sdist → publishes to PyPI via
Trusted Publishing → builds the Windows exe → creates a GitHub Release with
all artifacts and generated notes.

## 5. Post-release verification

```bash
uv tool install <distribution-name>
cabal --version          # matches the tag
cabal apply --dry-run    # sees the bundled payload (source_mode "wheel")
cabal doctor             # healthy / expected findings
```

## Install-surface summary (what users get)

| Command | Purpose |
|---|---|
| `cabal` | Interactive wizard (deploy, restore, doctor, uninstall, env init, tools) |
| `cabal apply [--components ...] [--dry-run] [--yes] [--json]` | Non-interactive deploy; exit 3 = confirmation required, 4 = interrupted apply detected |
| `cabal doctor [--json]` | Health check incl. manifest checks; exit 5 = legacy install without manifest |
| `cabal uninstall [--restore-backups] [--dry-run] [--yes] [--legacy] [--json]` | Manifest-driven uninstall; exit 5 = no manifest without `--legacy` |
| `cabal --version` | Installed version + source mode |

Full contract: [`specs/016-install-wizard/contracts/cli-contract.md`](../specs/016-install-wizard/contracts/cli-contract.md).
