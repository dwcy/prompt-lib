"""Project context, provider clone, and init-wizard routes/actions."""

from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from cabal import gh_accounts, recent_projects
from cabal._paths import GLOBAL_DIR
from cabal.claude_cli import spawn_claude
from cabal.gh_templates import GitHubTemplateRef, download_tarball, list_user_templates
from cabal.init_project_service import (
    InjectableFile,
    LocalTemplateRef,
    apply_plan,
    count_project_mcp_entries,
    ensure_mcp_gitignored,
    enumerate_github_template_files,
    enumerate_local_template_files,
    enumerate_run_launcher_files,
)
from cabal.installers.gh import gh_device_init, gh_device_poll, gh_status
from cabal.views.init_project_prompt import build_init_prompt, write_init_prompt
from cabal.webapi import security
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError, compute_precondition_digest, envelope_response, utc_now_iso

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

PROJECT_SELECT_ACTION_ID = "project.select"
PROVIDER_LOGIN_ACTION_ID = "provider.login"
PROVIDER_SWITCH_ACTION_ID = "provider.switch_account"
PROVIDER_FORGET_ACTION_ID = "provider.forget_account"
PROVIDER_CLONE_ACTION_ID = "provider.clone"
INIT_APPLY_ACTION_ID = "init.apply"

_NAME_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
_WIN_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)
_SCAFFOLD_RELPATHS = [
    ".claude/skills",
    ".claude/hooks",
    ".claude/agents",
    ".claude/settings.local.json",
]
_DEFAULT_GH_SCOPES = ["repo", "read:org"]
_PROCESS_POLL_SECONDS = 0.2


def _live_recents() -> list[dict[str, str]]:
    """Recents with dead paths pruned from the persisted store (T030 dead-path pruning)."""
    live: list[dict[str, str]] = []
    for recent in recent_projects.load_recents():
        if not Path(recent.path).is_dir():
            recent_projects.remove_recent(Path(recent.path))
            continue
        live.append(
            {
                "path": recent.path,
                "name": recent.name,
                "action": recent.action,
                "last_opened": recent.last_opened,
            }
        )
    return live


def _project_context(request: Request) -> dict[str, Any]:
    project = request.app.state.project
    path = Path(project) if project is not None else None
    return {
        "path": str(path) if path is not None else "",
        "name": path.name if path is not None else "",
        "is_git_repo": bool(path is not None and (path / ".git").exists()),
        "recents": _live_recents(),
        "selected_at": getattr(request.app.state, "project_selected_at", None),
    }


@router.get("/api/project")
def get_project(request: Request):
    return envelope_response(data=_project_context(request), source="projects")


def _account_payload(account: gh_accounts.GhAccount) -> dict[str, Any]:
    return {
        "user": account.user,
        "host": account.host,
        "active": account.active,
        "valid": account.valid,
        "storage": account.storage,
    }


def _accounts_digest() -> str:
    return compute_precondition_digest([_account_payload(account) for account in gh_accounts.list_accounts()])


def _provider_payload(state: Any) -> dict[str, Any]:
    accounts = [_account_payload(account) for account in gh_accounts.list_accounts()]
    active = next((account["user"] for account in accounts if account["active"] and account["valid"]), None)
    login_session = getattr(state, "provider_login_session", None)
    return {
        "authenticated": any(account["valid"] for account in accounts),
        "accounts": accounts,
        "active_account": active,
        "gh_status": gh_status(),
        "login": _login_session_payload(login_session),
    }


def _login_session_payload(session: dict[str, Any] | None) -> dict[str, Any]:
    if not session:
        return {"state": "idle"}
    return {
        "state": session.get("state", "code_issued"),
        "user_code": session.get("user_code", ""),
        "verification_uri": session.get("verification_uri", "https://github.com/login/device"),
        "expires_at": session.get("expires_at"),
        "scopes": session.get("scopes", []),
        "message": session.get("message", ""),
    }


