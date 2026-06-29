"""Serializers that expose Cabal data to the local web UI."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cabal.models.dashboard import (
    AvailabilityState,
    GitHubSection,
    GitSection,
    SupabaseSection,
    VercelSection,
)
from cabal.tool_catalog import (
    InstallChannel,
    SourceStatus,
    all_tool_definitions,
    category_slug,
    get_tool_definition,
)
from cabal.tools import _probe_key, _tool_unavailable_reason
from cabal.web.redaction import redact_text, redact_url, redact_value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def diagnostic_event(
    section: str,
    message: str,
    *,
    severity: str = "error",
    details: str | None = None,
    retryable: bool = True,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    safe_message = redact_text(message)
    return {
        "id": event_id or f"{section}:{severity}:{abs(hash((section, safe_message))) % 100000}",
        "section": section,
        "severity": severity,
        "message": safe_message,
        "details": redact_text(details) if details else None,
        "timestamp": timestamp or utc_now(),
        "retryable": bool(retryable),
    }


def section_health(
    section: str,
    state: str = "ready",
    *,
    message: str | None = None,
    retryable: bool = True,
    last_success_at: str | None = None,
) -> dict[str, Any]:
    return {
        "section": section,
        "state": state,
        "last_success_at": last_success_at,
        "message": redact_text(message) if message else None,
        "retryable": bool(retryable),
    }


def serialize_backend_health(
    *,
    host: str = "127.0.0.1",
    backend_version: str | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    diagnostics = diagnostics or []
    sections = [
        section_health("overview"),
        section_health("tools"),
        section_health("knowledge"),
        section_health("project_health"),
        section_health("diagnostics"),
    ]
    return redact_value(
        {
            "app": "cabal-web",
            "backend_version": backend_version,
            "read_only": True,
            "host": host,
            "sections": sections,
            "diagnostics": diagnostics,
        }
    )


def serialize_tool_catalog(*, include_status: bool = True) -> dict[str, Any]:
    items = [serialize_tool_item(tool.key, include_status=include_status) for tool in all_tool_definitions()]
    category_names = []
    categories_by_name: dict[str, list[str]] = {}
    for item in items:
        name = item["category"]
        if name not in categories_by_name:
            category_names.append(name)
            categories_by_name[name] = []
        categories_by_name[name].append(item["key"])
    categories = [
        {
            "name": name,
            "slug": category_slug(name),
            "keys": keys,
            "count": len(keys),
        }
        for name, keys in ((name, categories_by_name[name]) for name in category_names)
    ]
    return redact_value(
        {
            "categories": categories,
            "items": items,
            "status_counts": dict(Counter(item["status"] for item in items)),
            "source_status_counts": dict(Counter(item["source_status"] for item in items)),
            "install_channel_counts": dict(Counter(item["install_channel"] for item in items)),
        }
    )


def serialize_tool_item(key: str, *, include_status: bool = True) -> dict[str, Any]:
    definition = get_tool_definition(key)
    if definition is None:
        return {
            "key": key,
            "label": key,
            "category": "Unknown",
            "description": "",
            "source_url": None,
            "source_label": "Read more",
            "source_status": SourceStatus.UNAVAILABLE.value,
            "install_channel": InstallChannel.NONE.value,
            "platforms": [],
            "supports_current_platform": False,
            "status": "error",
            "status_detail": "Tool definition missing",
            "version_provider": None,
            "backup_policy": None,
            "badges": [],
            "safety_notes": ["Tool definition missing from cabal.tool_catalog."],
        }
    status, detail, notes = _tool_status(definition.key, include_status=include_status)
    source_url = redact_url(definition.source_url) if definition.source_url else None
    return {
        "key": definition.key,
        "label": definition.label,
        "category": definition.category,
        "description": redact_text(definition.description),
        "source_url": source_url,
        "source_label": definition.source_label,
        "source_status": definition.source_status.value,
        "install_channel": definition.install_channel.value,
        "platforms": list(definition.platforms),
        "supports_current_platform": definition.supports_current_platform,
        "status": status,
        "status_detail": redact_text(detail) if detail else None,
        "version_provider": definition.version_provider,
        "backup_policy": definition.backup_policy,
        "badges": list(definition.badges),
        "safety_notes": [redact_text(note) for note in notes],
    }


def serialize_knowledge_graph(project_root: Path) -> dict[str, Any]:
    graph_path = project_root / "docs" / "okf" / "prompt-lib" / "graph.json"
    if not graph_path.exists():
        return {
            "available": False,
            "bundle_path": None,
            "counts": {"nodes": 0, "edges": 0, "by_type": {}, "by_relation": {}},
            "nodes": [],
            "edges": [],
            "diagnostics": [
                diagnostic_event(
                    "knowledge",
                    "No OKF graph bundle exists. Run the OKF export before using this view.",
                    severity="info",
                    retryable=True,
                )
            ],
        }
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {
            "available": False,
            "bundle_path": _repo_relative(project_root, graph_path),
            "counts": {"nodes": 0, "edges": 0, "by_type": {}, "by_relation": {}},
            "nodes": [],
            "edges": [],
            "diagnostics": [
                diagnostic_event("knowledge", "Failed to read OKF graph.", details=str(exc))
            ],
        }

    nodes = [_serialize_node(item) for item in graph.get("nodes", []) if isinstance(item, dict)]
    edges = [_serialize_edge(item) for item in graph.get("edges", []) if isinstance(item, dict)]
    return redact_value(
        {
            "available": True,
            "bundle_path": _repo_relative(project_root, graph_path),
            "counts": {
                "nodes": len(nodes),
                "edges": len(edges),
                "by_type": dict(Counter(node["type"] for node in nodes)),
                "by_relation": dict(Counter(edge["kind"] for edge in edges)),
            },
            "nodes": nodes,
            "edges": edges,
            "diagnostics": [],
        }
    )


def serialize_project_health(project_root: Path) -> dict[str, Any]:
    from cabal.dashboard_git_service import collect_git
    from cabal.dashboard_github_service import collect_github
    from cabal.dashboard_supabase_service import collect_supabase
    from cabal.dashboard_vercel_service import collect_vercel

    captured_at = utc_now()
    diagnostics: list[dict[str, Any]] = []
    git = _collect_section("project_health", "Git", lambda: collect_git(project_root), diagnostics)
    github = _collect_section(
        "project_health",
        "GitHub",
        lambda: collect_github(
            project_root,
            git.current_branch if isinstance(git, GitSection) else None,
            git.remotes if isinstance(git, GitSection) else [],
        ),
        diagnostics,
    )
    supabase = _collect_section("project_health", "Supabase", lambda: collect_supabase(project_root), diagnostics)
    vercel = _collect_section("project_health", "Vercel", lambda: collect_vercel(project_root), diagnostics)
    return redact_value(
        {
            "project_path": str(project_root),
            "captured_at": captured_at,
            "git": serialize_project_section("Git", git),
            "github": serialize_project_section("GitHub", github),
            "supabase": serialize_project_section("Supabase", supabase),
            "vercel": serialize_project_section("Vercel", vercel),
            "diagnostics": diagnostics,
        }
    )


def serialize_project_section(title: str, section: object) -> dict[str, Any]:
    if isinstance(section, GitSection):
        facts = [
            _fact("branch", section.current_branch),
            _fact("detached", "yes" if section.detached else "no"),
            _fact("local branches", str(len(section.local_branches))),
            *[_fact(f"remote {remote.name}", remote.url) for remote in section.remotes],
        ]
        links = [_link("remote", remote.url) for remote in section.remotes if remote.url.startswith("http")]
    elif isinstance(section, GitHubSection):
        facts = [
            _fact("repo", section.owner_repo),
            _fact("remote", section.remote_used),
            _fact("workflow runs", str(len(section.runs))),
            _fact("open PRs", str(len(section.pull_requests))),
        ]
        links = [_link("run", run.url) for run in section.runs if run.url]
        links.extend(_link("PR", pr.url) for pr in section.pull_requests if pr.url)
    elif isinstance(section, SupabaseSection):
        facts = [
            _fact("ref", section.project_ref),
            _fact("status", section.status),
            _fact("region", section.region),
            _fact("plan", section.plan_name),
            _fact("db location", section.db_location),
            _fact("last migration", section.last_migration),
            _fact("last backup", section.last_backup),
        ]
        links = [_link("dashboard", section.dashboard_url), _link("schema visualizer", section.schema_visualizer_url)]
    elif isinstance(section, VercelSection):
        facts = [
            _fact("project", section.project_name),
            _fact("project id", section.project_id),
            _fact("deployment", section.latest_deployment_status),
            _fact("team / plan", section.team_plan),
        ]
        links = [_link("dashboard", section.dashboard_url), _link("latest deployment", section.latest_deployment_url)]
    else:
        return {
            "state": AvailabilityState.ERROR.value,
            "title": title,
            "summary": "Section unavailable",
            "facts": [],
            "links": [],
            "hint": "Section collector failed.",
            "enrich_state": None,
        }

    facts = [fact for fact in facts if fact["value"]]
    links = [link for link in links if link["url"]]
    state = _state_value(getattr(section, "state", AvailabilityState.ERROR))
    hint = getattr(section, "hint", None)
    enrich_state = getattr(section, "enrich_state", None)
    return {
        "state": state,
        "title": title,
        "summary": _section_summary(title, state, facts, hint),
        "facts": facts,
        "links": links,
        "hint": redact_text(hint) if hint else None,
        "enrich_state": _state_value(enrich_state) if enrich_state else None,
        "enrich_hint": redact_text(getattr(section, "enrich_hint", None) or "") or None,
    }


def serialize_overview(project_root: Path, diagnostics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    diagnostics = list(diagnostics or [])
    sections: list[dict[str, Any]] = []

    try:
        tools = serialize_tool_catalog(include_status=False)
        sections.append(section_health("tools", message=f"{len(tools['items'])} tools indexed"))
    except Exception as exc:  # pragma: no cover - exercised via API contract monkeypatches
        tools = {"items": [], "status_counts": {}}
        diagnostics.append(diagnostic_event("tools", "Tool catalog summary failed.", details=str(exc)))
        sections.append(section_health("tools", state="error", message="Tool catalog unavailable"))

    try:
        knowledge = serialize_knowledge_graph(project_root)
        sections.append(
            section_health(
                "knowledge",
                state="ready" if knowledge["available"] else "unavailable",
                message="OKF graph loaded" if knowledge["available"] else "OKF graph not generated",
            )
        )
    except Exception as exc:  # pragma: no cover - exercised via API contract monkeypatches
        knowledge = {
            "available": False,
            "counts": {"nodes": 0, "edges": 0, "by_type": {}, "by_relation": {}},
        }
        diagnostics.append(diagnostic_event("knowledge", "Knowledge summary failed.", details=str(exc)))
        sections.append(section_health("knowledge", state="error", message="Knowledge summary unavailable"))

    try:
        project_health = serialize_project_health(project_root)
        sections.append(section_health("project_health", message="Project health snapshot available"))
    except Exception as exc:  # pragma: no cover - exercised via API contract monkeypatches
        project_health = {}
        diagnostics.append(diagnostic_event("project_health", "Project health summary failed.", details=str(exc)))
        sections.append(section_health("project_health", state="error", message="Project health unavailable"))

    health_counts = Counter(
        section["state"]
        for section in (
            project_health.get("git", {}),
            project_health.get("github", {}),
            project_health.get("supabase", {}),
            project_health.get("vercel", {}),
        )
        if section.get("state")
    )
    sections.append(section_health("diagnostics", message=f"{len(diagnostics)} diagnostics"))
    return redact_value(
        {
            "tool_count": len(tools["items"]),
            "tool_status_counts": tools["status_counts"],
            "knowledge_available": knowledge["available"],
            "knowledge_counts": knowledge["counts"],
            "project_health_counts": dict(health_counts),
            "diagnostic_count": len(diagnostics),
            "sections": sections,
            "diagnostics": diagnostics,
        }
    )


def diagnostics_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(event.get("severity") or "info") for event in events))


def _tool_status(key: str, *, include_status: bool) -> tuple[str, str | None, list[str]]:
    reason = _tool_unavailable_reason(key)
    definition = get_tool_definition(key)
    if definition and not definition.supports_current_platform:
        return "unsupported", reason, [reason or "Unsupported on this platform."]
    if definition and definition.source_status == SourceStatus.MANUAL_REQUIRED:
        return "manual_required", reason, [reason or "Source confirmation required."]
    if definition and definition.source_status == SourceStatus.UNAVAILABLE:
        return "source_unavailable", reason, [reason or "Source unavailable."]
    if not include_status:
        return "loading", "Status probe deferred", []
    try:
        value = _probe_key(key)
    except Exception as exc:  # pragma: no cover - defensive around local host tools
        return "error", str(exc), ["Status probe failed."]
    if isinstance(value, dict):
        status = str(value.get("status") or "installed")
        detail = value.get("detail")
        notes = value.get("notes") if isinstance(value.get("notes"), list) else []
        return status, str(detail) if detail else None, [str(note) for note in notes]
    if isinstance(value, str) and value.strip():
        return "installed", value.strip(), []
    if value:
        return "installed", None, []
    return "missing", None, []


def _serialize_node(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "label": str(item.get("label") or item.get("id") or ""),
        "type": str(item.get("type") or "unknown"),
        "resource": str(item.get("resource") or item.get("doc") or ""),
        "tags": [str(tag) for tag in item.get("tags", []) if tag is not None],
    }


def _serialize_edge(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "source": str(item.get("source") or ""),
        "target": str(item.get("target") or "") or None,
        "target_ref": str(item.get("target_ref") or "") or None,
        "kind": str(item.get("kind") or "related"),
        "reason": redact_text(item.get("reason") or ""),
        "confidence": str(item.get("confidence") or "explicit"),
        "evidence": [
            {
                "resource": str(evidence.get("resource") or ""),
                "line": evidence.get("line") if isinstance(evidence.get("line"), int) else None,
                "text": redact_text(evidence.get("text") or ""),
            }
            for evidence in item.get("evidence", [])
            if isinstance(evidence, dict)
        ],
    }


def _collect_section(section_name: str, title: str, fn, diagnostics: list[dict[str, Any]]) -> object:
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensive around host integrations
        diagnostics.append(
            diagnostic_event(section_name, f"{title} collector failed.", details=str(exc))
        )
        return None


def _state_value(value: object) -> str:
    if isinstance(value, AvailabilityState):
        return value.value
    return str(value) if value is not None else AvailabilityState.ERROR.value


def _fact(label: str, value: object) -> dict[str, str]:
    return {"label": label, "value": redact_text(value) if value is not None else ""}


def _link(label: str, url: object) -> dict[str, str | None]:
    return {"label": label, "url": redact_url(url) if url else None}


def _section_summary(title: str, state: str, facts: list[dict[str, str]], hint: str | None) -> str:
    if state == AvailabilityState.OK.value and facts:
        return f"{title} ready: {facts[0]['value']}"
    if hint:
        return redact_text(hint)
    return f"{title} state: {state}"


def _repo_relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def to_plain(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    return value
