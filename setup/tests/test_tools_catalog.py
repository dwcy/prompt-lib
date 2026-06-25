# -*- coding: utf-8 -*-
"""Contract tests for the Cabal Tools metadata catalog."""

from __future__ import annotations

from cabal import tools
from cabal.tool_catalog import (
    CATALOG_BY_KEY,
    SourceStatus,
    get_tool_definition,
    redact_secret_text,
    validate_catalog,
)


def _rendered_keys() -> list[str]:
    return [key for _group, keys in tools.ENV_TOOL_GROUPS for key in keys]


def test_all_rendered_tools_have_metadata():
    for key in _rendered_keys():
        assert key in CATALOG_BY_KEY
        assert tools._installer_for(key) is not None


def test_all_tools_have_description_and_source_status():
    assert validate_catalog() == []
    for definition in CATALOG_BY_KEY.values():
        assert definition.description.strip()
        assert definition.source_status in SourceStatus
        if definition.source_status == SourceStatus.VERIFIED:
            assert definition.source_url


def test_source_required_tools_disable_automation():
    definition = get_tool_definition("hermes-agent")

    assert definition is not None
    assert definition.source_status == SourceStatus.MANUAL_REQUIRED
    assert definition.automation_enabled is False


def test_requested_tools_are_in_expected_categories():
    groups = dict(tools.ENV_TOOL_GROUPS)

    assert {"lm-studio", "hermes-agent", "opencode", "ollama", "vllm"} <= set(groups["Local AI"])
    assert {"zed", "rider", "visualstudio", "cursor", "windsurf", "antigravity", "vscode"} <= set(groups["AI Editors / IDEs"])
    assert {"turso-libsql", "duckdb", "sqlite", "redis", "mariadb", "qdrant", "weaviate", "milvus"} <= set(groups["Databases"])
    assert {"ssms", "dbeaver"} <= set(groups["Database Clients"])
    assert {"azure-sql-local", "cosmos-db-emulator", "azurite"} <= set(groups["Azure Local Tools"])
    assert {"postman", "hugo", "uvicorn"} <= set(groups["Developer Tools"])


def test_existing_tools_are_not_dropped():
    rendered = set(_rendered_keys())
    existing = {
        "git",
        "python",
        "dotnet",
        "node",
        "npm",
        "pnpm",
        "bun",
        "docker",
        "podman",
        "kubectl",
        "oc",
        "terraform",
        "az",
        "gcloud",
        "aws",
        "claude",
        "gemini",
        "codex",
        "opencode",
        "grok",
        "skills",
        "vercel-plugin",
        "cursor",
        "windsurf",
        "copilot",
        "antigravity",
        "vscode",
        "ollama",
        "vllm",
        "gh",
        "sqlcmd",
        "psql",
        "supabase",
        "neonctl",
    }

    assert existing <= rendered


def test_no_secret_shaped_literals_in_tool_metadata():
    for definition in CATALOG_BY_KEY.values():
        assert redact_secret_text(definition.description) == definition.description
        if definition.source_url:
            assert redact_secret_text(definition.source_url) == definition.source_url


def test_unsupported_platform_rows_remain_visible_and_disabled(monkeypatch):
    import cabal.tool_catalog as catalog

    monkeypatch.setattr(catalog.platform, "system", lambda: "Darwin")
    definition = get_tool_definition("visualstudio")

    assert definition is not None
    assert definition.supports_current_platform is False
    assert "visualstudio" in dict(tools.ENV_TOOL_GROUPS)["AI Editors / IDEs"]
    assert "Supported on Windows" in (tools._tool_unavailable_reason("visualstudio") or "")
