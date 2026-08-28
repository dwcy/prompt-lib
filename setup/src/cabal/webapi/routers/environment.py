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

from fastapi import APIRouter, Depends, Request

from cabal._paths import ENV_FILE
from cabal.components import ENV_DESCRIPTIONS
from cabal.env_profile import update_profile
from cabal.git_config import apply_git_line_endings
from cabal.git_policy import BUILTIN_DEFAULTS, load_policy, policy_source, save_policy
from cabal.redaction import redact_env_display
from cabal.webapi import security
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError, compute_precondition_digest, envelope_response

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

ENV_APPLY_ACTION_ID = "env.apply"
GIT_IDENTITY_SET_ACTION_ID = "git.identity.set"
GIT_POLICY_SET_ACTION_ID = "git.policy.set"

_PATH_KEYS = frozenset({"PROJECTS_PATH", "TEMP_PATH"})
_ENV_APPLY_SCHEMA = {
    "type": "object",
    "properties": {"values": {"type": "object"}},
    "required": ["values"],
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
    return {
        "summary": f"Apply {len(non_empty)} curated environment value(s)",
        "commands": commands,
        "files_changed": ["user environment"] if non_empty else [],
        "scopes": ["environment"],
        "backup": None,
        "removals": [],
    }


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
    return {
        "summary": f"Set {scope} git identity",
        "commands": [f"git config --{scope} {change}" for change in changes],
        "files_changed": [".git/config" if scope == "local" else "~/.gitconfig"],
        "scopes": ["git_identity", scope],
        "backup": None,
        "removals": [],
    }


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
    return {
        "summary": "Update agent commit policy",
        "commands": ["write ~/.claude/git-policy.json"],
        "files_changed": [str(Path.home() / ".claude" / "git-policy.json")],
        "scopes": ["git_identity", "commit_policy"],
        "backup": None,
        "removals": [],
    }


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

ENVIRONMENT_DESCRIPTORS = (
    ENV_APPLY_DESCRIPTOR,
    GIT_IDENTITY_SET_DESCRIPTOR,
    GIT_POLICY_SET_DESCRIPTOR,
)
