"""Integration tests for the InitProjectScreen flow (T085, US10).

Exercises the service-layer primitives (`apply_plan`, `ensure_mcp_gitignored`,
`count_project_mcp_entries`) and the INIT_PROMPT generator directly. The screen
itself is covered by source-inspection smoke checks since its DOM-coupled paths
require a mounted Textual app.
"""

from __future__ import annotations

import inspect
import json
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from cabal.init_project_service import (
    ApplyReport,
    InjectableFile,
    apply_plan,
    count_project_mcp_entries,
    ensure_mcp_gitignored,
)
from cabal.views.init_project import InitProjectScreen
from cabal.views.init_project_prompt import build_init_prompt, write_init_prompt


def _mk_injectable(
    source_path: Path,
    dest: str,
    origin: str = "github",
    selected: bool = True,
) -> InjectableFile:
    return InjectableFile(
        source_path=source_path,
        dest_relpath=PurePosixPath(dest),
        size_bytes=source_path.stat().st_size if source_path.is_file() else 0,
        selected=selected,
        status="NEW",
        origin=origin,
    )


# ------------------------------------------------------------------
# Group A — apply_plan service function
# ------------------------------------------------------------------


def test_apply_plan_writes_files_to_target(tmp_path, tmp_project_dir):
    src1 = tmp_path / "readme-src.md"
    src1.write_bytes(b"hello readme")
    src2 = tmp_path / "main-src.py"
    src2.write_bytes(b"print('hi')\n")
    f1 = _mk_injectable(src1, "README.md")
    f2 = _mk_injectable(src2, "src/main.py")

    report = apply_plan(tmp_project_dir, [f1, f2])

    assert (tmp_project_dir / "README.md").read_bytes() == b"hello readme"
    assert (tmp_project_dir / "src" / "main.py").read_bytes() == b"print('hi')\n"
    assert report.files_written == 2
    assert report.bytes_written == src1.stat().st_size + src2.stat().st_size


def test_apply_plan_skips_unselected(tmp_path, tmp_project_dir):
    src1 = tmp_path / "a.txt"
    src1.write_bytes(b"AAA")
    src2 = tmp_path / "b.txt"
    src2.write_bytes(b"BBB")
    f1 = _mk_injectable(src1, "a.txt", selected=True)
    f2 = _mk_injectable(src2, "b.txt", selected=False)

    report = apply_plan(tmp_project_dir, [f1, f2])

    assert (tmp_project_dir / "a.txt").exists()
    assert not (tmp_project_dir / "b.txt").exists()
    assert report.files_written == 1


def test_apply_plan_creates_parent_dirs(tmp_path, tmp_project_dir):
    src = tmp_path / "deep-src.txt"
    src.write_bytes(b"deep")
    inj = _mk_injectable(src, "a/b/c/deep.txt")

    apply_plan(tmp_project_dir, [inj])

    assert (tmp_project_dir / "a" / "b" / "c" / "deep.txt").read_bytes() == b"deep"


def test_apply_plan_scaffold_settings_local_json(tmp_project_dir):
    inj = InjectableFile(
        source_path=Path(""),
        dest_relpath=PurePosixPath(".claude/settings.local.json"),
        size_bytes=0,
        selected=True,
        status="NEW",
        origin="scaffold",
    )

    apply_plan(tmp_project_dir, [inj])

    dest = tmp_project_dir / ".claude" / "settings.local.json"
    assert dest.read_text(encoding="utf-8") == '{\n  "permissions": {\n    "allow": []\n  }\n}\n'


def test_apply_plan_scaffold_directory(tmp_project_dir):
    inj = InjectableFile(
        source_path=Path(""),
        dest_relpath=PurePosixPath(".claude/skills"),
        size_bytes=0,
        selected=True,
        status="NEW",
        origin="scaffold",
    )

    apply_plan(tmp_project_dir, [inj])

    dest = tmp_project_dir / ".claude" / "skills"
    assert dest.exists()
    assert dest.is_dir()


# ------------------------------------------------------------------
# Group B — ensure_mcp_gitignored
# ------------------------------------------------------------------


def test_ensure_mcp_gitignored_creates_when_absent(tmp_project_dir):
    added, tracked = ensure_mcp_gitignored(tmp_project_dir)

    assert (added, tracked) == (True, False)
    assert (tmp_project_dir / ".gitignore").read_text(encoding="utf-8") == ".mcp.json\n"


def test_ensure_mcp_gitignored_idempotent(tmp_project_dir):
    ensure_mcp_gitignored(tmp_project_dir)
    added, tracked = ensure_mcp_gitignored(tmp_project_dir)

    assert (added, tracked) == (False, False)
    body = (tmp_project_dir / ".gitignore").read_text(encoding="utf-8")
    matches = [ln for ln in body.splitlines() if re.match(r"^\.mcp\.json$", ln)]
    assert len(matches) == 1


