# -*- coding: utf-8 -*-
"""GitHub template repo fetcher — lists the user's template repos via `gh repo list` and
streams their default-branch tarball through `gh api` into a temp dir.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitHubTemplateRef:
    """A template repo owned by the authenticated gh user."""

    owner: str
    name: str
    description: str | None
    default_branch: str
    url: str
    is_template: bool = True


def list_user_templates() -> list[GitHubTemplateRef]:
    """Return template repos visible to the current `gh` auth context."""
    argv = [
        "gh", "repo", "list",
        "--json", "isTemplate,name,owner,description,defaultBranchRef,url",
        "--limit", "200",
    ]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError:
        raise RuntimeError("gh not found on PATH — install GitHub CLI first") from None

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gh repo list failed (exit {proc.returncode})")

    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse gh output: {e}") from None

    results: list[GitHubTemplateRef] = []
    for entry in rows:
        try:
            if entry.get("isTemplate") is not True:
                continue
            branch_ref = entry.get("defaultBranchRef")
            if not branch_ref or not branch_ref.get("name"):
                continue
            name = entry.get("name") or ""
            if not name:
                continue
            results.append(GitHubTemplateRef(
                owner=entry["owner"]["login"],
                name=name,
                description=entry.get("description"),
                default_branch=branch_ref["name"],
                url=entry.get("url", ""),
                is_template=True,
            ))
        except (KeyError, TypeError):
            continue
    return results


def download_tarball(ref: GitHubTemplateRef) -> Path:
    """Stream the default-branch tarball, validate it, and extract into a fresh temp dir."""
    from cabal.init_project_service import _validate_safe

    argv = ["gh", "api", f"repos/{ref.owner}/{ref.name}/tarball/{ref.default_branch}"]
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as f:
        try:
            proc = subprocess.run(argv, stdout=f, stderr=subprocess.PIPE, timeout=120, check=False)
        except FileNotFoundError:
            raise RuntimeError("gh not found on PATH — install GitHub CLI first") from None
        tarball_path = Path(f.name)

    if proc.returncode != 0:
        raise RuntimeError(f"gh api tarball failed: {proc.stderr.decode(errors='replace').strip()}")

    extract_dir = Path(tempfile.mkdtemp(prefix="cabal-tpl-"))
    with tarfile.open(tarball_path) as tar:
        _validate_safe(tar)
        if sys.version_info >= (3, 12):
            tar.extractall(extract_dir, filter="data")
        else:
            tar.extractall(extract_dir)
    return extract_dir
