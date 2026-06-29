"""Unit coverage for Cabal web serializers."""

from __future__ import annotations

import json

from cabal.models.dashboard import AvailabilityState, GitRemote, GitSection, SupabaseSection, VercelSection
from cabal.web import serializers
from cabal.web.redaction import REDACTION_MARKER


def _token() -> str:
    return "ghp_" + ("T" * 36)


def test_diagnostic_event_has_required_fields_and_redacts_text() -> None:
    token = _token()

    event = serializers.diagnostic_event("tools", f"failed {token}", details=f"Bearer {token}")

    assert {"id", "section", "severity", "message", "details", "timestamp", "retryable"} <= set(event)
    assert token not in json.dumps(event)
    assert REDACTION_MARKER in json.dumps(event)


def test_section_health_defaults_to_retryable_ready_state() -> None:
    health = serializers.section_health("tools", message="ready")

    assert health == {
        "section": "tools",
        "state": "ready",
        "last_success_at": None,
        "message": "ready",
        "retryable": True,
    }


def test_backend_health_is_read_only_and_lists_sections() -> None:
    health = serializers.serialize_backend_health(host="127.0.0.1")

    assert health["app"] == "cabal-web"
    assert health["read_only"] is True
    assert {section["section"] for section in health["sections"]} >= {"tools", "knowledge"}


def test_tool_item_serializer_maps_catalog_metadata(monkeypatch) -> None:
    monkeypatch.setattr(serializers, "_probe_key", lambda _key: "git version 2")
    monkeypatch.setattr(serializers, "_tool_unavailable_reason", lambda _key: None)

    item = serializers.serialize_tool_item("git")

    assert item["key"] == "git"
    assert item["label"]
    assert item["category"]
    assert item["status"] == "installed"
    assert "source_url" in item


def test_tool_item_serializer_accepts_structured_future_status(monkeypatch) -> None:
    monkeypatch.setattr(
        serializers,
        "_probe_key",
        lambda _key: {"status": "update_available", "detail": "2 -> 3", "notes": ["upgrade available"]},
    )
    monkeypatch.setattr(serializers, "_tool_unavailable_reason", lambda _key: None)

    item = serializers.serialize_tool_item("git")

    assert item["status"] == "update_available"
    assert item["status_detail"] == "2 -> 3"
    assert item["safety_notes"] == ["upgrade available"]


def test_tool_catalog_serializer_groups_categories(monkeypatch) -> None:
    monkeypatch.setattr(serializers, "_tool_unavailable_reason", lambda _key: None)

    catalog = serializers.serialize_tool_catalog(include_status=False)

    assert catalog["categories"]
    assert catalog["items"]
    assert catalog["status_counts"]
    assert catalog["install_channel_counts"]


def test_knowledge_graph_serializer_reads_okf_graph(tmp_path) -> None:
    graph_dir = tmp_path / "docs" / "okf" / "prompt-lib"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [{"id": "agent:python", "label": "Python", "type": "agent", "tags": ["code"]}],
                "edges": [
                    {
                        "id": "e1",
                        "source": "agent:python",
                        "target": "skill:test",
                        "kind": "uses",
                        "reason": "covers " + _token(),
                        "confidence": "explicit",
                        "evidence": [{"resource": "x.md", "line": 4, "text": "token " + _token()}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = serializers.serialize_knowledge_graph(tmp_path)

    assert graph["available"] is True
    assert graph["counts"]["nodes"] == 1
    assert graph["counts"]["edges"] == 1
    assert _token() not in json.dumps(graph)


def test_knowledge_graph_serializer_returns_missing_bundle_empty_state(tmp_path) -> None:
    graph = serializers.serialize_knowledge_graph(tmp_path)

    assert graph["available"] is False
    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["diagnostics"][0]["severity"] == "info"


def test_project_section_serializer_redacts_remote_urls() -> None:
    token = _token()
    section = GitSection(
        state=AvailabilityState.OK,
        current_branch="main",
        remotes=[GitRemote("origin", f"https://github.com/o/r?token={token}", True)],
    )

    data = serializers.serialize_project_section("Git", section)

    assert token not in json.dumps(data)
    assert "token=[redacted]" in json.dumps(data)


def test_project_section_serializer_handles_cloud_sections() -> None:
    supabase = SupabaseSection(
        state=AvailabilityState.TOKEN_MISSING,
        dashboard_url="https://supabase.test/project",
        project_ref="abc",
    )
    vercel = VercelSection(
        state=AvailabilityState.NOT_LINKED,
        project_name="site",
        dashboard_url="https://vercel.test/site",
    )

    assert serializers.serialize_project_section("Supabase", supabase)["title"] == "Supabase"
    assert serializers.serialize_project_section("Vercel", vercel)["title"] == "Vercel"


def test_overview_serializer_degrades_failed_project_health(monkeypatch, tmp_path) -> None:
    def broken(_root):
        raise RuntimeError("SECRET=" + _token())

    monkeypatch.setattr(serializers, "serialize_project_health", broken)
    monkeypatch.setattr(serializers, "_tool_unavailable_reason", lambda _key: None)

    overview = serializers.serialize_overview(tmp_path)

    assert any(section["state"] == "error" for section in overview["sections"])
    assert _token() not in json.dumps(overview)
