# -*- coding: utf-8 -*-
"""Pending intents and the approval token that binds one to the solution it was proposed against.

The gate is only real if approval cannot be replayed. An `intent_token` is derived from *both*
the intent's content and a fingerprint of the solution as it stood when the intent was proposed,
so an approval stops being valid the moment either changes. Two failure modes this closes:

* **replay** - re-submitting yesterday's token to authorise today's different change
* **drift** - approving a plan, editing the solution by hand, then applying the stale plan on top

Both would let code be written that no developer approved in its actual context, which is the one
thing SC-011 forbids. A refused token is an error, never a prompt to re-approve automatically.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cabal.dotnetgen import state
from cabal.dotnetgen.pipeline import ChangeIntent

PENDING_RELPATH: Final[str] = ".dotnetgen/pending-intent.json"
SOURCE_SUFFIXES: Final[tuple[str, ...]] = (".cs", ".csproj", ".sln", ".json")
IGNORED_DIRS: Final[frozenset[str]] = frozenset({"obj", "bin", "node_modules", "venv", "packages"})
"""Excluded from the fingerprint, alongside every dot-directory.

Build output, vendored trees, and tooling state. Fingerprinting them would make the token depend
on a restore or a package install, so an approval would go stale for reasons that have nothing to
do with the code the developer approved. .NET sources never live in a dot-directory, so those are
skipped wholesale rather than enumerated.
"""


def _is_ignored(relative: Path) -> bool:
    return any(part in IGNORED_DIRS or part.startswith(".") for part in relative.parts[:-1])


class IntentError(RuntimeError):
    """Base for pending-intent failures."""


class NoPendingIntentError(IntentError):
    """Raised when `apply` is given a token but nothing was ever proposed."""


class StaleIntentError(IntentError):
    """Raised when a token does not match the pending intent or the solution has moved on."""


@dataclass(frozen=True)
class PendingIntent:
    """One proposed change awaiting approval, and what it was proposed against."""

    token: str
    fingerprint: str
    request: str
    intent: ChangeIntent
    created_at: str

    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "fingerprint": self.fingerprint,
            "request": self.request,
            "created_at": self.created_at,
            "intent": {
                "summary": self.intent.summary,
                "target_files": list(self.intent.target_files),
                "target_symbols": list(self.intent.target_symbols),
                "rationale": self.intent.rationale,
            },
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "PendingIntent":
        missing = [k for k in ("token", "fingerprint", "intent") if k not in payload]
        if missing:
            raise IntentError(f"pending intent is missing {', '.join(missing)}")
        body = payload["intent"]
        return cls(
            token=payload["token"],
            fingerprint=payload["fingerprint"],
            request=payload.get("request", ""),
            created_at=payload.get("created_at", ""),
            intent=ChangeIntent(
                summary=body["summary"],
                target_files=tuple(body.get("target_files", ())),
                target_symbols=tuple(body.get("target_symbols", ())),
                rationale=body.get("rationale", ""),
            ),
        )


def solution_fingerprint(project: Path) -> str:
    """Fingerprint the solution's current shape - the context an approval is bound to."""
    sizes: dict[str, int] = {}
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(project)
        if _is_ignored(relative):
            continue
        sizes[relative.as_posix()] = path.stat().st_size
    return state.structural_fingerprint(sizes)


def derive_token(fingerprint: str, intent: ChangeIntent) -> str:
    """Bind intent content to solution state. Either changing produces a different token."""
    digest = hashlib.sha256()
    digest.update(fingerprint.encode("utf-8"))
    digest.update(b"\0")
    digest.update(
        json.dumps(
            {
                "summary": intent.summary,
                "target_files": list(intent.target_files),
                "target_symbols": list(intent.target_symbols),
                "rationale": intent.rationale,
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    return f"sha256:{digest.hexdigest()}"


def pending_path(project: Path) -> Path:
    return project / PENDING_RELPATH


def propose(project: Path, request: str, intent: ChangeIntent) -> PendingIntent:
    """Record an intent awaiting approval, returning the token that authorises it."""
    fingerprint = solution_fingerprint(project)
    pending = PendingIntent(
        token=derive_token(fingerprint, intent),
        fingerprint=fingerprint,
        request=request,
        intent=intent,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    path = pending_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending.to_dict(), indent=2) + "\n", encoding="utf-8")
    return pending


def load_pending(project: Path) -> PendingIntent:
    path = pending_path(project)
    if not path.is_file():
        raise NoPendingIntentError(
            f"no pending intent in {project}; run `plan` and approve it before `apply`"
        )
    return PendingIntent.from_dict(json.loads(path.read_text(encoding="utf-8")))


def redeem(project: Path, token: str) -> PendingIntent:
    """Validate a token against the pending intent and the solution's current state.

    Refuses on mismatch and on drift. The pending file is deliberately **not** cleared here -
    clearing belongs to a successful apply, so a failed write leaves the approval intact rather
    than forcing the developer through the gate again for a change they already approved.
    """
    pending = load_pending(project)
    if token != pending.token:
        raise StaleIntentError(
            "intent token does not match the pending intent; an approval authorises one specific "
            "change and cannot be replayed against another"
        )
    current = solution_fingerprint(project)
    if current != pending.fingerprint:
        raise StaleIntentError(
            "the solution changed after this intent was approved; re-run `plan` so the developer "
            "approves the change against the code it will actually be applied to"
        )
    return pending


def clear(project: Path) -> None:
    """Discard the pending intent after it has been successfully applied."""
    pending_path(project).unlink(missing_ok=True)
