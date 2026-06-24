# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib

import pytest

from cabal import gh_release


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_download_verified_asset_accepts_github_digest(tmp_path, monkeypatch):
    payload = b"verified"
    digest = _sha256(payload)
    dest = tmp_path / "tool.exe"

    def fake_download(_url: str, target):
        target.write_bytes(payload)

    monkeypatch.setattr(gh_release, "_download", fake_download)

    result = gh_release._download_verified_asset(
        {
            "name": "tool.exe",
            "browser_download_url": "https://example.test/tool.exe",
            "digest": f"sha256:{digest}",
        },
        dest,
    )

    assert result == digest
    assert dest.read_bytes() == payload


def test_download_verified_asset_accepts_release_checksum_file(tmp_path, monkeypatch):
    payload = b"verified"
    digest = _sha256(payload)
    dest = tmp_path / "tool.exe"

    def fake_download(_url: str, target):
        target.write_bytes(payload)

    monkeypatch.setattr(gh_release, "_download", fake_download)
    monkeypatch.setattr(
        gh_release,
        "_download_text",
        lambda _url: f"{digest}  tool.exe\n",
    )

    result = gh_release._download_verified_asset(
        {"name": "tool.exe", "browser_download_url": "https://example.test/tool.exe"},
        dest,
        release={
            "assets": [
                {
                    "name": "SHA256SUMS",
                    "browser_download_url": "https://example.test/SHA256SUMS",
                }
            ]
        },
    )

    assert result == digest
    assert dest.read_bytes() == payload


def test_download_verified_asset_rejects_mismatch_and_removes_file(tmp_path, monkeypatch):
    dest = tmp_path / "tool.exe"

    def fake_download(_url: str, target):
        target.write_bytes(b"tampered")

    monkeypatch.setattr(gh_release, "_download", fake_download)

    with pytest.raises(gh_release.DownloadVerificationError, match="SHA256 mismatch"):
        gh_release._download_verified_asset(
            {
                "name": "tool.exe",
                "browser_download_url": "https://example.test/tool.exe",
                "digest": f"sha256:{_sha256(b'expected')}",
            },
            dest,
        )

    assert not dest.exists()


def test_download_rejects_non_https_url(tmp_path):
    with pytest.raises(gh_release.DownloadVerificationError, match="non-HTTPS"):
        gh_release._download("http://example.test/tool.exe", tmp_path / "tool.exe")
