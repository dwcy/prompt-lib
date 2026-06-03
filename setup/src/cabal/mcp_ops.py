# -*- coding: utf-8 -*-
"""MCP server helpers — wraps `claude mcp` CLI and aggregates across scopes.

Claude Code stores MCP servers in ~/.claude.json (NOT settings.json). The CLI
`claude mcp add/remove/list` is the only supported interface. See add-mcp skill.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

from cabal._paths import MCP_TEMPLATES_FILE
from cabal.claude_cli import _run_claude_cli

_WINDOWS_CMD_WRAPPED = frozenset({"pnpm", "npx", "bunx"})


def _load_mcp_templates() -> dict:
    if not MCP_TEMPLATES_FILE.exists():
        return {}
    try:
        return json.loads(MCP_TEMPLATES_FILE.read_text(encoding="utf-8")).get(
            "templates", {}
        )
    except Exception:
        return {}


def _claude_dot_json() -> dict:
    p = Path.home() / ".claude.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _claude_mcp_list() -> list[dict]:
    """Parse `claude mcp list` output. Returns [{name, command_line, connected, status_text}].

    Line format: `<name>: <command> - <status>` — names may contain `:` (plugin:foo:bar),
    so we split on `: ` (colon + space) to find the name/command boundary.
    """
    rc, out, _ = _run_claude_cli(["mcp", "list"], timeout=60)
    if rc != 0:
        return []
    results = []
    for line in out.splitlines():
        line = line.strip()
        if not line or " - " not in line or ": " not in line:
            continue
        head, _, status = line.rpartition(" - ")
        name, _, cmdline = head.partition(": ")
        results.append(
            {
                "name": name.strip(),
                "command_line": cmdline.strip(),
                "connected": "Connected" in status,
                "status_text": status.strip(),
            }
        )
    return results


def enumerate_mcp_servers() -> dict[str, dict]:
    """Aggregate every known MCP server across scopes into one view.

    Returns: { name: { 'scopes': [str], 'active': bool, 'command_line': str,
                       'env_required': [str], 'is_plugin': bool, 'definitions': {scope: cfg} } }

    Scopes: 'plugin' | 'user' | 'local' | 'project' | 'template'
    'template' means defined in mcp-templates.json but not yet registered.
    """
    aggregated: dict[str, dict] = {}

    def _ensure(name: str) -> dict:
        return aggregated.setdefault(
            name,
            {
                "scopes": [],
                "active": False,
                "command_line": "",
                "env_required": [],
                "is_plugin": name.startswith("plugin:"),
                "definitions": {},
                "plugin_id": None,
                "plugin_enabled": None,
                "plugin_scope": None,
            },
        )

    cj = _claude_dot_json()
    for name, cfg in (cj.get("mcpServers") or {}).items():
        e = _ensure(name)
        e["scopes"].append("user")
        e["definitions"]["user"] = cfg

    for proj_path, proj_data in (cj.get("projects") or {}).items():
        for name, cfg in (proj_data.get("mcpServers") or {}).items():
            e = _ensure(name)
            e["scopes"].append("local")
            e["definitions"].setdefault("local", []).append(
                {"path": proj_path, "def": cfg}
            )

    cwd_mcp = Path.cwd() / ".mcp.json"
    if cwd_mcp.exists():
        try:
            d = json.loads(cwd_mcp.read_text(encoding="utf-8"))
            entries = d.get("mcpServers") or d
            for name, cfg in entries.items():
                e = _ensure(name)
                e["scopes"].append("project")
                e["definitions"]["project"] = cfg
        except Exception:
            pass

    for entry in _claude_mcp_list():
        name = entry["name"]
        e = _ensure(name)
        e["active"] = entry["connected"]
        e["command_line"] = entry["command_line"]
        if e["is_plugin"] and "plugin" not in e["scopes"]:
            e["scopes"].insert(0, "plugin")

    # Plugin-provided servers, incl. disabled plugins (absent from `claude mcp list`).
    for plug in claude_plugin_list():
        pid = plug.get("id") or ""
        if not pid:
            continue
        short = pid.split("@", 1)[0]
        enabled = bool(plug.get("enabled"))
        pscope = plug.get("scope")
        for server, cfg in (plug.get("mcpServers") or {}).items():
            e = _ensure(f"plugin:{short}:{server}")
            e["is_plugin"] = True
            if "plugin" not in e["scopes"]:
                e["scopes"].insert(0, "plugin")
            e["plugin_id"] = pid
            e["plugin_enabled"] = enabled
            e["plugin_scope"] = pscope
            e["definitions"]["plugin"] = cfg
            if not e["command_line"]:
                cmd = cfg.get("command") or ""
                e["command_line"] = (
                    " ".join([cmd, *(cfg.get("args") or [])]).strip()
                    if cmd
                    else (cfg.get("url") or "")
                )

    for name, tmpl in _load_mcp_templates().items():
        e = _ensure(name)
        e["env_required"] = list(tmpl.get("env_required") or [])
        e["definitions"]["template"] = tmpl
        if not e["scopes"]:
            e["scopes"].append("template")
        if not e["command_line"]:
            e["command_line"] = " ".join(
                [tmpl.get("command", "")] + list(tmpl.get("args") or [])
            )

    return aggregated


def claude_mcp_add_from_template(name: str, template: dict) -> tuple[bool, str]:
    """Register a server via `claude mcp add -s user`, wrapping pnpm/npx/bunx on Windows."""
    cmd = template.get("command", "")
    args = list(template.get("args") or [])
    transport = template.get("transport", "stdio")

    if platform.system() == "Windows" and cmd in _WINDOWS_CMD_WRAPPED:
        joined = " ".join([cmd] + args)
        subcmd, subargs = "cmd", ["/s", "/c", joined]
    else:
        subcmd, subargs = cmd, args

    full = ["mcp", "add", "-s", "user"]
    if transport != "stdio":
        full += ["--transport", transport]
    for var in template.get("env_required") or []:
        val = os.environ.get(var, "")
        if not val:
            return False, f"Missing env var: {var} (set it in your shell first)"
        full += ["-e", f"{var}={val}"]
    full += [name, "--", subcmd, *subargs]

    rc, out, err = _run_claude_cli(full)
    if rc == 0:
        return True, (out or "Added").strip().splitlines()[0]
    return False, (err or out or "unknown error").strip()


def claude_mcp_remove(name: str, scope: str) -> tuple[bool, str]:
    rc, out, err = _run_claude_cli(["mcp", "remove", "-s", scope, name])
    if rc == 0:
        return True, (out or "Removed").strip().splitlines()[0]
    return False, (err or out or "unknown error").strip()


def claude_plugin_list(available: bool = False) -> list[dict]:
    """Parse `claude plugin list --json`. Each item carries id/version/scope/enabled/mcpServers."""
    args = ["plugin", "list", "--json"]
    if available:
        args.append("--available")
    rc, out, _ = _run_claude_cli(args, timeout=60)
    if rc != 0 or not out:
        return []
    text = out.strip()
    try:
        data = json.loads(text)
    except Exception:
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1 or end < start:
            return []
        try:
            data = json.loads(text[start : end + 1])
        except Exception:
            return []
    return data if isinstance(data, list) else []


def claude_plugin_set_enabled(
    plugin: str, enabled: bool, scope: str | None = None
) -> tuple[bool, str]:
    """Enable/disable a whole plugin via `claude plugin enable/disable` — cycles all its MCP servers."""
    args = ["plugin", "enable" if enabled else "disable", plugin]
    if scope:
        args += ["-s", scope]
    rc, out, err = _run_claude_cli(args, timeout=120)
    fallback = "Enabled" if enabled else "Disabled"
    if rc == 0:
        msg = (out or fallback).strip()
        return True, msg.splitlines()[0] if msg else fallback
    return False, (err or out or "unknown error").strip()
