from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cabal.webapi import scheduled_tasks_service as service


@pytest.fixture
def task_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    claude_root = tmp_path / "Claude"
    codex_home = tmp_path / ".codex"
    monkeypatch.setattr(service, "_CLAUDE_ROOT", claude_root)
    monkeypatch.setattr(service, "_CODEX_HOME", codex_home)
    return claude_root, codex_home


def _write_claude_store(root: Path, mode: str, tasks: list[dict]) -> Path:
    path = root / mode / "workspace" / "session" / "scheduled-tasks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "scheduledTasks": tasks,
                "recordedSkips": {},
                "sundayAliasBoundaryStamped": True,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_codex_task(home: Path, task_id: str = "daily-review") -> Path:
    path = home / "automations" / task_id / "automation.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "version = 1",
                f'id = "{task_id}"',
                'kind = "cron"',
                'name = "Daily review"',
                'prompt = "Review open pull requests"',
                'status = "ACTIVE"',
                'rrule = "RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0"',
                'execution_environment = "worktree"',
                'model = "gpt-5.6-terra"',
                'cwds = ["C:\\\\projects\\\\prompt-lib"]',
                "created_at = 1786500000000",
                "updated_at = 1786503600000",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_list_scheduled_tasks_combines_and_deduplicates_providers(task_stores) -> None:
    claude_root, codex_home = task_stores
    claude_task = {
        "id": "morning-check",
        "name": "Morning check",
        "prompt": "Check the deployment",
        "cronExpression": "0 9 * * 1-5",
        "enabled": True,
        "cwd": "C:\\projects\\prompt-lib",
        "createdAt": 1786500000000,
        "updatedAt": 1786503600000,
    }
    _write_claude_store(claude_root, "claude-code-sessions", [claude_task])
    _write_claude_store(claude_root, "local-agent-mode-sessions", [claude_task])
    _write_codex_task(codex_home)

    payload = service.scheduled_tasks_payload()

    assert payload["counts"] == {"all": 2, "active": 2, "paused": 0, "completed": 0}
    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id["claude:morning-check"]["mirror_count"] == 2
    assert by_id["claude:morning-check"]["workspace"] == "C:\\projects\\prompt-lib"
    assert by_id["codex:daily-review"]["execution_environment"] == "worktree"
    assert by_id["codex:daily-review"]["model"] == "gpt-5.6-terra"


def test_delete_claude_task_updates_every_mirror_and_preserves_other_tasks(task_stores) -> None:
    claude_root, _codex_home = task_stores
    doomed = {"id": "remove-me", "name": "Remove me", "enabled": False}
    keeper = {"id": "keep-me", "name": "Keep me", "enabled": True}
    paths = [
        _write_claude_store(claude_root, "claude-code-sessions", [doomed, keeper]),
        _write_claude_store(claude_root, "local-agent-mode-sessions", [doomed, keeper]),
    ]

    result = service.delete_scheduled_task("claude", "remove-me")

    assert len(result["removed_from"]) == 2
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert [item["id"] for item in data["scheduledTasks"]] == ["keep-me"]
        assert data["sundayAliasBoundaryStamped"] is True


def test_delete_codex_task_removes_directory_and_sqlite_cache_row(task_stores) -> None:
    _claude_root, codex_home = task_stores
    automation_file = _write_codex_task(codex_home)
    (automation_file.parent / "memory.md").write_text("remember this", encoding="utf-8")
    other_file = _write_codex_task(codex_home, "keep-me")
    database = codex_home / "state_5.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE automations (id TEXT PRIMARY KEY, next_run_at INTEGER, last_run_at INTEGER)"
    )
    connection.executemany(
        "INSERT INTO automations VALUES (?, ?, ?)",
        [("daily-review", 1786600000000, None), ("keep-me", 1786700000000, None)],
    )
    connection.commit()
    connection.close()

    service.delete_scheduled_task("codex", "daily-review")

    assert not automation_file.parent.exists()
    assert other_file.is_file()
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT id FROM automations ORDER BY id").fetchall() == [("keep-me",)]
    connection.close()


def test_codex_task_id_must_match_its_direct_parent(task_stores) -> None:
    _claude_root, codex_home = task_stores
    path = _write_codex_task(codex_home, "safe-id")
    path.write_text(path.read_text(encoding="utf-8").replace('id = "safe-id"', 'id = "../escape"'), encoding="utf-8")

    assert service.list_scheduled_tasks() == []
