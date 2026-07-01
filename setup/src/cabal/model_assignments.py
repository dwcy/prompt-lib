# -*- coding: utf-8 -*-
"""Read and write per-agent/per-skill `model:` frontmatter assignments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cabal._paths import GLOBAL_DIR, TARGET
from cabal.okf.frontmatter import extract_frontmatter, parse_frontmatter

# Aliases Claude Code accepts in agent/skill frontmatter. `inherit` (or an absent
# `model:` line) means the session model is used.
VALID_MODEL_ALIASES = frozenset({"opus", "sonnet", "haiku", "fable", "inherit"})

# The values offered when assigning from the TUI, in display order.
ASSIGNABLE_MODELS = ("inherit", "opus", "sonnet", "haiku", "fable")

# Full model IDs currently served (aliases + active legacy), per the claude-api
# model catalog. Date-suffixed haiku is the one documented full ID.
KNOWN_MODEL_IDS = frozenset(
    {
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-opus-4-5",
        "claude-sonnet-4-6",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-haiku-4-5-20251001",
    }
)

_ALIAS_RESOLVES_TO = {
    "opus": "Opus 4.8",
    "sonnet": "Sonnet 4.6",
    "haiku": "Haiku 4.5",
    "fable": "Fable 5",
    "inherit": "session model",
}


@dataclass(frozen=True)
class ModelAssignment:
    kind: str  # "agent" | "skill"
    name: str
    model: str  # frontmatter value, or "inherit" when absent
    valid: bool


def resolves_to(model: str) -> str | None:
    """Friendly current-lineup name for an alias, or None for full IDs."""
    return _ALIAS_RESOLVES_TO.get(model)


def _read_model(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "inherit"
    frontmatter, _ = extract_frontmatter(text)
    if not frontmatter:
        return "inherit"
    value = parse_frontmatter(frontmatter).get("model")
    return str(value) if value else "inherit"


def _is_valid(model: str) -> bool:
    return model in VALID_MODEL_ALIASES or model in KNOWN_MODEL_IDS


def _skill_files(skills_dir: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    if not skills_dir.exists():
        return out
    for child in sorted(skills_dir.iterdir(), key=lambda p: p.name.lower()):
        if child.is_file() and child.suffix == ".md":
            out.append((child.stem, child))
        elif child.is_dir() and (child / "SKILL.md").is_file():
            out.append((child.name, child / "SKILL.md"))
    return out


def collect_model_assignments(
    global_dir: Path = GLOBAL_DIR,
) -> tuple[ModelAssignment, ...]:
    """One row per agent and skill under `global_dir`, with its model or `inherit`."""
    rows: list[ModelAssignment] = []
    agents_dir = global_dir / "agents"
    if agents_dir.exists():
        for path in sorted(agents_dir.glob("*.md"), key=lambda p: p.name.lower()):
            model = _read_model(path)
            rows.append(ModelAssignment("agent", path.stem, model, _is_valid(model)))
    for name, path in _skill_files(global_dir / "skills"):
        model = _read_model(path)
        rows.append(ModelAssignment("skill", name, model, _is_valid(model)))
    return tuple(rows)


def find_definition_path(kind: str, name: str, base_dir: Path) -> Path | None:
    """The definition file for an agent/skill under `base_dir`, or None."""
    if kind == "agent":
        p = base_dir / "agents" / f"{name}.md"
        return p if p.is_file() else None
    for candidate in (
        base_dir / "skills" / f"{name}.md",
        base_dir / "skills" / name / "SKILL.md",
    ):
        if candidate.is_file():
            return candidate
    return None


def _rewrite_model(text: str, model: str) -> str | None:
    """Return `text` with its frontmatter `model:` line set/removed, or None if no frontmatter."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    head = text[4:end]
    lines = [ln for ln in head.splitlines() if not ln.startswith("model:")]
    if model != "inherit":
        lines.append(f"model: {model}")
    return "---\n" + "\n".join(lines) + text[end:]


def set_model(
    kind: str,
    name: str,
    model: str,
    global_dir: Path = GLOBAL_DIR,
    target_dir: Path = TARGET,
) -> list[Path]:
    """Pin `model` on the agent/skill in the repo source AND the deployed copy.

    `inherit` removes the pin. Writes the repo file under `global_dir` (source of
    truth) and mirrors the change into the user's deployed `target_dir` copy when
    it exists, so the assignment takes effect without a full re-apply. Returns
    the files written; raises ValueError for unknown definitions or bad values.
    """
    if model not in VALID_MODEL_ALIASES and model not in KNOWN_MODEL_IDS:
        raise ValueError(f"unknown model value: {model!r}")
    written: list[Path] = []
    paths = [
        find_definition_path(kind, name, base) for base in (global_dir, target_dir)
    ]
    if paths[0] is None:
        raise ValueError(f"no {kind} named {name!r} under {global_dir}")
    for path in paths:
        if path is None:
            continue
        updated = _rewrite_model(path.read_text(encoding="utf-8"), model)
        if updated is None:
            raise ValueError(f"{path} has no frontmatter block")
        path.write_text(updated, encoding="utf-8", newline="\n")
        written.append(path)
    return written
