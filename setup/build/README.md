# setup/build/

Packaging pipeline that turns the Textual wizard into a single-file executable.

## Build

```bash
python setup/build/build_exe.py        # any OS
setup\build\build.cmd                  # Windows convenience
```

PyInstaller and textual are installed into the active interpreter on first run if missing.

## Output

```
setup/build/dist/cabal        (Linux / macOS)
setup/build/dist/cabal.exe    (Windows)
```

A 30–50 MiB onefile binary. Bundled inside:

- A full Python 3.x interpreter (`python3XX.dll`, `python3.dll`, the stdlib, `_ctypes.pyd`, etc.) — **the host machine does NOT need Python installed**.
- `textual` + `rich` (with their CSS styling assets and lazy-loaded submodules).
- `global/`, `setup/env/`, and root `README.md`.

PyInstaller's bootloader extracts the bundle to a per-run tempdir on first launch (~1–2 s) and runs from there. After the wizard exits, the tempdir is removed.

### Distributing to a fresh machine

Copy `cabal.exe` to any Windows 10/11 host. No Python, no pip, no virtualenv — just double-click or run from cmd / PowerShell / bash. The host only needs:

- Windows 10 1709 (build 16299) or later — for ANSI VT colour support in the TUI.
- The VC++ 2015–2022 runtime — already present on any reasonably-current Windows install; if missing the exe will fail to start with an error about `vcruntime140.dll` and the user can install it from Microsoft.

Optional extras the wizard *uses* if present, but degrades gracefully without:

| Tool | Used for | Wizard behaviour if missing |
|---|---|---|
| `git` | repo update check, local project `git init` | env summary shows `✗`, update check returns `no_git`, git init mode is disabled |
| `gh` | (not used directly by wizard) | env summary shows `✗` |
| `claude` (Claude Code CLI) | env summary only | env summary shows `✗` |
| `bash` | env summary only | env summary shows `✗` |

Antivirus on first run may quarantine the exe (PyInstaller's bootloader is unsigned and false-positives are common). Distribute via a trusted channel or code-sign for production use.

## Two run modes — same code

| Mode | Command | `global/` source | Git auto-update |
|---|---|---|---|
| Terminal (source) | `python setup/settings-configurator-ui.py` | repo working tree | yes (via `git pull`) |
| Standalone exe | `./cabal[.exe]` | bundled inside the exe | only if `.git` is found near the exe |
| Installed | `cabal` | bundled inside the wheel under `cabal/_data/` | n/a (immutable; reinstall to update) |

Resolution is centralised in `_resource_root()` / `_detect_repo_dir()` in `setup/src/cabal/_paths.py` (re-exported by `cabal.wizard` for backward compatibility). All three run modes execute the same wizard code; those two helpers detect frozen / wheel-installed / source-checkout layouts.

## Files

- `cabal.spec` — PyInstaller spec. Lists hidden imports for Textual's lazily-loaded internals and the data trees to bundle.
- `build_exe.py` — Cross-platform driver. Ensures PyInstaller + textual, runs the spec, prints the output path and size.
- `build.cmd` — Windows launcher that finds `py` or `python` on PATH.

## Updating the bundled config

The exe ships a frozen snapshot of `global/` at build time. To refresh:

1. Edit files under `global/` as usual.
2. Re-run `python setup/build/build_exe.py`.
3. Distribute the new `dist/cabal.exe`.

For people running from source, `git pull` is enough — no rebuild needed.
