# -*- coding: utf-8 -*-
"""Dev-mode shim — invokes the `cabal` wizard from a fresh git checkout.

For installed use, prefer:

    uv tool install cabal
    cabal

This shim only exists so `python setup/settings-configurator-ui.py` still
works for users running the wizard directly out of the repo (referenced from
setup/README.md and setup/settings-configurator-ui.cmd). It:

1. Adds `setup/src/` to sys.path so `import cabal` resolves.
2. Auto-installs `textual` + `rich` if missing — the wheel declares them as
   real deps; only the source-checkout path needs this safety net.
3. Hands off to cabal.__main__.main().
"""

from __future__ import annotations

import importlib
import site
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))


def _missing_deps() -> None:
    sys.stderr.write(
        "Dev shim could not import `textual` after attempting to install it.\n"
        "Install manually:\n"
        "  python -m pip install textual rich\n"
        "Then re-run.\n"
    )
    sys.exit(2)


def _ensure_deps() -> None:
    try:
        import textual  # noqa: F401
        import rich  # noqa: F401
        return
    except ImportError:
        pass
    print("First run — installing textual + rich...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "textual", "rich"]
        )
    except Exception:
        _missing_deps()
    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path:
        sys.path.append(user_site)
    importlib.invalidate_caches()
    try:
        import textual  # noqa: F401
        import rich  # noqa: F401
    except ImportError:
        _missing_deps()


if __name__ == "__main__":
    _ensure_deps()
    from cabal.__main__ import main
    main()
