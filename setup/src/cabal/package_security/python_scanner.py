# -*- coding: utf-8 -*-
"""Python scanner — `pip-audit` (vulnerable) + `pip list --outdated` (outdated)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from cabal.package_security.models import Finding, ScanOutcome, SEVERITY_INFO

_PIP_TIMEOUT_SECONDS = 60
_MISSING_PIP_AUDIT_NOTICE = (
    "pip-audit not installed — install it with `pip install pip-audit` to scan "
    "Python dependencies for known vulnerabilities."
)


def _run_json(cmd: list[str]) -> Any | None:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_PIP_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _scan_vulnerable() -> tuple[list[Finding], list[str]]:
    if not shutil.which("pip-audit"):
        return [], [_MISSING_PIP_AUDIT_NOTICE]

    data = _run_json(["pip-audit", "-f", "json"])
    if not isinstance(data, dict):
        return [], ["Could not parse `pip-audit -f json` output."]

    findings: list[Finding] = []
    for dep in data.get("dependencies", []):
        vulns = dep.get("vulns") or []
        if not vulns:
            continue
        name = dep.get("name", "?")
        current = dep.get("version", "?")
        fix_versions = vulns[0].get("fix_versions") or []
        target = fix_versions[0] if fix_versions else None
        ids = ", ".join(v.get("id", "") for v in vulns if v.get("id"))
        findings.append(
            Finding(
                ecosystem="python",
                package=name,
                kind="vulnerable",
                severity=SEVERITY_INFO,
                current_version=current,
                target_version=target,
                fix_command=f'pip install "{name}=={target}"' if target else None,
                detail=f"{len(vulns)} advisory(ies): {ids}",
            )
        )
    return findings, []


def _scan_outdated() -> tuple[list[Finding], list[str]]:
    data = _run_json([sys.executable, "-m", "pip", "list", "--outdated", "--format=json"])
    if not isinstance(data, list):
        return [], ["Could not parse `pip list --outdated --format=json` output."]

    findings: list[Finding] = []
    for pkg in data:
        if not isinstance(pkg, dict):
            continue
        name = pkg.get("name", "?")
        latest = pkg.get("latest_version")
        current = pkg.get("version", "?")
        if not latest:
            continue
        findings.append(
            Finding(
                ecosystem="python",
                package=name,
                kind="outdated",
                severity=SEVERITY_INFO,
                current_version=current,
                target_version=latest,
                fix_command=f'pip install "{name}=={latest}"',
            )
        )
    return findings, []


def scan_python(project: Path) -> ScanOutcome:
    """Scan the Python project rooted at `project` for vulnerable + outdated packages."""
    vulnerable, vuln_notices = _scan_vulnerable()
    outdated, outdated_notices = _scan_outdated()
    return ScanOutcome(
        ecosystem="python",
        findings=tuple(vulnerable + outdated),
        notices=tuple(vuln_notices + outdated_notices),
    )
