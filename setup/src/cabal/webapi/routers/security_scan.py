"""Package security scan routes, confirmed fix/install actions, and the per-package AI advisor."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from cabal.package_security import ai_advisor
from cabal.package_security.models import Finding, ScanOutcome
from cabal.package_security import service as package_security
from cabal.webapi import security
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError, compute_precondition_digest, envelope_response, utc_now_iso

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

SECURITY_APPLY_FIX_ACTION_ID = "security.apply_fix"
SECURITY_INSTALL_PIP_AUDIT_ACTION_ID = "security.install_pip_audit"
_INSTALL_TIMEOUT_SECONDS = 120

_FIX_SCHEMA = {
    "type": "object",
    "properties": {"finding_key": {"type": "string"}},
    "required": ["finding_key"],
    "additionalProperties": False,
}

_INSTALL_PIP_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def _project_path(state: Any) -> Path:
    project = getattr(state, "project", None)
    if project is None:
        raise ApiError(404, "no_project_selected", "Select a project before scanning package security")
    return Path(project)


def _finding_payload(finding: Finding) -> dict[str, Any]:
    return {
        "key": finding.key,
        "ecosystem": finding.ecosystem,
        "package": finding.package,
        "kind": finding.kind,
        "severity": finding.severity,
        "current": finding.current_version,
        "target": finding.target_version,
        "fix_available": bool(finding.fix_command),
        "fix_command_preview": finding.fix_command or "",
        "detail": finding.detail,
    }


def _outcome_payload(outcome: ScanOutcome) -> dict[str, Any]:
    return {
        "ecosystem": outcome.ecosystem,
        "findings": [_finding_payload(finding) for finding in outcome.findings],
        "notices": list(outcome.notices),
    }


def _scan_payload(project: Path, *, refresh: bool) -> tuple[dict[str, Any], bool]:
    cached = False
    outcomes = None if refresh else package_security.load_cached(project)
    if outcomes is None:
        outcomes = package_security.scan_project(project)
        package_security.save_cache(project, outcomes)
    else:
        cached = True
    findings = [finding for outcome in outcomes for finding in outcome.findings]
    notices = [notice for outcome in outcomes for notice in outcome.notices]
    data = {
        "project": str(project),
        "scanned_at": utc_now_iso(),
        "cached": cached,
        "ecosystems": [outcome.ecosystem for outcome in outcomes],
        "findings": [_finding_payload(finding) for finding in findings],
        "outcomes": [_outcome_payload(outcome) for outcome in outcomes],
        "notices": notices,
        "summary": {
            "total": len(findings),
            "fixable": sum(1 for finding in findings if finding.fix_command),
            "by_severity": _count_by(findings, "severity"),
            "by_ecosystem": _count_by(findings, "ecosystem"),
        },
    }
    return data, cached


def _count_by(findings: list[Finding], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        value = str(getattr(finding, field))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _find_finding(project: Path, key: str) -> Finding:
    outcomes = package_security.load_cached(project)
    if outcomes is None:
        outcomes = package_security.scan_project(project)
        package_security.save_cache(project, outcomes)
    for outcome in outcomes:
        for finding in outcome.findings:
            if finding.key == key:
                return finding
    raise ApiError(404, "finding_not_found", f"Unknown package security finding {key!r}")


def security_digest(project: Path) -> str:
    outcomes = package_security.load_cached(project) or []
    return compute_precondition_digest(
        {
            "project": str(project),
            "findings": [
                asdict(finding) for outcome in outcomes for finding in outcome.findings
            ],
        }
    )


@router.get("/api/security/scan")
def security_scan(request: Request, refresh: bool = False):
    project = _project_path(request.app.state)
    data, _cached = _scan_payload(project, refresh=refresh)
    return envelope_response(
        data=data,
        source="security_scan",
        precondition_digest=security_digest(project),
    )


def _advisor_payload(answer: Any) -> dict[str, Any] | None:
    if not answer.ok or answer.docs is None:
        return None
    return {
        "verdict": answer.verdict,
        "verdict_summary": answer.verdict_summary,
        "what_it_solves": answer.what_it_solves,
        "official_docs": {
            "url": answer.docs.url,
            "confident": answer.docs.confident,
            "description": answer.docs.description,
        },
        "alternatives": [
            {"name": alt.name, "reason": alt.reason} for alt in answer.alternatives
        ],
        "warning": answer.warning,
    }


@router.get("/api/security/ask")
def security_ask(request: Request, finding_key: str):
    """One-shot, unremembered AI opinion on a single finding — never cached, always re-asked.

    Always envelope-status "ok": a CLI/parse failure is honest, displayable content (`ok: false`
    + `error`), not a system error — the caller renders the structured `answer` when present, or
    the `error` message when not.
    """
    project = _project_path(request.app.state)
    finding = _find_finding(project, finding_key)
    answer = ai_advisor.ask_about_finding(finding)
    data = {
        "finding_key": finding_key,
        "ok": answer.ok,
        "model": answer.model,
        "error": answer.error,
        "answer": _advisor_payload(answer),
    }
    return envelope_response(data=data, source="security_ask")


def _apply_fix_prepare(params: dict, state: Any) -> dict:
    project = _project_path(state)
    finding = _find_finding(project, params["finding_key"])
    if not finding.fix_command:
        raise ApiError(422, "fix_unavailable", "This finding has no automated fix command")
    return {
        "summary": f"Apply package security fix for {finding.package}",
        "commands": [finding.fix_command],
        "files_changed": [str(project)],
        "scopes": ["package_security", finding.ecosystem],
        "backup": None,
        "removals": [],
    }


def _apply_fix_execute(params: dict, state: Any) -> ActionOutcome:
    project = _project_path(state)
    finding = _find_finding(project, params["finding_key"])

    def runner(handle) -> None:
        if not finding.fix_command:
            handle.finish("failed", exit_detail="No automated fix command")
            return
        handle.emit_line(f"Running: {finding.fix_command}")
        ok, message = package_security.apply_fix(finding, project)
        handle.emit_line(message)
        if ok:
            package_security.clear_cache(project)
        handle.finish("succeeded" if ok else "failed", exit_detail=None if ok else message)

    job = state.jobs.create(
        f"security.apply_fix:{finding.key}",
        runner=runner,
        exclusive_resource=f"security:{project}:{finding.key}",
    )
    return ActionOutcome(job_id=job.job_id)


SECURITY_APPLY_FIX_DESCRIPTOR = ActionDescriptor(
    action_id=SECURITY_APPLY_FIX_ACTION_ID,
    module="package_security",
    destructive=False,
    backup_policy=None,
    params_schema=_FIX_SCHEMA,
    prepare=_apply_fix_prepare,
    execute=_apply_fix_execute,
    compute_digest=lambda _params, state: security_digest(_project_path(state)),
)


def _install_pip_audit_prepare(_params: dict, _state: Any) -> dict:
    return {
        "summary": "Install pip-audit into this Python environment",
        "commands": [f"{sys.executable} -m pip install pip-audit"],
        "files_changed": [],
        "scopes": ["package_security", "python"],
        "backup": None,
        "removals": [],
    }


def _install_pip_audit_execute(_params: dict, state: Any) -> ActionOutcome:
    project = _project_path(state)

    def runner(handle) -> None:
        command = [sys.executable, "-m", "pip", "install", "pip-audit"]
        handle.emit_line(f"Running: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=_INSTALL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            handle.finish("failed", exit_detail=str(exc))
            return
        for line in (result.stdout or "").splitlines():
            handle.emit_line(line)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "pip install failed").strip()[:400]
            handle.finish("failed", exit_detail=detail)
            return
        package_security.clear_cache(project)
        handle.finish("succeeded")

    job = state.jobs.create(
        "security.install_pip_audit",
        runner=runner,
        exclusive_resource=f"security:{project}:install_pip_audit",
    )
    return ActionOutcome(job_id=job.job_id)


SECURITY_INSTALL_PIP_AUDIT_DESCRIPTOR = ActionDescriptor(
    action_id=SECURITY_INSTALL_PIP_AUDIT_ACTION_ID,
    module="package_security",
    destructive=False,
    backup_policy=None,
    params_schema=_INSTALL_PIP_AUDIT_SCHEMA,
    prepare=_install_pip_audit_prepare,
    execute=_install_pip_audit_execute,
)

SECURITY_DESCRIPTORS = (SECURITY_APPLY_FIX_DESCRIPTOR, SECURITY_INSTALL_PIP_AUDIT_DESCRIPTOR)
