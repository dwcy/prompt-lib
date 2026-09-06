# -*- coding: utf-8 -*-
"""End-to-end tests for `cabal.evals validate`: exit codes and error-line shape per contract."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from cabal.evals.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Shared helpers --------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )
    return result.stdout


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _task_toml(
    repo: Path,
    ref: str,
    *,
    rubrics: Sequence[str] = ("quality",),
    extra_lines: str = "",
) -> str:
    repo_str = str(repo).replace("\\", "/")
    rubrics_str = ", ".join(f'"{name}"' for name in rubrics)
    return (
        'title = "Sample task"\n'
        f'repo = "{repo_str}"\n'
        f'ref = "{ref}"\n'
        f"rubrics = [{rubrics_str}]\n"
        f"{extra_lines}"
        "\n[[checks]]\n"
        'kind = "test"\n'
        'cmd = ["python", "-c", "pass"]\n'
    )


def _split_error_line(line: str) -> tuple[str, str, str]:
    file_part, field_part, message_part = line.split(": ", 2)
    return file_part, field_part, message_part


@pytest.fixture(scope="module")
def sample_repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """A real git repo with one commit, referenced (read-only) by every task.toml under test."""
    repo = tmp_path_factory.mktemp("evals-validate-repo")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "evals-test@example.com")
    _git(repo, "config", "user.name", "Evals Test")
    _write(repo / "app.py", "value = 1\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-q", "-m", "initial commit")
    commit = _git(repo, "rev-parse", "HEAD").strip()
    return repo, commit


@pytest.fixture
def valid_tree(tmp_path: Path, sample_repo: tuple[Path, str]) -> Path:
    """One task, one rubric, two profiles, eval.config.toml -- the minimal tree that must pass."""
    repo, commit = sample_repo
    root = tmp_path / "evals"
    _write(root / "tasks" / "task-one" / "prompt.md", "Do the thing.\n")
    _write(root / "tasks" / "task-one" / "task.toml", _task_toml(repo, commit))
    _write(root / "rubrics" / "quality.md", "## Criteria\n- correctness\n")
    _write(
        root / "configs" / "baseline" / "profile.toml",
        'description = "baseline"\n\n[env]\nFOO = "bar"\n',
    )
    _write(
        root / "configs" / "candidate" / "profile.toml",
        'description = "candidate"\n\n[env]\nFOO = "baz"\n',
    )
    _write(root / "eval.config.toml", "runs_per_cell = 1\n")
    return root


# validate: a clean tree ------------------------------------------------------


class TestValidateGoodTree:
    def test_validate_minimal_valid_tree_exits_ok_with_one_line_summary(
        self, valid_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The documented happy path: one task/rubric, two profiles, one config -- must pass clean."""
        # Act
        exit_code = main(["validate", "--root", str(valid_tree)])

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_OK
        assert captured.out.strip() == (
            f"ok: 1 task(s), 2 profile(s), 1 rubric(s) validated under {valid_tree}"
        )


# validate: task.toml defects --------------------------------------------------


