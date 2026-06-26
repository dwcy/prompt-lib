# -*- coding: utf-8 -*-
"""Database CLI installers — MSSQL (sqlcmd), Postgres (psql), Supabase, Neon."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _npm_global_install, _run_install, _WINGET_FLAGS
from cabal.installers.container_services import (
    ContainerHealthCheck,
    ContainerPort,
    ContainerServiceSpec,
    ContainerVolume,
    EmbeddedDatabaseSpec,
    container_status,
    install_container_service,
)


DATABASE_CONTAINER_SPECS: dict[str, ContainerServiceSpec] = {
    "redis": ContainerServiceSpec(
        key="redis",
        image="redis:latest",
        container_name="cabal-redis",
        ports=(ContainerPort(6379, 6379),),
        volumes=(ContainerVolume("cabal-redis-data", "/data"),),
        health_check=ContainerHealthCheck(("exec", "cabal-redis", "redis-cli", "ping")),
        logs_hint="Logs: docker logs cabal-redis",
        cleanup_hint="Cleanup: docker rm -f cabal-redis && docker volume rm cabal-redis-data",
        security_notes=("Local development only; bind to localhost when exposing credentials.",),
    ),
    "mariadb": ContainerServiceSpec(
        key="mariadb",
        image="mariadb:latest",
        container_name="cabal-mariadb",
        ports=(ContainerPort(3306, 3306),),
        volumes=(ContainerVolume("cabal-mariadb-data", "/var/lib/mysql"),),
        environment={"MARIADB_ALLOW_EMPTY_ROOT_PASSWORD": "yes", "MARIADB_DATABASE": "cabal"},
        health_check=ContainerHealthCheck(("exec", "cabal-mariadb", "mariadb-admin", "ping", "-h", "127.0.0.1")),
        logs_hint="Logs: docker logs cabal-mariadb",
        cleanup_hint="Cleanup: docker rm -f cabal-mariadb && docker volume rm cabal-mariadb-data",
        security_notes=("Empty root password is for isolated local development only.",),
    ),
    "turso-libsql": ContainerServiceSpec(
        key="turso-libsql",
        image="ghcr.io/tursodatabase/libsql-server:latest",
        container_name="cabal-libsql",
        ports=(ContainerPort(8080, 8080),),
        volumes=(ContainerVolume("cabal-libsql-data", "/var/lib/sqld"),),
        logs_hint="Logs: docker logs cabal-libsql",
        cleanup_hint="Cleanup: docker rm -f cabal-libsql && docker volume rm cabal-libsql-data",
        security_notes=("Use local-only databases for development; do not store production tokens.",),
    ),
    "qdrant": ContainerServiceSpec(
        key="qdrant",
        image="qdrant/qdrant:latest",
        container_name="cabal-qdrant",
        ports=(ContainerPort(6333, 6333), ContainerPort(6334, 6334)),
        volumes=(ContainerVolume("cabal-qdrant-data", "/qdrant/storage"),),
        logs_hint="Logs: docker logs cabal-qdrant",
        cleanup_hint="Cleanup: docker rm -f cabal-qdrant && docker volume rm cabal-qdrant-data",
        security_notes=("Local vector database; configure auth before shared network exposure.",),
    ),
    "weaviate": ContainerServiceSpec(
        key="weaviate",
        image="semitechnologies/weaviate:latest",
        container_name="cabal-weaviate",
        ports=(ContainerPort(8081, 8080),),
        volumes=(ContainerVolume("cabal-weaviate-data", "/var/lib/weaviate"),),
        environment={"AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED": "true", "QUERY_DEFAULTS_LIMIT": "25"},
        logs_hint="Logs: docker logs cabal-weaviate",
        cleanup_hint="Cleanup: docker rm -f cabal-weaviate && docker volume rm cabal-weaviate-data",
        security_notes=("Anonymous access is local-development only.",),
    ),
    "milvus": ContainerServiceSpec(
        key="milvus",
        image="milvusdb/milvus:latest",
        container_name="cabal-milvus",
        ports=(ContainerPort(19530, 19530), ContainerPort(9091, 9091)),
        volumes=(ContainerVolume("cabal-milvus-data", "/var/lib/milvus"),),
        environment={"ETCD_USE_EMBED": "true", "COMMON_STORAGETYPE": "local"},
        command=("milvus", "run", "standalone"),
        logs_hint="Logs: docker logs cabal-milvus",
        cleanup_hint="Cleanup: docker rm -f cabal-milvus && docker volume rm cabal-milvus-data",
        security_notes=("Local standalone vector database; do not expose without auth/network controls.",),
    ),
    "azure-sql-local": ContainerServiceSpec(
        key="azure-sql-local",
        image="mcr.microsoft.com/azure-sql-edge:latest",
        container_name="cabal-azure-sql",
        ports=(ContainerPort(1433, 1433),),
        volumes=(ContainerVolume("cabal-azure-sql-data", "/var/opt/mssql"),),
        environment={"ACCEPT_EULA": "Y", "MSSQL_SA_PASSWORD": "LocalOnly_Password123"},
        logs_hint="Logs: docker logs cabal-azure-sql",
        cleanup_hint="Cleanup: docker rm -f cabal-azure-sql && docker volume rm cabal-azure-sql-data",
        security_notes=("Default password is for local development only; rotate before shared use.",),
    ),
    "azurite": ContainerServiceSpec(
        key="azurite",
        image="mcr.microsoft.com/azure-storage/azurite:latest",
        container_name="cabal-azurite",
        ports=(ContainerPort(10000, 10000), ContainerPort(10001, 10001), ContainerPort(10002, 10002)),
        volumes=(ContainerVolume("cabal-azurite-data", "/data"),),
        logs_hint="Logs: docker logs cabal-azurite",
        cleanup_hint="Cleanup: docker rm -f cabal-azurite && docker volume rm cabal-azurite-data",
        security_notes=("Azurite default development account is not for production use.",),
    ),
}


EMBEDDED_DATABASE_SPECS: dict[str, EmbeddedDatabaseSpec] = {
    "sqlite": EmbeddedDatabaseSpec(
        key="sqlite",
        command=("sqlite3",),
        setup_hint="SQLite is embedded/file-oriented. Use the sqlite3 CLI against a local .sqlite file.",
        source_url="https://sqlite.org/",
    ),
    "duckdb": EmbeddedDatabaseSpec(
        key="duckdb",
        command=("duckdb",),
        setup_hint="DuckDB is embedded/file-oriented. Use the duckdb CLI against local files or in-process libraries.",
        source_url="https://duckdb.org/",
    ),
}


def sqlcmd_install() -> tuple[bool, str]:
    """Microsoft SQL Server command-line tool (modern Go-based sqlcmd)."""
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Microsoft.Sqlcmd", *_WINGET_FLAGS])
        return False, "Install manually from https://aka.ms/go-sqlcmd"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "sqlcmd"])
        return False, "Install Homebrew or download from https://aka.ms/go-sqlcmd"
    if sysname == "Linux":
        # Microsoft repo + apt/dnf is the supported path; bare install often fails.
        return False, "See https://learn.microsoft.com/sql/tools/sqlcmd/go-sqlcmd-utility for distro-specific steps"
    return False, f"Unsupported platform: {sysname}"


def postgres_install() -> tuple[bool, str]:
    """PostgreSQL client (psql). On Windows / macOS the OS-native package brings the full
    server + client; on Linux we install just the client where the distro splits them."""
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "PostgreSQL.PostgreSQL.16", *_WINGET_FLAGS])
        if shutil.which("scoop"):
            return _run_install(["scoop", "install", "postgresql"])
        return False, "Install manually from https://www.postgresql.org/download/windows/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "postgresql@16"])
        return False, "Install Homebrew or download from https://www.postgresql.org/download/macosx/"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "postgresql-client"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "postgresql"])
        if shutil.which("pacman"):
            return _run_install(["sudo", "pacman", "-S", "--noconfirm", "postgresql"])
        return False, "Install via your distro's package manager"
    return False, f"Unsupported platform: {sysname}"


def supabase_install() -> tuple[bool, str]:
    """Supabase CLI — managed via scoop (Win), brew (macOS), or npm (cross-platform fallback)."""
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("scoop"):
            return _run_install(["scoop", "install", "supabase"])
        return _npm_global_install("supabase")
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "supabase/tap/supabase"])
        return _npm_global_install("supabase")
    if sysname == "Linux":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "supabase/tap/supabase"])
        return _npm_global_install("supabase")
    return False, f"Unsupported platform: {sysname}"


def neon_install() -> tuple[bool, str]:
    """Neon serverless Postgres CLI (`neonctl`)."""
    return _npm_global_install("neonctl")


def container_database_status(key: str) -> str | None:
    spec = DATABASE_CONTAINER_SPECS.get(key)
    if spec is None:
        return None
    status = container_status(spec)
    return f"container {status}" if status else None


def _container_install(key: str) -> tuple[bool, str]:
    return install_container_service(DATABASE_CONTAINER_SPECS[key])


def redis_install() -> tuple[bool, str]:
    return _container_install("redis")


def mariadb_install() -> tuple[bool, str]:
    return _container_install("mariadb")


def turso_libsql_install() -> tuple[bool, str]:
    return _container_install("turso-libsql")


def qdrant_install() -> tuple[bool, str]:
    return _container_install("qdrant")


def weaviate_install() -> tuple[bool, str]:
    return _container_install("weaviate")


def milvus_install() -> tuple[bool, str]:
    return _container_install("milvus")


def sqlite_install() -> tuple[bool, str]:
    if shutil.which("sqlite3"):
        return True, EMBEDDED_DATABASE_SPECS["sqlite"].setup_hint
    sysname = platform.system()
    if sysname == "Windows" and shutil.which("winget"):
        return _run_install(["winget", "install", "--id", "SQLite.SQLite", *_WINGET_FLAGS])
    if sysname == "Darwin" and shutil.which("brew"):
        return _run_install(["brew", "install", "sqlite"])
    if sysname == "Linux" and shutil.which("apt-get"):
        return _run_install(["sudo", "apt-get", "install", "-y", "sqlite3"])
    return False, EMBEDDED_DATABASE_SPECS["sqlite"].setup_hint


def duckdb_install() -> tuple[bool, str]:
    if shutil.which("duckdb"):
        return True, EMBEDDED_DATABASE_SPECS["duckdb"].setup_hint
    sysname = platform.system()
    if sysname == "Windows" and shutil.which("winget"):
        return _run_install(["winget", "install", "--id", "DuckDB.cli", *_WINGET_FLAGS])
    if sysname == "Darwin" and shutil.which("brew"):
        return _run_install(["brew", "install", "duckdb"])
    if sysname == "Linux":
        return False, "Install DuckDB CLI from https://duckdb.org/docs/installation/"
    return False, EMBEDDED_DATABASE_SPECS["duckdb"].setup_hint


def ssms_install() -> tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "SQL Server Management Studio is Windows-only."
    if shutil.which("winget"):
        return _run_install(["winget", "install", "--id", "Microsoft.SQLServerManagementStudio", *_WINGET_FLAGS])
    return False, "Install manually from https://learn.microsoft.com/ssms/install/install"


def dbeaver_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "dbeaver.dbeaver", *_WINGET_FLAGS])
        return False, "Install manually from https://dbeaver.io/download/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "dbeaver-community"])
        return False, "Install manually from https://dbeaver.io/download/"
    if sysname == "Linux":
        if shutil.which("snap"):
            return _run_install(["snap", "install", "dbeaver-ce"])
        return False, "Install manually from https://dbeaver.io/download/"
    return False, f"Unsupported platform: {sysname}"
