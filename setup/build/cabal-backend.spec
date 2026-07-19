# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Cabal desktop FastAPI sidecar.

Build from the repository root with:

    uv run --with pyinstaller python setup/build/build_backend.py

The output binary is named `cabal-backend-<target-triple>[.exe]`, matching
Tauri's production `sidecar("cabal-backend")` lookup convention.
"""

from pathlib import Path
import platform
import sys

from PyInstaller.utils.hooks import collect_submodules  # noqa: E402

REPO_ROOT = Path(SPECPATH).resolve().parent.parent  # noqa: F821 (SPECPATH injected by PyInstaller)
ENTRY = REPO_ROOT / "setup" / "src" / "cabal" / "webapi" / "__main__.py"
PACKAGE_ROOT = REPO_ROOT / "setup" / "src"

sys.path.insert(0, str(PACKAGE_ROOT))


def _tauri_target_triple() -> str:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"

datas = [
    (str(REPO_ROOT / "global"), "global"),
    (str(REPO_ROOT / "setup" / "env"), "setup/env"),
    (str(REPO_ROOT / "setup" / "mcp-templates.json"), "setup"),
    (str(REPO_ROOT / "README.md"), "."),
]

hiddenimports = [
    "cabal",
    *collect_submodules("cabal.webapi"),
    *collect_submodules("cabal.codex_setup"),
    *collect_submodules("cabal.installers"),
    *collect_submodules("cabal.okf"),
    *collect_submodules("cabal.package_security"),
    "cabal.claude_cli",
    "cabal.claude_settings",
    "cabal.cleanup_service",
    "cabal.components",
    "cabal.config_doctor",
    "cabal.diff_apply",
    "cabal.env_detect",
    "cabal.env_profile",
    "cabal.env_summary",
    "cabal.git_config",
    "cabal.git_policy",
    "cabal.gh_accounts",
    "cabal.gh_templates",
    "cabal.init_project_service",
    "cabal.local_setup",
    "cabal.mcp_ops",
    "cabal.mcp_view_logic",
    "cabal.model_assignments",
    "cabal.redaction",
    "cabal.recent_projects",
    "cabal.service_catalog",
    "cabal.service_prereqs",
    "cabal.service_supervisor",
    "cabal.session_reader",
    "cabal.session_pricing",
    "cabal.settings_helpers",
    "cabal.tool_catalog",
    "cabal.tools",
    "cabal.widget_cache",
]

a = Analysis(  # noqa: F821
    [str(ENTRY)],
    pathex=[str(PACKAGE_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[item for item in hiddenimports if item],
    hookspath=[],
    runtime_hooks=[],
    excludes=["textual"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=f"cabal-backend-{_tauri_target_triple()}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
