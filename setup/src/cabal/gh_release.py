# -*- coding: utf-8 -*-
"""GitHub Releases helpers — used by installers that fetch a prebuilt asset."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def _gh_latest_release(repo: str) -> dict:
    import urllib.request as _ur
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "prompt-lib-installer"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = _ur.Request(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
    with _ur.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _gh_pick_asset(release: dict, suffix: str) -> dict | None:
    for a in release.get("assets") or []:
        if a.get("name", "").endswith(suffix):
            return a
    return None


def _download(url: str, dest: Path) -> None:
    import urllib.request as _ur
    headers = {"User-Agent": "prompt-lib-installer", "Accept": "application/octet-stream"}
    req = _ur.Request(url, headers=headers)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _ur.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
