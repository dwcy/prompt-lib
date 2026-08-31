# -*- coding: utf-8 -*-
"""Fan-out, assembly, and reveal dispatch for the environment-variable source browser.

Local sources (repo files, .NET layers, the developer secret store) are file reads and
resolve inline. The three provider collectors are subprocess/socket-bound, so they run on
bounded daemon threads behind a shared deadline: a collector that hangs or raises becomes a
`degraded` source with a stated hint and never delays the response past the cap (research R5,
FR-039). Daemon threads specifically -- a hung collector must not keep the interpreter alive.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from cabal.models.envsources import (
    AvailabilityState,
    RevealResult,
    SourceKind,
    VariableSource,
    source_payload,
)
from cabal.webapi.envelope import ApiError, utc_now_iso

# One collector's own budget, and the ceiling the route answers within regardless of how
# many collectors are detected. SC-010 allows 3s to first usable content end to end.
COLLECTOR_TIMEOUT_S = 2.0
TOTAL_TIMEOUT_S = 2.5
MAX_CONCURRENT_COLLECTORS = 4

# One source refreshed on its own gets a far larger budget than the first paint allows.
# `az keyvault list` plus a `secret list` per vault runs to tens of seconds on a real
# subscription, so the only way to honour both SC-010 and FR-038 is to make the wait
# opt-in: the listing degrades fast, and the tab's refresh control waits properly.
REFRESH_TIMEOUT_S = 45.0

# Distinguishes "the listing has no such entry" from an entry whose type is legitimately None.
_MISSING = object()

_HINT_TIMEOUT = "{label} did not respond within {timeout:g}s — refresh this tab to wait longer"
_HINT_FAILED = "{label} could not be read: {detail}"


@dataclass(frozen=True)
class CollectorSpec:
    """A provider collector plus the identity its degraded stand-in needs when it fails."""

    id: str
    kind: SourceKind
    label: str
    collect: Callable[[Path], list[VariableSource]]
    outside_repository: bool = True
    # Source ids this collector can emit — one collector may produce several tabs, and the
    # per-source refresh has to map any of them back to the collector that owns it.
    produces: tuple[str, ...] = ()

    def emits(self, source_id: str) -> bool:
        return source_id == self.id or source_id in self.produces


def degraded_source(spec: CollectorSpec, hint: str) -> VariableSource:
    return VariableSource(
        id=spec.id,
        kind=spec.kind,
        label=spec.label,
        state=AvailabilityState.DEGRADED,
        hint=hint,
        outside_repository=spec.outside_repository,
    )


def fan_out(
    specs: Sequence[CollectorSpec],
    project: Path,
    *,
    total_timeout_s: float = TOTAL_TIMEOUT_S,
    max_concurrent: int = MAX_CONCURRENT_COLLECTORS,
) -> list[VariableSource]:
    """Run every collector concurrently and return their sources in `specs` order.

    Never raises and never blocks past `total_timeout_s`: a collector still running at the
    deadline is reported as degraded and abandoned, its thread left to finish into a result
    slot nobody reads.
    """
    if not specs:
        return []

    outcomes: dict[str, list[VariableSource] | BaseException] = {}
    lock = threading.Lock()
    gate = threading.Semaphore(max(1, max_concurrent))
    threads: list[tuple[CollectorSpec, threading.Thread]] = []

    for spec in specs:
        thread = threading.Thread(
            target=_run_collector,
            args=(spec, project, outcomes, lock, gate),
            name=f"envsource-{spec.id}",
            daemon=True,
        )
        thread.start()
        threads.append((spec, thread))

    deadline = time.monotonic() + total_timeout_s
    for _spec, thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))

    collected: list[VariableSource] = []
    for spec in specs:
        with lock:
            outcome = outcomes.get(spec.id)
        collected.extend(_resolve(spec, outcome, total_timeout_s))
    return collected


def _run_collector(
    spec: CollectorSpec,
    project: Path,
    outcomes: dict[str, list[VariableSource] | BaseException],
    lock: threading.Lock,
    gate: threading.Semaphore,
) -> None:
    with gate:
        try:
            result: list[VariableSource] | BaseException = list(spec.collect(project))
        except BaseException as exc:  # noqa: BLE001 - a collector may never break the route
            result = exc
    with lock:
        outcomes[spec.id] = result


def _resolve(
    spec: CollectorSpec,
    outcome: list[VariableSource] | BaseException | None,
    timeout_s: float,
) -> list[VariableSource]:
    if outcome is None:
        return [degraded_source(spec, _HINT_TIMEOUT.format(label=spec.label, timeout=timeout_s))]
    if isinstance(outcome, BaseException):
        detail = str(outcome).strip() or type(outcome).__name__
        return [degraded_source(spec, _HINT_FAILED.format(label=spec.label, detail=detail))]
    return outcome


# -- assembly ------------------------------------------------------------


def provider_specs(project: Path) -> list[CollectorSpec]:
    """The external collectors to fan out for `project`, in the order tabs should appear."""
    from cabal import envsource_azure_link
    from cabal import envsource_azure_service as azure
    from cabal import envsource_github_service as github
    from cabal import envsource_vercel_service as vercel

    explicit = envsource_azure_link.load_link(project)
    return [
        CollectorSpec(
            id=github.SOURCE_ID,
            kind=SourceKind.GITHUB,
            label=github.LABEL,
            collect=github.collect_github,
        ),
        CollectorSpec(
            id=azure.VAULT_SOURCE_ID,
            kind=SourceKind.AZURE_KEYVAULT,
            label=azure.VAULT_LABEL,
            collect=lambda path: azure.collect_azure(path, explicit),
            produces=(azure.APP_SOURCE_ID,),
        ),
        CollectorSpec(
            id=vercel.SOURCE_ID,
            kind=SourceKind.VERCEL,
            label=vercel.LABEL,
            collect=vercel.collect_vercel,
        ),
    ]


def build_payload(project: Path, *, only: str | None = None) -> dict:
    """The listing. `only` narrows it to one source and buys that source a longer wait (FR-038)."""
    if only is not None:
        return _single_source_payload(project, only)

    from cabal.envsource_discovery import collect_repo_files

    local, notices = collect_repo_files(project)
    external = fan_out(provider_specs(project), project, total_timeout_s=TOTAL_TIMEOUT_S)
    sources = [source for source in [*local, *external] if _is_present(source)]
    return _payload(project, sources, notices)


def _single_source_payload(project: Path, only: str) -> dict:
    """Re-collect exactly one source, with the generous budget a deliberate refresh earns."""
    from cabal.envsource_discovery import collect_repo_files

    spec = next((item for item in provider_specs(project) if item.emits(only)), None)
    if spec is not None:
        collected = fan_out([spec], project, total_timeout_s=REFRESH_TIMEOUT_S)
    else:
        collected, _notices = collect_repo_files(project)
    sources = [
        source for source in collected if source.id == only and _is_present(source)
    ]
    if not sources:
        raise ApiError(404, "source_not_found", f"No source {only!r} for the selected project")
    return _payload(project, sources, [])


def _payload(project: Path, sources: list[VariableSource], notices: list[str]) -> dict:
    return {
        "sources": [source_payload(source) for source in sources],
        "project": str(project),
        "scanned_at": utc_now_iso(),
        "notices": notices,
    }


def _is_present(source: VariableSource) -> bool:
    """A source with no link signal is absent from the response entirely (FR-005, C3)."""
    return source.state is not AvailabilityState.NOT_LINKED


# -- reveal dispatch -----------------------------------------------------


def reveal(project: Path, source_id: str, container_id: str, name: str) -> RevealResult:
    """Fetch exactly one value, routing by `source_id` to the collector that owns it.

    Raises `ApiError(404)` when the triple names nothing this module listed; a provider that
    refuses or cannot answer is a `denied`/`unavailable` result, not an error (contract R6).
    """
    from cabal import envsource_azure_service as azure
    from cabal import envsource_github_service as github
    from cabal import envsource_vercel_service as vercel

    if source_id.startswith(SourceKind.REPO_FILE.value + ":"):
        return _reveal_repo_file(project, source_id, name)
    if source_id.startswith(SourceKind.DOTNET_LAUNCH_PROFILE.value + ":"):
        return _reveal_launch_profile(project, source_id, container_id, name)
    if source_id.startswith(SourceKind.DOTNET_SECRETS.value + ":"):
        return _reveal_user_secret(project, source_id, name)
    if source_id == github.SOURCE_ID:
        return _reveal_github(project, container_id, name)
    if source_id == azure.VAULT_SOURCE_ID:
        value, reason = azure.reveal_vault_secret(container_id, name)
        return _from_provider(value, reason, denied=True)
    if source_id == azure.APP_SOURCE_ID:
        return _reveal_app_setting(container_id, name)
    if source_id == vercel.SOURCE_ID:
        return _reveal_vercel(project, container_id, name)
    raise _not_found()


def _reveal_github(project: Path, container_id: str, name: str) -> RevealResult:
    from cabal import envsource_github_service as github

    # A GitHub secret can never be returned, so the classification is authoritative and the
    # round trip is skipped entirely (data-model rule 8, contract R3).
    if container_id.endswith(":secrets"):
        return RevealResult(status="unavailable", reason=github.REASON_SECRET_NEVER)
    value, reason = github.reveal_github(project, container_id, name)
    return _from_provider(value, reason, denied=False)


def _reveal_vercel(project: Path, container_id: str, name: str) -> RevealResult:
    from cabal import envsource_vercel_service as vercel

    entry_type = _vercel_entry_type(project, container_id, name)
    if entry_type is _MISSING:
        raise _not_found()
    if str(entry_type or "").lower() == vercel.SENSITIVE_TYPE:
        return RevealResult(status="unavailable", reason=vercel.REASON_SENSITIVE_NEVER)
    value, reason = vercel.reveal_vercel(project, name, entry_type)
    return _from_provider(value, reason, denied=True)


def _vercel_entry_type(project: Path, container_id: str, name: str):
    """The entry's own Vercel classification, read from the listing -- never from a decrypt."""
    from cabal import envsource_vercel_service as vercel

    for source in vercel.collect_vercel(project):
        for container in source.containers:
            if container.id != container_id:
                continue
            for entry in container.entries:
                if entry.name == name:
                    return entry.entry_type
    return _MISSING


