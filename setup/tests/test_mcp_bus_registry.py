# -*- coding: utf-8 -*-
"""Registry + template smoke test — mcp-bus is wired into TOOLS, ENV_INSTALLERS, the MCP group, and templates."""

from __future__ import annotations

import cabal.tools
from cabal import mcp_ops
from cabal.installers.mcp_bus import mcp_bus_status
from cabal.tools import ENV_INSTALLERS, ENV_TOOL_GROUPS, TOOLS

MCP_BUS_KEY = "mcp-bus"
HEADROOM_KEY = "headroom"
MCP_GROUP = "MCP"


def test_mcp_bus_is_a_tool_entry():
    keys = {tool.key for tool in TOOLS}

    assert MCP_BUS_KEY in keys


def test_mcp_bus_is_an_env_installer():
    keys = {key for key, _label, _fn in ENV_INSTALLERS}

    assert MCP_BUS_KEY in keys


def test_mcp_bus_is_in_mcp_group():
    groups = dict(ENV_TOOL_GROUPS)

    assert MCP_BUS_KEY in groups[MCP_GROUP]


def test_mcp_group_keeps_headroom_alongside_mcp_bus():
    groups = dict(ENV_TOOL_GROUPS)

    assert groups[MCP_GROUP] == [HEADROOM_KEY, MCP_BUS_KEY]


def test_mcp_bus_status_returns_a_string():
    result = mcp_bus_status()

    assert isinstance(result, str)


def test_mcp_bus_template_definition_loads():
    templates = mcp_ops._load_mcp_templates()

    mcp_bus = templates[MCP_BUS_KEY]

    assert mcp_bus["command"] == "mcp-bus"
    assert mcp_bus["args"] == []
    assert mcp_bus["default_enabled"] is False
