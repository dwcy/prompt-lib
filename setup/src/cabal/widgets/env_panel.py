# -*- coding: utf-8 -*-
"""EnvPanel — env summary with inline Install buttons per detected gap."""

from __future__ import annotations

from typing import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Static

from cabal import widget_cache
from cabal._paths import GLOBAL_DIR, TARGET
from cabal.env_detect import detect_env
from cabal.env_summary import (
    _short_aws_version,
    _short_az_version,
    _short_docker_version,
    _short_gcloud_version,
    _short_podman_version,
    _short_terraform_version,
)
from cabal.tools import ENV_INSTALLERS
from cabal.widgets.update_panel import UpdatePanel

_CACHE_KEY = "env"


class EnvPanel(Widget):
    """Env summary with real, compact Install buttons inline next to each missing tool."""

    DEFAULT_CSS = """
    EnvPanel {
        height: auto;
        /* outer border/padding/margin come from the global #env-summary rule */
    }
    EnvPanel > Vertical {
        height: auto;
        padding: 0;
        margin: 0;
    }
    EnvPanel #env-info {
        height: auto;
        padding: 1 2;
        margin: 1 0 0 0;
        background: $boost;
        border: round $accent;
    }
    EnvPanel .env-panel-row {
        layout: horizontal;
        height: 1;
        margin: 0;
        padding: 0;
    }
    EnvPanel .env-cell {
        width: auto;
        height: 1;
        margin: 0 2 0 0;
        padding: 0;
    }
    EnvPanel Button.env-install,
    EnvPanel Button.env-install:hover,
    EnvPanel Button.env-install:focus {
        width: 11;
        min-width: 11;
        max-width: 11;
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0;
        margin: 0 2 0 0;
        border: none;
        border-top: none;
        border-bottom: none;
        color: white;
        text-style: bold;
        content-align: center middle;
        tint: rgba(0,0,0,0);
    }
    EnvPanel Button.env-install        { background: #155E75; }
    EnvPanel Button.env-install:hover  { background: #1B7A94; }
    EnvPanel Button.env-install:focus  { background: #0E4A5C; }
    EnvPanel #env-tools-row {
        layout: horizontal;
        height: 3;
        margin: 1 0 0 0;
        padding: 0;
        align-vertical: middle;
    }
    EnvPanel .env-spacer { width: 1fr; height: 1; }
    EnvPanel #env-paths {
        height: auto;
        width: 1fr;
        margin: 1 2 0 2;
        padding: 0 1;
        content-align: left middle;
    }
    EnvPanel #btn-op-tools { margin: 0; }
    EnvPanel #env-status {
        height: auto;
        max-height: 12;
        margin: 1 0 0 0;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield UpdatePanel()
            with Vertical(id="env-info"):
                yield Horizontal(classes="env-panel-row", id="env-row-system")     # OS, Pkg, git, github
                yield Horizontal(classes="env-panel-row", id="env-row-runtimes")   # Python, Node, .NET
                yield Horizontal(classes="env-panel-row", id="env-row-pkg-mgrs")   # npm, pnpm, bun
                yield Horizontal(classes="env-panel-row", id="env-row-infra")      # containers, k8s, IaC, clouds
                yield Horizontal(classes="env-panel-row", id="env-row-clis")       # AI CLIs
                yield Horizontal(classes="env-panel-row", id="env-row-local-ai")   # Local AI runtimes (Ollama)
                yield Horizontal(classes="env-panel-row", id="env-row-databases")  # Database CLIs
                yield Horizontal(classes="env-panel-row", id="env-row-editors")    # AI-augmented editors
                with Horizontal(id="env-tools-row"):
                    yield Static("", classes="env-spacer")
                    yield Button("⌬  Tools", id="btn-op-tools", variant="warning")
            yield Static("", id="env-paths")
            yield Static("", id="env-status")

    def on_mount(self) -> None:
        self.query_one("#env-info", Vertical).border_title = "Current setup"
        cached = widget_cache.load_entry(_CACHE_KEY)
        if isinstance(cached, dict):
            self._apply_env(cached)
        self.query_one("#env-status", Static).update("[dim italic]refreshing…[/]")
        self.run_worker(self._refresh_env, thread=True, exclusive=True)

    def _refresh_env(self) -> None:
        fresh = detect_env()
        widget_cache.save_entry(_CACHE_KEY, fresh)

        def _apply() -> None:
            self._apply_env(fresh)
            self.query_one("#env-status", Static).update("")

        self.app.call_from_thread(_apply)

    _LABEL = "bold #5FAFFF"  # light blue for every Label:

    @classmethod
    def _lbl(cls, label: str) -> str:
        return f"[{cls._LABEL}]{label}:[/]"

    def _apply_env(self, env: dict) -> None:
        system = self.query_one("#env-row-system", Horizontal)
        runtimes = self.query_one("#env-row-runtimes", Horizontal)
        pkg_mgrs = self.query_one("#env-row-pkg-mgrs", Horizontal)
        infra = self.query_one("#env-row-infra", Horizontal)
        clis = self.query_one("#env-row-clis", Horizontal)
        local_ai = self.query_one("#env-row-local-ai", Horizontal)
        databases = self.query_one("#env-row-databases", Horizontal)
        editors = self.query_one("#env-row-editors", Horizontal)
        for row in (system, runtimes, pkg_mgrs, infra, clis, local_ai, databases, editors):
            for w in list(row.children):
                w.remove()

        # Row 1 — system & VCS (always show OS / Python; rest only if installed)
        system.mount(Static(
            f"{self._lbl('OS')} {env['os']} {env['release']}", classes="env-cell",
        ))
        if env["pkg_manager"]:
            system.mount(Static(
                f"{self._lbl('Pkg')} {env['pkg_manager']}", classes="env-cell",
            ))
        if env["git"]:
            raw = env.get("git_version") or ""
            parts = raw.split()
            ver = parts[2] if len(parts) >= 3 and parts[0].lower() == "git" else (raw or "installed")
            system.mount(Static(f"{self._lbl('git')} {ver}", classes="env-cell"))
        if env["gh"]:
            login = env.get("gh_login")
            cell = Text()
            cell.append("github:", style=self._LABEL)
            cell.append(" ")
            if login:
                cell.append("● ", style="bright_green")
                cell.append(login, style="bright_green")
            else:
                cell.append("● ", style="bright_red")
                cell.append("(not logged in)", style="bright_red")
            system.mount(Static(cell, classes="env-cell"))

        # Row 2 — runtimes (Python is always present in this app)
        runtimes.mount(Static(f"{self._lbl('Python')} {env['python']}", classes="env-cell"))
        self._mount_installed(runtimes, "Node", env["node"])
        sdks = env.get("dotnet_sdks") or []
        if sdks:
            runtimes.mount(Static(
                f"{self._lbl('.NET')} {', '.join(sdks)}", classes="env-cell",
            ))

        # Row 3 — JS/TS package managers (only installed ones show)
        self._mount_installed(pkg_mgrs, "npm",  env["npm"])
        self._mount_installed(pkg_mgrs, "pnpm", env["pnpm"])
        self._mount_installed(pkg_mgrs, "bun",  env["bun"])

        # Row 3 — containers, orchestration, IaC, cloud CLIs (only installed)
        self._mount_installed(infra, "Docker",    _short_docker_version(env["docker"]))
        self._mount_installed(infra, "Podman",    _short_podman_version(env["podman"]))
        self._mount_installed(infra, "k8s",       env["kubectl"])
        self._mount_installed(infra, "Terraform", _short_terraform_version(env["terraform"]))
        self._mount_installed(infra, "Azure CLI", _short_az_version(env["az"]))
        self._mount_installed(infra, "Google Cloud", _short_gcloud_version(env["gcloud"]))
        self._mount_installed(infra, "AWS CLI",   _short_aws_version(env["aws"]))

        # Row 4 — AI coding CLIs (only installed; no version source → use checkmark)
        for label, key in (
            ("Claude CLI",  "claude"),
            ("Gemini CLI",  "gemini"),
            ("Codex CLI",   "codex"),
            ("OpenCode",    "opencode"),
            ("Grok",        "grok"),
            ("Copilot",     "copilot"),
        ):
            self._mount_present(clis, label, env[key])

        # Row 5 — Local AI runtimes (Ollama gets its own section)
        if env["ollama"]:
            models = env.get("ollama_models") or []
            cell = Text()
            cell.append("Ollama:", style=self._LABEL)
            cell.append(" ")
            if models:
                cell.append("✓ ", style="bright_green")
                cell.append(", ".join(models), style="bright_white")
            else:
                cell.append("✓ ", style="bright_green")
                cell.append("No local models installed", style="yellow")
            local_ai.mount(Static(cell, classes="env-cell"))

        # Row 6 — Database CLIs (only installed)
        for label, key in (
            ("MSSQL",    "sqlcmd"),
            ("Postgres", "psql"),
            ("Supabase", "supabase"),
            ("Neon",     "neonctl"),
        ):
            self._mount_present(databases, label, env[key])

        # Row 7 — AI-augmented editors / IDEs (only installed)
        for label, key in (
            ("Cursor",        "cursor"),
            ("Windsurf",      "windsurf"),
            ("Antigravity",   "antigravity"),
            ("VS Code",       "vscode"),
            ("Rider",         "rider"),
            ("Visual Studio", "visualstudio"),
        ):
            self._mount_present(editors, label, env[key])

        # Hide empty rows so the panel doesn't reserve blank lines for nothing.
        for row in (runtimes, pkg_mgrs, infra, clis, local_ai, databases, editors):
            row.display = bool(row.children)

        exists = "[bright_green](exists)[/]" if env["target_exists"] else "[bright_yellow](will be created)[/]"
        self.query_one("#env-paths", Static).update(
            f"{self._lbl('Source')} [cyan]{GLOBAL_DIR}[/]\n"
            f"{self._lbl('Target')} [cyan]{TARGET}[/] {exists}"
        )

    def _mount_installed(self, parent: Horizontal, label: str, value: str | None) -> None:
        """Mount a `label: <version>` cell only when the tool reports a version."""
        if value:
            parent.mount(Static(f"{self._lbl(label)} {value}", classes="env-cell"))

    def _mount_present(self, parent: Horizontal, label: str, present: bool) -> None:
        """Mount a `label: ✓` cell only when the tool is installed."""
        if present:
            parent.mount(Static(
                f"{self._lbl(label)} [bright_green]✓[/]", classes="env-cell",
            ))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if not bid.startswith("env-install-"):
            return
        event.stop()
        key = bid[len("env-install-"):]
        installer = next((fn for k, _l, fn in ENV_INSTALLERS if k == key), None)
        if installer is None:
            return
        btn = event.button
        btn.disabled = True
        btn.label = "Installing…"
        status = self.query_one("#env-status", Static)
        status.update(
            f"[yellow]⏳ Installing {key}…[/yellow]  "
            f"[dim](running in background — UI stays responsive)[/dim]"
        )
        self.run_worker(
            lambda: self._do_install(key, installer, btn),
            thread=True, exclusive=False,
        )

    def _do_install(self, key: str, installer: Callable[[], tuple[bool, str]], button: Button) -> None:
        try:
            ok, msg = installer()
        except Exception as e:
            ok, msg = False, f"error: {e}"

        def _done() -> None:
            mark = "[green bold]✓[/green bold]" if ok else "[red bold]✗[/red bold]"
            # Tail the captured output so a screenful of apt/winget chatter doesn't blow up the panel.
            lines = msg.splitlines() if msg else []
            snippet = "\n".join(lines[-8:]) if lines else ""
            body = f"\n[dim]{snippet}[/dim]" if snippet else ""
            self.query_one("#env-status", Static).update(
                f"{mark} {key} {'installed' if ok else 'failed'}{body}"
            )
            button.disabled = False
            button.label = "Install"
            self.run_worker(self._refresh_env, thread=True, exclusive=True)
        self.app.call_from_thread(_done)
