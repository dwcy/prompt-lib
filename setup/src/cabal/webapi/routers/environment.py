"""Environment variables, git identity, and commit-policy routes/actions."""

from __future__ import annotations

import json
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, Request

from fastapi.responses import JSONResponse

from cabal import envsource_azure_link
from cabal._paths import ENV_FILE
from cabal.components import ENV_DESCRIPTIONS
from cabal.env_profile import update_profile
from cabal.git_config import apply_git_line_endings
from cabal.git_policy import BUILTIN_DEFAULTS, load_policy, policy_source, save_policy
from cabal.redaction import redact_env_display
from cabal.webapi import envsources_service, security
from cabal.webapi.actions import ActionDescriptor, ActionOutcome, effect_preview
from cabal.webapi.envelope import (
    ApiError,
    compute_precondition_digest,
    envelope_body,
    envelope_response,
)

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

ENV_APPLY_ACTION_ID = "env.apply"
ENV_AZURE_LINK_ACTION_ID = "env.azure_link.set"
GIT_IDENTITY_SET_ACTION_ID = "git.identity.set"
GIT_POLICY_SET_ACTION_ID = "git.policy.set"

_PATH_KEYS = frozenset({"PROJECTS_PATH", "TEMP_PATH"})
_ENV_APPLY_SCHEMA = {
    "type": "object",
    "properties": {"values": {"type": "object"}},
    "required": ["values"],
    "additionalProperties": False,
}
# `subscription_id: null` is the clear operation (FR-033) rather than a separate flag: it
# keeps one action for one concern, and declaring the field required is what marks this as
# an action a blank-params sweep must not invoke.
_AZURE_LINK_SCHEMA = {
    "type": "object",
    "properties": {
        "subscription_id": {"type": ["string", "null"]},
        "resource_group": {"type": ["string", "null"]},
    },
    "required": ["subscription_id"],
    "additionalProperties": False,
}
_IDENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {"type": "string", "enum": ["global", "local"]},
        "name": {"type": "string"},
        "email": {"type": "string"},
    },
    "required": ["scope", "name", "email"],
    "additionalProperties": False,
}
_POLICY_SCHEMA = {
    "type": "object",
    "properties": {
        "agent_name": {"type": "string"},
        "agent_email": {"type": "string"},
        "allowed_types": {"type": "array", "items": {"type": "string"}},
        "refuse_on_branches": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "object"},
    },
    "required": ["agent_name", "agent_email", "allowed_types", "refuse_on_branches", "tags"],
    "additionalProperties": False,
}


def _env_defaults() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    try:
        data = json.loads(ENV_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(key): str(value) for key, value in data.items() if isinstance(key, str)}


def _curated_entries(q: str | None = None) -> list[dict[str, Any]]:
    defaults = _env_defaults()
    entries: list[dict[str, Any]] = []
    needle = (q or "").strip().lower()
    for key, default in defaults.items():
        current = os.environ.get(key)
        value = current if current is not None else default
        source = "system" if current is not None else ("default" if default else "unset")
        display = redact_env_display(key, str(value))
        row = {
            "name": key,
            "value_redacted": display,
            "default": redact_env_display(key, str(default)),
            "is_path": key in _PATH_KEYS,
            "source": source,
            "editable": True,
            "description": ENV_DESCRIPTIONS.get(key, ""),
        }
        if needle and needle not in key.lower() and needle not in display.lower():
            continue
        entries.append(row)
    return entries


def _system_entries(q: str | None = None) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for key, value in sorted(os.environ.items()):
        display = redact_env_display(key, value)
        if needle and needle not in key.lower() and needle not in display.lower():
            continue
        rows.append(
            {
                "name": key,
                "value_redacted": display,
                "default": "",
                "is_path": "PATH" in key.upper() or key.upper().endswith("_HOME"),
                "source": "system",
                "editable": False,
                "description": "",
            }
        )
    return rows


def env_digest() -> str:
    # Digest over the RAW curated state, not the redacted display rows: two
    # different secret values must not collapse into the same masked digest.
    raw = {key: os.environ.get(key, default) for key, default in _env_defaults().items()}
    return compute_precondition_digest({"curated": raw, "platform": platform.system()})


@router.get("/api/env")
def env_vars(scope: Literal["curated", "system"] = "curated", q: str | None = None):
    entries = _curated_entries(q) if scope == "curated" else _system_entries(q)
    data = {
        "scope": scope,
        "entries": entries,
        "count": len(entries),
        "editable_count": sum(1 for entry in entries if entry["editable"]),
        "platform": platform.system(),
    }
    return envelope_response(data=data, source="environment", precondition_digest=env_digest())


