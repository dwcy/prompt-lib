# -*- coding: utf-8 -*-
"""Data model for the evals/ definition tree: dataclasses, error type, and documented defaults."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn

ID_PATTERN = re.compile(r"^[a-z0-9-]+$")

TASK_FILENAME = "task.toml"
PROMPT_FILENAME = "prompt.md"
PROFILE_FILENAME = "profile.toml"
CONFIG_FILENAME = "eval.config.toml"
TASKS_DIRNAME = "tasks"
CONFIGS_DIRNAME = "configs"
RUBRICS_DIRNAME = "rubrics"

DEFAULT_RUNS_PER_CELL = 3
DEFAULT_ADAPTER = "claude-code"
DEFAULT_RUN_TIMEOUT_SECONDS = 900
DEFAULT_CHECK_TIMEOUT_SECONDS = 300
DEFAULT_RESULTS_DIR = Path("evals/results")
DEFAULT_JUDGE_DIFF_CHAR_LIMIT = 20000

CheckKind = Literal["test", "build", "lint", "custom"]
CheckParser = Literal["pytest", "dotnet", "exit-code"]
CHECK_KINDS: tuple[CheckKind, ...] = ("test", "build", "lint", "custom")
CHECK_PARSERS: tuple[CheckParser, ...] = ("pytest", "dotnet", "exit-code")
DEFAULT_CHECK_PARSER: CheckParser = "exit-code"


class DefinitionError(ValueError):
    """A definition file failed validation. Carries the file and the field that caused it."""

    def __init__(self, message: str, *, file: Path, field: str) -> None:
        super().__init__(f"{file} [{field}]: {message}")
        self.file = file
        self.field = field


def fail(file: Path, field: str, message: str) -> NoReturn:
    raise DefinitionError(message, file=file, field=field)


@dataclass(frozen=True)
class CheckSpec:
    """One deterministic check declared by a task, executed with cwd = the run's worktree."""

    kind: str
    cmd: list[str]
    parser: str
    timeout_seconds: int


@dataclass(frozen=True)
class Task:
    """One benchmark unit: pinned repo state + verbatim prompt + checks + rubric names."""

    id: str
    title: str
    repo: Path
    ref: str
    prompt: str
    checks: list[CheckSpec]
    expected_files: list[str]
    rubrics: list[str]
    timeout_seconds: int | None
    skip_permissions: bool


@dataclass(frozen=True)
class ConfigProfile:
    """A named, reproducible agent-visible configuration; all paths resolved inside its directory."""

    name: str
    description: str
    user_overlay: Path | None
    project_overlay: Path | None
    settings_file: Path | None
    env: dict[str, str]


@dataclass(frozen=True)
class EvalConfig:
    """Harness defaults from eval.config.toml; every field has a documented default."""

    runs_per_cell: int
    adapter: str
    agent_model: str | None
    run_timeout_seconds: int
    check_timeout_seconds: int
    results_dir: Path
    judge_model: str | None
    judge_diff_char_limit: int
