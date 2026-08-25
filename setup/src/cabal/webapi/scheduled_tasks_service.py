"""Read and remove local scheduled tasks created by Claude Desktop and Codex."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_config_path

from cabal.webapi.envelope import ApiError, compute_precondition_digest

Provider = Literal["claude", "codex"]

CLAUDE_ROUTINES_URL = "https://claude.ai/code/routines"
CODEX_SCHEDULED_DOCS_URL = "https://learn.chatgpt.com/docs/automations"


def _default_claude_root() -> Path:
    override = os.environ.get("PROMPTLIB_CLAUDE_APP_DATA")
    if override:
        return Path(override).expanduser()
    return user_config_path("Claude", appauthor=False, roaming=True)


def _default_codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    return Path(override).expanduser() if override else Path.home() / ".codex"


_CLAUDE_ROOT: Path | None = None
_CODEX_HOME: Path | None = None


def _claude_root() -> Path:
    return _CLAUDE_ROOT or _default_claude_root()


def _codex_home() -> Path:
    return _CODEX_HOME or _default_codex_home()


@dataclass(frozen=True)
class ScheduledTaskRecord:
    provider: Provider
    provider_task_id: str
    name: str
    description: str
    prompt: str
    schedule: str
    schedule_kind: str
    status: str
    enabled: bool
    next_run_at: str | None
    last_run_at: str | None
    created_at: str | None
    updated_at: str | None
    workspace: str | None
    execution_environment: str | None
    model: str | None
    source: str
    source_paths: tuple[Path, ...]

    @property
    def composite_id(self) -> str:
        return f"{self.provider}:{self.provider_task_id}"

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.composite_id,
            "provider": self.provider,
            "provider_task_id": self.provider_task_id,
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "schedule": self.schedule,
            "schedule_kind": self.schedule_kind,
            "status": self.status,
            "enabled": self.enabled,
            "next_run_at": self.next_run_at,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "workspace": self.workspace,
            "execution_environment": self.execution_environment,
            "model": self.model,
            "source": self.source,
            "mirror_count": len(self.source_paths),
            "can_delete": True,
        }


def _as_text(value: object, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _timestamp(value: object) -> str | None:
    if isinstance(value, str):
        return value or None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    seconds = value / 1000 if value > 10_000_000_000 else value
    try:
        return datetime.fromtimestamp(seconds, UTC).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _claude_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory in ("claude-code-sessions", "local-agent-mode-sessions"):
        base = root / directory
        if base.is_dir():
            files.extend(base.glob("*/*/scheduled-tasks.json"))
    return sorted(path for path in files if path.is_file())


def _read_claude_file(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    tasks = raw.get("scheduledTasks") if isinstance(raw, dict) else None
    return [task for task in tasks if isinstance(task, dict)] if isinstance(tasks, list) else []


def _claude_status(task: dict[str, Any]) -> tuple[str, bool]:
    enabled = task.get("enabled") is True
    fire_at = task.get("fireAt")
    fire_time = _timestamp(fire_at)
    if not enabled and fire_time:
        try:
            if datetime.fromisoformat(fire_time) <= datetime.now(UTC):
                return "completed", False
        except ValueError:
            pass
    return ("active", True) if enabled else ("paused", False)


def _claude_record(task: dict[str, Any], paths: tuple[Path, ...]) -> ScheduledTaskRecord | None:
    task_id = _as_text(task.get("id"))
    if not task_id:
        return None
    status, enabled = _claude_status(task)
    fire_at = _timestamp(task.get("fireAt"))
    cron = _as_text(task.get("cronExpression"))
    name = _as_text(task.get("displayName")) or _as_text(task.get("name")) or task_id
    workspace = _as_text(task.get("cwd")) or None
    return ScheduledTaskRecord(
        provider="claude",
        provider_task_id=task_id,
        name=name,
        description=_as_text(task.get("description")),
        prompt=_as_text(task.get("prompt")),
        schedule=cron or fire_at or "Manual",
        schedule_kind="one_time" if fire_at else ("recurring" if cron else "manual"),
        status=status,
        enabled=enabled,
        next_run_at=_timestamp(task.get("nextRunAt")) or (fire_at if enabled else None),
        last_run_at=_timestamp(task.get("lastRunAt")),
        created_at=_timestamp(task.get("createdAt")),
        updated_at=_timestamp(task.get("updatedAt")),
        workspace=workspace,
        execution_environment="worktree" if task.get("useWorktree") is True else "local",
        model=_as_text(task.get("model")) or None,
        source="claude_desktop_local",
        source_paths=paths,
    )


def _list_claude_tasks(root: Path) -> list[ScheduledTaskRecord]:
    grouped: dict[str, list[tuple[dict[str, Any], Path]]] = {}
    for path in _claude_files(root):
        for task in _read_claude_file(path):
            task_id = _as_text(task.get("id"))
            if task_id:
                grouped.setdefault(task_id, []).append((task, path))

    records: list[ScheduledTaskRecord] = []
    for task_id, copies in grouped.items():
        copies.sort(
            key=lambda item: (_timestamp(item[0].get("updatedAt")) or "", item[1].stat().st_mtime_ns),
            reverse=True,
        )
        record = _claude_record(copies[0][0], tuple(item[1] for item in copies))
        if record is not None:
            records.append(record)
    return records


def _codex_cache_values(home: Path) -> dict[str, tuple[object, object]]:
    values: dict[str, tuple[object, object]] = {}
    for path in (home / "state_5.sqlite", home / "sqlite" / "state_5.sqlite"):
        if not path.is_file():
            continue
        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=1)
            has_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'automations'"
            ).fetchone()
            if has_table:
                for row in connection.execute("SELECT id, next_run_at, last_run_at FROM automations"):
                    values[str(row[0])] = (row[1], row[2])
            connection.close()
        except sqlite3.Error:
            continue
    return values


def _codex_record(path: Path, cache: dict[str, tuple[object, object]]) -> ScheduledTaskRecord | None:
    try:
        task = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return None
    task_id = _as_text(task.get("id"))
    if not task_id or path.parent.name != task_id:
        return None
    raw_status = _as_text(task.get("status"), "ACTIVE").upper()
    status = {"ACTIVE": "active", "PAUSED": "paused", "DISABLED": "paused"}.get(
        raw_status, raw_status.lower()
    )
    next_run, last_run = cache.get(task_id, (None, None))
    cwds = task.get("cwds")
    workspace = next((value for value in cwds if isinstance(value, str)), None) if isinstance(cwds, list) else None
    target = task.get("target")
    if workspace is None and isinstance(target, dict) and target.get("type") == "project":
        workspace = _as_text(target.get("project_id")) or None
    return ScheduledTaskRecord(
        provider="codex",
        provider_task_id=task_id,
        name=_as_text(task.get("name")) or task_id,
        description="",
        prompt=_as_text(task.get("prompt")),
        schedule=_as_text(task.get("rrule")) or "Manual",
        schedule_kind="thread" if task.get("kind") == "heartbeat" else "recurring",
        status=status,
        enabled=status == "active",
        next_run_at=_timestamp(next_run),
        last_run_at=_timestamp(last_run),
        created_at=_timestamp(task.get("created_at")),
        updated_at=_timestamp(task.get("updated_at")),
        workspace=workspace,
        execution_environment=_as_text(task.get("execution_environment")) or None,
        model=_as_text(task.get("model")) or None,
        source="codex_desktop_local",
        source_paths=(path,),
    )


def _list_codex_tasks(home: Path) -> list[ScheduledTaskRecord]:
    root = home / "automations"
    if not root.is_dir():
        return []
    cache = _codex_cache_values(home)
    records = [_codex_record(path, cache) for path in sorted(root.glob("*/automation.toml"))]
    return [record for record in records if record is not None and record.status != "deleted"]


def list_scheduled_tasks() -> list[ScheduledTaskRecord]:
    records = _list_claude_tasks(_claude_root()) + _list_codex_tasks(_codex_home())
    return sorted(records, key=lambda task: (task.updated_at or task.created_at or "", task.name), reverse=True)


def scheduled_tasks_payload() -> dict[str, Any]:
    claude_root = _claude_root()
    codex_home = _codex_home()
    tasks = list_scheduled_tasks()
    counts = {"all": len(tasks), "active": 0, "paused": 0, "completed": 0}
    for task in tasks:
        if task.status in counts:
            counts[task.status] += 1
    provider_counts = {provider: sum(task.provider == provider for task in tasks) for provider in ("claude", "codex")}
    return {
        "counts": counts,
        "items": [task.payload() for task in tasks],
        "providers": [
            {
                "provider": "claude",
                "label": "Claude Desktop",
                "detected": claude_root.is_dir(),
                "task_count": provider_counts["claude"],
                "source": "Local Desktop scheduled tasks",
                "detail": "Cloud Routines are managed separately on claude.ai.",
                "management_url": CLAUDE_ROUTINES_URL,
            },
            {
                "provider": "codex",
                "label": "Codex",
                "detected": codex_home.is_dir(),
                "task_count": provider_counts["codex"],
                "source": "$CODEX_HOME/automations",
                "detail": "Web-only ChatGPT tasks are managed separately in Scheduled.",
                "management_url": CODEX_SCHEDULED_DOCS_URL,
            },
        ],
    }


def find_scheduled_task(provider: str, task_id: str) -> ScheduledTaskRecord:
    if provider not in {"claude", "codex"}:
        raise ApiError(422, "params_invalid", f"Unknown scheduled-task provider {provider!r}")
    match = next(
        (task for task in list_scheduled_tasks() if task.provider == provider and task.provider_task_id == task_id),
        None,
    )
    if match is None:
        raise ApiError(404, "scheduled_task_not_found", f"Unknown {provider} scheduled task {task_id!r}")
    return match


def scheduled_task_digest(provider: str, task_id: str) -> str:
    task = find_scheduled_task(provider, task_id)
    sources = []
    for path in task.source_paths:
        try:
            stat = path.stat()
            sources.append((str(path), stat.st_mtime_ns, stat.st_size))
        except OSError:
            sources.append((str(path), "missing"))
    return compute_precondition_digest({"provider": provider, "task_id": task_id, "sources": sources})


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _atomic_json_write(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _delete_claude_task(task: ScheduledTaskRecord) -> dict[str, Any]:
    root = _claude_root()
    changed: list[str] = []
    for path in task.source_paths:
        if not _is_within(path, root):
            raise ApiError(409, "unsafe_task_path", "Claude task source escaped the expected app-data root")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ApiError(409, "task_store_unreadable", f"Could not read {path}") from exc
        scheduled = data.get("scheduledTasks") if isinstance(data, dict) else None
        if not isinstance(scheduled, list):
            continue
        filtered = [item for item in scheduled if not (isinstance(item, dict) and item.get("id") == task.provider_task_id)]
        if len(filtered) != len(scheduled):
            data["scheduledTasks"] = filtered
            _atomic_json_write(path, data)
            changed.append(str(path))
    if not changed:
        raise ApiError(404, "scheduled_task_not_found", f"Claude task {task.provider_task_id!r} disappeared")
    return {"provider": "claude", "task_id": task.provider_task_id, "removed_from": changed}


def _delete_codex_cache_rows(home: Path, task_id: str) -> None:
    for path in (home / "state_5.sqlite", home / "sqlite" / "state_5.sqlite"):
        if not path.is_file():
            continue
        try:
            connection = sqlite3.connect(path, timeout=2)
            has_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'automations'"
            ).fetchone()
            if has_table:
                connection.execute("DELETE FROM automations WHERE id = ?", (task_id,))
                connection.commit()
            connection.close()
        except sqlite3.Error as exc:
            raise ApiError(409, "task_store_busy", "Codex task state is busy; close Codex and retry") from exc


def _delete_codex_task(task: ScheduledTaskRecord) -> dict[str, Any]:
    home = _codex_home()
    root = home / "automations"
    directory = root / task.provider_task_id
    if directory.parent.resolve() != root.resolve() or not _is_within(directory, root):
        raise ApiError(409, "unsafe_task_path", "Codex automation path escaped $CODEX_HOME/automations")
    automation_file = directory / "automation.toml"
    if not automation_file.is_file():
        raise ApiError(404, "scheduled_task_not_found", f"Codex task {task.provider_task_id!r} disappeared")
    _delete_codex_cache_rows(home, task.provider_task_id)
    shutil.rmtree(directory)
    return {"provider": "codex", "task_id": task.provider_task_id, "removed": str(directory)}


def delete_scheduled_task(provider: str, task_id: str) -> dict[str, Any]:
    task = find_scheduled_task(provider, task_id)
    return _delete_claude_task(task) if task.provider == "claude" else _delete_codex_task(task)
