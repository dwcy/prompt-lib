# -*- coding: utf-8 -*-
"""Database CLI installers — MSSQL (sqlcmd), Postgres (psql), Supabase, Neon."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _npm_global_install, _run_install, _WINGET_FLAGS


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