# -- multi-source browser (020-env-variable-sources) ----------------------
# Added alongside the curated/system routes above, which are untouched (FR-002).

_REVEAL_SCHEMA_FIELDS = ("source_id", "container_id", "name")
_NO_STORE_HEADERS = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


def _selected_project(state: Any) -> Path:
    project = getattr(state, "project", None)
    if project is None:
        # 404 rather than 409: every other project-scoped read in this app (docs, package
        # security, dashboard sections) answers a missing project that way, and the
        # action-safety GET sweep is written against that convention.
        raise ApiError(404, "no_project_selected", "Select a project before browsing its variables")
    return Path(project)


@router.get("/api/env/sources")
def env_sources(request: Request, source: str | None = None):
    """Names and metadata for every detected source. Never returns a value (FR-008)."""
    project = _selected_project(request.app.state)
    data = envsources_service.build_payload(project, only=source)
    return envelope_response(data=data, source="environment")


@router.post("/api/env/reveal")
def env_reveal(request: Request, body: dict[str, Any] = Body(...)):
    """Fetch exactly one value, on explicit user action, and audit the attempt (FR-012/16)."""
    project = _selected_project(request.app.state)
    source_id, container_id, name = _validated_reveal(body)

    result = envsources_service.reveal(project, source_id, container_id, name)
    audit = getattr(request.app.state, "audit", None)
    if audit is not None:
        audit.record_reveal(
            source_id=source_id,
            container_id=container_id,
            name=name,
            status=result.status,
        )

    # The envelope redacts every string it serialises, which is right for every other route
    # and wrong for exactly this field: a revealed token would come back as "[redacted]",
    # defeating the reveal the user explicitly asked for. So the value is re-seated after
    # the envelope is built, and only ever for a `revealed` result.
    payload = {
        "status": result.status,
        "value": None,
        "reason": result.reason,
        "is_reference": result.is_reference,
    }
    envelope = envelope_body(data=payload, source="environment")
    if result.status == "revealed":
        envelope["data"]["value"] = result.value
    return JSONResponse(envelope, status_code=200, headers=_NO_STORE_HEADERS)


def _validated_reveal(body: Any) -> tuple[str, str, str]:
    if not isinstance(body, dict):
        raise ApiError(422, "params_invalid", "Body must be an object naming exactly one entry")
    values: list[str] = []
    for field in _REVEAL_SCHEMA_FIELDS:
        value = body.get(field)
        # There is no array form by design (FR-012): one reveal, one audit record.
        if not isinstance(value, str) or not value:
            raise ApiError(422, "params_invalid", f"{field} must be a non-empty string")
        values.append(value)
    return values[0], values[1], values[2]


def _azure_link_prepare(params: dict, state: Any) -> dict:
    _selected_project(state)
    summary = (
        "Record an Azure scope for this project"
        if _is_recording(params)
        else "Clear the recorded Azure scope for this project"
    )
    return effect_preview(
        summary,
        files_changed=[str(envsource_azure_link.store_path())],
        scopes=["environment", "azure_link"],
    )


def _is_recording(params: dict) -> bool:
    return bool(str(params.get("subscription_id") or "").strip())


def _azure_link_execute(params: dict, state: Any) -> ActionOutcome:
    project = _selected_project(state)
    if not _is_recording(params):
        cleared = envsource_azure_link.clear_link(project)
        return ActionOutcome(data={"cleared": cleared, "link": None})
    link = envsource_azure_link.save_link(
        project,
        str(params["subscription_id"]).strip(),
        str(params.get("resource_group") or "").strip() or None,
    )
    return ActionOutcome(
        data={
            "cleared": False,
            "link": {
                "subscription_id": link.subscription_id,
                "resource_group": link.resource_group,
                "confidence": link.confidence.value,
                "reason": link.reason,
                "is_explicit": link.is_explicit,
            },
        }
    )


def azure_link_digest(state: Any) -> str:
    project = getattr(state, "project", None)
    if project is None:
        return compute_precondition_digest({"azure_link": None})
    link = envsource_azure_link.load_link(Path(project))
    return compute_precondition_digest(
        {
            "project": str(project),
            "subscription_id": link.subscription_id if link else None,
            "resource_group": link.resource_group if link else None,
        }
    )


