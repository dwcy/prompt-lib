# Claude Runtime Features Not Converted To Codex

These Claude Code features do not have a direct Codex runtime equivalent in this
repo's first Codex setup pass.

## Hooks

Claude hooks under `global/hooks/` are event-driven scripts for Claude Code
session starts, tool use, stops, and session ends. Codex does not run these
Claude hook events from `~/.codex`, so they are not deployed as active runtime
hooks.

## Statusline

`global/statusline.py` depends on Claude Code's statusline contract and stdin
snapshot. Codex does not consume that contract, so the statusline is not copied
as an active Codex feature.

## MCP And Plugin Settings

Claude MCP/plugin settings are configured through Claude Code files and commands.
Codex MCP servers and plugins are configured through Codex's own `config.toml`
and desktop plugin system, so this setup does not overwrite them.

## Output Styles

Claude output styles are not a Codex runtime feature. They are copied as
references only, so a Codex session can read the style guidance explicitly.

## Keybindings

Claude Code keybindings are not applicable to Codex and are not deployed.
