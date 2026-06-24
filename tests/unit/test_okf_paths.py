from __future__ import annotations

from pathlib import Path

import pytest

from cabal.okf.paths import has_secret_value, normalize_resource, to_resource


def test_normalize_resource_uses_posix_paths() -> None:
    assert normalize_resource(r"global\agents\python-architect.md") == (
        "global/agents/python-architect.md"
    )


def test_normalize_resource_rejects_unsafe_paths() -> None:
    with pytest.raises(ValueError):
        normalize_resource("../secret.txt")


def test_to_resource_requires_path_under_root(tmp_path: Path) -> None:
    source = tmp_path / "global" / "agents" / "a.md"
    source.parent.mkdir(parents=True)
    source.write_text("# a", encoding="utf-8")

    assert to_resource(tmp_path, source) == "global/agents/a.md"


def test_secret_value_detection_catches_token_shapes() -> None:
    assert has_secret_value("OPENAI_API_KEY=sk-" + ("a" * 28))
    assert not has_secret_value("PROMPTLIB_DISABLED_HOOKS")
