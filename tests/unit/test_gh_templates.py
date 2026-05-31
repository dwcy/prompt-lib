"""Unit tests for cabal.gh_templates (T068).

These tests are written ahead of the implementation. They MUST fail with
ImportError until cabal.gh_templates exists — that is the TDD red state.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _mk_completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


def test_filters_is_template_true():
    from cabal.gh_templates import list_user_templates

    payload = [
        {"isTemplate": True, "name": "tpl-a", "owner": {"login": "alice"},
         "description": "A", "defaultBranchRef": {"name": "main"},
         "url": "https://github.com/alice/tpl-a"},
        {"isTemplate": False, "name": "not-tpl", "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": {"name": "main"},
         "url": "https://github.com/alice/not-tpl"},
        {"isTemplate": True, "name": "tpl-b", "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": {"name": "master"},
         "url": "https://github.com/alice/tpl-b"},
    ]
    with patch("cabal.gh_templates.subprocess.run",
               return_value=_mk_completed(stdout=json.dumps(payload))):
        result = list_user_templates()

    assert len(result) == 2
    assert all(r.is_template is True for r in result)
    names = {r.name for r in result}
    assert names == {"tpl-a", "tpl-b"}
    by_name = {r.name: r for r in result}
    assert by_name["tpl-a"].owner == "alice"
    assert by_name["tpl-a"].default_branch == "main"
    assert by_name["tpl-b"].default_branch == "master"


def test_drops_entries_missing_defaultbranchref():
    from cabal.gh_templates import list_user_templates

    payload = [
        {"isTemplate": True, "name": "good", "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": {"name": "main"},
         "url": "https://github.com/alice/good"},
        {"isTemplate": True, "name": "empty-repo", "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": None,
         "url": "https://github.com/alice/empty-repo"},
    ]
    with patch("cabal.gh_templates.subprocess.run",
               return_value=_mk_completed(stdout=json.dumps(payload))):
        result = list_user_templates()

    assert len(result) == 1
    assert result[0].name == "good"


def test_drops_entries_with_empty_name():
    from cabal.gh_templates import list_user_templates

    payload = [
        {"isTemplate": True, "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": {"name": "main"},
         "url": "https://github.com/alice/"},
        {"isTemplate": True, "name": "ok", "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": {"name": "main"},
         "url": "https://github.com/alice/ok"},
    ]
    with patch("cabal.gh_templates.subprocess.run",
               return_value=_mk_completed(stdout=json.dumps(payload))):
        result = list_user_templates()

    assert len(result) == 1
    assert result[0].name == "ok"


def test_json_decode_error_raises_runtime_error():
    from cabal.gh_templates import list_user_templates

    with patch("cabal.gh_templates.subprocess.run",
               return_value=_mk_completed(stdout="not json {{")):
        with pytest.raises(RuntimeError, match="could not parse gh output"):
            list_user_templates()


def test_gh_not_found_raises_runtime_error():
    from cabal.gh_templates import list_user_templates

    with patch("cabal.gh_templates.subprocess.run",
               side_effect=FileNotFoundError("gh")):
        with pytest.raises(RuntimeError,
                           match="gh not found on PATH — install GitHub CLI first"):
            list_user_templates()


def test_gh_nonzero_returncode_raises():
    from cabal.gh_templates import list_user_templates

    with patch("cabal.gh_templates.subprocess.run",
               return_value=_mk_completed(returncode=1, stderr="not authenticated")):
        with pytest.raises(RuntimeError, match="not authenticated"):
            list_user_templates()


def test_missing_is_template_field_returns_empty():
    from cabal.gh_templates import list_user_templates

    payload = [
        {"name": "old-a", "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": {"name": "main"},
         "url": "https://github.com/alice/old-a"},
        {"name": "old-b", "owner": {"login": "alice"},
         "description": None, "defaultBranchRef": {"name": "main"},
         "url": "https://github.com/alice/old-b"},
    ]
    with patch("cabal.gh_templates.subprocess.run",
               return_value=_mk_completed(stdout=json.dumps(payload))):
        result = list_user_templates()

    assert result == []


def test_subprocess_argv_shape():
    from cabal.gh_templates import list_user_templates

    with patch("cabal.gh_templates.subprocess.run",
               return_value=_mk_completed(stdout="[]")) as run_mock:
        list_user_templates()

    argv = run_mock.call_args.args[0]
    assert argv == [
        "gh", "repo", "list",
        "--json", "isTemplate,name,owner,description,defaultBranchRef,url",
        "--limit", "200",
    ]
