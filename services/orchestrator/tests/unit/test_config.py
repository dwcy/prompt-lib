"""Unit tests for ``orchestrator.config.Config`` (T008).

Pins the env-var schema documented in ``research.md`` R8 and the validation
rules in ``data-model.md``. Per Constitution Principle III these tests land
BEFORE the implementation (T009); until then every test is expected to fail
with ``ImportError`` on ``orchestrator.config``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

REQUIRED_VARS: tuple[str, ...] = (
    "ORCHESTRATOR_REPO",
    "ORCHESTRATOR_NTFY_TOPIC",
    "A2A_BEARER_TOKEN",
)

OPTIONAL_VARS: tuple[str, ...] = (
    "ORCHESTRATOR_POLL_SECONDS",
    "ORCHESTRATOR_DB_PATH",
    "A2A_PEER_URL",
    "ORCHESTRATOR_NTFY_BASE",
)

ALL_VARS: tuple[str, ...] = REQUIRED_VARS + OPTIONAL_VARS


def _import_config() -> type:
    from orchestrator.config import Config

    return Config


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ALL_VARS:
        monkeypatch.delenv(name, raising=False)


def _set_minimal_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_REPO", "owner/repo")
    monkeypatch.setenv("ORCHESTRATOR_NTFY_TOPIC", "test-topic")
    monkeypatch.setenv("A2A_BEARER_TOKEN", "a-very-secret-bearer-token-1234567890")


# ---------------------------------------------------------------------------
# Required variables
# ---------------------------------------------------------------------------


class TestRequiredVarsMissing:
    @pytest.mark.parametrize("missing_var", REQUIRED_VARS)
    def test_construction_fails_when_required_var_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        missing_var: str,
    ) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.delenv(missing_var, raising=False)

        with pytest.raises(ValidationError):
            Config()


# ---------------------------------------------------------------------------
# ORCHESTRATOR_REPO slug regex
# ---------------------------------------------------------------------------


class TestRepoSlugValidation:
    @pytest.mark.parametrize(
        "invalid_repo",
        [
            "foo",
            "foo//bar",
            "/foo/bar",
            "",
            "foo bar/baz",
        ],
    )
    def test_invalid_repo_slug_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        invalid_repo: str,
    ) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.setenv("ORCHESTRATOR_REPO", invalid_repo)

        with pytest.raises(ValidationError):
            Config()

    @pytest.mark.parametrize(
        "valid_repo",
        [
            "owner/repo",
            "foo-bar/baz_qux.dot",
            "a/b",
        ],
    )
    def test_valid_repo_slug_accepted(
        self,
        monkeypatch: pytest.MonkeyPatch,
        valid_repo: str,
    ) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.setenv("ORCHESTRATOR_REPO", valid_repo)

        config = Config()

        assert config.orchestrator_repo == valid_repo


# ---------------------------------------------------------------------------
# A2A_BEARER_TOKEN
# ---------------------------------------------------------------------------


class TestBearerTokenValidation:
    def test_empty_bearer_token_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.setenv("A2A_BEARER_TOKEN", "")

        with pytest.raises(ValidationError):
            Config()


# ---------------------------------------------------------------------------
# ORCHESTRATOR_POLL_SECONDS
# ---------------------------------------------------------------------------


class TestPollSeconds:
    def test_defaults_to_30_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)

        config = Config()

        assert config.orchestrator_poll_seconds == 30

    @pytest.mark.parametrize("invalid_value", ["0", "-1", "-100"])
    def test_non_positive_values_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        invalid_value: str,
    ) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.setenv("ORCHESTRATOR_POLL_SECONDS", invalid_value)

        with pytest.raises(ValidationError):
            Config()

    @pytest.mark.parametrize("invalid_value", ["abc", "3.14", ""])
    def test_non_int_values_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        invalid_value: str,
    ) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.setenv("ORCHESTRATOR_POLL_SECONDS", invalid_value)

        with pytest.raises(ValidationError):
            Config()

    def test_positive_int_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.setenv("ORCHESTRATOR_POLL_SECONDS", "60")

        config = Config()

        assert config.orchestrator_poll_seconds == 60


# ---------------------------------------------------------------------------
# Optional defaults
# ---------------------------------------------------------------------------


class TestOptionalDefaults:
    def test_db_path_defaults_to_user_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)

        config = Config()

        expected = Path(os.path.expanduser("~/.claude/orchestrator/events.db"))
        assert Path(config.orchestrator_db_path) == expected

    def test_a2a_peer_url_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)

        config = Config()

        assert str(config.a2a_peer_url).rstrip("/") == "http://127.0.0.1:8765"

    def test_ntfy_base_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)

        config = Config()

        assert str(config.orchestrator_ntfy_base).rstrip("/") == "https://ntfy.sh"


class TestWorktreeEnabledFlag:
    def test_worktree_enabled_DefaultsToFalse_WhenEnvUnset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.delenv("ORCHESTRATOR_WORKTREE_ENABLED", raising=False)

        config = Config()

        assert config.orchestrator_worktree_enabled is False

    def test_worktree_enabled_IsTrue_WhenEnvSetToTrue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        Config = _import_config()
        _clear_env(monkeypatch)
        _set_minimal_required(monkeypatch)
        monkeypatch.setenv("ORCHESTRATOR_WORKTREE_ENABLED", "true")

        config = Config()

        assert config.orchestrator_worktree_enabled is True
