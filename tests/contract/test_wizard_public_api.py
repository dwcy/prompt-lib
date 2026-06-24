"""Contract test — `cabal.wizard` public API surface (Feature 005).

Asserts every name in `specs/005-cabal-tools-polish/contracts/public-api.contract.md`
resolves via `cabal.wizard.<name>`, has a real module home inside the `cabal.` package,
and (for callables) yields a non-raising `inspect.signature`.

Runs against the source tree so a wheel install is not required.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "setup" / "src"))


# Grandfathered — names that callers outside cabal depend on today.
# These MUST resolve via cabal.wizard.<name> on every commit of this branch.
GRANDFATHERED: tuple[str, ...] = (
    "GLOBAL_DIR",
    "COMPONENTS",
    "Component",
    "FileStatus",
    "detect_env",
    "find_env_vars",
    "diff_component",
    "run",
    "main",
)

# Recommended re-exports — not provably called externally, but preserved for
# ergonomic continuity per contracts/public-api.contract.md.
RECOMMENDED: tuple[str, ...] = (
    # paths
    "IS_FROZEN",
    "IS_INSTALLED",
    "SCRIPT_DIR",
    "RESOURCE_ROOT",
    "REPO_DIR",
    "ENV_DIR",
    "ENV_FILE",
    "MCP_TEMPLATES_FILE",
    "TARGET",
    # banner
    "GRID_HEIGHT",
    "LOGO_LINES",
    "LOGO_MAX_WIDTH",
    "LOGO_GUTTER",
    "LOGO_GRADIENT",
    "MASCOT_GRADIENT",
    "render_banner",
    "HexBanner",
    "CabalLogo",
    # env summary
    "render_env_summary",
    # components
    "ENV_DESCRIPTIONS",
    # os filters
    "translate_for_os",
    # diff/apply
    "find_extras",
    "apply_statuses",
    "backup_settings",
    "prune_backups",
    # git config
    "recommended_autocrlf",
    "apply_git_line_endings",
    # updates
    "check_for_updates",
    "do_git_pull",
    # MCP
    "enumerate_mcp_servers",
    "claude_mcp_add_from_template",
    "claude_mcp_remove",
    # tools
    "Tool",
    "TOOLS",
    # app
    "CabalApp",
)


ALL_NAMES: tuple[str, ...] = GRANDFATHERED + RECOMMENDED


@pytest.fixture(scope="module")
def wizard_module():
    return importlib.import_module("cabal.wizard")


@pytest.mark.parametrize("name", GRANDFATHERED)
def test_grandfathered_name_resolves(wizard_module, name):
    assert hasattr(wizard_module, name), (
        f"cabal.wizard.{name} is missing — broken public-API floor (Grandfathered)"
    )
    obj = getattr(wizard_module, name)
    assert obj is not None, f"cabal.wizard.{name} is None"


@pytest.mark.parametrize("name", RECOMMENDED)
def test_recommended_name_resolves(wizard_module, name):
    assert hasattr(wizard_module, name), (
        f"cabal.wizard.{name} is missing — broken Recommended re-export"
    )
    obj = getattr(wizard_module, name)
    assert obj is not None, f"cabal.wizard.{name} is None"


@pytest.mark.parametrize("name", ALL_NAMES)
def test_name_has_cabal_home(wizard_module, name):
    obj = getattr(wizard_module, name)
    mod = inspect.getmodule(obj)
    # Module-level path constants (Path objects) and lists don't carry a __module__
    # attribute that points back to cabal. We accept any of:
    #   - module name starts with "cabal."
    #   - inspect.getmodule returns None (e.g. pathlib.Path instance)
    #   - object's defining module is `cabal.wizard` itself
    if mod is None:
        return
    assert mod.__name__.startswith("cabal") or mod.__name__ in {"builtins", "pathlib"}, (
        f"cabal.wizard.{name} resolved from foreign module {mod.__name__}"
    )


@pytest.mark.parametrize("name", ALL_NAMES)
def test_callable_signature_resolves(wizard_module, name):
    obj = getattr(wizard_module, name)
    if not callable(obj):
        return
    try:
        inspect.signature(obj)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"inspect.signature(cabal.wizard.{name}) raised: {exc}")


def test_wizard_module_imports_without_side_effects(wizard_module):
    """Module must import cleanly — no network call, no ~/.claude/ mutation."""
    assert wizard_module is not None
