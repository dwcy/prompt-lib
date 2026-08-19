"""Contract tests pinning evals/ definition file formats (task.toml, profile.toml, eval.config.toml)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cabal.evals.definitions import (
    CheckSpec,
    DefinitionError,
    load_eval_config,
    load_profile,
    load_task,
    validate_tree,
)

# Shared helpers ------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _toml_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _task_toml(repo: Path, ref: str, *, extra: str = "", checks: str | None = None) -> str:
    checks_block = (
        checks if checks is not None else '[[checks]]\nkind = "test"\ncmd = ["echo", "ok"]\n'
    )
    return (
        'title = "Sample task"\n'
        f'repo = "{_toml_path(repo)}"\n'
        f'ref = "{ref}"\n'
        f"{extra}"
        f"{checks_block}"
    )


def _make_task_dir(
    evals_root: Path, task_id: str, toml_body: str, *, prompt: str | None = "Do the thing.\n"
) -> Path:
    task_dir = evals_root / "tasks" / task_id
    _write(task_dir / "task.toml", toml_body)
    if prompt is not None:
        _write(task_dir / "prompt.md", prompt)
    return task_dir


def _profile_toml(*, description: str = "Baseline profile", body: str = "") -> str:
    return f'description = "{description}"\n{body}'


@pytest.fixture(scope="module")
def scratch_git_repo(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """Real git repo (no mocking) shared read-only across every ref-resolution test."""
    repo = tmp_path_factory.mktemp("scratch-repo")
    _git(repo, "init")
    _git(repo, "config", "user.email", "evals-test@example.com")
    _git(repo, "config", "user.name", "Evals Test")
    _write(repo / "README.md", "scratch\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial commit")
    commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "branch", "eval/task-base")
    return {"path": repo, "commit": commit, "ref": "eval/task-base"}


@pytest.fixture
def evals_root(tmp_path: Path) -> Path:
    root = tmp_path / "evals"
    root.mkdir()
    return root


# task.toml (rules 1, 2, 3, 4, 5, 6, 7) --------------------------------------


class TestLoadTaskValidDefinition:
    def test_load_task_with_full_valid_definition_returns_populated_task(
        self, evals_root: Path, scratch_git_repo: dict[str, object]
    ) -> None:
        """Rule 1: every documented field round-trips through a real git ref."""
        # Arrange
        _write(evals_root / "rubrics" / "architecture.md", "## Criteria\n- clarity\n")
        toml_body = _task_toml(
            scratch_git_repo["path"],
            scratch_git_repo["ref"],
            extra=(
                'expected_files = ["src/**"]\n'
                'rubrics = ["architecture"]\n'
                "timeout_seconds = 600\n"
                "skip_permissions = true\n"
            ),
        )
        task_dir = _make_task_dir(evals_root, "sample-task", toml_body, prompt="Add caching.\n")

        # Act
        task = load_task(task_dir)

        # Assert
        assert task.id == "sample-task"
        assert task.title == "Sample task"
        assert task.ref == scratch_git_repo["ref"]
        assert task.prompt == "Add caching.\n"
        assert task.expected_files == ["src/**"]
        assert task.rubrics == ["architecture"]
        assert task.timeout_seconds == 600
        assert task.skip_permissions is True
        assert task.checks == [
            CheckSpec(kind="test", cmd=["echo", "ok"], parser="exit-code", timeout_seconds=300)
        ]

    def test_load_task_with_ref_as_raw_commit_sha_resolves(
        self, evals_root: Path, scratch_git_repo: dict[str, object]
    ) -> None:
        """Rule 3 positive case: a bare commit sha is a valid commit-ish, not just a branch name."""
        # Arrange
        toml_body = _task_toml(scratch_git_repo["path"], scratch_git_repo["commit"])
        task_dir = _make_task_dir(evals_root, "sha-ref-task", toml_body)

        # Act
        task = load_task(task_dir)

        # Assert
        assert task.ref == scratch_git_repo["commit"]


_TASK_TOML_ERROR_CASES = [
    pytest.param("bad-key-task", None, "bogus_field = true\n", None, "bogus_field", id="rule1-unknown-key"),
    pytest.param("bad-ref-task", "does-not-exist-ref", "", None, "ref", id="rule3-unresolvable-ref"),
    pytest.param("no-checks-task", None, "", "", "checks", id="rule4-no-checks"),
    pytest.param(
        "empty-cmd-task",
        None,
        "",
        '[[checks]]\nkind = "test"\ncmd = []\n',
        "checks[0].cmd",
        id="rule4-empty-check-cmd",
    ),
    pytest.param(
        "missing-rubric-task", None, 'rubrics = ["nonexistent"]\n', None, "rubrics", id="rule5-missing-rubric"
    ),
    pytest.param("Bad_Task_Name", None, "", None, "id", id="rule7-invalid-directory-name"),
]


class TestLoadTaskValidationErrors:
    """Rules 1, 3, 4, 5, 7: each authoring mistake fails independently with the field that caused it."""

    @pytest.mark.parametrize(("task_id", "ref_override", "extra", "checks", "expected_field"), _TASK_TOML_ERROR_CASES)
    def test_load_task_toml_error_cases_raise_naming_file_and_field(
        self,
        evals_root: Path,
        scratch_git_repo: dict[str, object],
        task_id: str,
        ref_override: str | None,
        extra: str,
        checks: str | None,
        expected_field: str,
    ) -> None:
        """Each case is a distinct authoring mistake that must independently fail load_task with its own field."""
        # Arrange
        ref = ref_override or scratch_git_repo["ref"]
        toml_body = _task_toml(scratch_git_repo["path"], ref, extra=extra, checks=checks)
        task_dir = _make_task_dir(evals_root, task_id, toml_body)

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_task(task_dir)

        # Assert
        assert excinfo.value.file == task_dir / "task.toml"
        assert excinfo.value.field == expected_field

    def test_load_task_with_nonexistent_repo_raises_naming_field(self, evals_root: Path) -> None:
        """Rule 2: repo must exist before ref resolution is attempted."""
        # Arrange
        toml_body = _task_toml(Path("C:/does/not/exist-really"), "HEAD")
        task_dir = _make_task_dir(evals_root, "missing-repo-task", toml_body)

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_task(task_dir)

        # Assert
        assert excinfo.value.field == "repo"

    def test_load_task_with_non_git_repo_path_raises_naming_field(
        self, evals_root: Path, tmp_path: Path
    ) -> None:
        """Rule 2: an ordinary directory (no .git) is not a valid repo target."""
        # Arrange
        plain_dir = tmp_path / "not-a-repo"
        plain_dir.mkdir()
        toml_body = _task_toml(plain_dir, "HEAD")
        task_dir = _make_task_dir(evals_root, "non-git-task", toml_body)

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_task(task_dir)

        # Assert
        assert excinfo.value.field == "repo"

    @pytest.mark.parametrize("prompt", [None, ""], ids=["missing-prompt-file", "empty-prompt-file"])
    def test_load_task_with_missing_or_empty_prompt_raises_naming_field(
        self, evals_root: Path, scratch_git_repo: dict[str, object], prompt: str | None
    ) -> None:
        """Rule 6: prompt.md is the verbatim agent prompt -- absent or empty both mean no run is possible."""
        # Arrange
        toml_body = _task_toml(scratch_git_repo["path"], scratch_git_repo["ref"])
        task_dir = _make_task_dir(evals_root, "prompt-error-task", toml_body, prompt=prompt)

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_task(task_dir)

        # Assert
        assert excinfo.value.field == "prompt"


# configs/<name>/profile.toml (rule 8) ---------------------------------------


class TestLoadProfile:
    def test_load_profile_with_valid_definition_returns_populated_profile(
        self, evals_root: Path
    ) -> None:
        """Rule 8: overlay/settings/env fields all resolve relative to the profile's own directory."""
        # Arrange
        profile_dir = evals_root / "configs" / "baseline"
        _write(profile_dir / "user" / "CLAUDE.md", "# baseline\n")
        _write(profile_dir / "settings.json", "{}\n")
        toml_body = _profile_toml(
            body='user_overlay = "user"\nsettings_file = "settings.json"\n\n[env]\nFOO = "bar"\n'
        )
        _write(profile_dir / "profile.toml", toml_body)

        # Act
        profile = load_profile(profile_dir)

        # Assert
        assert profile.name == "baseline"
        assert profile.description == "Baseline profile"
        assert profile.user_overlay == profile_dir / "user"
        assert profile.settings_file == profile_dir / "settings.json"
        assert profile.env == {"FOO": "bar"}
        assert profile.project_overlay is None

    def test_load_profile_missing_description_raises_naming_field(self, evals_root: Path) -> None:
        """Rule 8: description is what makes an A/B result readable in the report -- never optional."""
        # Arrange
        profile_dir = evals_root / "configs" / "no-desc"
        _write(profile_dir / "user" / "CLAUDE.md", "# x\n")
        _write(profile_dir / "profile.toml", 'user_overlay = "user"\n')

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_profile(profile_dir)

        # Assert
        assert excinfo.value.field == "description"

    def test_load_profile_with_absolute_overlay_path_raises_naming_field(
        self, evals_root: Path, tmp_path: Path
    ) -> None:
        """Rule 8: an absolute path could point anywhere on disk, defeating profile confinement."""
        # Arrange
        profile_dir = evals_root / "configs" / "absolute-path"
        outside = tmp_path / "outside-overlay"
        outside.mkdir()
        toml_body = _profile_toml(body=f'user_overlay = "{_toml_path(outside)}"\n')
        _write(profile_dir / "profile.toml", toml_body)

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_profile(profile_dir)

        # Assert
        assert excinfo.value.field == "user_overlay"

    def test_load_profile_with_parent_traversal_path_raises_naming_field(
        self, evals_root: Path
    ) -> None:
        """Rule 8: `..` traversal is the sneaky sibling of an absolute-path escape."""
        # Arrange
        profile_dir = evals_root / "configs" / "traversal"
        _write(profile_dir / "profile.toml", _profile_toml(body='project_overlay = "../../escape"\n'))

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_profile(profile_dir)

        # Assert
        assert excinfo.value.field == "project_overlay"

    def test_load_profile_with_no_overlay_fields_raises_naming_file(self, evals_root: Path) -> None:
        """Rule 8: a profile with no overlay/settings/env source can never differ from baseline."""
        # Arrange
        profile_dir = evals_root / "configs" / "empty-profile"
        _write(profile_dir / "profile.toml", _profile_toml())

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_profile(profile_dir)

        # Assert
        assert excinfo.value.file == profile_dir / "profile.toml"

    def test_load_profile_with_invalid_directory_name_raises_naming_id_field(
        self, evals_root: Path
    ) -> None:
        """Rule: profile ids share the same `[a-z0-9-]+` directory-name pattern as task ids."""
        # Arrange
        profile_dir = evals_root / "configs" / "Bad Name"
        _write(profile_dir / "user" / "CLAUDE.md", "# x\n")
        _write(profile_dir / "profile.toml", _profile_toml(body='user_overlay = "user"\n'))

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_profile(profile_dir)

        # Assert
        assert excinfo.value.field == "id"


