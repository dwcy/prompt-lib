# -*- coding: utf-8 -*-
"""Shared fixtures for the dotnetgen test suite: repo paths, contract schemas, and a temp solution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_DIR = REPO_ROOT / "specs" / "018-dotnet-codegen"
CONTRACTS_DIR = SPEC_DIR / "contracts"


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
    """Directory holding the JSON Schemas that the contract tests validate against."""
    assert CONTRACTS_DIR.is_dir(), f"contracts directory missing: {CONTRACTS_DIR}"
    return CONTRACTS_DIR


@pytest.fixture(scope="session")
def edit_operation_schema(contracts_dir: Path) -> dict:
    return json.loads((contracts_dir / "edit-operation.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def run_record_schema(contracts_dir: Path) -> dict:
    return json.loads((contracts_dir / "run-record.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def solution_dir(tmp_path: Path) -> Path:
    """An empty directory standing in for a generated solution root."""
    root = tmp_path / "solution"
    root.mkdir()
    return root
