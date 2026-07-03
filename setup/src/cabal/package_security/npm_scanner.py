# -*- coding: utf-8 -*-
"""npm/pnpm/bun scanner — audit (vulnerable) + outdated, matching the detected lockfile.

Only reads status (`audit`, `outdated`) — never installs. Per-project-manager output
shapes differ (npm's `vulnerabilities` map, pnpm's legacy `advisories` map, bun's
package-keyed array, and bun's `outdated` having no JSON mode at all), so each shape
gets its own small parser instead of one lookalike-but-lying dict traversal.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from cabal.package_security.models import Finding, ScanOutcome, SEVERITY_INFO

_NPM_TIMEOUT_SECONDS = 60
_LOCKFILE_TO_PM = {
    "pnpm-lock.yaml": "pnpm",
    "bun.lock": "bun",
    "bun.lockb": "bun",
}


def _detect_package_manager(project: Path) -> str:
    for lockfile, pm in _LOCKFILE_TO_PM.items():
        if (project / lockfile).exists():
            return pm
    return "npm"


def _run(cmd: list[str], project: Path) -> tuple[str | None, bool]:
    """Run `cmd` in `project`; return (stdout, tool_was_found)."""
    resolved = shutil.which(cmd[0])
    if not resolved:
        return None, False
    try:
        result = subprocess.run(
            [resolved, *cmd[1:]],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=_NPM_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, True
    # audit/outdated commands intentionally exit non-zero when findings exist.
    return result.stdout, True


def _run_json(cmd: list[str], project: Path) -> tuple[Any | None, bool]:
    stdout, found = _run(cmd, project)
    if stdout is None:
        return None, found
    try:
        return json.loads(stdout), found
    except json.JSONDecodeError:
        return None, found


def _install_command(pm: str, package: str, version: str) -> str:
    if pm == "npm":
        return f"npm install {package}@{version}"
    return f"{pm} add {package}@{version}"


def _lockfile_installed_version(project: Path, package: str) -> str | None:
    """Best-effort exact installed version from package-lock.json (npm only)."""
    lock_path = project / "package-lock.json"
    if not lock_path.exists():
        return None
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    packages = data.get("packages")
    if isinstance(packages, dict):
        entry = packages.get(f"node_modules/{package}")
        if isinstance(entry, dict) and entry.get("version"):
            return str(entry["version"])
    dependencies = data.get("dependencies")
    if isinstance(dependencies, dict):
        entry = dependencies.get(package)
        if isinstance(entry, dict) and entry.get("version"):
            return str(entry["version"])
    return None


def _parse_npm_vulnerabilities(data: dict[str, Any], project: Path, pm: str) -> list[Finding]:
    findings: list[Finding] = []
    for name, entry in (data.get("vulnerabilities") or {}).items():
        fix = entry.get("fixAvailable")
        target = fix.get("version") if isinstance(fix, dict) else None
        current = _lockfile_installed_version(project, name) or f"range {entry.get('range', '?')}"
        via = entry.get("via") or []
        titles = [v.get("title") for v in via if isinstance(v, dict) and v.get("title")]
        findings.append(
            Finding(
                ecosystem="npm",
                package=name,
                kind="vulnerable",
                severity=str(entry.get("severity", SEVERITY_INFO)),
                current_version=current,
                target_version=target,
                fix_command=_install_command(pm, name, target) if target else None,
                detail="; ".join(titles) or "vulnerable range: " + str(entry.get("range", "")),
            )
        )
    return findings


def _parse_legacy_advisories(data: dict[str, Any], pm: str) -> list[Finding]:
    """pnpm's `audit --json` still ships npm's legacy v1 shape: `advisories` keyed by id."""
    by_package: dict[str, list[dict[str, Any]]] = {}
    for advisory in (data.get("advisories") or {}).values():
        by_package.setdefault(advisory.get("module_name", "?"), []).append(advisory)

    findings: list[Finding] = []
    for name, advisories in by_package.items():
        worst = max(advisories, key=lambda a: a.get("severity", ""))
        current = "?"
        for finding_entry in worst.get("findings", []):
            if finding_entry.get("version"):
                current = finding_entry["version"]
                break
        target = _first_version_in_range(worst.get("patched_versions", ""))
        findings.append(
            Finding(
                ecosystem="npm",
                package=name,
                kind="vulnerable",
                severity=str(worst.get("severity", SEVERITY_INFO)),
                current_version=current,
                target_version=target,
                fix_command=_install_command(pm, name, target) if target else None,
                detail=f"{len(advisories)} advisory(ies), e.g. {worst.get('title', '')}",
            )
        )
    return findings


def _parse_bun_audit(data: dict[str, Any], pm: str) -> list[Finding]:
    """bun's `audit --json` is package-name-keyed directly to a list of advisories."""
    findings: list[Finding] = []
    for name, advisories in data.items():
        if not isinstance(advisories, list) or not advisories:
            continue
        worst = max(advisories, key=lambda a: a.get("severity", ""))
        target = None  # bun does not report a patched version, only the vulnerable range.
        findings.append(
            Finding(
                ecosystem="npm",
                package=name,
                kind="vulnerable",
                severity=str(worst.get("severity", SEVERITY_INFO)),
                current_version=f"range {worst.get('vulnerable_versions', '?')}",
                target_version=target,
                fix_command=None,
                detail=f"{len(advisories)} advisory(ies), e.g. {worst.get('title', '')}",
            )
        )
    return findings


