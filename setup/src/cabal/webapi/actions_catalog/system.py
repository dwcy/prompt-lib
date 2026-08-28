"""Cabal source-checkout update action."""

from __future__ import annotations

import subprocess

from cabal._paths import REPO_DIR
from cabal.updates import do_git_pull
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import compute_precondition_digest

_EMPTY_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def _revision() -> str:
    if REPO_DIR is None:
        return "no-repo"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _digest() -> str:
    return compute_precondition_digest({"repo": str(REPO_DIR), "revision": _revision()})


def _prepare(_params: dict, _state) -> dict:
    return {
        "summary": "Pull the latest Cabal revision",
        "commands": ["git pull"],
        "files_changed": [str(REPO_DIR)] if REPO_DIR is not None else [],
        "scopes": ["system", "cabal"],
        "backup": "Git history retains the previous revision",
        "removals": [],
    }


def _execute(_params: dict, state) -> ActionOutcome:
    def runner(handle) -> None:
        handle.emit_line("Pulling the latest Cabal revision...")
        ok, output = do_git_pull()
        for line in output.splitlines():
            handle.emit_line(line)
        handle.finish("succeeded" if ok else "failed", exit_detail=None if ok else output)

    job = state.jobs.create("system.update", runner=runner, exclusive_resource="system:cabal-update")
    return ActionOutcome(job_id=job.job_id)


SYSTEM_UPDATE_DESCRIPTOR = ActionDescriptor(
    action_id="system.update",
    module="home_overview",
    destructive=False,
    params_schema=_EMPTY_SCHEMA,
    prepare=_prepare,
    execute=_execute,
    compute_digest=lambda _params, _state: _digest(),
)