# eval.config.toml (rule 9) --------------------------------------------------


class TestLoadEvalConfig:
    def test_load_eval_config_applies_defaults_when_fields_omitted(self, tmp_path: Path) -> None:
        """Rule 9: an author who only sets `adapter` still gets the documented harness defaults."""
        # Arrange
        config_path = tmp_path / "eval.config.toml"
        _write(config_path, 'adapter = "claude-code"\n')

        # Act
        config = load_eval_config(config_path)

        # Assert
        assert config.runs_per_cell == 3
        assert config.run_timeout_seconds == 900
        assert config.check_timeout_seconds == 300
        assert config.results_dir == Path("evals/results")
        assert config.judge_model is None

    def test_load_eval_config_with_runs_per_cell_zero_raises_naming_field(
        self, tmp_path: Path
    ) -> None:
        """Rule 9: zero repetitions would make every statistic in the report undefined."""
        # Arrange
        config_path = tmp_path / "eval.config.toml"
        _write(config_path, "runs_per_cell = 0\n")

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_eval_config(config_path)

        # Assert
        assert excinfo.value.field == "runs_per_cell"

    def test_load_eval_config_with_judge_section_missing_model_raises_naming_field(
        self, tmp_path: Path
    ) -> None:
        """Rule 9: an opted-in `[judge]` table without a model can never produce a comparison."""
        # Arrange
        config_path = tmp_path / "eval.config.toml"
        _write(config_path, "[judge]\ndiff_char_limit = 5000\n")

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_eval_config(config_path)

        # Assert
        assert excinfo.value.field == "judge.model"

    def test_load_eval_config_with_judge_model_populates_judge_fields(self, tmp_path: Path) -> None:
        """Rule 9: a valid `[judge]` table both satisfies the model requirement and applies its own default."""
        # Arrange
        config_path = tmp_path / "eval.config.toml"
        _write(config_path, '[judge]\nmodel = "claude-haiku-4-5-20251001"\n')

        # Act
        config = load_eval_config(config_path)

        # Assert
        assert config.judge_model == "claude-haiku-4-5-20251001"
        assert config.judge_diff_char_limit == 20000

    def test_load_eval_config_accepts_unrecognized_adapter_name(self, tmp_path: Path) -> None:
        """Rule 9: adapter-name validity is the registry's job, not the definitions loader's."""
        # Arrange
        config_path = tmp_path / "eval.config.toml"
        _write(config_path, 'adapter = "not-yet-registered"\n')

        # Act
        config = load_eval_config(config_path)

        # Assert
        assert config.adapter == "not-yet-registered"

    def test_load_eval_config_with_unknown_key_raises_naming_field(self, tmp_path: Path) -> None:
        """Rule 1 (shared with task.toml): typo'd harness-level keys must be caught, too."""
        # Arrange
        config_path = tmp_path / "eval.config.toml"
        _write(config_path, "bogus_field = true\n")

        # Act
        with pytest.raises(DefinitionError) as excinfo:
            load_eval_config(config_path)

        # Assert
        assert excinfo.value.field == "bogus_field"


