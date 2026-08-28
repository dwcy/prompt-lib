# -*- coding: utf-8 -*-
"""Knowledge export/doctor/index action descriptors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal.knowledge_rag_logic import bundle_root, index_path, prepare_index, resolve_repo_root
from cabal.okf.doctor import doctor_bundle, render_human
from cabal.okf.exporter import export_okf
from cabal.webapi.actions import ActionDescriptor, ActionOutcome, effect_preview
from cabal.webapi.knowledge_service import knowledge_digest

KNOWLEDGE_EXPORT_ACTION_ID = "knowledge.export"
KNOWLEDGE_DOCTOR_ACTION_ID = "knowledge.doctor"
KNOWLEDGE_INDEX_ACTION_ID = "knowledge.index"

_EMPTY_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

_INDEX_SCHEMA = {
    "type": "object",
    "properties": {"force": {"type": "boolean"}},
    "additionalProperties": False,
}


def _repo_root(state: Any) -> Path:
    project = getattr(state, "project", None)
    return resolve_repo_root(Path(project) if project is not None else None)


def _export_prepare(_params: dict, state: Any) -> dict:
    repo = _repo_root(state)
    return effect_preview(
        "Export the OKF knowledge bundle",
        commands=["python -m cabal.okf export --out docs/okf/prompt-lib"],
        files_changed=[str(bundle_root(repo))],
        scopes=["knowledge", "okf_bundle"],
    )


def _export_execute(_params: dict, state: Any) -> ActionOutcome:
    repo = _repo_root(state)

    def runner(handle) -> None:
        out_root = bundle_root(repo)
        handle.emit_line(f"Exporting OKF bundle to {out_root}...")
        result = export_okf(repo, out_root)
        handle.emit_line(f"Generated {result.document_count} documents.")
        handle.emit_line(f"Resolved {result.relation_count} graph relations.")
        handle.emit_line(f"Wrote {len(result.generated_files)} files.")
        handle.finish("succeeded")

    job = state.jobs.create("knowledge.export", runner=runner, exclusive_resource="knowledge:bundle")
    return ActionOutcome(job_id=job.job_id)


def _index_prepare(params: dict, state: Any) -> dict:
    repo = _repo_root(state)
    force = bool(params.get("force", False))
    return effect_preview(
        "Rebuild the OKF search index" if force else "Refresh the OKF search index",
        commands=["python -m cabal.okf index docs/okf/prompt-lib"],
        files_changed=[str(index_path(repo))],
        scopes=["knowledge", "okf_index"],
    )


def _doctor_prepare(_params: dict, state: Any) -> dict:
    repo = _repo_root(state)
    return effect_preview(
        "Validate the OKF knowledge bundle",
        commands=["python -m cabal.okf doctor docs/okf/prompt-lib"],
        scopes=["knowledge", "okf_bundle"],
    )


def _doctor_execute(_params: dict, state: Any) -> ActionOutcome:
    repo = _repo_root(state)

    def runner(handle) -> None:
        root = bundle_root(repo)
        handle.emit_line(f"Validating OKF bundle at {root}...")
        report = doctor_bundle(root, repo)
        for line in render_human(report).splitlines():
            handle.emit_line(line)
        handle.finish("succeeded" if report.ok else "failed")

    job = state.jobs.create("knowledge.doctor", runner=runner, exclusive_resource="knowledge:bundle")
    return ActionOutcome(job_id=job.job_id)


def _index_execute(params: dict, state: Any) -> ActionOutcome:
    repo = _repo_root(state)
    force = bool(params.get("force", False))

    def runner(handle) -> None:
        root = bundle_root(repo)
        db_path = index_path(repo)
        handle.emit_line(f"Preparing OKF index at {db_path}...")
        _path, message, rebuilt = prepare_index(repo, root, db_path, force=force)
        handle.emit_line(message)
        handle.emit_line("Index rebuilt." if rebuilt else "Index already current.")
        handle.finish("succeeded")

    job = state.jobs.create("knowledge.index", runner=runner, exclusive_resource="knowledge:index")
    return ActionOutcome(job_id=job.job_id)


KNOWLEDGE_EXPORT_DESCRIPTOR = ActionDescriptor(
    action_id=KNOWLEDGE_EXPORT_ACTION_ID,
    module="knowledge",
    destructive=False,
    params_schema=_EMPTY_SCHEMA,
    prepare=_export_prepare,
    execute=_export_execute,
    compute_digest=lambda _params, state: knowledge_digest(getattr(state, "project", None)),
)

KNOWLEDGE_INDEX_DESCRIPTOR = ActionDescriptor(
    action_id=KNOWLEDGE_INDEX_ACTION_ID,
    module="knowledge",
    destructive=False,
    params_schema=_INDEX_SCHEMA,
    prepare=_index_prepare,
    execute=_index_execute,
    compute_digest=lambda _params, state: knowledge_digest(getattr(state, "project", None)),
)

KNOWLEDGE_DOCTOR_DESCRIPTOR = ActionDescriptor(
    action_id=KNOWLEDGE_DOCTOR_ACTION_ID,
    module="knowledge",
    destructive=False,
    params_schema=_EMPTY_SCHEMA,
    prepare=_doctor_prepare,
    execute=_doctor_execute,
    compute_digest=lambda _params, state: knowledge_digest(getattr(state, "project", None)),
)

KNOWLEDGE_DESCRIPTORS = (
    KNOWLEDGE_EXPORT_DESCRIPTOR,
    KNOWLEDGE_DOCTOR_DESCRIPTOR,
    KNOWLEDGE_INDEX_DESCRIPTOR,
)
