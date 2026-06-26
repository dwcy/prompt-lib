"""Container-backed database service contract tests."""

from __future__ import annotations

from cabal.installers import container_services as services
from cabal.installers.databases import DATABASE_CONTAINER_SPECS, EMBEDDED_DATABASE_SPECS


def test_container_service_specs_have_required_fields():
    required = {"redis", "mariadb", "turso-libsql", "qdrant", "weaviate", "milvus"}

    assert required <= set(DATABASE_CONTAINER_SPECS)
    for spec in DATABASE_CONTAINER_SPECS.values():
        assert spec.key
        assert spec.image
        assert spec.container_name
        assert spec.logs_hint
        assert spec.cleanup_hint
        assert spec.security_notes


def test_database_services_declare_ports_and_volumes():
    for spec in DATABASE_CONTAINER_SPECS.values():
        assert spec.ports
        assert spec.volumes
        assert all(port.host and port.container for port in spec.ports)
        assert all(volume.name and volume.target for volume in spec.volumes)


def test_embedded_engines_are_not_marked_daemon_services():
    for key in ("sqlite", "duckdb"):
        spec = EMBEDDED_DATABASE_SPECS[key]
        assert spec.file_oriented is True
        assert spec.daemon_service is False


def test_preflight_blocks_when_container_engine_missing(monkeypatch):
    monkeypatch.setattr(services, "detect_container_engine", lambda: None)

    result = services.preflight_container_service(DATABASE_CONTAINER_SPECS["redis"])

    assert result.ok is False
    assert "Container engine missing" in result.format()


def test_port_conflict_blocks_install(monkeypatch):
    monkeypatch.setattr(services, "detect_container_engine", lambda: "docker")
    monkeypatch.setattr(services, "is_host_port_available", lambda port: False)
    monkeypatch.setattr(services, "container_exists", lambda spec, engine=None: False)

    result = services.preflight_container_service(DATABASE_CONTAINER_SPECS["redis"])

    assert result.ok is False
    assert "Port conflict" in result.format()


def test_health_failure_does_not_report_success(monkeypatch):
    spec = DATABASE_CONTAINER_SPECS["redis"]
    monkeypatch.setattr(
        services,
        "preflight_container_service",
        lambda spec: services.PreflightResult(True, ("ok",), "docker"),
    )
    monkeypatch.setattr(services, "_run_install", lambda cmd: (True, "ok"))
    monkeypatch.setattr(services, "run_health_check", lambda spec, engine: (False, "no ping"))

    ok, message = services.install_container_service(spec)

    assert ok is False
    assert "Health check failed" in message


def test_database_status_detects_existing_container(monkeypatch):
    monkeypatch.setattr(services, "detect_container_engine", lambda: "docker")
    monkeypatch.setattr(
        services,
        "_run_engine_command",
        lambda args, timeout=10: type("R", (), {"returncode": 0, "stdout": "running\n", "stderr": ""})(),
    )

    assert services.container_status(DATABASE_CONTAINER_SPECS["redis"]) == "running"


def test_database_logs_and_cleanup_guidance_are_present():
    spec = DATABASE_CONTAINER_SPECS["qdrant"]

    assert "logs" in spec.logs_hint.lower()
    assert "cleanup" in spec.cleanup_hint.lower()
