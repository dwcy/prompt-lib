# -*- coding: utf-8 -*-
"""`.NET` scanner — `dotnet list package` (vulnerable / outdated / deprecated) per project."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from cabal.package_security.models import Finding, ScanOutcome, SEVERITY_INFO

_SKIP_DIRS = {"bin", "obj", "node_modules", ".git", ".venv", "venv", "__pycache__"}
_DOTNET_TIMEOUT_SECONDS = 60
_VULNERABLE_FLAGS = ("--vulnerable", "--include-transitive")
_OUTDATED_FLAGS = ("--outdated",)
_DEPRECATED_FLAGS = ("--deprecated",)
_MISSING_DOTNET_NOTICE = (
    "dotnet CLI not found on PATH — install the .NET SDK to run .NET package "
    "security checks (see the Tools screen)."
)


def _find_dotnet_targets(project: Path) -> list[Path]:
    """Solutions take priority (they cover every referenced project); else every .csproj."""
    solutions = _walk_for_suffix(project, ".sln")
    if solutions:
        return solutions
    return _walk_for_suffix(project, ".csproj")


def _walk_for_suffix(project: Path, suffix: str) -> list[Path]:
    found: list[Path] = []
    stack = [project]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name not in _SKIP_DIRS:
                    stack.append(entry)
            elif entry.suffix == suffix:
                found.append(entry)
    return sorted(found)


def _run_dotnet_list(dotnet: str, target: Path, *flags: str) -> dict[str, Any] | None:
    try:
        result = subprocess.run(
            [dotnet, "list", str(target), "package", *flags, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=_DOTNET_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _iter_package_entries(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Yield (project_path, package_dict) for every top-level + transitive package."""
    entries: list[tuple[str, dict[str, Any]]] = []
    for proj in data.get("projects", []):
        proj_path = proj.get("path", "")
        for framework in proj.get("frameworks", []):
            for pkg in framework.get("topLevelPackages", []):
                entries.append((proj_path, pkg))
            for pkg in framework.get("transitivePackages", []):
                entries.append((proj_path, pkg))
    return entries


def _parse_vulnerable(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for proj_path, pkg in _iter_package_entries(data):
        vulns = pkg.get("vulnerabilities") or []
        if not vulns:
            continue
        worst = max(vulns, key=lambda v: v.get("severity", ""))
        current = pkg.get("resolvedVersion") or pkg.get("requestedVersion") or "?"
        findings.append(
            Finding(
                ecosystem="dotnet",
                package=pkg.get("id", "?"),
                kind="vulnerable",
                severity=str(worst.get("severity", SEVERITY_INFO)),
                current_version=current,
                target_version=None,
                fix_command=None,
                detail=(
                    f"{len(vulns)} advisory(ies), e.g. {worst.get('advisoryurl', '')}; "
                    f"project: {proj_path}"
                ),
            )
        )
    return findings


def _parse_outdated(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for proj_path, pkg in _iter_package_entries(data):
        latest = pkg.get("latestVersion")
        if not latest:
            continue
        current = pkg.get("resolvedVersion") or pkg.get("requestedVersion") or "?"
        pkg_id = pkg.get("id", "?")
        findings.append(
            Finding(
                ecosystem="dotnet",
                package=pkg_id,
                kind="outdated",
                severity=SEVERITY_INFO,
                current_version=current,
                target_version=latest,
                fix_command=f'dotnet add "{proj_path}" package {pkg_id} --version {latest}',
                detail=f"project: {proj_path}",
            )
        )
    return findings


def _parse_deprecated(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for proj_path, pkg in _iter_package_entries(data):
        reasons = pkg.get("deprecationReasons") or []
        if not reasons:
            continue
        current = pkg.get("resolvedVersion") or pkg.get("requestedVersion") or "?"
        alt = pkg.get("alternativePackage") or {}
        alt_id = alt.get("id", "")
        detail = f"reasons: {', '.join(reasons)}; project: {proj_path}"
        if alt_id:
            detail += f"; suggested replacement: {alt_id} {alt.get('versionRange', '')}"
        findings.append(
            Finding(
                ecosystem="dotnet",
                package=pkg.get("id", "?"),
                kind="deprecated",
                severity=SEVERITY_INFO,
                current_version=current,
                # Replacing a deprecated package means removing one dependency and
                # adding a different one — not a version bump — so no automated
                # fix_command is offered; the finding is informational only.
                target_version=alt_id or None,
                fix_command=None,
                detail=detail,
            )
        )
    return findings


def scan_dotnet(project: Path) -> ScanOutcome:
    """Scan every .NET project/solution under `project` for vulnerable/outdated/deprecated packages."""
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return ScanOutcome(ecosystem="dotnet", findings=(), notices=(_MISSING_DOTNET_NOTICE,))

    targets = _find_dotnet_targets(project)
    if not targets:
        return ScanOutcome(ecosystem="dotnet", findings=())

    by_key: dict[str, Finding] = {}
    notices: list[str] = []
    for target in targets:
        vuln_data = _run_dotnet_list(dotnet, target, *_VULNERABLE_FLAGS)
        if vuln_data is None:
            notices.append(f"Could not read vulnerable packages for {target.name}.")
        else:
            for f in _parse_vulnerable(vuln_data):
                by_key.setdefault(f.key, f)

        outdated_data = _run_dotnet_list(dotnet, target, *_OUTDATED_FLAGS)
        if outdated_data is None:
            notices.append(f"Could not read outdated packages for {target.name}.")
        else:
            for f in _parse_outdated(outdated_data):
                by_key.setdefault(f.key, f)

        deprecated_data = _run_dotnet_list(dotnet, target, *_DEPRECATED_FLAGS)
        if deprecated_data is None:
            notices.append(f"Could not read deprecated packages for {target.name}.")
        else:
            for f in _parse_deprecated(deprecated_data):
                by_key.setdefault(f.key, f)

    return ScanOutcome(ecosystem="dotnet", findings=tuple(by_key.values()), notices=tuple(notices))
