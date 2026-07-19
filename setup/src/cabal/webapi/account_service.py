# -*- coding: utf-8 -*-
"""Account, doctor, assistant-info, and model-assignment payloads for US4."""

from __future__ import annotations

import json
import platform
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cabal._paths import GLOBAL_DIR, TARGET
from cabal import config_doctor, model_assignments
from cabal.webapi.envelope import compute_precondition_digest

CLAUDE_JSON = Path.home() / ".claude.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _find_email(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("email", "login", "username"):
            candidate = value.get(key)
            if isinstance(candidate, str) and ("@" in candidate or key != "email"):
                return candidate
        for child in value.values():
            found = _find_email(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_email(child)
            if found:
                return found
    return None


def account_payload(claude_json: Path = CLAUDE_JSON) -> dict:
    raw = _read_json(claude_json)
    identity = _find_email(raw)
    return {
        "authenticated": claude_json.is_file(),
        "identity": identity or ("configured account" if claude_json.is_file() else None),
        "credential_sources": [
            {
                "label": "Claude account file",
                "path": str(claude_json),
                "present": claude_json.is_file(),
                "value_state": "present" if claude_json.is_file() else "missing",
            }
        ],
    }


def doctor_payload(project: Path | None, target: Path = TARGET) -> dict:
    findings, from_cache = config_doctor.run_doctor_cached(target=target, project=project)
    counts = {"error": 0, "warning": 0}
    for finding in findings:
        if finding.severity in counts:
            counts[finding.severity] += 1
    return {
        "findings": [asdict(finding) for finding in findings],
        "counts": counts,
        "from_cache": from_cache,
        "checked_target": str(target),
        "project": str(project) if project is not None else None,
    }


def _assignment_map(base_dir: Path) -> dict[tuple[str, str], str]:
    return {
        (assignment.kind, assignment.name): assignment.model
        for assignment in model_assignments.collect_model_assignments(base_dir)
    }


def models_payload(global_dir: Path = GLOBAL_DIR, target_dir: Path = TARGET) -> dict:
    target_models = _assignment_map(target_dir)
    assignments = []
    for assignment in model_assignments.collect_model_assignments(global_dir):
        target_model = target_models.get((assignment.kind, assignment.name))
        assignments.append(
            {
                "asset_kind": assignment.kind,
                "asset_name": assignment.name,
                "pinned_model": assignment.model,
                "resolved_to": model_assignments.resolves_to(assignment.model),
                "assignable_models": list(model_assignments.ASSIGNABLE_MODELS),
                "repo_and_target_in_sync": target_model in {None, assignment.model},
                "target_model": target_model,
                "valid": assignment.valid,
            }
        )
    return {
        "assignments": assignments,
        "assignable_models": list(model_assignments.ASSIGNABLE_MODELS),
        "counts": {
            "total": len(assignments),
            "invalid": sum(1 for row in assignments if not row["valid"]),
            "out_of_sync": sum(1 for row in assignments if not row["repo_and_target_in_sync"]),
        },
    }


def models_digest(kind: str, name: str, global_dir: Path = GLOBAL_DIR, target_dir: Path = TARGET) -> str:
    payload = models_payload(global_dir, target_dir)
    row = next(
        (
            item
            for item in payload["assignments"]
            if item["asset_kind"] == kind and item["asset_name"] == name
        ),
        None,
    )
    return compute_precondition_digest({"kind": kind, "name": name, "row": row})


def _document_summary(label: str, path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    preview = "\n".join(line for line in text.splitlines()[:8] if line.strip())
    return {
        "label": label,
        "path": str(path),
        "present": path.is_file(),
        "line_count": len(text.splitlines()) if text else 0,
        "preview": preview,
    }


def claude_info_payload(project: Path | None, global_dir: Path = GLOBAL_DIR, target: Path = TARGET) -> dict:
    documents = [
        _document_summary("Repo project instructions", Path.cwd() / "CLAUDE.md"),
        _document_summary("Repo global instructions", global_dir / "CLAUDE.md"),
        _document_summary("Deployed global instructions", target / "CLAUDE.md"),
    ]
    if project is not None:
        documents.append(_document_summary("Selected project instructions", project / "CLAUDE.md"))
    return {
        "documents": documents,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "project": str(project) if project is not None else None,
        },
    }
