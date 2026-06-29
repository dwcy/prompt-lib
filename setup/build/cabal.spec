# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the CABAL Claude Code Setup Wizard.

Builds a single-file executable that bundles `global/`, `setup/env/`, and
`setup/mcp-templates.json` so it can run on a machine without a checkout of
prompt-lib. Run via:

    pyinstaller setup/build/cabal.spec

Or use the wrapper: `python setup/build/build_exe.py`.

Textual ships CSS data files and lazy-imports many submodules — we use
`collect_all` so every submodule, datafile, and metadata entry is included.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all  # noqa: E402

REPO_ROOT = Path(SPECPATH).resolve().parent.parent  # noqa: F821 (SPECPATH injected by PyInstaller)
ENTRY = REPO_ROOT / "setup" / "src" / "cabal" / "__main__.py"
PACKAGE_ROOT = REPO_ROOT / "setup" / "src"

_textual_datas, _textual_binaries, _textual_hidden = collect_all("textual")
_rich_datas, _rich_binaries, _rich_hidden = collect_all("rich")

datas = [
    (str(REPO_ROOT / "global"), "global"),
    (str(REPO_ROOT / "setup" / "src" / "cabal" / "assets"), "cabal/assets"),
    (str(REPO_ROOT / "setup" / "env"), "setup/env"),
    (str(REPO_ROOT / "setup" / "mcp-templates.json"), "setup"),
    (str(REPO_ROOT / "README.md"), "."),
    *_textual_datas,
    *_rich_datas,
]

binaries = [*_textual_binaries, *_rich_binaries]

hiddenimports = [
    "cabal",
    "cabal.wizard",
    "cabal._paths",
    "cabal.os_filters",
    "cabal.banner",
    "cabal.env_summary",
    "cabal.settings_helpers",
    "cabal.components",
    "cabal.env_detect",
    "cabal.mcp_ops",
    "cabal.mcp_view_logic",
    "cabal.diff_apply",
    "cabal.git_config",
    "cabal.updates",
    "cabal.gh_release",
    "cabal.claude_cli",
    "cabal.gh_accounts",
    "cabal.gh_templates",
    "cabal.init_project_service",
    "cabal.tool_catalog",
    "cabal.tools",
    "cabal.app_widgets",
    "cabal.app",
    "cabal.installers",
    "cabal.installers._common",
    "cabal.installers.ai_clis",
    "cabal.installers.cdt",
    "cabal.installers.claude_cli",
    "cabal.installers.cloud",
    "cabal.installers.containers",
    "cabal.installers.container_services",
    "cabal.installers.databases",
    "cabal.installers.devtools",
    "cabal.installers.editors",
    "cabal.installers.gh",
    "cabal.installers.runtimes",
    "cabal.installers.runtime_backups",
    "cabal.installers.specify",
    "cabal.installers.uv",
    "cabal.installers.versions",
    "cabal.installers.vcs",
    "cabal.installers.vercel_plugin",
    "cabal.widgets",
    "cabal.widgets.claude_stats_panel",
    "cabal.widgets.disable_scope_modal",
    "cabal.widgets.env_panel",
    "cabal.widgets.logo",
    "cabal.widgets.update_panel",
    "cabal.views",
    "cabal.views.env",
    "cabal.views.folder_browser",
    "cabal.views.gh_accounts_modal",
    "cabal.views.gh_device",
    "cabal.views.git_config",
    "cabal.views.github_repos",
    "cabal.views.global_env",
    "cabal.views.home",
    "cabal.views.init_project",
    "cabal.views.init_project_prompt",
    "cabal.views.local",
    "cabal.views.mcp",
    "cabal.views.operations",
    "cabal.views.project_mcp",
    "cabal.views.readme",
    "cabal.views.restore",
    "cabal.views.tools",
    "cabal.views.update",
    *_textual_hidden,
    *_rich_hidden,
]

a = Analysis(  # noqa: F821
    [str(ENTRY)],
    pathex=[str(PACKAGE_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    name="cabal",
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
