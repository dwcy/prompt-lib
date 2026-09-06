# -*- coding: utf-8 -*-
"""Stage bindings: which provider and model executes each pipeline stage.

Resolution order, most specific first:
  1. `<solution>/.dotnetgen/bindings.toml`  - per-project override
  2. `~/.claude/dotnetgen-bindings.toml`    - the deployed per-machine file
  3. `global/dotnetgen-bindings.toml`       - the in-repo source of truth

Names only. API keys are never stored here: a binding carries `api_key_env`, the *name* of an
environment variable, and the key is read at call time.

`verify` deliberately has no binding - it runs the .NET toolchain, not a model. That asymmetry
is the point: the verification signal costs nothing.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from cabal._paths import GLOBAL_DIR, TARGET

MODEL_STAGES: Final[tuple[str, ...]] = ("route", "architect", "write")
DEFAULT_RETRY_CEILING: Final[int] = 3
DEFAULT_MAP_TOKEN_BUDGET: Final[int] = 1024

REPO_BINDINGS_PATH: Final[Path] = GLOBAL_DIR / "dotnetgen-bindings.toml"
DEPLOYED_BINDINGS_PATH: Final[Path] = TARGET / "dotnetgen-bindings.toml"
PROJECT_BINDINGS_RELPATH: Final[str] = ".dotnetgen/bindings.toml"


class BindingsError(ValueError):
    """Raised when the bindings file is missing, malformed, or incomplete."""


@dataclass(frozen=True)
class StageBinding:
    """One stage's provider/model pair, plus an optional fallback used on provider failure."""

    stage: str
    provider: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    fallback: "StageBinding | None" = None

    @property
    def requires_api_key(self) -> bool:
        return self.api_key_env is not None

    def api_key(self) -> str | None:
        """Read the key from the environment at call time. Never cached, never persisted."""
        if self.api_key_env is None:
            return None
        return os.environ.get(self.api_key_env)

    def missing_key(self) -> bool:
        return self.requires_api_key and not self.api_key()


@dataclass(frozen=True)
class Bindings:
    """The resolved binding set for one project."""

    stages: dict[str, StageBinding]
    retry_ceiling: int = DEFAULT_RETRY_CEILING
    map_token_budget: int = DEFAULT_MAP_TOKEN_BUDGET
    source: Path | None = None

    def for_stage(self, stage: str) -> StageBinding:
        if stage not in self.stages:
            raise BindingsError(f"no binding for stage {stage!r}; expected one of {MODEL_STAGES}")
        return self.stages[stage]

    def stages_missing_keys(self) -> tuple[str, ...]:
        """Stages whose bound provider needs an API key that is not present in the environment."""
        return tuple(name for name, b in sorted(self.stages.items()) if b.missing_key())


def default_search_paths(project: Path | None = None) -> tuple[Path, ...]:
    paths: list[Path] = []
    if project is not None:
        paths.append(project / PROJECT_BINDINGS_RELPATH)
    paths.extend((DEPLOYED_BINDINGS_PATH, REPO_BINDINGS_PATH))
    return tuple(paths)


def _parse_binding(stage: str, table: dict) -> StageBinding:
    for field in ("provider", "model"):
        if not table.get(field):
            raise BindingsError(f"stage {stage!r} is missing {field!r}")

    fallback_table = table.get("fallback")
    fallback = None
    if isinstance(fallback_table, dict):
        fallback = _parse_binding(f"{stage}.fallback", fallback_table)

    return StageBinding(
        stage=stage,
        provider=table["provider"],
        model=table["model"],
        base_url=table.get("base_url"),
        api_key_env=table.get("api_key_env"),
        fallback=fallback,
    )


def parse_bindings(document: dict, source: Path | None = None) -> Bindings:
    """Turn a parsed TOML document into a validated `Bindings`."""
    stage_tables = document.get("stages")
    if not isinstance(stage_tables, dict):
        raise BindingsError("bindings file has no [stages] table")

    stages: dict[str, StageBinding] = {}
    for stage in MODEL_STAGES:
        table = stage_tables.get(stage)
        if not isinstance(table, dict):
            raise BindingsError(f"bindings file has no [stages.{stage}] table")
        stages[stage] = _parse_binding(stage, table)

    unknown = sorted(set(stage_tables) - set(MODEL_STAGES))
    if unknown:
        raise BindingsError(
            f"unknown stage table(s): {', '.join(unknown)}. "
            "`verify` takes no binding - it runs the .NET toolchain, not a model."
        )

    defaults = document.get("defaults", {})
    if not isinstance(defaults, dict):
        raise BindingsError("[defaults] must be a table")

    ceiling = defaults.get("retry_ceiling", DEFAULT_RETRY_CEILING)
    budget = defaults.get("map_token_budget", DEFAULT_MAP_TOKEN_BUDGET)
    if not isinstance(ceiling, int) or ceiling < 0:
        raise BindingsError(f"retry_ceiling must be a non-negative integer, got {ceiling!r}")
    if not isinstance(budget, int) or budget <= 0:
        raise BindingsError(f"map_token_budget must be a positive integer, got {budget!r}")

    return Bindings(stages=stages, retry_ceiling=ceiling, map_token_budget=budget, source=source)


def load_bindings(project: Path | None = None, search: tuple[Path, ...] | None = None) -> Bindings:
    """Load the first bindings file that exists, most specific first."""
    candidates = search if search is not None else default_search_paths(project)
    for path in candidates:
        if path.is_file():
            try:
                document = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as exc:
                raise BindingsError(f"{path} is not valid TOML: {exc}") from exc
            return parse_bindings(document, source=path)

    listed = "\n  ".join(str(p) for p in candidates)
    raise BindingsError(f"no bindings file found. Looked in:\n  {listed}")


def override_stage(bindings: Bindings, stage: str, binding: StageBinding) -> Bindings:
    """Return a copy with one stage rebound. Used by `--stage` overrides and by tests."""
    if stage not in MODEL_STAGES:
        raise BindingsError(f"cannot bind unknown stage {stage!r}")
    stages = dict(bindings.stages)
    stages[stage] = replace(binding, stage=stage)
    return replace(bindings, stages=stages)
