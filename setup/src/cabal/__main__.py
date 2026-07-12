# -*- coding: utf-8 -*-
"""Console-script entry: no args → Textual wizard; flags/subcommands → headless CLI.

Used by:
- The `cabal` console command declared in pyproject.toml's [project.scripts].
- `python -m cabal` invocations.
- The PyInstaller build (entry script = this file).
- The dev-mode shim at setup/settings-configurator-ui.py.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        # Lazy import so headless use never pays the Textual import cost.
        from cabal.wizard import run

        run()
        return 0
    if args == ["--version"]:
        from cabal.headless import version_line

        print(version_line())
        return 0
    from cabal.headless import main as headless_main

    return headless_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
