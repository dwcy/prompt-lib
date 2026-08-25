# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.worktree and cabal.evals.profile."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cabal.evals.definitions_model import ConfigProfile
from cabal.evals.profile import MaterializedProfile, cleanup, materialize, profiles_identical
from cabal.evals.worktree import WorktreeError, collect_diff, create_worktree, remove_worktree

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


def _make_profile(
    *,
    user_overlay: Path | None = None,
    project_overlay: Path | None = None,
    settings_file: Path | None = None,
    env: dict[str, str] | None = None,
) -> ConfigProfile:
    return ConfigProfile(
        name="test-profile",
        description="A profile for unit tests",
        user_overlay=user_overlay,
        project_overlay=project_overlay,
        settings_file=settings_file,
        env=dict(env or {}),
    )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A real git repo with one commit on its default branch, used as a worktree source."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "evals-test@example.com")
    _git(repo, "config", "user.name", "Evals Test")
    _write(repo / "tracked.txt", "original\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


# worktree.py: full lifecycle --------------------------------------------------


class TestWorktreeLifecycle:
    def test_create_mutate_collect_remove_reports_diff_and_leaves_no_trace(
        self, scratch_repo: Path, tmp_path: Path
    ) -> None:
        """Guards the create -> mutate -> diff -> remove pipeline the harness runs once per cell."""
        # Arrange
        dest = tmp_path / "wt"
        commit = _git(scratch_repo, "rev-parse", "HEAD").strip()
        worktree = create_worktree(scratch_repo, commit, dest)
        (worktree / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (worktree / "untracked.txt").write_text("new file\n", encoding="utf-8")

        # Act
        diff = collect_diff(worktree)

        # Assert
        assert "tracked.txt" in diff.patch_text
        assert "untracked.txt" in diff.patch_text
        assert set(diff.changed_files) == {"tracked.txt", "untracked.txt"}
        assert diff.insertions > 0
        assert diff.empty_diff is False

        # Act
        remove_worktree(scratch_repo, worktree)

        # Assert
        assert not worktree.exists()
        listing = _git(scratch_repo, "worktree", "list", "--porcelain")
        assert listing.count("worktree ") == 1

    def test_collect_diff_with_no_changes_reports_empty_diff(
        self, scratch_repo: Path, tmp_path: Path
    ) -> None:
        """A freshly checked-out worktree with no agent edits must never be misreported as changed."""
        # Arrange
        dest = tmp_path / "wt"
        worktree = create_worktree(scratch_repo, "HEAD", dest)

        # Act
        diff = collect_diff(worktree)

        # Assert
        assert diff.empty_diff is True
        assert diff.changed_files == ()

    def test_create_worktree_with_unresolvable_ref_raises_worktree_error_with_stderr(
        self, scratch_repo: Path, tmp_path: Path
    ) -> None:
        """A typo'd ref in task.toml must surface git's own diagnostic, not a bare traceback."""
        # Arrange
        dest = tmp_path / "wt"

        # Act
        with pytest.raises(WorktreeError) as excinfo:
            create_worktree(scratch_repo, "does-not-exist-ref", dest)

        # Assert
        assert "does-not-exist-ref" in str(excinfo.value)

    def test_remove_worktree_on_locked_worktree_falls_back_to_rmtree_and_prune(
        self, scratch_repo: Path, tmp_path: Path
    ) -> None:
        """When git itself refuses direct removal (locked worktree), the rmtree fallback must not raise.

        Note: `git worktree prune` intentionally skips locked worktrees even once their directory
        is gone (git safety behavior, verified against the real CLI) -- so `worktree list` still
        carries a stale, unlockable entry after this call. `remove_worktree` only guarantees the
        directory itself is reclaimed, which is what this test asserts.
        """
        # Arrange
        dest = tmp_path / "wt"
        worktree = create_worktree(scratch_repo, "HEAD", dest)
        _git(scratch_repo, "worktree", "lock", str(worktree))

        # Act
        remove_worktree(scratch_repo, worktree)

        # Assert
        assert not worktree.exists()

    def test_create_worktree_checks_out_detached_with_no_branch(
        self, scratch_repo: Path, tmp_path: Path
    ) -> None:
        """The harness must never create named branches per run (FR-015 / research.md R4)."""
        # Arrange
        dest = tmp_path / "wt"
        worktree = create_worktree(scratch_repo, "HEAD", dest)

        # Act
        branch = _git(worktree, "branch", "--show-current").strip()

        # Assert
        assert branch == ""
        with pytest.raises(subprocess.CalledProcessError):
            _git(worktree, "symbolic-ref", "HEAD")


# profile.py: materialize -------------------------------------------------------


class TestMaterialize:
    def test_materialize_copies_overlays_and_resolves_settings_and_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The scratch config dir and worktree must reflect exactly what the profile overlay declares."""
        # Arrange
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake-home-no-creds")
        user_overlay = tmp_path / "user-overlay"
        _write(user_overlay / "CLAUDE.md", "# user overlay\n")
        project_overlay = tmp_path / "project-overlay"
        _write(project_overlay / ".claude" / "settings.json", "{}\n")
        settings_file = _write(tmp_path / "settings.json", "{}\n")
        profile = _make_profile(
            user_overlay=user_overlay,
            project_overlay=project_overlay,
            settings_file=settings_file,
            env={"FOO": "bar"},
        )
        scratch = tmp_path / "scratch"
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        # Act
        materialized = materialize(profile, scratch, worktree)

        # Assert
        assert (materialized.config_dir / "CLAUDE.md").read_text(encoding="utf-8") == "# user overlay\n"
        assert (worktree / ".claude" / "settings.json").exists()
        assert materialized.settings_file == settings_file.resolve()
        assert materialized.env == {"FOO": "bar"}

    def test_materialize_copies_real_credentials_file_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Per research.md R2 (T010-resolved): without the credential copy every run fails 'Not logged in'."""
        # Arrange
        fake_home = tmp_path / "fake-home"
        _write(fake_home / ".claude" / ".credentials.json", '{"token": "abc"}')
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        profile = _make_profile()
        scratch = tmp_path / "scratch"
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        # Act
        materialized = materialize(profile, scratch, worktree)

        # Assert
        copied = materialized.config_dir / ".credentials.json"
        assert copied.read_text(encoding="utf-8") == '{"token": "abc"}'

    def test_materialize_succeeds_when_no_credentials_file_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A machine with no logged-in Claude CLI must not block materialization."""
        # Arrange
        fake_home = tmp_path / "fake-home-empty"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        profile = _make_profile()
        scratch = tmp_path / "scratch"
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        # Act
        materialized = materialize(profile, scratch, worktree)

        # Assert
        assert not (materialized.config_dir / ".credentials.json").exists()


# profile.py: cleanup ------------------------------------------------------------


class TestCleanup:
    def test_cleanup_removes_scratch_tree_including_credentials(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Credentials must never outlive the run they were copied in for."""
        # Arrange
        fake_home = tmp_path / "fake-home"
        _write(fake_home / ".claude" / ".credentials.json", "secret")
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        profile = _make_profile()
        scratch = tmp_path / "scratch"
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        materialize(profile, scratch, worktree)

        # Act
        result = cleanup(scratch)

        # Assert
        assert result is True
        assert not scratch.exists()

    def test_cleanup_called_twice_on_already_missing_dir_is_a_noop(self, tmp_path: Path) -> None:
        """A second cleanup call (e.g. after a retry) must never raise on an already-gone directory."""
        # Arrange
        scratch = tmp_path / "already-gone"

        # Act
        first = cleanup(scratch)
        second = cleanup(scratch)

        # Assert
        assert first is True
        assert second is True


# profile.py: profiles_identical --------------------------------------------------


class TestProfilesIdentical:
    def test_profiles_identical_returns_true_for_byte_identical_profiles(self, tmp_path: Path) -> None:
        """Backs the 'no-op comparison' warning: identical profiles must compare equal."""
        # Arrange
        config_dir_a = tmp_path / "a"
        _write(config_dir_a / "CLAUDE.md", "same content\n")
        config_dir_b = tmp_path / "b"
        _write(config_dir_b / "CLAUDE.md", "same content\n")
        a = MaterializedProfile(config_dir=config_dir_a, settings_file=None, env={"X": "1"})
        b = MaterializedProfile(config_dir=config_dir_b, settings_file=None, env={"X": "1"})

        # Act
        result = profiles_identical(a, b)

        # Assert
        assert result is True

    def test_profiles_identical_returns_false_after_one_byte_change(self, tmp_path: Path) -> None:
        """A single-byte drift in the overlay content must be enough to break equality."""
        # Arrange
        config_dir_a = tmp_path / "a"
        _write(config_dir_a / "CLAUDE.md", "same content\n")
        config_dir_b = tmp_path / "b"
        _write(config_dir_b / "CLAUDE.md", "sam3 content\n")
        a = MaterializedProfile(config_dir=config_dir_a, settings_file=None, env={})
        b = MaterializedProfile(config_dir=config_dir_b, settings_file=None, env={})

        # Act
        result = profiles_identical(a, b)

        # Assert
        assert result is False
