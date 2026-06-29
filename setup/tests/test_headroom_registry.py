# -*- coding: utf-8 -*-
"""Registry smoke test — headroom is wired into the tool catalog, ENV_INSTALLERS, and the MCP group."""

from __future__ import annotations

import cabal.tools
from cabal.installers.headroom import headroom_status
from cabal.tool_catalog import CATALOG_BY_KEY, get_tool_definition
from cabal.tools import ENV_INSTALLERS, ENV_TOOL_GROUPS

HEADROOM_KEY = "headroom"
MCP_GROUP = "MCP"


def test_headroom_is_in_catalog():
    assert HEADROOM_KEY in CATALOG_BY_KEY
    assert get_tool_definition(HEADROOM_KEY) is not None


def test_headroom_is_an_env_installer():
    keys = {key for key, _label, _fn in ENV_INSTALLERS}

    assert HEADROOM_KEY in keys


def test_headroom_is_in_mcp_group():
    groups = dict(ENV_TOOL_GROUPS)

    assert HEADROOM_KEY in groups[MCP_GROUP]


def test_headroom_status_returns_a_string():
    result = headroom_status()

    assert isinstance(result, str)
