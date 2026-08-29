# -*- coding: utf-8 -*-
"""Format-preserving read/write over the benchmark definition tree (`evals/`).

The user chose full GUI authoring (FR-050-FR-055) of a tree that is version-controlled
benchmark-as-code; the failure this module exists to prevent is the classic config-editor
one -- parse into a model, re-serialise, and silently drop the comments, key order, and
unmodelled fields a human wrote (research.md R6, `contracts/definition-roundtrip.md`).
Every save is validated first and refused -- nothing written -- on failure; a definition
this service cannot represent faithfully enough to guarantee round-trip fidelity opens
read-only instead of being silently normalised.
"""

from __future__ import annotations

from pathlib import Path

from cabal.webapi.run_supervisor import NotWiredError


def list_definitions(project: Path) -> list[dict]:
    """The benchmark tree: tasks, rubrics, config profiles.

    Each entry reports `editable` (false when the file cannot be represented faithfully,
    research.md R6) and `uncommitted` (FR-055). Implemented in T063 and T067.
    """
    raise NotWiredError("evals_definitions_service.list_definitions", "T063")


def validate_definitions(project: Path) -> dict:
    """Run the subsystem's own validator; each problem carries its file and enough
    locating detail to fix it on the first attempt (FR-030, SC-006).

    Implemented in T057.
    """
    raise NotWiredError("evals_definitions_service.validate_definitions", "T057")


def read_definition(project: Path, path: str) -> dict:
    """Load one definition file, preserving anything this service does not itself model.

    Implemented in T063.
    """
    raise NotWiredError("evals_definitions_service.read_definition", "T063")


def save_definition(project: Path, path: str, content: dict, *, expected_content_hash: str) -> dict:
    """Validate, then write atomically; refuses on a hash mismatch with
    `definition_changed_externally` rather than silently overwriting an external edit
    (FR-053). Round-trip guarantees G1-G4 in `contracts/definition-roundtrip.md` apply.

    Implemented in T065.
    """
    raise NotWiredError("evals_definitions_service.save_definition", "T065")


def delete_definition(project: Path, path: str) -> dict:
    """Delete a definition without breaking any stored run that referenced it -- a run
    is read against the manifest it recorded at launch, never the current tree (FR-054).

    Implemented in T066.
    """
    raise NotWiredError("evals_definitions_service.delete_definition", "T066")


def uncommitted_status(project: Path) -> dict:
    """Which definition files are uncommitted against the project's git tree (FR-055).

    Git operations stop at reporting status; committing stays the user's own workflow
    (`contracts/definition-roundtrip.md`). Implemented in T067.
    """
    raise NotWiredError("evals_definitions_service.uncommitted_status", "T067")
