# -*- coding: utf-8 -*-
"""Contract-test guard: no assertion about the CLI surface may reach a real model."""

from __future__ import annotations

import json

import pytest


class _StubProvider:

    """Answers every stage from a canned reply. Never leaves the process."""

    name = "stub"

    def complete(self, request: object) -> object:
        from cabal.dotnetgen.providers.base import CompletionResult, Usage

        reply = json.dumps(
            {
                "summary": "Stubbed intent from the test provider.",
                "target_files": [],
                "target_symbols": [],
                "rationale": "",
            }
        )
        return CompletionResult(
            text=reply,
            usage=Usage(input_tokens=0, output_tokens=0),
            model="stub",
            provider=self.name,
        )


@pytest.fixture(autouse=True)
def _no_live_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may reach a real model.

    Before this, the parametrised CLI-surface tests invoked `plan` for real once it was wired -
    30 seconds and billed tokens per run, for assertions about argument parsing. Tests that want
    a specific reply override `factory.provider_for` themselves; this only sets the floor.
    """
    from cabal.dotnetgen.providers import factory

    monkeypatch.setattr(factory, "provider_for", lambda binding: _StubProvider())