def _first_version_in_range(range_text: str) -> str | None:
    match = re.search(r"\d+\.\d+\.\d+", range_text or "")
    return match.group(0) if match else None


def _parse_vulnerable_payload(data: Any, project: Path, pm: str) -> list[Finding]:
    if not isinstance(data, dict):
        return []
    if "vulnerabilities" in data:
        return _parse_npm_vulnerabilities(data, project, pm)
    if "advisories" in data:
        return _parse_legacy_advisories(data, pm)
    return _parse_bun_audit(data, pm)


def _parse_outdated_json(data: dict[str, Any], pm: str) -> list[Finding]:
    findings: list[Finding] = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        latest = entry.get("latest")
        current = entry.get("current")
        if not latest or not current or latest == current:
            continue
        findings.append(
            Finding(
                ecosystem="npm",
                package=name,
                kind="outdated",
                severity=SEVERITY_INFO,
                current_version=str(current),
                target_version=str(latest),
                fix_command=_install_command(pm, name, latest),
            )
        )
    return findings


_BUN_TABLE_ROW = re.compile(
    r"^\|\s*(?P<name>\S+)\s*\|\s*(?P<current>\S+)\s*\|\s*(?P<update>\S+)\s*\|\s*(?P<latest>\S+)\s*\|$"
)


def _is_separator_row(text: str) -> bool:
    return set(text) <= {"-"}


def _parse_bun_outdated_table(text: str, pm: str) -> list[Finding]:
    """`bun outdated` has no JSON mode — parse its fixed-width pipe table instead."""
    findings: list[Finding] = []
    for line in text.splitlines():
        match = _BUN_TABLE_ROW.match(line.strip())
        if not match:
            continue
        name, current, latest = match["name"], match["current"], match["latest"]
        if name == "Package" or _is_separator_row(name) or current == latest:
            continue
        findings.append(
            Finding(
                ecosystem="npm",
                package=name,
                kind="outdated",
                severity=SEVERITY_INFO,
                current_version=current,
                target_version=latest,
                fix_command=_install_command(pm, name, latest),
            )
        )
    return findings


def scan_npm(project: Path) -> ScanOutcome:
    """Scan the frontend project rooted at `project` for vulnerable + outdated packages."""
    pm = _detect_package_manager(project)
    notices: list[str] = []

    audit_cmd = [pm, "audit", "--json"]
    audit_data, found = _run_json(audit_cmd, project)
    if not found:
        notices.append(f"{pm} not found on PATH — cannot run `{' '.join(audit_cmd)}`.")
        vulnerable: list[Finding] = []
    elif audit_data is None:
        notices.append(f"Could not parse `{' '.join(audit_cmd)}` output.")
        vulnerable = []
    else:
        vulnerable = _parse_vulnerable_payload(audit_data, project, pm)

    if pm == "bun":
        outdated_cmd = ["bun", "outdated"]
        stdout, found = _run(outdated_cmd, project)
        if not found:
            notices.append(f"{pm} not found on PATH — cannot run `{' '.join(outdated_cmd)}`.")
            outdated: list[Finding] = []
        else:
            outdated = _parse_bun_outdated_table(stdout or "", pm)
    else:
        outdated_cmd = [pm, "outdated", "--format", "json"] if pm == "pnpm" else [pm, "outdated", "--json"]
        outdated_data, found = _run_json(outdated_cmd, project)
        if not found:
            notices.append(f"{pm} not found on PATH — cannot run `{' '.join(outdated_cmd)}`.")
            outdated = []
        elif not isinstance(outdated_data, dict):
            notices.append(f"Could not parse `{' '.join(outdated_cmd)}` output.")
            outdated = []
        else:
            outdated = _parse_outdated_json(outdated_data, pm)

    return ScanOutcome(ecosystem="npm", findings=tuple(vulnerable + outdated), notices=tuple(notices))
