"""Unit tests for cabal.dashboard_links — pure link-file parsing + URL derivation.

Covers C-L1 (parse_github_remote over HTTPS/SSH/non-GitHub) and C-L2 (Supabase/Vercel
link discovery from temp dirs). No subprocess, no network.
"""

from __future__ import annotations

import json

import pytest

from cabal.dashboard_links import (
    find_supabase_ref,
    find_vercel_link,
    parse_github_remote,
    supabase_dashboard_url,
    supabase_schema_url,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/o/r", ("o", "r")),
        ("https://github.com/o/r.git", ("o", "r")),
        ("git@github.com:o/r.git", ("o", "r")),
        ("https://gitlab.com/o/r", None),
        ("https://github.com/only-owner", None),
    ],
)
def test_parse_github_remote(url, expected):
    assert parse_github_remote(url) == expected


def test_find_supabase_ref_returns_none_when_no_file(tmp_project_dir):
    assert find_supabase_ref(tmp_project_dir) is None


def test_find_supabase_ref_reads_project_id_from_config(tmp_project_dir):
    config = tmp_project_dir / "supabase" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('project_id = "abcdefgh"\n', encoding="utf-8")

    assert find_supabase_ref(tmp_project_dir) == "abcdefgh"


def test_supabase_dashboard_url_contains_ref_and_project_segment():
    url = supabase_dashboard_url("abc")

    assert "abc" in url
    assert "/dashboard/project/" in url


def test_supabase_schema_url_contains_ref_and_schema_segment():
    url = supabase_schema_url("abc")

    assert "abc" in url
    assert url.endswith("/database/schemas")


def test_find_vercel_link_returns_pair_of_none_when_absent(tmp_project_dir):
    assert find_vercel_link(tmp_project_dir) == (None, None)


def test_find_vercel_link_reads_project_and_org_ids(tmp_project_dir):
    link = tmp_project_dir / ".vercel" / "project.json"
    link.parent.mkdir(parents=True)
    link.write_text(json.dumps({"projectId": "p1", "orgId": "o1"}), encoding="utf-8")

    assert find_vercel_link(tmp_project_dir) == ("p1", "o1")
