"""Guard: Ctrl+C must NOT be bound to quit on CabalApp.

Textual >= 8 uses Ctrl+C as the native copy shortcut for selected text.
Binding ctrl+c -> quit breaks terminal copy and terminates the app whenever
the user tries to copy content. Quit is on Ctrl+Q (and the `q` key).

If Ctrl+C ever "appears to do nothing" in the wizard, that is because no text
is selected -- not because the binding is missing. Do not re-add it.
"""

from __future__ import annotations

from cabal.app import CabalApp
from cabal.views.tools import ToolsScreen


def test_ctrl_c_not_bound_on_cabal_app():
    binding_keys = {b.key for b in CabalApp.BINDINGS}

    assert "ctrl+c" not in binding_keys


def test_tools_screen_does_not_bind_ctrl_c_to_quit():
    binding_keys = {b.key for b in ToolsScreen.BINDINGS}

    assert "ctrl+c" not in binding_keys
