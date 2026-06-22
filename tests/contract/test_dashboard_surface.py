"""Contract test — dashboard public surface (Feature 008, C-P-C1).

The dashboard is reached via HomeScreen, not the cabal.wizard facade, so no name is
re-exported there. This asserts the surface resolves the way the design states:
DashboardPanel imports from its widget module and HomeScreen references it.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CABAL_SRC = REPO_ROOT / "setup" / "src"
if str(CABAL_SRC) not in sys.path:
    sys.path.insert(0, str(CABAL_SRC))


def test_dashboard_panel_resolves_from_widget_module():
    from cabal.widgets.dashboard_panel import DashboardPanel

    assert inspect.isclass(DashboardPanel)


def test_dashboard_panel_is_not_re_exported_through_wizard_facade():
    wizard = importlib.import_module("cabal.wizard")

    assert not hasattr(wizard, "DashboardPanel")


def test_home_module_imports_dashboard_panel():
    source = (CABAL_SRC / "cabal" / "views" / "home.py").read_text(encoding="utf-8")

    assert "from cabal.widgets.dashboard_panel import DashboardPanel" in source
