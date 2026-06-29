# -*- coding: utf-8 -*-
"""EnvPanel — env summary with inline Install buttons per detected gap."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Static

from cabal import widget_cache
from cabal._paths import CODEX_DIR, GEMINI_DIR, GLOBAL_DIR, TARGET
from cabal.env_detect import detect_env
from cabal.env_summary import (
    _short_aws_version,
    _short_az_version,
    _short_docker_version,
    _short_gcloud_version,
    _short_podman_version,
    _short_terraform_version,
)
from cabal.tools import ENV_INSTALLERS, _tool_unavailable_reason
from cabal.widgets.update_panel import UpdatePanel

_CACHE_KEY = "env"
_INNER_BORDER_TITLE = "[bold #FF85B3]Overview[/]"
_INNER_BORDER_SUBTITLE = "[bold #CC006B][@click=screen.readme]README[/][/]"
_LABEL_STYLE = "bold #5FAFFF"
_VERSION_STATUS_STYLE = "bold #55FFA5"
_VERSION_METADATA_STYLE = "bold #FF85B3"
_ENV_DEFAULTS = {
    "os": "Unknown",
    "release": "",
    "python": "unknown",
    "pkg_manager": None,
    "git": False,
    "gh": False,
    "node": None,
    "npm": None,
    "pnpm": None,
    "bun": None,
    "uv": None,
    "dotnet_sdks": [],
    "docker": None,
    "podman": None,
    "kubectl": None,
    "terraform": None,
    "az": None,
    "gcloud": None,
    "aws": None,
    "sqlcmd": False,
    "psql": False,
    "supabase": False,
    "neonctl": False,
    "cursor": False,
    "windsurf": False,
    "antigravity": False,
    "vscode": False,
    "rider": False,
    "visualstudio": False,
}


class EnvPanel(Widget):
    """Env summary with real, compact Install buttons inline next to each missing tool."""

    DEFAULT_CSS = """
    EnvPanel {
        height: auto;
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
        border: round #CC006B;
    }
    EnvPanel .env-panel-row,
    EnvPanel #env-row-system,
    EnvPanel #env-row-runtimes,
    EnvPanel #env-row-pkg-mgrs,
    EnvPanel #env-row-infra,
    EnvPanel #env-row-clis,
    EnvPanel #env-row-local-ai,
    EnvPanel #env-row-databases,
    EnvPanel #env-row-editors {
        layout: horizontal;
        height: 1;
        margin: 1 0;
        padding: 0;
    }
    EnvPanel .env-cell {
        width: auto;
        height: 1;
        margin: 0 2 0 0;
        padding: 0;
    }
    EnvPanel #env-version-row {
        layout: horizontal;
        height: auto;
        margin: 0 0 1 0;
        padding: 0;
        align-vertical: middle;
    }
    EnvPanel #env-version-meta {
        width: 1fr;
        height: 1;
        margin: 0;
        padding: 0;
        content-align: left middle;
    }
    EnvPanel #env-info UpdatePanel {
        width: auto;
        height: auto;
        margin: 0;
        padding: 0;
    }
    EnvPanel #env-info #update-row {
        width: auto;
        margin: 0;
        padding: 0;
        align-horizontal: right;
    }
    EnvPanel #env-info #env-refresh {
        width: auto;
        padding: 0;
        content-align: right middle;
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
        margin: 1 0 0 0;
        padding: 0;
        content-align: left middle;
    }
    EnvPanel #btn-github,
    EnvPanel #btn-github:focus {
        background: #16A34A;
        border: none;
        border-top: tall #86EFAC;
        border-bottom: tall #166534;
        color: white;
        margin: 0 2 0 0;
    }
    EnvPanel #btn-github:hover {
        background: #15803D;
        border: none;
        border-top: tall #22C55E;
        border-bottom: tall #14532D;
        color: white;
    }
    EnvPanel #btn-env,
    EnvPanel #btn-env:focus {
        background: black;
        color: white;
        margin: 0 2 0 0;
    }
    EnvPanel #btn-env:hover { background: #1A1A1A; color: white; }
    EnvPanel #btn-op-tools { margin: 0; }
    EnvPanel #env-status {
        display: none;
        height: auto;
        max-height: 12;
        margin: 1 0 0 0;
        padding: 0 2 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="env-info"):
                with Horizontal(id="env-version-row"):
                    yield Static(
                        self._format_update_metadata({"status": "checking"}),
                        id="env-version-meta",
                    )
                    yield UpdatePanel(
                        on_result=self._set_update_metadata,
                        show_status=False,
                    )
                yield Horizontal(
                    classes="env-panel-row", id="env-row-system"
                )  # OS, Pkg, git, github
                yield Horizontal(
                    classes="env-panel-row", id="env-row-runtimes"
                )  # Python, Node, .NET
                yield Horizontal(
                    classes="env-panel-row", id="env-row-pkg-mgrs"
                )  # npm, pnpm, bun
                yield Horizontal(
                    classes="env-panel-row", id="env-row-infra"
                )  # containers, k8s, IaC, clouds
                yield Horizontal(classes="env-panel-row", id="env-row-clis")  # AI CLIs
                yield Horizontal(
                    classes="env-panel-row", id="env-row-local-ai"
                )  # Local AI runtimes (Ollama)
                yield Horizontal(
                    classes="env-panel-row", id="env-row-databases"
                )  # Database CLIs
                yield Horizontal(
                    classes="env-panel-row", id="env-row-editors"
                )  # AI-augmented editors
                yield Static("", id="env-paths")
                with Horizontal(id="env-tools-row"):
                    yield Static("", classes="env-spacer")
                    yield Button("GitHub", id="btn-github")
                    yield Button("Env vars", id="btn-env")
                    yield Button("⌬  Tools", id="btn-op-tools", variant="warning")
            yield Static("", id="env-status")

    def on_mount(self) -> None:
        info = self.query_one("#env-info", Vertical)
        info.border_title = _INNER_BORDER_TITLE
        info.border_subtitle = _INNER_BORDER_SUBTITLE
        cached = widget_cache.load_entry(_CACHE_KEY)
        if isinstance(cached, dict):
            self._apply_env(cached)
        self.refresh_env()

    def _set_update_metadata(self, result: dict) -> None:
        self.query_one("#env-version-meta", Static).update(
            self._format_update_metadata(result)
        )

    @staticmethod
    def _format_update_metadata(result: dict) -> str:
        status = result.get("status")
        unknown = "[dim]unknown[/dim]"
        cabal_label = f"[{_LABEL_STYLE}]Cabal:[/]"
        hash_label = f"[{_LABEL_STYLE}]hash:[/]"
        date_label = f"[{_LABEL_STYLE}]date:[/]"
        if status == "up_to_date":
            date = result.get("date") or unknown
            return (
                f"{cabal_label} [{_VERSION_STATUS_STYLE}]✓ Latest version[/]  "
                f"{hash_label} "
                f"[{_VERSION_METADATA_STYLE}]{result.get('hash', 'unknown')}[/]  "
                f"{date_label} "
                f"[{_VERSION_METADATA_STYLE}]{date}[/]"
            )
        if status == "behind":
            count = result.get("behind_count")
            count_str = f" ({count})" if count else ""
            return (
                f"{cabal_label} [yellow bold]⬆ Update available{count_str}[/yellow bold]  "
                f"{hash_label} "
                f"[{_VERSION_METADATA_STYLE}]{result.get('remote', 'unknown')}[/]  "
                f"{date_label} {unknown}"
            )
        if status == "checking":
            return (
                f"{cabal_label} [dim]Checking for updates…[/dim]  "
                f"{hash_label} [dim]checking[/dim]  "
                f"{date_label} [dim]checking[/dim]"
            )
        if status == "no_upstream":
            return (
                f"{cabal_label} [dim]Updates not tracked[/dim]  "
                f"{hash_label} [dim]no upstream[/dim]  "
                f"{date_label} {unknown}"
            )
        if status == "no_git":
            return (
                f"{cabal_label} [dim]Git not found[/dim]  "
                f"{hash_label} {unknown}  "
                f"{date_label} {unknown}"
            )
        return (
            f"{cabal_label} [dim]Could not reach remote[/dim]  "
            f"{hash_label} {unknown}  "
            f"{date_label} {unknown}"
        )

    def refresh_env(self) -> None:
        """Re-scan the host env in a worker (spinner shown, stale-while-revalidate).

        Called on mount and after a tool install/update so the panel reflects the
        new state without an app restart.
        """
        self._start_refresh_status()
        self.run_worker(self._refresh_env, thread=True, exclusive=True)

    def _refresh_env(self) -> None:
        fresh = detect_env()
        widget_cache.save_entry(_CACHE_KEY, fresh)

        def _apply() -> None:
            self._apply_env(fresh)
            self._stop_refresh_status()

        self.app.call_from_thread(_apply)

    _SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def _start_refresh_status(self) -> None:
        """Animate a spinner on the update row while detecting env."""
        status = self.query_one("#env-refresh", Static)
        status.display = True
        state: dict = {"frame": 0}

        def tick() -> None:
            frame = self._SPINNER_FRAMES[state["frame"]]
            state["frame"] = (state["frame"] + 1) % len(self._SPINNER_FRAMES)
            status.update(f"[cyan]{frame}[/] [dim italic]refreshing…[/]")

        tick()
        self.query_one(UpdatePanel).sync_visibility()
        state["timer"] = self.set_interval(0.08, tick)
        self._refresh_spinner = state

    def _stop_refresh_status(self) -> None:
        state = getattr(self, "_refresh_spinner", None)
        if state and "timer" in state:
            state["timer"].stop()
        self._refresh_spinner = None
        try:
            indicator = self.query_one("#env-refresh", Static)
            indicator.update("")
            indicator.display = False
            self.query_one(UpdatePanel).sync_visibility()
        except Exception:
            pass

    _LABEL = _LABEL_STYLE  # light blue for every Label:

    @classmethod
    def _lbl(cls, label: str) -> str:
        return f"[{cls._LABEL}]{label}:[/]"

    def _apply_env(self, env: dict) -> None:
        env = {**_ENV_DEFAULTS, **env}
        system = self.query_one("#env-row-system", Horizontal)
        runtimes = self.query_one("#env-row-runtimes", Horizontal)
        pkg_mgrs = self.query_one("#env-row-pkg-mgrs", Horizontal)
        infra = self.query_one("#env-row-infra", Horizontal)
        clis = self.query_one("#env-row-clis", Horizontal)
        local_ai = self.query_one("#env-row-local-ai", Horizontal)
        databases = self.query_one("#env-row-databases", Horizontal)
        editors = self.query_one("#env-row-editors", Horizontal)
        for row in (
            system,
            runtimes,
            pkg_mgrs,
            infra,
            clis,
            local_ai,
            databases,
            editors,
        ):
            for w in list(row.children):
                w.remove()

        # Row 1 — system & VCS (always show OS / Python; rest only if installed)
        system.mount(
            Static(
                f"{self._lbl('OS')} {env['os']} {env['release']}",
                classes="env-cell",
            )
        )
        if env["pkg_manager"]:
            system.mount(
                Static(
                    f"{self._lbl('Pkg')} {env['pkg_manager']}",
                    classes="env-cell",
                )
            )
        if env["git"]:
            raw = env.get("git_version") or ""
            parts = raw.split()
            ver = (
                parts[2]
                if len(parts) >= 3 and parts[0].lower() == "git"
                else (raw or "installed")
            )
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
        runtimes.mount(
            Static(f"{self._lbl('Python')} {env['python']}", classes="env-cell")
        )
        self._mount_installed(runtimes, "Node", env["node"])
        sdks = env.get("dotnet_sdks") or []
        if sdks:
            runtimes.mount(
                Static(
                    f"{self._lbl('.NET')} {', '.join(sdks)}",
                    classes="env-cell",
                )
            )

        # Row 3 — JS/TS package managers (only installed ones show)
        self._mount_installed(pkg_mgrs, "npm", env["npm"])
        self._mount_installed(pkg_mgrs, "pnpm", env["pnpm"])
        self._mount_installed(pkg_mgrs, "bun", env["bun"])
        self._mount_installed(pkg_mgrs, "uv", env["uv"])

        # Row 3 — containers, orchestration, IaC, cloud CLIs (only installed)
        self._mount_installed(infra, "Docker", _short_docker_version(env["docker"]))
        self._mount_installed(infra, "Podman", _short_podman_version(env["podman"]))
        self._mount_installed(infra, "k8s", env["kubectl"])
        self._mount_installed(
            infra, "Terraform", _short_terraform_version(env["terraform"])
        )
        self._mount_installed(infra, "Azure CLI", _short_az_version(env["az"]))
        self._mount_installed(
            infra, "Google Cloud", _short_gcloud_version(env["gcloud"])
        )
        self._mount_installed(infra, "AWS CLI", _short_aws_version(env["aws"]))

        # Row 4 — AI coding CLIs (only installed; no version source → use checkmark)
        for label, key in (
            ("Claude CLI", "claude"),
            ("Gemini CLI", "gemini"),
            ("Hugging Face CLI", "huggingface"),
            ("Codex CLI", "codex"),
            ("OpenCode", "opencode"),
            ("Grok", "grok"),
            ("Copilot CLI", "copilot"),
            ("Vercel Skills CLI", "skills"),
        ):
            self._mount_present(clis, label, env.get(key, False))

        # Row 5 — Local AI runtimes (Ollama gets its own section)
        if env.get("ollama"):
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
        vllm_reason = _tool_unavailable_reason("vllm")
        vllm_value = env.get("vllm")
        if vllm_value:
            cell = Text()
            cell.append("vLLM:", style=self._LABEL)
            cell.append(" ")
            cell.append("OK ", style="bright_green")
            if isinstance(vllm_value, str):
                cell.append(vllm_value, style="bright_white")
            else:
                cell.append("installed", style="bright_white")
            local_ai.mount(Static(cell, classes="env-cell"))
        elif vllm_reason:
            cell = Text()
            cell.append("vLLM:", style=self._LABEL)
            cell.append(" ")
            cell.append(vllm_reason, style="yellow")
            local_ai.mount(Static(cell, classes="env-cell"))

        # Row 6 — Database CLIs (only installed)
        for label, key in (
            ("MSSQL", "sqlcmd"),
            ("Postgres", "psql"),
            ("Supabase", "supabase"),
            ("Neon", "neonctl"),
        ):
            self._mount_present(databases, label, env[key])

        # Row 7 — AI-augmented editors / IDEs (only installed)
        for label, key in (
            ("Cursor", "cursor"),
            ("Windsurf", "windsurf"),
            ("Antigravity", "antigravity"),
            ("VS Code", "vscode"),
            ("Rider", "rider"),
            ("Visual Studio", "visualstudio"),
        ):
            self._mount_present(editors, label, env[key])

        # Hide empty rows so the panel doesn't reserve blank lines for nothing.
        for row in (runtimes, pkg_mgrs, infra, clis, local_ai, databases, editors):
            row.display = bool(row.children)

        self._update_paths()

    def _update_paths(self) -> None:
        claude_mark = (
            "[bright_green](exists)[/]"
            if TARGET.exists()
            else "[bright_yellow](will be created)[/]"
        )
        self.query_one("#env-paths", Static).update(
            f"{self._lbl('Source')} [#FFAF5F]{GLOBAL_DIR}[/]\n"
            f"{self._lbl('Claude')} [cyan]{TARGET}[/] {claude_mark}\n"
            f"{self._lbl('OpenAI')} [cyan]{CODEX_DIR}[/] {self._dir_mark(CODEX_DIR)}\n"
            f"{self._lbl('Gemini')} [cyan]{GEMINI_DIR}[/] {self._dir_mark(GEMINI_DIR)}"
        )

    @staticmethod
    def _dir_mark(path: Path) -> str:
        return "[bright_green](exists)[/]" if path.exists() else "[dim](not found)[/]"

    def refresh_project(self) -> None:
        """Re-render the paths block after the active project changes."""
        try:
            self._update_paths()
        except Exception:
            pass

    def _mount_installed(
        self, parent: Horizontal, label: str, value: str | None
    ) -> None:
        """Mount a `label: <version>` cell only when the tool reports a version."""
        if value:
            parent.mount(Static(f"{self._lbl(label)} {value}", classes="env-cell"))

    def _mount_present(self, parent: Horizontal, label: str, present: bool) -> None:
        """Mount a `label: ✓` cell only when the tool is installed."""
        if present:
            parent.mount(
                Static(
                    f"{self._lbl(label)} [bright_green]✓[/]",
                    classes="env-cell",
                )
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if not bid.startswith("env-install-"):
            return
        event.stop()
        key = bid[len("env-install-") :]
        installer = next((fn for k, _l, fn in ENV_INSTALLERS if k == key), None)
        if installer is None:
            return
        btn = event.button
        btn.disabled = True
        btn.label = "Installing…"
        status = self.query_one("#env-status", Static)
        status.display = True
        status.update(
            f"[yellow]⏳ Installing {key}…[/yellow]  "
            f"[dim](running in background — UI stays responsive)[/dim]"
        )
        self.run_worker(
            lambda: self._do_install(key, installer, btn),
            thread=True,
            exclusive=False,
        )

    def _do_install(
        self, key: str, installer: Callable[[], tuple[bool, str]], button: Button
    ) -> None:
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
            status = self.query_one("#env-status", Static)
            status.display = True
            status.update(f"{mark} {key} {'installed' if ok else 'failed'}{body}")
            button.disabled = False
            button.label = "Install"
            self.run_worker(self._refresh_env, thread=True, exclusive=True)

        self.app.call_from_thread(_done)
