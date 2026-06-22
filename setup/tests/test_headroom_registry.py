# -*- coding: utf-8 -*-
"""Registry smoke test — headroom is wired into TOOLS, ENV_INSTALLERS, and the AI CLIs group."""

from __future__ import annotations

import cabal.tools
from cabal.installers.headroom import headroom_status
from cabal.tools import ENV_INSTALLERS, ENV_TOOL_GROUPS, TOOLS

HEADROOM_KEY = "headroom"
AI_CLIS_GROUP = "AI CLIs"


def test_headroom_is_a_tool_entry():
    keys = {tool.key for tool in TOOLS}

    assert HEADROOM_KEY in keys


def test_headroom_is_an_env_installer():
    keys = {key for key, _label, _fn in ENV_INSTALLERS}

    assert HEADROOM_KEY in keys


def test_headroom_is_in_ai_clis_group():
    groups = dict(ENV_TOOL_GROUPS)

    assert HEADROOM_KEY in groups[AI_CLIS_GROUP]


def test_headroom_status_returns_a_string():
    result = headroom_status()

    assert isinstance(result, str)