# validate_tree (whole-tree aggregate reporting) -----------------------------


class TestValidateTree:
    def test_validate_tree_on_fully_valid_tree_returns_no_errors(
        self, evals_root: Path, scratch_git_repo: dict[str, object]
    ) -> None:
        """The `validate` CLI's happy path: a correctly authored tree produces zero findings."""
        # Arrange
        _write(evals_root / "eval.config.toml", 'adapter = "claude-code"\n')
        _write(evals_root / "rubrics" / "architecture.md", "## Criteria\n- clarity\n")
        toml_body = _task_toml(
            scratch_git_repo["path"], scratch_git_repo["ref"], extra='rubrics = ["architecture"]\n'
        )
        _make_task_dir(evals_root, "good-task", toml_body)
        profile_dir = evals_root / "configs" / "baseline"
        _write(profile_dir / "user" / "CLAUDE.md", "# x\n")
        _write(profile_dir / "profile.toml", _profile_toml(body='user_overlay = "user"\n'))

        # Act
        errors = validate_tree(evals_root)

        # Assert
        assert errors == []

    def test_validate_tree_collects_errors_from_multiple_definitions_with_file_and_field(
        self, evals_root: Path, scratch_git_repo: dict[str, object]
    ) -> None:
        """Aggregate validation must report every problem across the tree in one pass, not just the first."""
        # Arrange
        _write(evals_root / "eval.config.toml", "runs_per_cell = 0\n")
        toml_body = _task_toml(scratch_git_repo["path"], "unresolvable-ref")
        _make_task_dir(evals_root, "broken-task", toml_body)

        # Act
        errors = validate_tree(evals_root)

        # Assert
        error_fields = {(Path(e.file).name, e.field) for e in errors}
        assert ("eval.config.toml", "runs_per_cell") in error_fields
        assert ("task.toml", "ref") in error_fields
