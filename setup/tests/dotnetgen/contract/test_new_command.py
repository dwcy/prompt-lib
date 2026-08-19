# -*- coding: utf-8 -*-
"""Contract test (T028) for the closed template set and the `new` command's refusal behaviour.

FR-001 makes the template set closed and FR-001c makes an unknown id an error rather than a
fallback. Both are protocol surfaces: the skill reads the refusal off stderr, and `state.json`
records the chosen id for the project's lifetime. The rule this pins is narrow and absolute -
**a request the tool cannot honour must never be silently converted into one it can.**

Written before T029 wires `new`. The refusal assertions pass from the registry and the argparse
surface; the "creates no files" and scaffold assertions fail until T029 exists, which is the
Gate 3 observation this file is here to make.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cabal.dotnetgen import cli, scaffold, state
from cabal.dotnetgen.templates import registry


def test_registry_is_the_single_source_of_the_closed_set() -> None:
    """cli and state must not carry their own copies - they did, and could drift."""
    assert cli.TEMPLATE_IDS is registry.TEMPLATE_IDS
    assert state.TEMPLATE_IDS is registry.TEMPLATE_IDS
    assert cli.DEFAULT_TEMPLATE in registry.TEMPLATE_IDS


def test_unknown_template_raises_and_never_falls_back() -> None:
    with pytest.raises(registry.UnknownTemplateError) as excinfo:
        registry.get("hexagonal")
    message = str(excinfo.value)
    for template_id in registry.TEMPLATE_IDS:
        assert template_id in message, "the refusal must name the whole closed set"
    assert registry.DEFAULT_TEMPLATE not in message.split("expected one of")[0], (
        "the default must appear only as a listed member, never as a substituted answer"
    )


def test_every_declared_template_names_the_task_that_builds_it() -> None:
    """Declared-but-unbuilt is explicit deferral; it must point at a task, not fail vaguely."""
    for template in registry.all_templates():
        assert template.built_in_task.startswith("T")
        if not template.is_built:
            with pytest.raises(registry.TemplateNotBuiltError) as excinfo:
                registry.require_built(template.id)
            assert template.built_in_task in str(excinfo.value)


def test_the_default_template_is_built() -> None:
    """Phase 3 ships a closed set of one built member; the default must be that member."""
    assert registry.get(registry.DEFAULT_TEMPLATE).is_built, (
        "the default template's files must exist - T024 builds them"
    )


def test_built_overlay_matches_the_declared_project_graph() -> None:
    """The registry declares the reference graph; the overlay's .csproj files ship it.

    Two sources for one fact, so they are asserted equal here. The graph feeds the structural
    map's layer ranking (research R3), so a template whose csproj disagrees with its declaration
    would mis-rank every file in every later `map` run.
    """
    for template in registry.all_templates():
        if not template.is_built:
            continue
        for project in template.project_layout:
            csproj = template.overlay_root / project.path / f"{project.name}.csproj"
            assert csproj.is_file(), f"{template.id}: overlay is missing {csproj.name}"
            text = csproj.read_text(encoding="utf-8")
            for reference in project.references:
                assert f"{reference}.csproj" in text, (
                    f"{template.id}/{project.name}.csproj must reference {reference}"
                )


def test_pruned_files_are_not_shipped_in_the_overlay() -> None:
    """Prune removes what `dotnet new` emits; shipping the same path would be contradictory."""
    for template in registry.all_templates():
        for relpath in template.prune:
            assert not (template.overlay_root / relpath).exists(), (
                f"{template.id}: {relpath} is both pruned and shipped"
            )


def test_overlay_never_offers_build_artifacts(tmp_path: Path) -> None:
    """`dotnet format` restores in place, so obj/ and bin/ appear in a working tree.

    They are gitignored and never reach a clone, but they would otherwise be copied into every
    generated solution as another machine's stale artifacts.
    """
    template = registry.get(registry.DEFAULT_TEMPLATE)
    stray = template.overlay_root / "src" / "Api" / "obj" / "Debug" / "stale.cs"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("// left behind by a local build\n", encoding="utf-8")
    try:
        listed = scaffold.plan(tmp_path / "svc", template.id).overlay_files
    finally:
        shutil.rmtree(template.overlay_root / "src" / "Api" / "obj")
    assert not [f for f in listed if "/obj/" in f or "/bin/" in f]


def test_unknown_template_exits_two_and_lists_the_closed_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["new", "--template", "hexagonal", "--description", "x"])
    assert excinfo.value.code == cli.EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == "", "a usage error must not pollute the --json channel"
    for template_id in registry.TEMPLATE_IDS:
        assert template_id in captured.err


def test_unknown_template_creates_no_files(tmp_path: Path) -> None:
    target = tmp_path / "service"
    target.mkdir()
    with pytest.raises(SystemExit):
        cli.main(["new", "--template", "hexagonal", "--description", "x", "--project", str(target)])
    assert list(target.iterdir()) == [], "a refused run must leave the target untouched"


def test_new_dry_run_plans_without_writing(
    solution_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--dry-run` reports the whole recipe and writes nothing - not even the state file.

    The real scaffold is asserted by the T036 integration test, which needs the .NET SDK and a
    package restore. This contract covers the shape the skill parses.
    """
    exit_code = cli.main(
        [
            "new",
            "--template",
            registry.DEFAULT_TEMPLATE,
            "--description",
            "an order service",
            "--project",
            str(solution_dir),
            "--dry-run",
            "--json",
        ]
    )
    assert exit_code == cli.EXIT_OK

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "planned"
    assert payload["template"] == registry.DEFAULT_TEMPLATE
    assert payload["scaffold_command"].startswith("dotnet new sln")
    assert payload["conventions_digest"].startswith("sha256:")
    assert [p["name"] for p in payload["projects"]] == [
        p.name for p in registry.get(registry.DEFAULT_TEMPLATE).project_layout
    ]
    assert list(solution_dir.iterdir()) == [], "a dry run must leave the target untouched"


def test_new_refuses_a_declared_but_unbuilt_template(solution_dir: Path) -> None:
    """An unbuilt member is a usage error naming its task, never a silent substitution."""
    unbuilt = next((t for t in registry.all_templates() if not t.is_built), None)
    if unbuilt is None:
        pytest.skip("every declared template is built - Phase 7b has landed")
    exit_code = cli.main(
        ["new", "--template", unbuilt.id, "--description", "x", "--project", str(solution_dir)]
    )
    assert exit_code == cli.EXIT_USAGE
    assert list(solution_dir.iterdir()) == []


def test_template_change_is_refused_naming_the_recorded_template(solution_dir: Path) -> None:
    created = state.create(solution_dir, "vertical-slice")
    with pytest.raises(state.TemplateLockError) as excinfo:
        state.save(solution_dir, replace_template(created, "clean-arch"))
    message = str(excinfo.value)
    assert "vertical-slice" in message, "the refusal must name what the project is locked to"
    assert "clean-arch" in message, "and what was refused"


def replace_template(current: state.ProjectState, template_id: str) -> state.ProjectState:
    from dataclasses import replace

    return replace(current, template_id=template_id)
