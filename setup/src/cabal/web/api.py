"""Read-only API surface for the Cabal web UI."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from cabal.web import SCHEMA_VERSION
from cabal.web.redaction import redact_value
from cabal.web.serializers import (
    diagnostic_event,
    diagnostics_counts,
    serialize_backend_health,
    serialize_knowledge_graph,
    serialize_overview,
    serialize_project_health,
    serialize_tool_catalog,
    utc_now,
)

READ_METHODS = {"GET", "HEAD", "OPTIONS"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class WebApi:
    """Small localhost API facade over existing Cabal data sources."""

    def __init__(self, project_root: Path, *, host: str = "127.0.0.1") -> None:
        self.project_root = Path(project_root).resolve()
        self.host = host
        self._diagnostics: deque[dict[str, Any]] = deque(maxlen=100)

    def handle(self, path: str, method: str = "GET") -> tuple[int, dict[str, Any]]:
        method = method.upper()
        if method in MUTATING_METHODS:
            event = diagnostic_event(
                "api",
                f"Method {method} is not allowed on the read-only web API.",
                severity="warning",
                retryable=False,
            )
            return 405, self.envelope("api", None, status="error", error=event)
        if method not in READ_METHODS:
            event = diagnostic_event("api", f"Method {method} is not supported.", retryable=False)
            return 405, self.envelope("api", None, status="error", error=event)
        route = path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if route == "/api/health":
                return 200, self.envelope("health", serialize_backend_health(host=self.host, diagnostics=self.diagnostics()))
            if route == "/api/diagnostics":
                events = self.diagnostics()
                return 200, self.envelope("diagnostics", {"events": events, "counts": diagnostics_counts(events)})
            if route == "/api/tools":
                return 200, self.envelope("tools", serialize_tool_catalog(include_status=False))
            if route == "/api/knowledge":
                return 200, self.envelope("knowledge", serialize_knowledge_graph(self.project_root))
            if route == "/api/project-health":
                return 200, self.envelope("project_health", serialize_project_health(self.project_root))
            if route == "/api/overview":
                overview = serialize_overview(self.project_root, self.diagnostics())
                overview_status = (
                    "partial"
                    if any(section.get("state") == "error" for section in overview.get("sections", []))
                    else "ok"
                )
                return 200, self.envelope("overview", overview, status=overview_status)
        except Exception as exc:  # pragma: no cover - defensive around host integrations
            event = diagnostic_event(route.lstrip("/") or "api", "Endpoint failed.", details=str(exc))
            self._diagnostics.append(event)
            return 500, self.envelope(route.lstrip("/") or "api", None, status="error", error=event)
        event = diagnostic_event("api", f"Unknown route: {route}", retryable=False)
        return 404, self.envelope("api", None, status="error", error=event)

    def diagnostics(self) -> list[dict[str, Any]]:
        return list(self._diagnostics)

    def envelope(
        self,
        source: str,
        data: object,
        *,
        status: str = "ok",
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = {
            "schema_version": SCHEMA_VERSION,
            "captured_at": utc_now(),
            "status": status,
            "source": source,
            "data": data if status != "error" else None,
            "error": error,
        }
        return redact_value(body)
