"""Unit tests for cabal.service_catalog — seed invariants and validate_catalog (T003)."""

from __future__ import annotations

import pytest

from cabal import service_catalog
from cabal.service_catalog import (
    ServiceDefinition,
    ServiceStatus,
    all_services,
    get_service,
    validate_catalog,
)


def _replace_seed(
    monkeypatch: pytest.MonkeyPatch, definitions: tuple[ServiceDefinition, ...]
) -> None:
    monkeypatch.setattr(service_catalog, "SERVICE_DEFINITIONS", definitions)
    monkeypatch.setattr(
        service_catalog,
        "SERVICE_BY_KEY",
        {service.key: service for service in definitions},
    )


def _definition(**overrides) -> ServiceDefinition:
    base = dict(
        key="dummy",
        label="Dummy",
        description="A placeholder service.",
        run_command="dummy serve",
        source_url="https://example.test/dummy",
        runnable=True,
        depends_on=(),
        install_path="services/dummy",
        console_name="dummy",
        prereq_keys=(),
        dashboard_command=None,
        log_hint=None,
        default_port=None,
    )
    base.update(overrides)
    return ServiceDefinition(**base)


# ------------------------------------------------------------------
# Seed invariants (C1 guarantees)
# ------------------------------------------------------------------


def test_validate_catalog_passes_on_real_seed():
    assert validate_catalog() is None


def test_catalog_has_the_two_runnable_services():
    assert len(all_services()) == 2


def test_catalog_keys_are_the_two_expected():
    keys = {service.key for service in all_services()}

    assert keys == {"a2a-bridge", "orchestrator"}


def test_info_only_status_is_a_distinct_status():
    assert ServiceStatus.INFO_ONLY in set(ServiceStatus)


def test_orchestrator_depends_on_a2a_bridge():
    assert get_service("orchestrator").depends_on == ("a2a-bridge",)


def test_get_service_unknown_key_raises_keyerror():
    with pytest.raises(KeyError):
        get_service("nope")


# ------------------------------------------------------------------
# Negative validation (validate_catalog raises ValueError on breach)
# ------------------------------------------------------------------


def test_validate_catalog_rejects_empty_catalog(monkeypatch):
    _replace_seed(monkeypatch, ())

    with pytest.raises(ValueError):
        validate_catalog()


def test_validate_catalog_rejects_undefined_dependency(monkeypatch):
    bad = _definition(key="a", depends_on=("ghost",))
    _replace_seed(monkeypatch, (bad, _definition(key="b"), _definition(key="c")))

    with pytest.raises(ValueError):
        validate_catalog()


def test_validate_catalog_rejects_non_runnable_with_dashboard(monkeypatch):
    bad = _definition(key="a", runnable=False, dashboard_command="a dash")
    _replace_seed(monkeypatch, (bad, _definition(key="b"), _definition(key="c")))

    with pytest.raises(ValueError):
        validate_catalog()


def test_validate_catalog_rejects_empty_required_field(monkeypatch):
    bad = _definition(key="a", label="")
    _replace_seed(monkeypatch, (bad, _definition(key="b"), _definition(key="c")))

    with pytest.raises(ValueError):
        validate_catalog()
