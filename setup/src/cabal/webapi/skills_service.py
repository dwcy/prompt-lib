# -*- coding: utf-8 -*-
"""Payload shaping for the Agent Setup module's Skills view: the inventory (what is installed,
where, which copy wins, whether it matches this repo's source) and one skill's full structure.
Read-only — every path comes from discovery, never from the request."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal._paths import GLOBAL_DIR, REPO_DIR, TARGET
from cabal.skill_catalog import (
    SkillRecord,
    SkillSource,
    count_bundled,
    discover_skills,
    iso_mtime,
    split_frontmatter,
)
from cabal.skill_structure import bundled_files, extract_references, parse_blocks
from cabal.webapi.envelope import ApiError

MAX_BODY_BYTES = 512 * 1024

# Same invocation defined twice: the narrower scope is the one Claude Code loads.
_SCOPE_PRECEDENCE = {"project": 0, "user": 1, "plugin": 2}

# Listing order, which is not the precedence order: the reader looks for their own skills first.
_DISPLAY_ORDER = {"user": 0, "project": 1, "plugin": 2}

DRIFT_IN_SYNC = "in_sync"
DRIFT_DIFFERS = "differs"
DRIFT_NOT_IN_REPO = "not_in_repo"
DRIFT_NOT_APPLICABLE = "not_applicable"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _normalised(text: str) -> str:
    """Compare content, not line endings — a checkout can hold CRLF where the source has LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _repo_source_for(record: SkillRecord) -> Path | None:
    if record.scope != "user" or record.kind != "skill":
        return None
    candidate = GLOBAL_DIR / "skills" / record.name / "SKILL.md"
    return candidate if candidate.is_file() else None


def _drift_for(record: SkillRecord) -> str:
    if record.scope != "user" or record.kind != "skill":
        return DRIFT_NOT_APPLICABLE
    source = _repo_source_for(record)
    if source is None:
        return DRIFT_NOT_IN_REPO
    return (
        DRIFT_IN_SYNC
        if _normalised(_read_text(source)) == _normalised(_read_text(record.path))
        else DRIFT_DIFFERS
    )


def _precedence(records: tuple[SkillRecord, ...]) -> dict[str, dict[str, Any]]:
    """Per record id: whether it is the copy that loads, and what else defines its invocation."""
    by_invocation: dict[str, list[SkillRecord]] = {}
    for record in records:
        by_invocation.setdefault(record.invocation, []).append(record)

    resolved: dict[str, dict[str, Any]] = {}
    for group in by_invocation.values():
        loadable = [record for record in group if record.loaded]
        others = {record.id: [item.id for item in group if item.id != record.id] for record in group}
        if len(loadable) <= 1:
            for record in group:
                resolved[record.id] = {
                    "precedence": "effective" if record.loaded else "not_loaded",
                    "duplicates": others[record.id],
                }
            continue
        ranked = sorted(loadable, key=lambda record: _SCOPE_PRECEDENCE.get(record.scope, 9))
        best = _SCOPE_PRECEDENCE.get(ranked[0].scope, 9)
        tied = [record for record in ranked if _SCOPE_PRECEDENCE.get(record.scope, 9) == best]
        winner_ids = {record.id for record in tied}
        for record in group:
            if not record.loaded:
                state = "not_loaded"
            elif record.id not in winner_ids:
                state = "shadowed"
            else:
                state = "ambiguous" if len(tied) > 1 else "effective"
            resolved[record.id] = {"precedence": state, "duplicates": others[record.id]}
    return resolved


def _counts(text: str) -> tuple[int, int]:
    lines = text.splitlines()
    headings = sum(1 for line in lines if line.startswith("#") and not line.startswith("#!"))
    return len(lines), headings


def _summary(record: SkillRecord, precedence: dict[str, Any]) -> dict[str, Any]:
    text = _read_text(record.path)
    line_count, heading_count = _counts(text)
    try:
        size_bytes: int | None = record.path.stat().st_size
    except OSError:
        size_bytes = None
    return {
        "id": record.id,
        "name": record.name,
        "invocation": record.invocation,
        "scope": record.scope,
        "kind": record.kind,
        "plugin": record.plugin,
        "marketplace": record.marketplace,
        "plugin_enabled": record.plugin_enabled,
        "description": record.description,
        "allowed_tools": list(record.allowed_tools),
        "model": record.model,
        "argument_hint": record.argument_hint,
        "path": str(record.path),
        "dir_path": str(record.dir_path) if record.dir_path is not None else None,
        "size_bytes": size_bytes,
        "line_count": line_count,
        "heading_count": heading_count,
        "modified_at": iso_mtime(record.path),
        "bundled_count": count_bundled(record.dir_path) if record.dir_path is not None else 0,
        "loaded": record.loaded,
        "not_loaded_reason": record.not_loaded_reason,
        "precedence": precedence["precedence"],
        "duplicates": precedence["duplicates"],
        "drift": _drift_for(record),
    }


def _source_payload(source: SkillSource) -> dict[str, Any]:
    return {
        "key": source.key,
        "label": source.label,
        "scope": source.scope,
        "path": str(source.path),
        "exists": source.exists,
        "count": source.count,
        "plugin_version": source.plugin_version,
        "plugin_enabled": source.plugin_enabled,
    }