def _validated_env_values(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ApiError(422, "params_invalid", "values must be an object")
    defaults = _env_defaults()
    values: dict[str, str] = {}
    for key, value in raw.items():
        key_str = str(key)
        if key_str not in defaults:
            raise ApiError(422, "params_invalid", f"{key_str!r} is not a curated environment key")
        values[key_str] = str(value)
    return values


def _env_apply_prepare(params: dict, _state: Any) -> dict:
    values = _validated_env_values(params["values"])
    non_empty = {key: value for key, value in values.items() if value.strip()}
    commands = []
    if platform.system() == "Windows":
        commands.extend(f"setx {key} <value>" for key in non_empty)
    elif non_empty:
        commands.append("rewrite shell profile claude-code-env block")
    if non_empty.get("GIT_LINE_ENDINGS"):
        commands.append(f"git config --global core.autocrlf {non_empty['GIT_LINE_ENDINGS']}")
    return effect_preview(
        f"Apply {len(non_empty)} curated environment value(s)",
        commands=commands,
        files_changed=["user environment"] if non_empty else [],
        scopes=["environment"],
    )


def _env_apply_execute(params: dict, _state: Any) -> ActionOutcome:
    values = _validated_env_values(params["values"])
    non_empty = {key: value for key, value in values.items() if value.strip()}
    messages: list[str] = []
    if platform.system() == "Windows":
        for key, value in non_empty.items():
            result = subprocess.run(["setx", key, value], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                messages.append(f"setx {key}")
            else:
                messages.append(f"setx {key} failed: {(result.stderr or result.stdout).strip()}")
    elif non_empty:
        export_lines = [f"export {key}={shlex.quote(value)}" for key, value in non_empty.items()]
        for profile in ["~/.bashrc", "~/.zshrc", "~/.profile"]:
            update_profile(profile, list(non_empty), export_lines)
        messages.append("Updated shell profile files")
    line_endings = non_empty.get("GIT_LINE_ENDINGS", "").strip()
    if line_endings:
        ok, message = apply_git_line_endings(line_endings)
        messages.append(message if ok else f"git line endings failed: {message}")
    return ActionOutcome(data={"messages": messages, "restart_required": bool(non_empty)})


def _git() -> str | None:
    return shutil.which("git")


def _repo_root(state: Any) -> Path | None:
    project = getattr(state, "project", None)
    start = Path(project) if project is not None else Path.cwd()
    for path in (start, *start.parents):
        if (path / ".git").exists():
            return path
    return None


def _read_git_config(key: str, scope: Literal["global", "local"], repo: Path | None) -> str:
    git = _git()
    if not git:
        return ""
    if scope == "local" and repo is None:
        return ""
    cmd = [git]
    if scope == "local" and repo is not None:
        cmd += ["-C", str(repo)]
    cmd += ["config", f"--{scope}", key]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout or "").strip()


def _write_git_config(key: str, value: str, scope: Literal["global", "local"], repo: Path | None) -> tuple[bool, str]:
    git = _git()
    if not git:
        return False, "git not found"
    if scope == "local" and repo is None:
        return False, "no git repository selected for local scope"
    cmd = [git]
    if scope == "local" and repo is not None:
        cmd += ["-C", str(repo)]
    cmd += ["config", f"--{scope}", key, value]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return result.returncode == 0, (result.stderr or "").strip()


def _identity_payload(state: Any) -> dict[str, Any]:
    repo = _repo_root(state)
    rows = []
    for scope in ("global", "local"):
        rows.append(
            {
                "scope": scope,
                "name": _read_git_config("user.name", scope, repo),
                "email": _read_git_config("user.email", scope, repo),
                "available": scope == "global" or repo is not None,
                "source": str(repo / ".git/config") if scope == "local" and repo else str(Path.home() / ".gitconfig"),
            }
        )
    return {"repo_root": str(repo) if repo is not None else None, "identities": rows}


def identity_digest(state: Any) -> str:
    return compute_precondition_digest(_identity_payload(state))


@router.get("/api/git/identity")
def git_identity(request: Request):
    return envelope_response(
        data=_identity_payload(request.app.state),
        source="git_identity",
        precondition_digest=identity_digest(request.app.state),
    )


def _policy_payload() -> dict[str, Any]:
    return {
        "policy": load_policy(),
        "source": str(policy_source()),
        "defaults": BUILTIN_DEFAULTS,
    }


def policy_digest() -> str:
    return compute_precondition_digest(_policy_payload())


@router.get("/api/git/policy")
def git_policy():
    return envelope_response(data=_policy_payload(), source="git_identity", precondition_digest=policy_digest())


def _identity_prepare(params: dict, state: Any) -> dict:
    scope = params["scope"]
    if scope == "local" and _repo_root(state) is None:
        raise ApiError(422, "params_invalid", "No git repository selected for local identity")
    changes = []
    if params.get("name", "").strip():
        changes.append(f"user.name={params['name'].strip()}")
    if params.get("email", "").strip():
        changes.append("user.email=<value>")
    return effect_preview(
        f"Set {scope} git identity",
        commands=[f"git config --{scope} {change}" for change in changes],
        files_changed=[".git/config" if scope == "local" else "~/.gitconfig"],
        scopes=["git_identity", scope],
    )


def _identity_execute(params: dict, state: Any) -> ActionOutcome:
    scope: Literal["global", "local"] = params["scope"]
    repo = _repo_root(state)
    results: list[dict[str, Any]] = []
    for key, value in (("user.name", params["name"].strip()), ("user.email", params["email"].strip())):
        if not value:
            continue
        ok, message = _write_git_config(key, value, scope, repo)
        results.append({"key": key, "ok": ok, "message": message})
    if any(not result["ok"] for result in results):
        raise ApiError(500, "git_config_failed", "One or more git config writes failed", extra={"results": results})
    return ActionOutcome(data={"results": results, "identity": _identity_payload(state)})


def _validate_policy(params: dict) -> dict[str, Any]:
    tags = params.get("tags")
    if not isinstance(tags, dict):
        raise ApiError(422, "params_invalid", "tags must be an object")
    allowed_types = params.get("allowed_types")
    refuse_on_branches = params.get("refuse_on_branches")
    if not isinstance(allowed_types, list) or not all(isinstance(item, str) and item.strip() for item in allowed_types):
        raise ApiError(422, "params_invalid", "allowed_types must be a non-empty string array")
    if not isinstance(refuse_on_branches, list) or not all(isinstance(item, str) and item.strip() for item in refuse_on_branches):
        raise ApiError(422, "params_invalid", "refuse_on_branches must be a non-empty string array")
    for key in ("agent_may_tag", "auto_push"):
        if key in tags and not isinstance(tags[key], bool):
            raise ApiError(422, "params_invalid", f"tags.{key} must be boolean")
    return {
        "agent_name": str(params["agent_name"]).strip() or BUILTIN_DEFAULTS["agent_name"],
        "agent_email": str(params["agent_email"]).strip() or BUILTIN_DEFAULTS["agent_email"],
        "allowed_types": [item.strip() for item in allowed_types],
        "refuse_on_branches": [item.strip() for item in refuse_on_branches],
        "tags": {
            "agent_may_tag": bool(tags.get("agent_may_tag", False)),
            "auto_push": bool(tags.get("auto_push", False)),
        },
    }


def _policy_prepare(params: dict, _state: Any) -> dict:
    policy = _validate_policy(params)
    return effect_preview(
        "Update agent commit policy",
        commands=["write ~/.claude/git-policy.json"],
        files_changed=[str(Path.home() / ".claude" / "git-policy.json")],
        scopes=["git_identity", "commit_policy"],
    )


def _policy_execute(params: dict, _state: Any) -> ActionOutcome:
    policy = _validate_policy(params)
    written = save_policy(policy)
    return ActionOutcome(data={"written": str(written), "policy": policy})


ENV_APPLY_DESCRIPTOR = ActionDescriptor(
    action_id=ENV_APPLY_ACTION_ID,
    module="environment",
    destructive=False,
    params_schema=_ENV_APPLY_SCHEMA,
    prepare=_env_apply_prepare,
    execute=_env_apply_execute,
    compute_digest=lambda _params, _state: env_digest(),
)

GIT_IDENTITY_SET_DESCRIPTOR = ActionDescriptor(
    action_id=GIT_IDENTITY_SET_ACTION_ID,
    module="git_identity",
    destructive=False,
    params_schema=_IDENTITY_SCHEMA,
    prepare=_identity_prepare,
    execute=_identity_execute,
    compute_digest=lambda _params, state: identity_digest(state),
)

GIT_POLICY_SET_DESCRIPTOR = ActionDescriptor(
    action_id=GIT_POLICY_SET_ACTION_ID,
    module="git_identity",
    destructive=False,
    params_schema=_POLICY_SCHEMA,
    prepare=_policy_prepare,
    execute=_policy_execute,
    compute_digest=lambda _params, _state: policy_digest(),
)

ENV_AZURE_LINK_DESCRIPTOR = ActionDescriptor(
    action_id=ENV_AZURE_LINK_ACTION_ID,
    module="environment",
    destructive=False,
    params_schema=_AZURE_LINK_SCHEMA,
    prepare=_azure_link_prepare,
    execute=_azure_link_execute,
    compute_digest=lambda _params, state: azure_link_digest(state),
)

ENVIRONMENT_DESCRIPTORS = (
    ENV_APPLY_DESCRIPTOR,
    ENV_AZURE_LINK_DESCRIPTOR,
    GIT_IDENTITY_SET_DESCRIPTOR,
    GIT_POLICY_SET_DESCRIPTOR,
)