class TestValidateBadRef:
    def test_validate_unresolvable_ref_fails_and_names_ref_field(
        self, valid_tree: Path, sample_repo: tuple[Path, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A typo'd ref must be reported against task.toml's `ref` field, not a bare traceback."""
        # Arrange
        repo, _commit = sample_repo
        task_file = valid_tree / "tasks" / "task-one" / "task.toml"
        task_file.write_text(_task_toml(repo, "not-a-real-ref"), encoding="utf-8")

        # Act
        exit_code = main(["validate", "--root", str(valid_tree)])

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_FAILURE
        [error_line] = [line for line in captured.out.splitlines() if "task.toml" in line]
        file_part, field_part, _message = _split_error_line(error_line)
        assert file_part.endswith("task.toml")
        assert field_part == "ref"


class TestValidateMissingRubric:
    def test_validate_missing_rubric_reference_fails_and_names_rubrics_field(
        self, valid_tree: Path, sample_repo: tuple[Path, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A rubric name with no matching evals/rubrics/<name>.md must be reported by field."""
        # Arrange
        repo, commit = sample_repo
        task_file = valid_tree / "tasks" / "task-one" / "task.toml"
        task_file.write_text(
            _task_toml(repo, commit, rubrics=("does-not-exist",)), encoding="utf-8"
        )

        # Act
        exit_code = main(["validate", "--root", str(valid_tree)])

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_FAILURE
        [error_line] = [line for line in captured.out.splitlines() if "task.toml" in line]
        _file_part, field_part, _message = _split_error_line(error_line)
        assert field_part == "rubrics"


class TestValidateOutOfProfilePath:
    @pytest.mark.parametrize(
        "bad_path",
        [
            pytest.param("C:/outside/settings.json", id="absolute-path"),
            pytest.param("../outside/settings.json", id="dot-dot-traversal"),
        ],
    )
    def test_validate_profile_path_escaping_profile_dir_fails_and_names_field(
        self, valid_tree: Path, bad_path: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """profile.toml paths must stay inside their own directory -- no absolute paths, no ``..``."""
        # Arrange
        profile_file = valid_tree / "configs" / "baseline" / "profile.toml"
        profile_file.write_text(
            f'description = "baseline"\nsettings_file = "{bad_path}"\n', encoding="utf-8"
        )

        # Act
        exit_code = main(["validate", "--root", str(valid_tree)])

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_FAILURE
        [error_line] = [line for line in captured.out.splitlines() if "profile.toml" in line]
        _file_part, field_part, _message = _split_error_line(error_line)
        assert field_part == "settings_file"


class TestValidateEmptyPrompt:
    def test_validate_empty_prompt_file_fails(
        self, valid_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """prompt.md must be non-empty -- a blank file is as invalid as a missing one."""
        # Arrange
        (valid_tree / "tasks" / "task-one" / "prompt.md").write_text("", encoding="utf-8")

        # Act
        exit_code = main(["validate", "--root", str(valid_tree)])

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_FAILURE
        [error_line] = [line for line in captured.out.splitlines() if "task.toml" in line]
        _file_part, field_part, _message = _split_error_line(error_line)
        assert field_part == "prompt"


class TestValidateUnknownKey:
    def test_validate_unknown_task_toml_key_fails_and_names_the_key(
        self, valid_tree: Path, sample_repo: tuple[Path, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An unrecognized top-level key in task.toml must be reported by its own name."""
        # Arrange
        repo, commit = sample_repo
        task_file = valid_tree / "tasks" / "task-one" / "task.toml"
        task_file.write_text(
            _task_toml(repo, commit, extra_lines='bogus_key = "nope"\n'), encoding="utf-8"
        )

        # Act
        exit_code = main(["validate", "--root", str(valid_tree)])

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_FAILURE
        [error_line] = [line for line in captured.out.splitlines() if "task.toml" in line]
        _file_part, field_part, _message = _split_error_line(error_line)
        assert field_part == "bogus_key"


# validate: --tasks filter -----------------------------------------------------


class TestValidateTasksFilter:
    @pytest.fixture
    def tree_with_one_broken_task(
        self, valid_tree: Path, sample_repo: tuple[Path, str]
    ) -> Path:
        """A second task directory with an unresolvable ref, alongside the already-valid task-one."""
        repo, _commit = sample_repo
        _write(valid_tree / "tasks" / "task-two" / "prompt.md", "Do another thing.\n")
        _write(
            valid_tree / "tasks" / "task-two" / "task.toml",
            _task_toml(repo, "still-not-a-real-ref"),
        )
        return valid_tree

    def test_validate_tasks_filter_to_valid_task_skips_the_broken_one(
        self, tree_with_one_broken_task: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Filtering to the healthy task must pass even while an unfiltered sibling task is broken."""
        # Act
        exit_code = main(
            ["validate", "--root", str(tree_with_one_broken_task), "--tasks", "task-one"]
        )

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_OK
        assert "1 task(s)" in captured.out

    def test_validate_tasks_filter_with_unknown_id_is_a_usage_error(
        self, tree_with_one_broken_task: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An unrecognized --tasks id is a usage mistake (exit 2), distinct from a definition error."""
        # Act
        exit_code = main(
            ["validate", "--root", str(tree_with_one_broken_task), "--tasks", "unknown-id"]
        )

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_USAGE
        assert "unknown-id" in captured.err


# validate: the repo's own seeded evals/ tree ----------------------------------


class TestValidateRealSeededTree:
    def test_validate_repo_evals_tree_is_clean(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Regression guard: the seed data committed under evals/ must always pass its own rules."""
        # Act
        exit_code = main(["validate", "--root", str(_REPO_ROOT / "evals")])

        # Assert
        captured = capsys.readouterr()
        assert exit_code == EXIT_OK, captured.out + captured.err
