#!/usr/bin/env python3
"""Validate the prompt-lib Claude Code plugin.

Runs three checks. Exits 0 only if all pass.

1. `claude plugin validate .` against repo root (manifest schema, frontmatter).
   Skipped (with WARN) if `claude` CLI is not on PATH.
2. MCP authority: `global/.mcp.json` MUST exist with non-empty `mcpServers`, AND
   `global/settings.json` MUST NOT carry `mcpServers` / `mcpServersDisabled`.
   Rationale: Claude Code never reads MCP definitions from settings.json — the
   canonical sources are `~/.claude.json` (user scope, via `claude mcp add`) and
   `.mcp.json` (project / plugin scope). Duplicating into settings.json creates
   a false impression that the block is live. See global/skills/add-mcp/SKILL.md.
3. Hooks parity: for every event in {SessionStart, PreToolUse, PostToolUse, Stop}, the set of
   (matcher, script-basename) tuples in `global/hooks/hooks.json` MUST equal the same set in
   `global/settings.json.hooks`, ignoring the path prefix difference
   (`${CLAUDE_PLUGIN_ROOT}/hooks/` vs `$USERPROFILE/.claude/hooks/`).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / "global" / "settings.json"
MCP_JSON = REPO_ROOT / "global" / ".mcp.json"
HOOKS_JSON = REPO_ROOT / "global" / "hooks" / "hooks.json"

_SCRIPT_RE = re.compile(r"(?:[\$\{\w/.~\-]+/)?hooks/([\w.\-]+)")


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def step_claude_validate() -> tuple[bool, str]:
    claude = shutil.which("claude")
    if claude is None:
        return (
            True,
            "SKIP   claude CLI not on PATH (install Claude Code to run schema validation)",
        )
    try:
        proc = subprocess.run(
            [claude, "plugin", "validate", "."],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return (False, "FAIL   claude plugin validate timed out after 60s")
    if proc.returncode != 0:
        return (
            False,
            f"FAIL   claude plugin validate exit {proc.returncode}\n{proc.stdout}\n{proc.stderr}",
        )
    return (True, "OK     claude plugin validate")


def step_mcp_authority() -> tuple[bool, str]:
    if not MCP_JSON.exists():
        return (False, f"FAIL   mcp-authority: {MCP_JSON} is missing")
    mcp = load_json(MCP_JSON).get("mcpServers", {})
    if not mcp:
        return (False, "FAIL   mcp-authority: global/.mcp.json has no mcpServers")
    settings = load_json(SETTINGS)
    leaks = [k for k in ("mcpServers", "mcpServersDisabled") if k in settings]
    if leaks:
        return (
            False,
            "FAIL   mcp-authority: global/settings.json contains dead keys "
            f"{leaks} — strip them (see global/skills/add-mcp/SKILL.md)",
        )
    return (
        True,
        f"OK     mcp-authority ({len(mcp)} servers in .mcp.json; settings.json clean)",
    )


def _script_basename(command: str) -> str | None:
    m = _SCRIPT_RE.search(command)
    return m.group(1) if m else None


def _hook_tuples(hooks_block: dict) -> dict[str, set[tuple[str, str]]]:
    out: dict[str, set[tuple[str, str]]] = {}
    for event, entries in hooks_block.items():
        bucket: set[tuple[str, str]] = set()
        for entry in entries:
            matcher = entry.get("matcher", "")
            for h in entry.get("hooks", []):
                if h.get("type") != "command":
                    continue
                script = _script_basename(h.get("command", ""))
                if script is None:
                    continue
                bucket.add((matcher, script))
        out[event] = bucket
    return out


def step_hooks_parity() -> tuple[bool, str]:
    settings_hooks = load_json(SETTINGS).get("hooks", {})
    plugin_hooks = load_json(HOOKS_JSON).get("hooks", {})

    settings_tuples = _hook_tuples(settings_hooks)
    plugin_tuples = _hook_tuples(plugin_hooks)

    if settings_tuples == plugin_tuples:
        total = sum(len(v) for v in plugin_tuples.values())
        return (
            True,
            f"OK     hooks-sync ({total} hook entries in parity across {len(plugin_tuples)} events)",
        )

    lines = ["FAIL   hooks-sync: global/hooks/hooks.json != global/settings.json hooks"]
    events = sorted(set(settings_tuples) | set(plugin_tuples))
    for ev in events:
        s = settings_tuples.get(ev, set())
        p = plugin_tuples.get(ev, set())
        if s != p:
            only_s = s - p
            only_p = p - s
            lines.append(f"       event '{ev}':")
            if only_s:
                lines.append(f"         only in settings.json: {sorted(only_s)}")
            if only_p:
                lines.append(f"         only in hooks.json:    {sorted(only_p)}")
    return (False, "\n".join(lines))


def main() -> int:
    print("prompt-lib plugin validation")
    print("=" * 60)
    results = [
        step_claude_validate(),
        step_mcp_authority(),
        step_hooks_parity(),
    ]
    for ok, msg in results:
        print(msg)
    print("=" * 60)
    all_ok = all(ok for ok, _ in results)
    print("PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
