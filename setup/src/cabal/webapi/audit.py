"""Mutation audit trail and diagnostics recording: SQLite persistence + in-memory SSE feed."""

from __future__ import annotations

import threading
from typing import Literal

from cabal.redaction import redact_text
from cabal.webapi.envelope import utc_now_iso
from cabal.webapi.storage import Storage

Severity = Literal["info", "warning", "error"]
DiagnosticKind = Literal["data_source", "mutation", "backend"]
AuditOutcome = Literal["succeeded", "failed", "cancelled"]


class DiagnosticsRecorder:
    """Redact-on-write diagnostic events: persisted history plus an in-memory live feed."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._lock = threading.Lock()
        self._feed: list[dict] = []

    def record(
        self,
        *,
        severity: Severity,
        module: str,
        message: str,
        kind: DiagnosticKind = "data_source",
    ) -> dict:
        event = {
            "severity": severity,
            "module": module,
            "message": redact_text(message),
            "kind": kind,
            "occurred_at": utc_now_iso(),
        }
        event["id"] = self._storage.add_diagnostic(event)
        with self._lock:
            self._feed.append(event)
        return event

    def list(self, limit: int | None = None, severity: str | None = None) -> list[dict]:
        return self._storage.list_diagnostics(limit=limit, severity=severity)

    def feed_after(self, last_id: int) -> list[dict]:
        with self._lock:
            return [event for event in self._feed if event["id"] > last_id]


class AuditRecorder:
    """Writes one AuditEntry per executed mutation and mirrors it into diagnostics."""

    def __init__(self, storage: Storage, diagnostics: DiagnosticsRecorder) -> None:
        self._storage = storage
        self._diagnostics = diagnostics

    def record(
        self,
        *,
        action_id: str,
        ticket_id: str | None,
        job_id: str | None,
        effect_summary: str,
        outcome: AuditOutcome,
    ) -> dict:
        entry = {
            "action_id": action_id,
            "ticket_id": ticket_id,
            "job_id": job_id,
            "effect_summary": redact_text(effect_summary),
            "outcome": outcome,
            "performed_at": utc_now_iso(),
        }
        entry["id"] = self._storage.add_audit(entry)
        self._diagnostics.record(
            severity="info" if outcome == "succeeded" else "warning",
            module=action_id.split(".", 1)[0],
            message=f"action {action_id} {outcome}",
            kind="mutation",
        )
        return entry

    def list(self) -> list[dict]:
        return self._storage.list_audit()
