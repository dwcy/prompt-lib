"""Aggregated Home payload for GET /api/overview: dashboard/sessions/account/doctor/
knowledge/security summaries plus claude+codex deploy-drift flags."""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from cabal import diff_apply
from cabal.codex_setup import diff_apply as codex_diff_apply
from cabal.config_doctor import finding_order, run_doctor_cached
from cabal.gh_accounts import list_accounts
from cabal.manifest_doctor import manifest_report
from cabal.package_security import service as package_security_service
from cabal.web.serializers import serialize_knowledge_graph
from cabal.webapi.dashboard_service import SECTIONS, get_dashboard_section

_PROJECTS_DIR = Path.home() / ".claude" / "projects"
_MAX_RECENT_SESSIONS = 5
_DOCTOR_FINDINGS_SHOWN = 10
_EMPTY_SECURITY_SUMMARY = {"vulnerable": 0, "outdated": 0, "deprecated": 0, "notices": 0}

T = TypeVar("T")


def build_overview(project: Path | None) -> tuple[dict[str, Any], bool, list[str]]:
    """Return (overview_data, degraded, failed_sections) for the OVERVIEW_SECTION_KEYS payload."""
    sections: dict[str, Any] = {}
    failed_sections: list[str] = []

    for key, fallback, fn in (
        ("dashboard_summary", {"project_path": None, "sections": {}}, lambda: _dashboard_summary(project)),
        ("recent_sessions", [], lambda: _recent_sessions(project) if project is not None else []),
        ("account", {"authenticated": False, "active_account": None, "accounts": []}, _account_summary),
        ("doctor", {"healthy": True, "error_count": 0, "warning_count": 0, "findings": []}, lambda: _doctor_summary(project)),
        ("knowledge_availability", {"available": False, "counts": {}}, lambda: _knowledge_availability(project)),
        ("security_summary", dict(_EMPTY_SECURITY_SUMMARY), lambda: _security_summary(project) if project is not None else dict(_EMPTY_SECURITY_SUMMARY)),
        ("drift_flags", {"claude": False, "codex": False}, _drift_flags),
    ):
        value, ok = _safe(fn, fallback)
        sections[key] = value
        if not ok:
            failed_sections.append(key)

    return sections, bool(failed_sections), failed_sections


def _safe(fn: Callable[[], T], fallback: T) -> tuple[T, bool]:
    try:
        return fn(), True
    except Exception:
        return fallback, False


def _dashboard_summary(project: Path | None) -> dict[str, Any]:
    if project is None:
        return {"project_path": None, "sections": {}}
    sections: dict[str, Any] = {}
    for name in SECTIONS:
        data, stale = get_dashboard_section(project, name)
        sections[name] = {**data, "stale": stale}
    return {"project_path": str(project), "sections": sections}


def _project_dir_name(path: Path) -> str:
    """Mirror Claude Code's ~/.claude/projects/ directory-name encoding — same
    transform as `widgets/claude_sessions_panel.py`'s Textual-side counterpart."""
    return re.sub(r"[:/\\]", "-", str(path)).lower()


def _recent_sessions(project: Path) -> list[dict[str, Any]]:
    from cabal.session_pricing import load_pricing
    from cabal.session_reader import compute_summary, infer_session_tree, read_session, scan_projects_dir

    all_sessions = scan_projects_dir(_PROJECTS_DIR)
    encoded = _project_dir_name(project)
    matched = [s for s in all_sessions if _project_dir_name(Path(s.project_path)) == encoded]
    if not matched:
        return []

    pricing = load_pricing()
    summaries = [compute_summary(session, read_session(session), pricing) for session in matched]
    infer_session_tree(summaries)
    summaries.sort(
        key=lambda s: s.start_time or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return [
        {
            "session_id": s.session_id,
            "started_at": s.start_time.isoformat() if s.start_time else None,
            "branch": s.git_branch,
            "duration_seconds": s.duration_seconds,
            "cost_usd": s.estimated_cost_usd,
        }
        for s in summaries[:_MAX_RECENT_SESSIONS]
    ]


def _account_summary() -> dict[str, Any]:
    accounts = list_accounts()
    return {
        "authenticated": any(account.valid for account in accounts),
        "active_account": next((account.user for account in accounts if account.active), None),
        "accounts": [
            {"user": a.user, "host": a.host, "active": a.active, "valid": a.valid} for a in accounts
        ],
    }


def _doctor_summary(project: Path | None) -> dict[str, Any]:
    from cabal._paths import TARGET

    findings, _ = run_doctor_cached(TARGET, project=project)
    findings = [*findings, *manifest_report().findings]
    findings.sort(key=finding_order)
    errors = sum(1 for finding in findings if finding.severity == "error")
    return {
        "healthy": not findings,
        "error_count": errors,
        "warning_count": len(findings) - errors,
        "findings": [asdict(finding) for finding in findings[:_DOCTOR_FINDINGS_SHOWN]],
    }


def _knowledge_availability(project: Path | None) -> dict[str, Any]:
    graph = serialize_knowledge_graph(project or Path.cwd())
    return {"available": graph["available"], "counts": graph["counts"]}


def _security_summary(project: Path) -> dict[str, Any]:
    outcomes = package_security_service.load_cached(project)
    if outcomes is None:
        outcomes = package_security_service.scan_project(project)
        package_security_service.save_cache(project, outcomes)
    counts = {"vulnerable": 0, "outdated": 0, "deprecated": 0}
    notices = 0
    for outcome in outcomes:
        for finding in outcome.findings:
            counts[finding.kind] += 1
        notices += len(outcome.notices)
    return {**counts, "notices": notices}


def _drift_flags() -> dict[str, bool]:
    return {"claude": diff_apply.has_deploy_drift(), "codex": codex_diff_apply.has_codex_deploy_drift()}
