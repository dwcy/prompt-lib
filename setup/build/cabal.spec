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
