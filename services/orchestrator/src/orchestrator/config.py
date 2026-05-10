"""Environment-driven configuration for the orchestrator (T009).

Per research.md R8: read from process env via ``pydantic-settings`` only —
never from ``.env`` files. Each env var is validated at construction time so
that mis-configured deployments fail loudly on daemon startup rather than
mid-run.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_URL_RE = re.compile(r"^https?://[^\s]+$")


class Config(BaseSettings):
    """Process-environment configuration for the orchestrator daemon.

    All fields are sourced from environment variables matching the field name
    in upper-case (case-insensitive). No ``.env`` file is ever read.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    orchestrator_repo: str
    orchestrator_ntfy_topic: str
    a2a_bearer_token: str

    orchestrator_poll_seconds: int = 30
    orchestrator_db_path: Path = Path.home() / ".claude" / "orchestrator" / "events.db"
    a2a_peer_url: str = "http://127.0.0.1:8765"
    orchestrator_ntfy_base: str = "https://ntfy.sh"

    orchestrator_repo_path: Path = Path.cwd()
    orchestrator_worktree_root: Path = (
        Path.home() / ".claude" / "orchestrator" / "worktrees"
    )
    orchestrator_worktree_max_count: int = 20
    orchestrator_worktree_max_age_days: int = 14

    @field_validator("orchestrator_repo")
    @classmethod
    def _validate_repo_slug(cls, value: str) -> str:
        if not _REPO_SLUG_RE.match(value):
            raise ValueError(
                "ORCHESTRATOR_REPO must match '<owner>/<repo>' "
                "(letters, digits, '_', '.', '-')"
            )
        return value

    @field_validator("orchestrator_ntfy_topic")
    @classmethod
    def _validate_ntfy_topic(cls, value: str) -> str:
        if not value:
            raise ValueError("ORCHESTRATOR_NTFY_TOPIC must be non-empty")
        return value

    @field_validator("a2a_bearer_token")
    @classmethod
    def _validate_bearer_token(cls, value: str) -> str:
        if not value:
            raise ValueError("A2A_BEARER_TOKEN must be non-empty")
        return value

    @field_validator("orchestrator_poll_seconds")
    @classmethod
    def _validate_poll_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ORCHESTRATOR_POLL_SECONDS must be > 0")
        return value

    @field_validator("orchestrator_worktree_max_count")
    @classmethod
    def _validate_max_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("ORCHESTRATOR_WORKTREE_MAX_COUNT must be >= 0")
        return value

    @field_validator("orchestrator_worktree_max_age_days")
    @classmethod
    def _validate_max_age_days(cls, value: int) -> int:
        if value < 0:
            raise ValueError("ORCHESTRATOR_WORKTREE_MAX_AGE_DAYS must be >= 0")
        return value

    @field_validator("a2a_peer_url")
    @classmethod
    def _validate_peer_url(cls, value: str) -> str:
        if not _URL_RE.match(value):
            raise ValueError("A2A_PEER_URL must be an http(s) URL")
        return value

    @field_validator("orchestrator_ntfy_base")
    @classmethod
    def _validate_ntfy_base(cls, value: str) -> str:
        if not _URL_RE.match(value):
            raise ValueError("ORCHESTRATOR_NTFY_BASE must be an http(s) URL")
        return value
