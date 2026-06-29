# Contract: Database and Azure Container Services

## Purpose

Make database installs reliable, reversible, and testable by modelling services as container specs instead of ad hoc host package installs.

## Service contract

Every container-backed service must define:

- `key`
- `image`
- `container_name`
- host/container `ports`
- persistent `volumes`
- preflight checks
- install/start command generation
- status command generation
- health check strategy
- logs guidance
- cleanup guidance
- security notes

## Required preflight behavior

- Detect Docker or Podman availability before install.
- Report missing/stopped container engine as a blocking condition.
- Check host port conflicts before install.
- Check name conflicts before install.
- Check volume conflicts before install.
- Pull or verify the image before reporting success.
- Run health checks before reporting success.

## MVP service coverage

| Key | Mode | Notes |
|---|---|---|
| `redis` | container service | Official Docker image |
| `mariadb` | container service | Official Docker image |
| `turso-libsql` | container service | Local libSQL/Turso-compatible service |
| `qdrant` | container service | Vector database |
| `weaviate` | container service | Vector database |
| `milvus` | container service | Vector database |
| `azure-sql-local` | container/dev container | Azure SQL local development path |
| `cosmos-db-emulator` | container/app emulator | Platform-aware Microsoft emulator |
| `azurite` | container or npm service | Azure Storage emulator |
| `sqlite` | embedded utility | Must be labelled as embedded/file-oriented |
| `duckdb` | embedded utility | Must be labelled as embedded/file-oriented |

## Expected contract tests

- `test_container_service_specs_have_required_fields`
- `test_database_services_declare_ports_and_volumes`
- `test_embedded_engines_are_not_marked_daemon_services`
- `test_preflight_blocks_when_container_engine_missing`
- `test_port_conflict_blocks_install`
- `test_health_failure_does_not_report_success`
- `test_database_status_detects_existing_container`
- `test_database_logs_and_cleanup_guidance_are_present`
