"""Per-tool installer modules used by ToolsScreen / EnvPanel.

Each submodule exposes one or more `<name>_install()` (and sometimes
`<name>_status()`) functions. `cabal.tools` aggregates them into the
`ENV_INSTALLERS` and `TOOLS` registries.
"""
