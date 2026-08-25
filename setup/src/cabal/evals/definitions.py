# -*- coding: utf-8 -*-
"""Loaders and whole-tree validation for the evals/ definition tree (public facade).

Every rule from `specs/019-agent-eval-harness/contracts/definitions-format.md` is enforced here;
each failure names the offending file and field so `validate` output is directly actionable.
Data model in `definitions_model.py`, low-level helpers in `definitions_support.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cabal.evals.definitions_model import (
    CONFIG_FILENAME,
    CONFIGS_DIRNAME,
    DEFAULT_ADAPTER,
    DEFAULT_CHECK_TIMEOUT_SECONDS,
    DEFAULT_JUDGE_DIFF_CHAR_LIMIT,
    DEFAULT_RESULTS_DIR,
    DEFAULT_RUN_TIMEOUT_SECONDS,
    DEFAULT_RUNS_PER_CELL,
    ID_PATTERN,
    PROFILE_FILENAME,
    PROMPT_FILENAME,
    RUBRICS_DIRNAME,
    TASK_FILENAME,
    TASKS_DIRNAME,
    CheckSpec,
    ConfigProfile,
    DefinitionError,
    EvalConfig,
    Task,
    fail,
)
from cabal.evals.definitions_support import (
    git_output,
    is_git_repo,
    load_toml,
    parse_checks,
    reject_unknown_keys,
    str_list,
)

__all__ = [
    "CheckSpec",
    "ConfigProfile",
    "DefinitionError",
    "EvalConfig",
    "Task",
    "load_eval_config",
    "load_profile",
    "load_task",
    "validate_tree",
]

_TASK_KEYS = frozenset(
    {"title", "repo", "ref", "expected_files", "rubrics", "timeout_seconds", "skip_permissions", "checks"}
)
_PROFILE_KEYS = frozenset({"description", "user_overlay", "project_overlay", "settings_file", "env"})
_PROFILE_PATH_KEYS = ("user_overlay", "project_overlay", "settings_file")
_CONFIG_KEYS = frozenset(
    {"runs_per_cell", "adapter", "agent_model", "run_timeout_seconds", "check_timeout_seconds", "results_dir", "judge"}
)
_JUDGE_KEYS = frozenset({"model", "diff_char_limit"})


def load_task(dir_path: Path) -> Task:
    """Load and validate one `evals/tasks/<id>/` directory into a Task."""
    dir_path = Path(dir_path)
    file = dir_path / TASK_FILENAME
    task_id = dir_path.name
    if not ID_PATTERN.fullmatch(task_id):
        fail(file, "id", f"task directory name must match {ID_PATTERN.pattern}")
    data = load_toml(file)
    reject_unknown_keys(data, _TASK_KEYS, file)
    for key in ("title", "repo", "ref"):
        if not isinstance(data.get(key), str) or not data[key]:
            fail(file, key, f"{key} is required and must be a non-empty string")

    repo = Path(data["repo"])
    if not repo.is_absolute():
        repo = dir_path.parents[2] / repo
    if not repo.is_dir() or not is_git_repo(repo):
        fail(file, "repo", f"not an existing git repository: {repo}")
    ref = data["ref"]
    if git_output(repo, "rev-parse", "--verify", f"{ref}^{{commit}}") is None:
        fail(file, "ref", f"ref does not resolve to a commit in {repo}: {ref}")

    checks = parse_checks(data.get("checks"), file)
    expected_files = str_list(data, "expected_files", file)
    rubrics = str_list(data, "rubrics", file)
    rubrics_dir = dir_path.parents[1] / RUBRICS_DIRNAME
    for name in rubrics:
        if not (rubrics_dir / f"{name}.md").is_file():
            fail(file, "rubrics", f"rubric not found: {rubrics_dir / (name + '.md')}")

    timeout = data.get("timeout_seconds")
    if timeout is not None and (not isinstance(timeout, int) or timeout < 1):
        fail(file, "timeout_seconds", "timeout_seconds must be a positive integer")
    skip_permissions = data.get("skip_permissions", False)
    if not isinstance(skip_permissions, bool):
        fail(file, "skip_permissions", "skip_permissions must be a boolean")

    prompt_file = dir_path / PROMPT_FILENAME
    prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""
    if not prompt.strip():
        fail(file, "prompt", f"{PROMPT_FILENAME} is missing or empty")

    return Task(
        id=task_id,
        title=data["title"],
        repo=repo,
        ref=ref,
        prompt=prompt,
        checks=checks,
        expected_files=expected_files,
        rubrics=rubrics,
        timeout_seconds=timeout,
        skip_permissions=skip_permissions,
    )


def load_profile(dir_path: Path) -> ConfigProfile:
    """Load and validate one `evals/configs/<name>/` directory into a ConfigProfile."""
    dir_path = Path(dir_path)
    file = dir_path / PROFILE_FILENAME
    name = dir_path.name
    if not ID_PATTERN.fullmatch(name):
        fail(file, "id", f"profile directory name must match {ID_PATTERN.pattern}")
    data = load_toml(file)
    reject_unknown_keys(data, _PROFILE_KEYS, file)
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        fail(file, "description", "description is required")

    resolved: dict[str, Path | None] = {}
    for key in _PROFILE_PATH_KEYS:
        raw = data.get(key)
        if raw is None:
            resolved[key] = None
            continue
        if not isinstance(raw, str) or not raw:
            fail(file, key, f"{key} must be a non-empty relative path")
        rel = Path(raw)
        if rel.anchor or ".." in rel.parts:
            fail(file, key, f"{key} must stay inside the profile directory (no absolute paths, no ..)")
        target = dir_path / rel
        if not target.exists():
            fail(file, key, f"{key} does not exist: {target}")
        resolved[key] = target

    env = data.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        fail(file, "env", "env must be a table of string values")

    if all(resolved[key] is None for key in _PROFILE_PATH_KEYS) and not env:
        fail(file, "profile", "at least one of user_overlay/project_overlay/settings_file/env is required")

    return ConfigProfile(
        name=name,
        description=description,
        user_overlay=resolved["user_overlay"],
        project_overlay=resolved["project_overlay"],
        settings_file=resolved["settings_file"],
        env=dict(env),
    )


def load_eval_config(path: Path) -> EvalConfig:
    """Load eval.config.toml, applying the documented harness defaults for omitted fields."""
    path = Path(path)
    data = load_toml(path)
    reject_unknown_keys(data, _CONFIG_KEYS, path)

    runs_per_cell = data.get("runs_per_cell", DEFAULT_RUNS_PER_CELL)
    if not isinstance(runs_per_cell, int) or runs_per_cell < 1:
        fail(path, "runs_per_cell", "runs_per_cell must be an integer >= 1")

    judge_model: str | None = None
    judge_diff_char_limit = DEFAULT_JUDGE_DIFF_CHAR_LIMIT
    judge = data.get("judge")
    if judge is not None:
        if not isinstance(judge, dict):
            fail(path, "judge", "[judge] must be a table")
        reject_unknown_keys(judge, _JUDGE_KEYS, path, "judge.")
        model = judge.get("model")
        if not isinstance(model, str) or not model:
            fail(path, "judge.model", "[judge] requires a model")
        judge_model = model
        limit = judge.get("diff_char_limit", DEFAULT_JUDGE_DIFF_CHAR_LIMIT)
        if not isinstance(limit, int) or limit < 1:
            fail(path, "judge.diff_char_limit", "diff_char_limit must be a positive integer")
        judge_diff_char_limit = limit

    return EvalConfig(
        runs_per_cell=runs_per_cell,
        adapter=str(data.get("adapter", DEFAULT_ADAPTER)),
        agent_model=data.get("agent_model"),
        run_timeout_seconds=int(data.get("run_timeout_seconds", DEFAULT_RUN_TIMEOUT_SECONDS)),
        check_timeout_seconds=int(data.get("check_timeout_seconds", DEFAULT_CHECK_TIMEOUT_SECONDS)),
        results_dir=Path(data.get("results_dir", DEFAULT_RESULTS_DIR)),
        judge_model=judge_model,
        judge_diff_char_limit=judge_diff_char_limit,
    )


def validate_tree(evals_root: Path, task_ids: Sequence[str] | None = None) -> list[DefinitionError]:
    """Validate every definition under evals_root, collecting all errors instead of stopping at the first.

    `task_ids` restricts which task directories are validated; config and profiles are always checked.
    """
    evals_root = Path(evals_root)
    errors: list[DefinitionError] = []

    def collect(loader: Any, target: Path) -> None:
        try:
            loader(target)
        except DefinitionError as exc:
            errors.append(exc)

    config_file = evals_root / CONFIG_FILENAME
    if config_file.is_file():
        collect(load_eval_config, config_file)
    tasks_dir = evals_root / TASKS_DIRNAME
    if tasks_dir.is_dir():
        for task_dir in sorted(child for child in tasks_dir.iterdir() if child.is_dir()):
            if task_ids is not None and task_dir.name not in task_ids:
                continue
            collect(load_task, task_dir)
    configs_dir = evals_root / CONFIGS_DIRNAME
    if configs_dir.is_dir():
        for profile_dir in sorted(child for child in configs_dir.iterdir() if child.is_dir()):
            collect(load_profile, profile_dir)
    return errors
