# -*- coding: utf-8 -*-
"""GitHub Releases helpers — used by installers that fetch a prebuilt asset."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse


_SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")


class DownloadVerificationError(RuntimeError):
    """Raised when a downloaded release asset cannot be verified."""


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


def _require_https(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise DownloadVerificationError(f"refusing non-HTTPS download URL: {url}")


def _download(url: str, dest: Path) -> None:
    import urllib.request as _ur

    _require_https(url)
    headers = {"User-Agent": "prompt-lib-installer", "Accept": "application/octet-stream"}
    req = _ur.Request(url, headers=headers)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _ur.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _download_text(url: str) -> str:
    import urllib.request as _ur

    _require_https(url)
    headers = {"User-Agent": "prompt-lib-installer", "Accept": "text/plain"}
    req = _ur.Request(url, headers=headers)
    with _ur.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _asset_name(asset: dict) -> str:
    name = asset.get("name")
    if not isinstance(name, str) or not name:
        raise DownloadVerificationError("release asset is missing a name")
    return name


def _asset_url(asset: dict) -> str:
    url = asset.get("browser_download_url")
    if not isinstance(url, str) or not url:
        raise DownloadVerificationError("release asset is missing a download URL")
    return url


def _digest_from_asset(asset: dict) -> str | None:
    raw = asset.get("digest")
    if not isinstance(raw, str):
        return None
    prefix = "sha256:"
    if not raw.lower().startswith(prefix):
        return None
    candidate = raw[len(prefix) :].strip()
    if _SHA256_RE.fullmatch(candidate):
        return candidate.lower()
    return None


def _checksum_assets(release: dict, target_name: str) -> list[dict]:
    assets = [a for a in release.get("assets") or [] if isinstance(a, dict)]
    exact = {
        f"{target_name}.sha256",
        f"{target_name}.sha256sum",
        f"{target_name}.sha256.txt",
        f"{target_name}.checksums.txt",
    }
    scored: list[tuple[int, dict]] = []
    for asset in assets:
        name = asset.get("name")
        if not isinstance(name, str):
            continue
        lowered = name.lower()
        if name in exact:
            scored.append((0, asset))
        elif target_name in name and "sha256" in lowered:
            scored.append((1, asset))
        elif "sha256" in lowered or "checksum" in lowered or "checksums" in lowered:
            scored.append((2, asset))
    return [asset for _, asset in sorted(scored, key=lambda item: item[0])]


def _parse_checksum_text(text: str, target_name: str, *, allow_single_hash: bool) -> str | None:
    hashes: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _SHA256_RE.search(line)
        if not match:
            continue
        digest = match.group(0).lower()
        hashes.append(digest)
        if target_name in line:
            return digest
    if allow_single_hash and len(set(hashes)) == 1:
        return hashes[0]
    return None


def _expected_sha256(asset: dict, release: dict | None = None) -> str | None:
    direct = _digest_from_asset(asset)
    if direct:
        return direct
    if not release:
        return None

    target_name = _asset_name(asset)
    for checksum_asset in _checksum_assets(release, target_name):
        checksum_name = _asset_name(checksum_asset)
        text = _download_text(_asset_url(checksum_asset))
        expected = _parse_checksum_text(
            text,
            target_name,
            allow_single_hash=checksum_name.startswith(target_name),
        )
        if expected:
            return expected
    return None


def _download_verified_asset(asset: dict, dest: Path, *, release: dict | None = None) -> str:
    """Download a GitHub release asset and verify its SHA256 digest.

    Verification uses the GitHub Release asset `digest` field when present, or
    a checksum asset in the same release (`*.sha256`, `SHA256SUMS`, etc.).
    The function refuses to leave an unverified executable/package on disk.
    """
    name = _asset_name(asset)
    expected = _expected_sha256(asset, release)
    if not expected:
        raise DownloadVerificationError(f"no SHA256 checksum found for {name}")

    _download(_asset_url(asset), dest)
    actual = _sha256(dest)
    if actual != expected:
        dest.unlink(missing_ok=True)
        raise DownloadVerificationError(
            f"SHA256 mismatch for {name}: expected {expected}, got {actual}"
        )
    return actual