def test_ensure_mcp_gitignored_appends_to_existing(tmp_project_dir):
    gi = tmp_project_dir / ".gitignore"
    gi.write_text("node_modules/\n", encoding="utf-8")

    added, tracked = ensure_mcp_gitignored(tmp_project_dir)

    body = gi.read_text(encoding="utf-8")
    assert added is True
    assert tracked is False
    assert "node_modules/" in body
    assert any(ln == ".mcp.json" for ln in body.splitlines())


def test_ensure_mcp_gitignored_does_not_duplicate(tmp_project_dir):
    gi = tmp_project_dir / ".gitignore"
    gi.write_text("node_modules/\n.mcp.json\n", encoding="utf-8")
    before = gi.read_text(encoding="utf-8")

    added, tracked = ensure_mcp_gitignored(tmp_project_dir)

    assert (added, tracked) == (False, False)
    assert gi.read_text(encoding="utf-8") == before


def test_ensure_mcp_gitignored_already_tracked_warning(tmp_project_dir):
    if not shutil.which("git"):
        pytest.skip("git not on PATH")
    subprocess.run(["git", "init"], cwd=tmp_project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=tmp_project_dir, check=True, capture_output=True,
    )
    (tmp_project_dir / ".mcp.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", ".mcp.json"], cwd=tmp_project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "add mcp"],
        cwd=tmp_project_dir, check=True, capture_output=True,
    )

    _added, tracked = ensure_mcp_gitignored(tmp_project_dir)

    assert tracked is True


# ------------------------------------------------------------------
# Group C — count_project_mcp_entries
# ------------------------------------------------------------------


def test_count_project_mcp_no_file_returns_zero(tmp_project_dir):
    assert count_project_mcp_entries(tmp_project_dir) == 0


def test_count_project_mcp_with_entries(tmp_project_dir):
    payload = {"mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}}}
    (tmp_project_dir / ".mcp.json").write_text(json.dumps(payload), encoding="utf-8")

    assert count_project_mcp_entries(tmp_project_dir) == 2


def test_count_project_mcp_corrupt_returns_zero(tmp_project_dir):
    (tmp_project_dir / ".mcp.json").write_text("garbage {", encoding="utf-8")

    assert count_project_mcp_entries(tmp_project_dir) == 0


# ------------------------------------------------------------------
# Group D — INIT_PROMPT.md generator
# ------------------------------------------------------------------


def test_build_init_prompt_contains_required_sections():
    target = Path("/tmp/demo")

    out = build_init_prompt(
        target_dir=target,
        template_attribution="local: python",
        files_written=["CLAUDE.md", ".claude/skills/foo.md"],
        agents=["python-architect"],
        skills=["plan"],
        commands=[],
    )

    assert "# Init Project Prompt" in out
    assert "local: python" in out
    assert "CLAUDE.md" in out
    assert "@python-architect" in out
    assert "/plan" in out
    assert "## Your task" in out
    assert str(target) in out


def test_write_init_prompt_creates_file(tmp_project_dir):
    out_path = write_init_prompt(tmp_project_dir, "hello")

    assert out_path == tmp_project_dir / ".claude" / "INIT_PROMPT.md"
    assert (tmp_project_dir / ".claude" / "INIT_PROMPT.md").read_text(encoding="utf-8") == "hello"


def test_build_init_prompt_no_agents_shows_placeholder():
    out = build_init_prompt(
        target_dir=Path("/tmp/demo"),
        template_attribution="local: python",
        files_written=[],
        agents=[],
        skills=[],
        commands=[],
    )

    assert "(none discovered" in out


# ------------------------------------------------------------------
# Group E — InitProjectScreen smoke source checks
# ------------------------------------------------------------------


def test_init_project_screen_has_apply_worker():
    src = inspect.getsource(InitProjectScreen)

    assert "_apply_worker" in src
    assert "ensure_mcp_gitignored" in src
    assert "write_init_prompt" in src
    assert "spawn_claude" in src
    assert "cancelled" in src


def test_init_project_screen_target_empty_check_accepts_only_mcp_json():
    src = inspect.getsource(inspect.getmodule(InitProjectScreen))

    assert "_target_is_empty_or_only_mcp_json" in src
    assert ".mcp.json" in src


def test_init_project_screen_no_token_leaks():
    src = inspect.getsource(inspect.getmodule(InitProjectScreen)).lower()

    assert "oauthtoken" not in src
    assert "accesstoken" not in src
    assert "apikey" not in src
    assert "sk-" not in src