def _reveal_app_setting(container_id: str, name: str) -> RevealResult:
    from cabal import envsource_azure_service as azure

    if container_id.count(":") < 2:
        raise _not_found()
    value, reason = azure.reveal_app_setting(container_id, name)
    result = _from_provider(value, reason, denied=True)
    if result.status != "revealed":
        return result
    is_reference = bool(value) and value.startswith(azure.KEYVAULT_REFERENCE_PREFIX)
    return replace(result, is_reference=is_reference)


def _reveal_repo_file(project: Path, source_id: str, name: str) -> RevealResult:
    from cabal.envsource_discovery import read_value

    path = _resolve_repo_path(project, source_id)
    value = read_value(path, name)
    if value is None:
        raise _not_found()
    return RevealResult(status="revealed", value=value)


def _reveal_launch_profile(
    project: Path, source_id: str, container_id: str, name: str
) -> RevealResult:
    path = _resolve_repo_path(project, source_id)
    profile_name = container_id.rsplit("#", 1)[-1] if "#" in container_id else None
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise _not_found() from None
    profiles = document.get("profiles") if isinstance(document, dict) else None
    profile = profiles.get(profile_name) if isinstance(profiles, dict) and profile_name else None
    variables = profile.get("environmentVariables") if isinstance(profile, dict) else None
    if not isinstance(variables, dict) or name not in variables:
        raise _not_found()
    value = variables[name]
    return RevealResult(status="revealed", value="" if value is None else str(value))


