# -*- coding: utf-8 -*-
"""Package Security Check orchestration — ecosystem detection, scan dispatch, fix execution.

Detects which ecosystems are present in a project from marker files, dispatches to
the matching scanner module, and caches results per project path via `widget_cache`
(stale-while-revalidate, same as UpdatePanel/EnvPanel). `apply_fix` is the single
place that mutates installed dependencies — always called after the caller has
gotten explicit per-finding user confirmation.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cabal import widget_cache
from cabal.package_security.dotnet_scanner import _find_dotnet_targets, scan_dotnet
from cabal.package_security.models import Ecosystem, Finding, ScanOutcome
from cabal.package_security.npm_scanner import scan_npm
from cabal.package_security.python_scanner import scan_python

_CACHE_KEY_PREFIX = "pkgsec:"
_FIX_TIMEOUT_SECONDS = 120

_SCANNERS = {
    "dotnet": scan_dotnet,
    "npm": scan_npm,
    "python": scan_python,
}


def _cache_key(project: Path) -> str:
    return f"{_CACHE_KEY_PREFIX}{project}"


def detect_ecosystems(project: Path) -> list[Ecosystem]:
    """Ecosystems present in `project`, based on marker files (root-level for npm/python;
    .NET reuses the scanner's own recursive project/solution search, so detection and
    scanning can never disagree about which projects exist)."""
    ecosystems: list[Ecosystem] = []
    if _find_dotnet_targets(project):
        ecosystems.append("dotnet")
    if (project / "package.json").exists():
        ecosystems.append("npm")
    if (project / "requirements.txt").exists() or (project / "pyproject.toml").exists():
        ecosystems.append("python")
    return ecosystems


def scan_project(project: Path) -> list[ScanOutcome]:
    """Run every scanner whose ecosystem is detected in `project`."""
    return [_SCANNERS[eco](project) for eco in detect_ecosystems(project)]


def load_cached(project: Path) -> list[ScanOutcome] | None:
    payload = widget_cache.load_entry(_cache_key(project))
    if not isinstance(payload, list):
        return None
    try:
        return [_outcome_from_payload(entry) for entry in payload]
    except (KeyError, TypeError, ValueError):
        return None


def save_cache(project: Path, outcomes: list[ScanOutcome]) -> None:
    widget_cache.save_entry(_cache_key(project), [asdict(outcome) for outcome in outcomes])


def clear_cache(project: Path) -> None:
    save_cache(project, [])


def _outcome_from_payload(entry: dict[str, Any]) -> ScanOutcome:
    findings = tuple(Finding(**f) for f in entry["findings"])
    return ScanOutcome(
        ecosystem=entry["ecosystem"],
        findings=findings,
        notices=tuple(entry.get("notices", ())),
    )


def apply_fix(finding: Finding, project: Path) -> tuple[bool, str]:
    """Run `finding.fix_command` after the caller has obtained user confirmation."""
    if not finding.fix_command:
        return False, "No automated fix available for this finding."
    try:
        args = shlex.split(finding.fix_command)
        result = subprocess.run(
            args,
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=_FIX_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "command failed").strip()[:400]
    return True, f"Applied: {finding.fix_command}"
