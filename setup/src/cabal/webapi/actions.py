"""Action-safety protocol: descriptor registry, confirmation tickets, prepare/execute."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from cabal.redaction import redact_value
from cabal.webapi.audit import AuditRecorder
from cabal.webapi.envelope import ApiError, compute_precondition_digest
from cabal.webapi.jobs import JobConflict
from cabal.webapi.params_schema import validate_params
from cabal.webapi.storage import Storage

TICKET_TTL = timedelta(minutes=5)
_PREVIEW_LIST_FIELDS = ("commands", "files_changed", "scopes", "removals")


@dataclass
class ActionDescriptor:
    action_id: str
    module: str
    destructive: bool
    params_schema: dict
    prepare: Callable[[dict, Any], dict]
    execute: Callable[[dict, Any], "ActionOutcome"]
    compute_digest: Callable[[dict, Any], str | None] | None = None


@dataclass
class ActionOutcome:
    """Exactly one field populated: job_id => 202, data => 200."""

    job_id: str | None = None
    data: dict | None = None


class ActionRegistry:
    """The closed registry behind POST /api/actions/{id}/prepare|execute — the only write path."""

    def __init__(self, *, storage: Storage, audit: AuditRecorder) -> None:
        self._storage = storage
        self._audit = audit
        self._descriptors: dict[str, ActionDescriptor] = {}

    def register(self, descriptor: ActionDescriptor) -> None:
        self._descriptors[descriptor.action_id] = descriptor

    def get(self, action_id: str) -> ActionDescriptor | None:
        return self._descriptors.get(action_id)

    def ids(self) -> list[str]:
        return list(self._descriptors)

    def prepare(self, action_id: str, params: dict, state: Any) -> dict:
        """Validate params, build the redactable EffectPreview, store a single-use TTL ticket."""
        descriptor = self._require_descriptor(action_id)
        errors = validate_params(params, descriptor.params_schema)
        if errors:
            raise ApiError(422, "params_invalid", "; ".join(errors))
        preview = redact_value(descriptor.prepare(params, state))
        self._validate_preview(descriptor, preview)
        now = datetime.now(timezone.utc)
        ticket = {
            "ticket_id": str(uuid.uuid4()),
            "action_id": action_id,
            "params": params,
            "effect_preview": preview,
            "precondition_digest": self._digest(descriptor, params, state),
            "created_at": now.isoformat(),
            "expires_at": (now + TICKET_TTL).isoformat(),
            "state": "pending",
        }
        self._storage.save_ticket(ticket)
        return {key: ticket[key] for key in ("ticket_id", "action_id", "effect_preview", "precondition_digest", "created_at", "expires_at")}

    def execute(self, action_id: str, ticket_id: str, state: Any) -> tuple[int, dict]:
        """Recompute the digest, enforce single-use + TTL, run the descriptor, audit the outcome."""
        descriptor = self._require_descriptor(action_id)
        ticket = self._storage.load_ticket(ticket_id)
        if ticket is None or ticket["action_id"] != action_id:
            raise ApiError(404, "ticket_not_found", f"No pending ticket {ticket_id!r} for {action_id!r}")
        self._check_ticket_state(ticket)
        current_digest = self._digest(descriptor, ticket["params"], state)
        if current_digest != ticket["precondition_digest"]:
            self._storage.set_ticket_state(ticket_id, "invalidated")
            raise ApiError(
                409,
                "state_changed",
                "Source state changed since the preview was prepared; re-review and prepare again",
                extra={"precondition_digest": current_digest},
            )
        summary = str(ticket["effect_preview"].get("summary", ""))
        # Claim the ticket BEFORE running the descriptor: the atomic
        # pending->executed flip in storage is what makes tickets single-use
        # under concurrent execute requests (load-then-set would let both run).
        if not self._storage.consume_ticket(ticket_id):
            raise ApiError(409, "ticket_consumed", "Ticket already executed; tickets are single-use")
        try:
            outcome = descriptor.execute(ticket["params"], state)
        except JobConflict as exc:
            # No side effect happened; release the claim so the ticket can retry.
            self._storage.set_ticket_state(ticket_id, "pending")
            raise ApiError(
                409,
                "job_conflict",
                "Another job already holds this exclusive resource",
                extra={"blocking_job_id": exc.blocking_job_id},
            ) from exc
        except ApiError:
            # Descriptor-raised ApiErrors reported no side effect worth
            # consuming the ticket over; release the claim for a retry.
            self._storage.set_ticket_state(ticket_id, "pending")
            raise
        except Exception as exc:
            self._storage.clear_ticket_params(ticket_id)
            self._record_audit(action_id, ticket_id, None, summary, "failed")
            raise ApiError(500, "execution_failed", str(exc)) from exc
        self._storage.clear_ticket_params(ticket_id)
        if outcome.job_id is not None:
            state.jobs.attach_ticket(outcome.job_id, ticket_id)
            self._audit_on_terminal(action_id, ticket_id, outcome.job_id, summary, state)
            return 202, {"job_id": outcome.job_id}
        self._record_audit(action_id, ticket_id, None, summary, "succeeded")
        return 200, outcome.data or {}

    def force_expire_ticket_for_test(self, ticket_id: str) -> None:
        """Test-only hook: flip a pending ticket straight to expired so 410 is reachable."""
        self._storage.set_ticket_state(ticket_id, "expired")

    def _require_descriptor(self, action_id: str) -> ActionDescriptor:
        descriptor = self.get(action_id)
        if descriptor is None:
            raise ApiError(404, "action_not_found", f"Unknown action {action_id!r}")
        return descriptor

    @staticmethod
    def _validate_preview(descriptor: ActionDescriptor, preview: Any) -> None:
        """Fail closed when an action cannot produce the confirmation contract."""
        if not isinstance(preview, dict):
            raise ApiError(500, "invalid_action_preview", "Action preview must be an object")
        summary = preview.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ApiError(500, "invalid_action_preview", "Action preview summary must be non-empty")
        for field in _PREVIEW_LIST_FIELDS:
            value = preview.get(field)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ApiError(500, "invalid_action_preview", f"Action preview {field} must be a string list")
        backup = preview.get("backup")
        if backup is not None and not isinstance(backup, str):
            raise ApiError(500, "invalid_action_preview", "Action preview backup must be a string or null")
        if descriptor.destructive and (not preview["removals"] or not backup):
            raise ApiError(
                500,
                "invalid_action_preview",
                "Destructive action previews must name removals and backup or recovery behavior",
            )

    def _check_ticket_state(self, ticket: dict) -> None:
        ticket_state = ticket["state"]
        if ticket_state == "executed":
            raise ApiError(409, "ticket_consumed", "Ticket already executed; tickets are single-use")
        if ticket_state == "invalidated":
            raise ApiError(409, "state_changed", "Ticket was invalidated by precondition drift")
        expired = ticket_state == "expired" or datetime.now(timezone.utc) > datetime.fromisoformat(
            ticket["expires_at"]
        )
        if expired:
            if ticket_state != "expired":
                self._storage.set_ticket_state(ticket["ticket_id"], "expired")
            raise ApiError(410, "ticket_expired", "Ticket TTL elapsed; prepare the action again")

    def _digest(self, descriptor: ActionDescriptor, params: dict, state: Any) -> str:
        if descriptor.compute_digest is not None:
            digest = descriptor.compute_digest(params, state)
            if digest is not None:
                return digest
        return compute_precondition_digest({"action_id": descriptor.action_id, "params": params})

    def _record_audit(
        self,
        action_id: str,
        ticket_id: str,
        job_id: str | None,
        summary: str,
        outcome: str,
    ) -> None:
        self._audit.record(
            action_id=action_id,
            ticket_id=ticket_id,
            job_id=job_id,
            effect_summary=summary,
            outcome=outcome,  # type: ignore[arg-type]
        )

    def _audit_on_terminal(
        self,
        action_id: str,
        ticket_id: str,
        job_id: str,
        summary: str,
        state: Any,
    ) -> None:
        """Job-backed outcomes audit once, at terminal, with the job's real outcome."""

        def _on_terminal(record: dict) -> None:
            outcome = record["state"] if record["state"] in {"succeeded", "failed", "cancelled"} else "failed"
            self._record_audit(action_id, ticket_id, job_id, summary, outcome)

        state.jobs.add_terminal_callback(job_id, _on_terminal)
