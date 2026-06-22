# -*- coding: utf-8 -*-
"""Dev-mode shim — invokes the `cabal` wizard from a fresh git checkout.

For installed use, prefer:

    uv tool install cabal
    cabal

This shim only exists so `python setup/settings-configurator-ui.py` still
works for users running the wizard directly out of the repo (referenced from
setup/README.md and setup/settings-configurator-ui.cmd). It:

1. Adds `setup/src/` to sys.path so `import cabal` resolves.
2. Offers to install `textual` + `rich` if missing — the wheel declares them as
   real deps; only the source-checkout path needs this safety net.
3. Hands off to cabal.__main__.main().
"""

from __future__ import annotations

import importlib
import os
import site
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

DEV_DEPENDENCIES = ("textual>=0.50,<7", "rich>=13,<15")
AUTO_INSTALL_ENV = "PROMPTLIB_AUTO_INSTALL_DEPS"


def _missing_deps(reason: str | None = None) -> None:
    if reason:
        sys.stderr.write(reason.rstrip() + "\n")
    sys.stderr.write(
        "Dev shim could not import `textual` and `rich`.\n"
        "Install manually:\n"
        f"  python -m pip install {' '.join(DEV_DEPENDENCIES)}\n"
        f"Or re-run with {AUTO_INSTALL_ENV}=1 to let this shim install them.\n"
    )
    sys.exit(2)


def _confirm_install() -> bool:
    value = os.environ.get(AUTO_INSTALL_ENV, "").strip().lower()
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    if not sys.stdin.isatty():
        return False
    answer = input("Install Python packages textual + rich now? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _ensure_deps() -> None:
    try:
        import textual  # noqa: F401
        import rich  # noqa: F401
        return
    except ImportError:
        pass
    if not _confirm_install():
        _missing_deps("Python packages textual + rich are missing.")

    print("Installing textual + rich...")
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--disable-pip-version-check",
                *DEV_DEPENDENCIES,
            ]
        )
    except Exception:
        _missing_deps("Dependency installation failed.")
    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path:
        sys.path.append(user_site)
    importlib.invalidate_caches()
    try:
        import textual  # noqa: F401
        import rich  # noqa: F401
    except ImportError:
        _missing_deps("Dependency installation completed, but imports still failed.")


if __name__ == "__main__":
    _ensure_deps()
    from cabal.__main__ import main
    main()
