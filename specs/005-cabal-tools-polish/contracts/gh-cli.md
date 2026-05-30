# Contract — `gh` CLI invocation shapes (Part B)

This file documents every external `gh` call the Init Project flow makes, including expected output schema and error handling. The `gh` CLI itself is the authoritative spec — this file captures the subset we depend on.

Min version: **`gh ≥ 2.20`** (when `isTemplate` was added to `gh repo list --json`).

## C1 — List the user's template repos

**Command**:

```bash
gh repo list \
  --json isTemplate,name,owner,description,defaultBranchRef,url \
  --limit 200
```

**Working directory**: any.
**Auth**: assumes `gh auth status` is OK; if not, command exits non-zero with stderr `"error: not authenticated"`.

**Expected stdout** (JSON array; one element per repo):

```json
[
  {
    "isTemplate": true,
    "name": "tanstack-template",
    "owner": {"login": "username"},
    "description": "Vite + TanStack starter",
    "defaultBranchRef": {"name": "main"},
    "url": "https://github.com/username/tanstack-template"
  },
  {
    "isTemplate": false,
    "name": "private-app",
    "owner": {"login": "username"},
    "description": null,
    "defaultBranchRef": {"name": "main"},
    "url": "https://github.com/username/private-app"
  }
]
```

**Our handling**:

- Parse with `json.loads`. On `JSONDecodeError`, surface `"could not parse gh output: <e>"`.
- Filter `r["isTemplate"] is True`.
- Skip entries where `defaultBranchRef` is `None` (empty repo).
- Skip entries where `name` is missing or empty.

**Failure modes we surface (never raise)**:

- `gh not found on PATH` → `RuntimeError("gh not found on PATH — install GitHub CLI first")`. UI shows a yellow status and falls back to local templates (FR-9/R13).
- `gh auth missing` (stderr contains `"not authenticated"`) → UI shows red status with `"Run `gh auth login` from the Tools screen, then retry."`; falls back to local templates.
- Network timeout (≥ 30 s) → red status; falls back.
- `isTemplate` field missing on every row (older `gh`) → yellow status `"gh ≥ 2.20 required — falling back to local templates."`; falls back.

## C2 — Download a template repo as a tarball

**Command**:

```bash
gh api repos/<owner>/<name>/tarball/<defaultBranch>
```

**Working directory**: any.

**Output**: raw `.tar.gz` bytes on stdout. The first directory inside the archive is `<owner>-<name>-<sha>/` (GitHub convention) — we strip it on extract so the user's destination ends up with the repo contents directly.

**Implementation**:

```python
# pseudocode
with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as f:
    r = subprocess.run(
        ["gh", "api", f"repos/{ref.owner}/{ref.name}/tarball/{ref.default_branch}"],
        stdout=f, stderr=subprocess.PIPE, timeout=120, check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh api tarball failed: {r.stderr.decode().strip()}")
    f.flush()

with tarfile.open(f.name) as tar:
    _validate_safe(tar)   # R14: no `..`, no absolute paths, no symlinks
    extract_dir = Path(tempfile.mkdtemp(prefix="cabal-tpl-"))
    tar.extractall(extract_dir, filter="data" if PY312 else None)
```

**Our handling**:

- Timeout 120 s (templates are typically < 10 MB; 120 s is generous).
- On non-zero exit, surface `gh api tarball failed: <stderr>` to the user; offer Cancel / Retry / Switch to local.
- On `tarfile.TarError`, surface `tarball is corrupt or not a tar archive`.
- On unsafe-path detection (`_validate_safe`), surface `Template archive rejected — unsafe paths.` and refuse to extract.

## C3 — Detect `gh` version (advisory)

**Command**: `gh --version`

**Output**: first line of `gh version X.Y.Z (...)`.

We parse `X.Y` for the `isTemplate` capability check (see C1). If parse fails OR version < 2.20, we degrade to "no GH templates" path silently (R13).

## Out of scope

- `gh auth login`, `gh repo clone`, `gh repo create`, `gh release` — those live in `cabal/installers/gh.py` or `cabal/views/gh_device.py` and are not changed by Part B.
- Streaming JSON or partial result parsing — we always read the full JSON array.
