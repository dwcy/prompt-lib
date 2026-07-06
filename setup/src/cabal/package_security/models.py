# -*- coding: utf-8 -*-
"""Shared data model for Package Security Check findings across ecosystems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Ecosystem = Literal["dotnet", "npm", "python"]
FindingKind = Literal["vulnerable", "outdated", "deprecated"]

SEVERITY_INFO = "info"


@dataclass(frozen=True)
class Finding:
    """One actionable package issue surfaced by a Package Security Check scan.

    `target_version` and `fix_command` are None when no safe, automatable fix
    could be determined (e.g. a deprecated package with no drop-in replacement) —
    the view must not offer a Fix action in that case.
    """

    ecosystem: Ecosystem
    package: str
    kind: FindingKind
    severity: str
    current_version: str
    target_version: str | None
    fix_command: str | None
    detail: str = ""

    @property
    def key(self) -> str:
        """Stable identity for DataTable row keys and per-finding lookups."""
        return f"{self.ecosystem}::{self.package}::{self.kind}"


@dataclass(frozen=True)
class ScanOutcome:
    """Result of scanning one ecosystem: findings plus actionable notices.

    `notices` carries human-readable, actionable messages for conditions that
    stop a scan short of producing findings (e.g. a missing prerequisite CLI) —
    surfaced in the UI instead of raising.
    """

    ecosystem: Ecosystem
    findings: tuple[Finding, ...]
    notices: tuple[str, ...] = ()