def _run_gh_json(args: list[str], *, timeout: int = 30) -> Any:
    if not shutil.which("gh"):
        raise RuntimeError("gh CLI not found - install GitHub CLI first")
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gh {' '.join(args)} failed (exit {proc.returncode})")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not parse gh JSON output: {exc}") from exc


def _repo_payload(entry: dict[str, Any]) -> dict[str, Any]:
    owner = entry.get("owner")
    owner_login = owner.get("login") if isinstance(owner, dict) else str(owner or "")
    name = str(entry.get("name") or "")
    full_name = f"{owner_login}/{name}" if owner_login and name else name
    return {
        "name": name,
        "owner": owner_login,
        "full_name": full_name,
        "visibility": str(entry.get("visibility") or ("private" if entry.get("isPrivate") else "public")),
        "updated_at": str(entry.get("updatedAt") or ""),
        "url": str(entry.get("url") or ""),
        "description": entry.get("description") or "",
    }


def _list_repos(q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows = _run_gh_json(
        [
            "repo",
            "list",
            "--json",
            "name,owner,visibility,updatedAt,url,description,isPrivate",
            "--limit",
            str(max(1, min(limit, 200))),
        ],
        timeout=45,
    )
    repos = [_repo_payload(entry) for entry in rows if isinstance(entry, dict)]
    needle = (q or "").strip().lower()
    if needle:
        repos = [
            repo
            for repo in repos
            if needle in repo["full_name"].lower() or needle in str(repo.get("description", "")).lower()
        ]
    return repos


@router.get("/api/provider")
def provider_state(request: Request):
    return envelope_response(data=_provider_payload(request.app.state), source="provider")


@router.get("/api/provider/repos")
def provider_repos(q: str | None = None, limit: int = 100):
    try:
        repos = _list_repos(q=q, limit=limit)
    except Exception as exc:
        return envelope_response(
            status="degraded",
            source="provider",
            data={"repos": [], "count": 0},
            error={"code": "provider_repos_unavailable", "message": str(exc)},
        )
    return envelope_response(data={"repos": repos, "count": len(repos)}, source="provider")


def _local_template_refs() -> list[LocalTemplateRef]:
    template_root = GLOBAL_DIR / "project-templates"
    templates = sorted(template_root.glob("*.md")) if template_root.exists() else []
    return [LocalTemplateRef(stem=path.stem, path=path, gitignore_preset_name=path.stem) for path in templates]


def _template_payload(ref: LocalTemplateRef | GitHubTemplateRef) -> dict[str, Any]:
    if isinstance(ref, LocalTemplateRef):
        return {
            "id": f"local:{ref.stem}",
            "source": "local",
            "label": ref.stem,
            "description": f"Local {ref.stem} project template",
            "owner": "",
            "name": ref.stem,
            "default_branch": "",
            "url": str(ref.path),
        }
    return {
        "id": f"github:{ref.owner}/{ref.name}@{ref.default_branch}",
        "source": "github",
        "label": f"{ref.owner}/{ref.name}",
        "description": ref.description or "",
        "owner": ref.owner,
        "name": ref.name,
        "default_branch": ref.default_branch,
        "url": ref.url,
    }


def _list_templates_payload() -> tuple[dict[str, Any], bool, str | None]:
    local = [_template_payload(ref) for ref in _local_template_refs()]
    github: list[dict[str, Any]] = []
    error: str | None = None
    try:
        github = [_template_payload(ref) for ref in list_user_templates()]
    except Exception as exc:
        error = str(exc)
    return {"local": local, "github": github, "default_template": local[0]["id"] if local else None}, bool(error), error


@router.get("/api/init/templates")
def init_templates():
    data, degraded, error_message = _list_templates_payload()
    return envelope_response(
        status="degraded" if degraded else "ok",
        source="init",
        data=data,
        error={"code": "github_templates_unavailable", "message": error_message} if error_message else None,
    )


def _target_is_empty_or_only_mcp_json(target: Path) -> bool:
    if not target.exists():
        return True
    if not target.is_dir():
        return False
    entries = list(target.iterdir())
    if not entries:
        return True
    return len(entries) == 1 and entries[0].name == ".mcp.json"


def _target_state(target: Path) -> dict[str, Any]:
    if not target.exists():
        return {"exists": False, "kind": "missing", "entries": []}
    if not target.is_dir():
        return {"exists": True, "kind": "file", "entries": []}
    return {
        "exists": True,
        "kind": "directory",
        "entries": sorted(path.name for path in target.iterdir()),
    }


def _validate_init_target(parent: Path, name: str) -> tuple[bool, str]:
    if not name:
        return False, "Enter a project name."
    if not _NAME_RE.match(name):
        return False, "Name must match [A-Za-z0-9._-] and be 1-64 chars."
    if name.upper() in _WIN_RESERVED:
        return False, f"{name!r} is a Windows-reserved name."
    if not parent.is_dir():
        return False, "Parent directory does not exist."
    target = parent / name
    if not _target_is_empty_or_only_mcp_json(target):
        return False, f"{target} exists and is not empty."
    return True, f"Target ready: {target}"


def _parse_template(template_id: str) -> LocalTemplateRef | GitHubTemplateRef:
    if template_id.startswith("local:"):
        stem = template_id.split(":", 1)[1]
        match = next((ref for ref in _local_template_refs() if ref.stem == stem), None)
        if match is None:
            raise ApiError(422, "params_invalid", f"Unknown local template {stem!r}")
        return match
    if template_id.startswith("github:"):
        raw = template_id.split(":", 1)[1]
        slug, _, branch = raw.partition("@")
        owner, sep, name = slug.partition("/")
        if not owner or not sep or not name:
            raise ApiError(422, "params_invalid", f"Invalid GitHub template id {template_id!r}")
        return GitHubTemplateRef(
            owner=owner,
            name=name,
            description=None,
            default_branch=branch or "main",
            url=f"https://github.com/{owner}/{name}",
        )
    raise ApiError(422, "params_invalid", f"Unknown template id {template_id!r}")


def _with_run_launcher(files: list[InjectableFile]) -> list[InjectableFile]:
    existing = {str(file.dest_relpath) for file in files}
    launchers = [
        file
        for file in enumerate_run_launcher_files(GLOBAL_DIR / "project-templates")
        if str(file.dest_relpath) not in existing
    ]
    return files + launchers


def _stage_template_files(template_id: str) -> tuple[list[InjectableFile], str, Path | None]:
    ref = _parse_template(template_id)
    if isinstance(ref, LocalTemplateRef):
        files = enumerate_local_template_files(ref, scaffold_dir_relpaths=_SCAFFOLD_RELPATHS)
        return _with_run_launcher(files), f"local: {ref.stem}", None
    extract_dir = download_tarball(ref)
    files = enumerate_github_template_files(extract_dir)
    return _with_run_launcher(files), f"GitHub: {ref.owner}/{ref.name}@{ref.default_branch}", extract_dir


def _file_payload(file: InjectableFile, target: Path, selected: bool | None = None) -> dict[str, Any]:
    dest = target / Path(str(file.dest_relpath))
    if file.origin == "scaffold":
        state = "new" if not dest.exists() else "skip"
    elif dest.exists():
        state = "changed"
    else:
        state = "new"
    return {
        "rel_path": str(file.dest_relpath),
        "state": state,
        "selected": file.selected if selected is None else selected,
        "origin": file.origin,
        "size_bytes": file.size_bytes,
    }


def _normalize_selected_files(raw: Any) -> set[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ApiError(422, "params_invalid", "selected_files must be a list of relative paths")
    return {str(item) for item in raw}


def _build_init_plan(
    *,
    dest: str,
    name: str,
    template: str,
    selected_files: set[str] | None = None,
) -> tuple[dict[str, Any], list[InjectableFile]]:
    parent = Path(dest).expanduser()
    target = parent / name.strip()
    valid, message = _validate_init_target(parent, name.strip())
    files: list[InjectableFile] = []
    warnings = [message] if not valid else []
    extract_dir: Path | None = None
    try:
        if valid:
            files, attribution, extract_dir = _stage_template_files(template)
        else:
            attribution = template
        selected_count = 0
        file_rows = []
        for file in files:
            selected = str(file.dest_relpath) in selected_files if selected_files is not None else file.selected
            file.selected = selected
            if selected:
                selected_count += 1
            file_rows.append(_file_payload(file, target, selected=selected))
        if valid and not file_rows:
            warnings.append("Template did not stage any files.")
        mcp_entries = count_project_mcp_entries(target) if target.exists() else 0
        plan = {
            "destination": str(target),
            "parent": str(parent),
            "name": name.strip(),
            "name_valid": valid,
            "validation_message": message,
            "template": template,
            "template_source": "github" if template.startswith("github:") else "local",
            "template_attribution": attribution,
            "staged_files": file_rows,
            "selected_count": selected_count,
            "mcp_config": {"entries": mcp_entries, "path": str(target / ".mcp.json")},
            "handoff_prompt_present": True,
            "warnings": warnings,
        }
        return plan, files
    finally:
        if extract_dir is not None:
            shutil.rmtree(extract_dir, ignore_errors=True)


def _init_digest(params: dict, _state: Any) -> str:
    target = Path(params["dest"]).expanduser() / str(params["name"]).strip()
    selected_files = sorted(_normalize_selected_files(params.get("selected_files")) or [])
    return compute_precondition_digest(
        {
            "target": str(target),
            "target_state": _target_state(target),
            "template": params["template"],
            "selected_files": selected_files,
            "mcp_json": str(params.get("mcp_json", "")),
        }
    )


@router.get("/api/init/plan")
def init_plan(dest: str, name: str, template: str):
    plan, _files = _build_init_plan(dest=dest, name=name, template=template)
    return envelope_response(data=plan, source="init", precondition_digest=_init_digest({"dest": dest, "name": name, "template": template}, None))


def _finish_process(proc: subprocess.Popen, handle: Any) -> int:
    output: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        try:
            assert proc.stdout is not None
            for raw in iter(proc.stdout.readline, ""):
                if raw == "":
                    break
                output.put(raw.rstrip("\n"))
        finally:
            output.put(None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    reader_done = False
    while proc.poll() is None or not reader_done:
        if handle.is_cancelled() and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        try:
            item = output.get(timeout=_PROCESS_POLL_SECONDS)
        except queue.Empty:
            continue
        if item is None:
            reader_done = True
            continue
        if item.strip():
            handle.emit_line(item.strip())
    thread.join(timeout=1)
    return int(proc.returncode or 0)


def _set_active_project(state: Any, target: Path, action: str) -> None:
    state.project = target
    state.project_selected_at = utc_now_iso()
    recent_projects.record_recent(target, action)


def _select_prepare(params: dict, _state: Any) -> dict:
    target = Path(params["path"])
    if not target.is_dir():
        raise ApiError(422, "params_invalid", f"{target} is not an existing directory")
    return {
        "summary": f"Switch active project to {target}",
        "commands": [],
        "files_changed": [],
        "scopes": ["project"],
        "backup": None,
        "removals": [],
    }


def _select_digest(_params: dict, state: Any) -> str:
    """Digest over the *current* active project, so a concurrent switch invalidates the ticket."""
    return compute_precondition_digest({"active_project": str(getattr(state, "project", None))})


def _select_execute(params: dict, state: Any) -> ActionOutcome:
    target = Path(params["path"])
    _set_active_project(state, target, "open")
    return ActionOutcome(
        data={"path": str(target), "name": target.name, "selected_at": state.project_selected_at}
    )


PROJECT_SELECT_DESCRIPTOR = ActionDescriptor(
    action_id=PROJECT_SELECT_ACTION_ID,
    module="project_gate",
    destructive=False,
    params_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    },
    prepare=_select_prepare,
    execute=_select_execute,
    compute_digest=_select_digest,
)


def _provider_login_prepare(params: dict, state: Any) -> dict:
    scopes = [str(scope) for scope in params.get("scopes", _DEFAULT_GH_SCOPES)]
    device = gh_device_init(scopes)
    if device is None:
        raise ApiError(500, "provider_login_failed", "Could not start GitHub device login")
    expires_at = time.monotonic() + int(device.get("expires_in", 900))
    session = {
        **device,
        "state": "code_issued",
        "scopes": scopes,
        "expires_at": expires_at,
    }
    state.provider_login_session = session
    code = device.get("user_code", "unknown")
    uri = device.get("verification_uri", "https://github.com/login/device")
    return {
        "summary": f"Authorize GitHub CLI access with device code {code}",
        "commands": [f"Open {uri}", f"Enter code {code}", "Store token in gh credentials"],
        "files_changed": [],
        "scopes": ["provider", "github", *scopes],
        "backup": None,
        "removals": [],
    }


def _provider_login_execute(_params: dict, state: Any) -> ActionOutcome:
    session = getattr(state, "provider_login_session", None)
    if not session:
        raise ApiError(410, "login_session_expired", "Prepare a new provider.login action to get a fresh code")

    def runner(handle) -> None:
        session["state"] = "polling"
        uri = session.get("verification_uri", "https://github.com/login/device")
        code = session.get("user_code", "unknown")
        handle.emit_line(f"Open {uri}")
        handle.emit_line(f"Enter code {code}")
        ok, token, message = gh_device_poll(
            str(session.get("device_code", "")),
            int(session.get("interval", 5)),
            float(session.get("expires_at", time.monotonic())),
            handle.is_cancelled,
        )
        if not ok:
            session["state"] = "expired" if "expired" in message else "idle"
            session["message"] = message
            handle.finish("cancelled" if message == "cancelled" else "failed", exit_detail=message)
            return
        stored, store_message = gh_accounts.add_account_with_token(token)
        session["state"] = "authenticated" if stored else "idle"
        session["message"] = store_message
        handle.emit_line(store_message)
        handle.finish("succeeded" if stored else "failed", exit_detail=None if stored else store_message)

    job = state.jobs.create("provider.login", runner=runner, exclusive_resource="provider:login")
    return ActionOutcome(job_id=job.job_id)


def _clone_target(params: dict) -> Path:
    return Path(params["destination"]).expanduser()


def _validate_clone_params(params: dict) -> tuple[str, Path]:
    repo = str(params["repo"]).strip()
    target = _clone_target(params)
    if "/" not in repo:
        raise ApiError(422, "params_invalid", "repo must be an owner/name slug")
    if target.exists():
        if not target.is_dir():
            raise ApiError(422, "params_invalid", f"{target} exists and is not a directory")
        if any(target.iterdir()):
            raise ApiError(422, "params_invalid", f"{target} already exists and is not empty")
    if not target.parent.is_dir():
        raise ApiError(422, "params_invalid", f"Destination parent does not exist: {target.parent}")
    return repo, target


def _provider_clone_prepare(params: dict, _state: Any) -> dict:
    repo, target = _validate_clone_params(params)
    return {
        "summary": f"Clone {repo} into {target}",
        "commands": [f"gh repo clone {repo} {target}"],
        "files_changed": [str(target)],
        "scopes": ["provider", "clone", repo],
        "backup": None,
        "removals": [],
    }


def _provider_clone_digest(params: dict, _state: Any) -> str:
    target = _clone_target(params)
    return compute_precondition_digest(
        {"repo": params["repo"], "destination": str(target), "target_state": _target_state(target), "accounts": _accounts_digest()}
    )


def _provider_clone_execute(params: dict, state: Any) -> ActionOutcome:
    repo, target = _validate_clone_params(params)
    switch_to_project = bool(params.get("switch_to_project", True))

    def runner(handle) -> None:
        if not shutil.which("gh"):
            handle.finish("failed", exit_detail="gh CLI not found")
            return
        handle.emit_line(f"Cloning {repo} into {target}...")
        proc = subprocess.Popen(
            ["gh", "repo", "clone", repo, str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        returncode = _finish_process(proc, handle)
        if handle.is_cancelled():
            handle.finish("cancelled")
            return
        if returncode != 0:
            handle.finish("failed", exit_detail=f"gh clone exited {returncode}")
            return
        if switch_to_project:
            _set_active_project(state, target, "open")
            handle.emit_line(f"Workspace switched to {target}.")
        handle.finish("succeeded")

    job = state.jobs.create(f"provider.clone:{repo}", runner=runner, exclusive_resource=f"provider:clone:{target}")
    return ActionOutcome(job_id=job.job_id)


def _provider_account(params: dict) -> tuple[str, str]:
    user = str(params["user"]).strip()
    host = str(params.get("host") or "github.com").strip()
    if not user:
        raise ApiError(422, "params_invalid", "user is required")
    account = next(
        (
            item
            for item in gh_accounts.list_accounts(host)
            if item.user == user and item.host == host
        ),
        None,
    )
    if account is None:
        raise ApiError(404, "account_not_found", f"GitHub account {user}@{host} was not found")
    return user, host


def _provider_switch_prepare(params: dict, _state: Any) -> dict:
    user, host = _provider_account(params)
    return {
        "summary": f"Make {user} the active GitHub account on {host}",
        "commands": [f"gh auth switch --hostname {host} --user {user}"],
        "files_changed": [],
        "scopes": ["provider", "account", host, user],
        "backup": None,
        "removals": [],
    }


def _provider_switch_execute(params: dict, _state: Any) -> ActionOutcome:
    user, host = _provider_account(params)
    ok, message = gh_accounts.switch_account(user, host)
    if not ok:
        raise ApiError(502, "provider_action_failed", message)
    return ActionOutcome(data={"message": message, "active_account": user})


def _provider_forget_prepare(params: dict, _state: Any) -> dict:
    user, host = _provider_account(params)
    return {
        "summary": f"Forget GitHub account {user} on {host}",
        "commands": [f"gh auth logout --hostname {host} --user {user}"],
        "files_changed": [],
        "scopes": ["provider", "account", host, user],
        "backup": "No backup; authenticate the account again to recover",
        "removals": [f"Stored GitHub credentials for {user}@{host}"],
    }


def _provider_forget_execute(params: dict, _state: Any) -> ActionOutcome:
    user, host = _provider_account(params)
    ok, message = gh_accounts.forget_account(user, host)
    if not ok:
        raise ApiError(502, "provider_action_failed", message)
    return ActionOutcome(data={"message": message, "forgotten_account": user})


def _init_prepare(params: dict, _state: Any) -> dict:
    selected_files = _normalize_selected_files(params.get("selected_files"))
    mcp_json = str(params.get("mcp_json", "")).strip()
    if mcp_json:
        try:
            parsed_mcp = json.loads(mcp_json)
        except json.JSONDecodeError as exc:
            raise ApiError(422, "params_invalid", f"mcp_json is not valid JSON: {exc}") from exc
        if not isinstance(parsed_mcp, dict):
            raise ApiError(422, "params_invalid", "mcp_json must be a JSON object")
    plan, _files = _build_init_plan(
        dest=str(params["dest"]),
        name=str(params["name"]),
        template=str(params["template"]),
        selected_files=selected_files,
    )
    if not plan["name_valid"]:
        raise ApiError(422, "params_invalid", str(plan["validation_message"]))
    if plan["selected_count"] == 0:
        raise ApiError(422, "params_invalid", "Select at least one staged file")
    selected = [row["rel_path"] for row in plan["staged_files"] if row["selected"]]
    changed = [plan["destination"], *selected[:30]]
    if mcp_json:
        changed.append(str(Path(plan["destination"]) / ".mcp.json"))
    return {
        "summary": f"Create {plan['name']} from {plan['template_attribution']}",
        "commands": ["write staged files", "write .claude/INIT_PROMPT.md", "run claude -p INIT_PROMPT.md"],
        "files_changed": changed,
        "scopes": ["init", "project", plan["template_source"]],
        "backup": None,
        "removals": [],
    }


def _init_execute(params: dict, state: Any) -> ActionOutcome:
    selected_files = _normalize_selected_files(params.get("selected_files"))
    run_claude = bool(params.get("run_claude", True))
    mcp_json = str(params.get("mcp_json", "")).strip()
    dest = str(params["dest"])
    name = str(params["name"])
    template = str(params["template"])

    def runner(handle) -> None:
        extract_dir: Path | None = None
        try:
            plan, _preview_files = _build_init_plan(
                dest=dest,
                name=name,
                template=template,
                selected_files=selected_files,
            )
            if not plan["name_valid"]:
                handle.finish("failed", exit_detail=str(plan["validation_message"]))
                return
            files, _attribution, extract_dir = _stage_template_files(template)
            for file in files:
                if selected_files is not None:
                    file.selected = str(file.dest_relpath) in selected_files
            target = Path(plan["destination"])
            handle.emit_line(f"Writing {plan['selected_count']} staged items to {target}...")
            report = apply_plan(target, files)
            if mcp_json:
                try:
                    parsed_mcp = json.loads(mcp_json)
                except json.JSONDecodeError as exc:
                    handle.finish("failed", exit_detail=f"mcp_json is not valid JSON: {exc}")
                    return
                if not isinstance(parsed_mcp, dict):
                    handle.finish("failed", exit_detail="mcp_json must be a JSON object")
                    return
                (target / ".mcp.json").write_text(json.dumps(parsed_mcp, indent=2) + "\n", encoding="utf-8")
                handle.emit_line("Wrote staged project MCP configuration.")
            added, tracked = ensure_mcp_gitignored(target)
            report.gitignore_added = added
            report.gitignore_already_tracked = tracked
            report.mcp_entries = count_project_mcp_entries(target)
            selected = [str(file.dest_relpath) for file in files if file.selected]
            agents = sorted(p.stem for p in (target / ".claude" / "agents").glob("*.md")) if (target / ".claude" / "agents").is_dir() else []
            skills = sorted(p.stem for p in (target / ".claude" / "skills").glob("*.md")) if (target / ".claude" / "skills").is_dir() else []
            commands = sorted(p.stem for p in (target / ".claude" / "commands").glob("*.md")) if (target / ".claude" / "commands").is_dir() else []
            prompt = build_init_prompt(target, str(plan["template_attribution"]), selected, agents, skills, commands)
            prompt_path = write_init_prompt(target, prompt)
            handle.emit_line(f"Wrote {report.files_written} files ({report.bytes_written} bytes).")
            handle.emit_line(f"Wrote handoff prompt {prompt_path}.")
            if report.gitignore_added:
                handle.emit_line("Added .mcp.json to .gitignore.")
            if report.gitignore_already_tracked:
                handle.emit_line(".mcp.json is already tracked; run git rm --cached .mcp.json later if needed.")
            if report.mcp_entries:
                handle.emit_line(f"Detected {report.mcp_entries} project MCP entries.")
            if run_claude and shutil.which("claude"):
                handle.emit_line("Starting claude handoff...")
                proc = spawn_claude(args=["-p", prompt], cwd=target)
                returncode = _finish_process(proc, handle)
                if handle.is_cancelled():
                    handle.finish("cancelled")
                    return
                if returncode != 0:
                    handle.emit_line(f"claude exited {returncode}; project files are still staged.")
            elif run_claude:
                handle.emit_line("claude CLI not found; skipping handoff.")
            _set_active_project(state, target, "init")
            handle.emit_line(f"Workspace switched to {target}.")
            handle.finish("succeeded")
        except Exception as exc:
            handle.finish("failed", exit_detail=str(exc))
        finally:
            if extract_dir is not None:
                shutil.rmtree(extract_dir, ignore_errors=True)

    target = Path(dest).expanduser() / name.strip()
    job = state.jobs.create(f"init.apply:{target.name}", runner=runner, exclusive_resource=f"init:{target}")
    return ActionOutcome(job_id=job.job_id)


PROVIDER_LOGIN_DESCRIPTOR = ActionDescriptor(
    action_id=PROVIDER_LOGIN_ACTION_ID,
    module="provider",
    destructive=False,
    params_schema={
        "type": "object",
        "properties": {"scopes": {"type": "array", "items": {"type": "string"}}},
        "additionalProperties": False,
    },
    prepare=_provider_login_prepare,
    execute=_provider_login_execute,
    compute_digest=lambda _params, _state: _accounts_digest(),
)

PROVIDER_CLONE_DESCRIPTOR = ActionDescriptor(
    action_id=PROVIDER_CLONE_ACTION_ID,
    module="provider",
    destructive=False,
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string"},
            "destination": {"type": "string"},
            "switch_to_project": {"type": "boolean"},
        },
        "required": ["repo", "destination"],
        "additionalProperties": False,
    },
    prepare=_provider_clone_prepare,
    execute=_provider_clone_execute,
    compute_digest=_provider_clone_digest,
)

_PROVIDER_ACCOUNT_SCHEMA = {
    "type": "object",
    "properties": {"user": {"type": "string"}, "host": {"type": "string"}},
    "required": ["user", "host"],
    "additionalProperties": False,
}

PROVIDER_SWITCH_DESCRIPTOR = ActionDescriptor(
    action_id=PROVIDER_SWITCH_ACTION_ID,
    module="provider",
    destructive=False,
    params_schema=_PROVIDER_ACCOUNT_SCHEMA,
    prepare=_provider_switch_prepare,
    execute=_provider_switch_execute,
    compute_digest=lambda _params, _state: _accounts_digest(),
)

PROVIDER_FORGET_DESCRIPTOR = ActionDescriptor(
    action_id=PROVIDER_FORGET_ACTION_ID,
    module="provider",
    destructive=True,
    params_schema=_PROVIDER_ACCOUNT_SCHEMA,
    prepare=_provider_forget_prepare,
    execute=_provider_forget_execute,
    compute_digest=lambda _params, _state: _accounts_digest(),
)

INIT_APPLY_DESCRIPTOR = ActionDescriptor(
    action_id=INIT_APPLY_ACTION_ID,
    module="init_wizard",
    destructive=False,
    params_schema={
        "type": "object",
        "properties": {
            "dest": {"type": "string"},
            "name": {"type": "string"},
            "template": {"type": "string"},
            "selected_files": {"type": "array", "items": {"type": "string"}},
            "run_claude": {"type": "boolean"},
            "mcp_json": {"type": "string"},
        },
        "required": ["dest", "name", "template"],
        "additionalProperties": False,
    },
    prepare=_init_prepare,
    execute=_init_execute,
    compute_digest=_init_digest,
)

PROJECT_LIFECYCLE_DESCRIPTORS = (
    PROVIDER_LOGIN_DESCRIPTOR,
    PROVIDER_SWITCH_DESCRIPTOR,
    PROVIDER_FORGET_DESCRIPTOR,
    PROVIDER_CLONE_DESCRIPTOR,
    INIT_APPLY_DESCRIPTOR,
)
