"""Console-script entry point.

Used by:
- The `cabal` console command declared in pyproject.toml's [project.scripts].
- `python -m cabal` invocations.
- The PyInstaller build (entry script = this file).
- The dev-mode shim at setup/settings-configurator-ui.py.
"""

from cabal.wizard import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
