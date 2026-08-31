# -*- coding: utf-8 -*-
"""The degradation matrix every provider must satisfy, plus the Azure link ladder.

One row per condition in contracts/env-sources.contract.md: absent CLI, unauthenticated CLI,
missing credential, timeout, empty provider. None of them may raise, and none may return a
state that reads like a different problem than the one that occurred.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal import envsource_azure_link
from cabal import envsource_azure_service as azure
from cabal import envsource_github_service as github
from cabal import envsource_vercel_service as vercel
from cabal.models.envsources import AvailabilityState, LinkConfidence, Retrievability


def _states(sources) -> list[AvailabilityState]:
    return [source.state for source in sources]


# -- GitHub --------------------------------------------------------------


@pytest.fixture
def github_repo(monkeypatch):
    monkeypatch.setattr(github, "_owner_repo", lambda _project: "dwcy/prompt-lib")


def test_github_without_the_cli_is_degraded_and_names_the_missing_tool(
    tmp_path, monkeypatch, github_repo
) -> None:
    monkeypatch.setattr(github.shutil, "which", lambda _name: None)

    (source,) = github.collect_github(tmp_path)

    assert source.state is AvailabilityState.DEGRADED
    assert "not installed" in source.hint


def test_github_unauthenticated_is_degraded_and_says_sign_in_is_required(
    tmp_path, monkeypatch, github_repo
) -> None:
    monkeypatch.setattr(github.shutil, "which", lambda _name: "gh")
    monkeypatch.setattr(github, "_api", lambda _path: (1, "gh: To get started with GitHub CLI, please run: gh auth login"))

    (source,) = github.collect_github(tmp_path)

    assert source.state is AvailabilityState.DEGRADED
    assert "sign-in is required" in source.hint


def test_github_with_nothing_configured_is_empty_not_broken(
    tmp_path, monkeypatch, github_repo
) -> None:
    monkeypatch.setattr(github.shutil, "which", lambda _name: "gh")
    monkeypatch.setattr(github, "_api", lambda _path: (0, json.dumps({"variables": [], "secrets": [], "environments": []})))

    (source,) = github.collect_github(tmp_path)

    assert source.state is AvailabilityState.EMPTY
    assert source.hint is None


def test_a_project_with_no_github_origin_contributes_no_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(github, "_owner_repo", lambda _project: None)

    assert github.collect_github(tmp_path) == []


def test_a_timed_out_gh_call_names_the_timeout(tmp_path, monkeypatch, github_repo) -> None:
    monkeypatch.setattr(github.shutil, "which", lambda _name: "gh")
    monkeypatch.setattr(github, "_api", lambda _path: (1, github._HINT_TIMEOUT.format(timeout=8)))

    (source,) = github.collect_github(tmp_path)

    assert source.state is AvailabilityState.DEGRADED
    assert "did not answer within" in source.hint


def test_every_github_secret_is_never_and_every_variable_is_readable(
    tmp_path, monkeypatch, github_repo
) -> None:
    monkeypatch.setattr(github.shutil, "which", lambda _name: "gh")

    def api(path: str):
        if "secrets" in path:
            return 0, json.dumps({"secrets": [{"name": "DEPLOY_KEY", "updated_at": "2026-01-01T00:00:00Z"}]})
        if "environments" in path:
            return 0, json.dumps({"environments": []})
        return 0, json.dumps({"variables": [{"name": "REGION", "updated_at": "2026-01-01T00:00:00Z"}]})

    monkeypatch.setattr(github, "_api", api)
    (source,) = github.collect_github(tmp_path)
    entries = {entry.name: entry for container in source.containers for entry in container.entries}

    assert entries["DEPLOY_KEY"].retrievability is Retrievability.NEVER
    assert "never returns" in entries["DEPLOY_KEY"].retrievability_reason
    assert entries["REGION"].retrievability is Retrievability.READABLE
    assert entries["REGION"].retrievability_reason is None


def test_a_reveal_on_a_github_secret_makes_no_network_call(tmp_path, monkeypatch) -> None:
    from cabal.webapi import envsources_service

    calls: list[str] = []
    monkeypatch.setattr(github, "_api", lambda path: calls.append(path) or (0, "{}"))

    result = envsources_service.reveal(tmp_path, "github", "github:repository:secrets", "DEPLOY_KEY")

    assert result.status == "unavailable"
    assert result.value is None
    assert calls == []


# -- Azure link ladder ---------------------------------------------------


def test_each_link_signal_wins_in_its_documented_order(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(azure, "_machine_subscription", lambda: "sub-machine")
    explicit = envsource_azure_link.save_link(
        tmp_path, "sub-explicit", "rg-explicit", path=tmp_path / "links.json"
    )
    (tmp_path / "azure.yaml").write_text("name: app\n", encoding="utf-8")
    infra = tmp_path / "infra"
    infra.mkdir()
    (infra / "main.bicep").write_text("// infra", encoding="utf-8")

    assert azure.detect_link(tmp_path, explicit)[0] is LinkConfidence.EXPLICIT
    assert azure.detect_link(tmp_path)[0] is LinkConfidence.AZD
    (tmp_path / "azure.yaml").unlink()
    assert azure.detect_link(tmp_path)[0] is LinkConfidence.IAC
    (infra / "main.bicep").unlink()
    assert azure.detect_link(tmp_path)[0] is LinkConfidence.MACHINE_DEFAULT


def test_a_machine_default_is_never_presented_as_a_project_link(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(azure, "_machine_subscription", lambda: "sub-machine")

    confidence, reason, subscription, _group = azure.detect_link(tmp_path)

    assert confidence is LinkConfidence.MACHINE_DEFAULT
    assert "not a link to this project" in reason
    assert subscription == "sub-machine"


def test_a_project_with_no_signal_and_no_sign_in_contributes_no_azure_source(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(azure, "_machine_subscription", lambda: None)

    assert azure.collect_azure(tmp_path) == []


def test_the_explicit_link_survives_a_reload_and_clearing_restores_detection(tmp_path) -> None:
    store = tmp_path / "links.json"
    envsource_azure_link.save_link(tmp_path, "sub-1", "rg-1", path=store)

    reloaded = envsource_azure_link.load_link(tmp_path, path=store)
    assert reloaded.subscription_id == "sub-1"
    assert reloaded.is_explicit is True
    assert reloaded.confidence is LinkConfidence.EXPLICIT

    assert envsource_azure_link.clear_link(tmp_path, path=store) is True
    assert envsource_azure_link.load_link(tmp_path, path=store) is None
    assert envsource_azure_link.clear_link(tmp_path, path=store) is False


# -- Azure collector -----------------------------------------------------


@pytest.fixture
def azure_linked(monkeypatch):
    monkeypatch.setattr(azure, "_machine_subscription", lambda: "sub-machine")


def test_azure_without_the_cli_is_degraded_and_names_the_missing_tool(
    tmp_path, monkeypatch, azure_linked
) -> None:
    monkeypatch.setattr(azure.shutil, "which", lambda _name: None)

    sources = azure.collect_azure(tmp_path)

    assert _states(sources) == [AvailabilityState.DEGRADED]
    assert "not installed" in sources[0].hint


def test_azure_not_signed_in_says_so(tmp_path, monkeypatch, azure_linked) -> None:
    monkeypatch.setattr(azure.shutil, "which", lambda _name: "az")
    monkeypatch.setattr(azure, "_az", lambda _args: (1, "Please run 'az login' to setup account."))

    sources = azure.collect_azure(tmp_path)

    assert all(source.state is AvailabilityState.DEGRADED for source in sources)
    assert all("sign-in is required" in source.hint for source in sources)


def test_a_subscription_with_no_vaults_is_empty(tmp_path, monkeypatch, azure_linked) -> None:
    monkeypatch.setattr(azure.shutil, "which", lambda _name: "az")
    monkeypatch.setattr(azure, "_az", lambda _args: (0, "[]"))

    vault, app = azure.collect_azure(tmp_path)

    assert vault.state is AvailabilityState.EMPTY
    assert app.state is AvailabilityState.EMPTY
    assert vault.link_confidence is LinkConfidence.MACHINE_DEFAULT


def test_an_azure_timeout_names_the_timeout(tmp_path, monkeypatch, azure_linked) -> None:
    monkeypatch.setattr(azure.shutil, "which", lambda _name: "az")
    monkeypatch.setattr(azure, "_az", lambda _args: (1, azure._HINT_TIMEOUT.format(timeout=15)))

    sources = azure.collect_azure(tmp_path)

    assert all("did not answer within" in source.hint for source in sources)


def test_vault_secrets_are_permission_gated_and_keyvault_references_are_marked(
    tmp_path, monkeypatch, azure_linked
) -> None:
    monkeypatch.setattr(azure.shutil, "which", lambda _name: "az")

    def run(args: list[str]):
        if args[:2] == ["keyvault", "list"]:
            return 0, json.dumps([{"name": "kv-prod"}])
        if args[:3] == ["keyvault", "secret", "list"]:
            return 0, json.dumps([{"name": "DbPassword", "attributes": {"updated": "2026-01-01T00:00:00Z"}}])
        if args[:2] == ["webapp", "list"]:
            return 0, json.dumps([{"name": "api", "resourceGroup": "rg-prod"}])
        return 0, json.dumps(
            [
                {"name": "PLAIN", "value": "literal"},
                {"name": "REF", "value": "@Microsoft.KeyVault(SecretUri=https://kv/x)"},
            ]
        )

    monkeypatch.setattr(azure, "_az", run)
    vault, app = azure.collect_azure(tmp_path)
    secret = vault.containers[0].entries[0]
    settings = {entry.name: entry for entry in app.containers[0].entries}

    assert secret.retrievability is Retrievability.PERMISSION_GATED
    assert "Key Vault Secrets User" in secret.retrievability_reason
    assert settings["REF"].is_reference is True
    assert settings["PLAIN"].is_reference is False


def test_a_permission_refusal_yields_denied_naming_the_role(monkeypatch) -> None:
    monkeypatch.setattr(
        azure, "_az", lambda _args: (1, "ERROR: Caller is not authorized to perform action")
    )

    value, reason = azure.reveal_vault_secret("azure_keyvault:kv-prod", "DbPassword")

    assert value is None
    assert "Key Vault Secrets User" in reason


# -- Vercel --------------------------------------------------------------


@pytest.fixture
def vercel_linked(tmp_path):
    link = tmp_path / ".vercel"
    link.mkdir()
    (link / "project.json").write_text(
        json.dumps({"projectId": "prj_1", "orgId": "team_1"}), encoding="utf-8"
    )
    return tmp_path


def test_vercel_with_no_credential_names_the_missing_one(vercel_linked, monkeypatch) -> None:
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)

    (source,) = vercel.collect_vercel(vercel_linked)

    assert source.state is AvailabilityState.DEGRADED
    assert "VERCEL_TOKEN" in source.hint


def test_a_rejected_vercel_token_says_so(vercel_linked, monkeypatch) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "bad")
    monkeypatch.setattr(vercel, "_api_get", lambda _path, _token: (401, None))

    (source,) = vercel.collect_vercel(vercel_linked)

    assert source.state is AvailabilityState.DEGRADED
    assert "rejected" in source.hint


def test_a_project_with_no_vercel_link_contributes_no_source(tmp_path) -> None:
    assert vercel.collect_vercel(tmp_path) == []


def test_a_vercel_timeout_names_the_timeout(vercel_linked, monkeypatch) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "ok")
    monkeypatch.setattr(vercel, "_api_get", lambda _path, _token: (0, None))

    (source,) = vercel.collect_vercel(vercel_linked)

    assert "did not answer" in source.hint


def test_a_reachable_but_empty_vercel_project_is_empty(vercel_linked, monkeypatch) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "ok")
    monkeypatch.setattr(vercel, "_api_get", lambda _path, _token: (200, {"envs": []}))

    (source,) = vercel.collect_vercel(vercel_linked)

    assert source.state is AvailabilityState.EMPTY


def test_sensitive_entries_are_never_and_others_are_permission_gated(
    vercel_linked, monkeypatch
) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "ok")
    monkeypatch.setattr(
        vercel,
        "_api_get",
        lambda _path, _token: (
            200,
            {
                "envs": [
                    {"key": "SECRET", "type": "sensitive", "target": ["production"]},
                    {"key": "PUBLIC", "type": "encrypted", "target": ["preview", "production"]},
                ]
            },
        ),
    )

    (source,) = vercel.collect_vercel(vercel_linked)
    by_target = {container.label: container for container in source.containers}
    production = {entry.name: entry for entry in by_target["production"].entries}

    assert set(by_target) == {"preview", "production"}
    assert production["SECRET"].retrievability is Retrievability.NEVER
    assert production["PUBLIC"].retrievability is Retrievability.PERMISSION_GATED


def test_a_sensitive_entry_never_triggers_a_decrypt_request(vercel_linked, monkeypatch) -> None:
    from cabal.webapi import envsources_service

    monkeypatch.setenv("VERCEL_TOKEN", "ok")
    calls: list[str] = []

    def api(path: str, _token: str):
        calls.append(path)
        return 200, {"envs": [{"key": "SECRET", "type": "sensitive", "target": ["production"]}]}

    monkeypatch.setattr(vercel, "_api_get", api)
    result = envsources_service.reveal(vercel_linked, "vercel", "vercel:production", "SECRET")

    assert result.status == "unavailable"
    assert all("decrypt" not in path for path in calls)


# -- read-only guarantee -------------------------------------------------


def test_nothing_in_the_collectors_issues_a_write_verb() -> None:
    """FR-023: read-only against every provider, asserted against the sources themselves."""
    import inspect

    write_verbs = (
        '"create"',
        '"update"',
        '"delete"',
        '"set"',
        '"POST"',
        '"PUT"',
        '"PATCH"',
        '"DELETE"',
    )
    for module in (azure, github, vercel):
        text = inspect.getsource(module)
        found = [verb for verb in write_verbs if verb in text]
        assert found == [], f"{module.__name__} names a write verb: {found}"


def test_the_azure_link_action_writes_only_to_the_local_store(tmp_path, monkeypatch) -> None:
    import inspect

    source = inspect.getsource(envsource_azure_link)

    assert "subprocess" not in source
    assert "urllib" not in source
    store = tmp_path / "links.json"
    envsource_azure_link.save_link(tmp_path, "sub-1", None, path=store)
    assert store.is_file()
    assert json.loads(store.read_text(encoding="utf-8"))["schema"] == "cabal-azure-links.v1"