def _unapplied_repo_skills(records: tuple[SkillRecord, ...]) -> list[dict[str, Any]]:
    """Skills this repo carries in global/skills that never reached ~/.claude/skills."""
    source_dir = GLOBAL_DIR / "skills"
    if not source_dir.is_dir():
        return []
    applied = {record.name for record in records if record.scope == "user" and record.kind == "skill"}
    missing: list[dict[str, Any]] = []
    for child in sorted(source_dir.iterdir(), key=lambda item: item.name.lower()):
        if child.is_dir() and (child / "SKILL.md").is_file() and child.name not in applied:
            missing.append({"name": child.name, "path": str(child / "SKILL.md")})
    return missing


def build_skill_inventory(
    project: Path | None,
    *,
    claude_home: Path = TARGET,
) -> dict[str, Any]:
    records, sources = discover_skills(project, claude_home=claude_home)
    precedence = _precedence(records)
    summaries = [_summary(record, precedence[record.id]) for record in records]
    summaries.sort(
        key=lambda item: (_DISPLAY_ORDER.get(str(item["scope"]), 9), str(item["name"]).lower())
    )

    scope_counts = {scope: 0 for scope in ("user", "project", "plugin")}
    for summary in summaries:
        scope_counts[summary["scope"]] = scope_counts.get(summary["scope"], 0) + 1

    return {
        "project_path": str(project) if project is not None else None,
        "claude_home": str(claude_home),
        "repo_skills_path": str(GLOBAL_DIR / "skills") if (GLOBAL_DIR / "skills").is_dir() else None,
        "counts": {
            "total": len(summaries),
            "loaded": sum(1 for item in summaries if item["loaded"]),
            "not_loaded": sum(1 for item in summaries if not item["loaded"]),
            "shadowed": sum(1 for item in summaries if item["precedence"] == "shadowed"),
            "ambiguous": sum(1 for item in summaries if item["precedence"] == "ambiguous"),
            "drifted": sum(1 for item in summaries if item["drift"] == DRIFT_DIFFERS),
            **scope_counts,
        },
        "sources": [_source_payload(source) for source in sources],
        "skills": summaries,
        "unapplied_repo_skills": _unapplied_repo_skills(records),
    }


def _known_agents(project: Path | None, claude_home: Path) -> list[str]:
    directories = [claude_home / "agents"]
    if project is not None:
        directories.append(project / ".claude" / "agents")
    names: list[str] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        names.extend(path.stem for path in directory.glob("*.md"))
    return names


def _locate(
    skill_id: str, project: Path | None, claude_home: Path
) -> tuple[SkillRecord, tuple[SkillRecord, ...]]:
    records, _ = discover_skills(project, claude_home=claude_home)
    for record in records:
        if record.id == skill_id:
            return record, records
    raise ApiError(404, "not_found", f"No installed skill matches {skill_id!r}")


def build_skill_detail(
    skill_id: str,
    project: Path | None,
    *,
    claude_home: Path = TARGET,
) -> dict[str, Any]:
    record, records = _locate(skill_id, project, claude_home)
    raw = _read_text(record.path)
    truncated = len(raw.encode("utf-8", errors="replace")) > MAX_BODY_BYTES
    if truncated:
        raw = raw.encode("utf-8", errors="replace")[:MAX_BODY_BYTES].decode("utf-8", errors="ignore")
    frontmatter_raw, body = split_frontmatter(raw)
    preamble, sections = parse_blocks(body)
    known_skills = {item.invocation: item.id for item in records if item.loaded}
    references = extract_references(
        body,
        self_invocation=record.invocation,
        known_skills=known_skills,
        known_agents=_known_agents(project, claude_home),
        path_roots=[path for path in (project, REPO_DIR) if path is not None],
    )
    repo_source = _repo_source_for(record)
    precedence = _precedence(records)[record.id]

    return {
        **_summary(record, precedence),
        "frontmatter_raw": frontmatter_raw.strip(),
        "frontmatter": {key: value for key, value in record.frontmatter.items()},
        "preamble": preamble,
        "sections": sections,
        "raw": raw,
        "truncated": truncated,
        "bundled_files": bundled_files(record.dir_path),
        "references": references,
        "repo_source_path": str(repo_source) if repo_source is not None else None,
    }


def read_skill_asset(
    skill_id: str,
    rel_path: str,
    project: Path | None,
    *,
    claude_home: Path = TARGET,
) -> dict[str, Any]:
    """One bundled file's text, resolved strictly inside the owning skill's folder."""
    record, _ = _locate(skill_id, project, claude_home)
    if record.dir_path is None:
        raise ApiError(404, "not_found", f"{record.invocation} is a single file — it bundles nothing")
    base = record.dir_path.resolve()
    target = (record.dir_path / rel_path).resolve()
    if target != base and not target.is_relative_to(base):
        raise ApiError(400, "path_outside_root", "Path escapes the skill folder")
    if not target.is_file():
        raise ApiError(404, "not_found", f"{rel_path} was not found in {record.invocation}")

    payload = target.read_bytes()
    sample = payload[:MAX_BODY_BYTES]
    binary = b"\x00" in sample[:8192]
    content: str | None = None
    if not binary:
        try:
            content = sample.decode("utf-8")
        except UnicodeDecodeError:
            binary = True
    return {
        "skill_id": skill_id,
        "rel_path": rel_path,
        "path": str(target),
        "content": content,
        "binary": binary,
        "truncated": len(payload) > MAX_BODY_BYTES,
        "size_bytes": len(payload),
    }