def _reveal_user_secret(project: Path, source_id: str, name: str) -> RevealResult:
    from cabal.envsource_dotnet import find_user_secrets, read_secret_value

    secrets_id = source_id.split(":", 1)[1]
    # FR-047: only a store the SELECTED project declares is ever read.
    if secrets_id not in {item.secrets_id for item in find_user_secrets(project)}:
        raise _not_found()
    value = read_secret_value(secrets_id, name)
    if value is None:
        raise _not_found()
    return RevealResult(status="revealed", value=value)


def _resolve_repo_path(project: Path, source_id: str) -> Path:
    relative = source_id.split(":", 1)[1].replace("~", "/")
    candidate = (Path(project) / relative).resolve()
    try:
        candidate.relative_to(Path(project).resolve())
    except ValueError:
        # A source id that climbs out of the project is not one this module produced.
        raise _not_found() from None
    if not candidate.is_file():
        raise _not_found()
    return candidate


def _from_provider(value: str | None, reason: str | None, *, denied: bool) -> RevealResult:
    if value is not None:
        return RevealResult(status="revealed", value=value)
    status = "denied" if denied else "unavailable"
    return RevealResult(status=status, reason=reason or "the value could not be retrieved")


def _not_found() -> ApiError:
    return ApiError(404, "entry_not_found", "No such entry in the current listing")
