# -*- coding: utf-8 -*-
"""Plain-text env summary block (no install controls).

Per-tool version formatters strip CLI noise into a short version string for
the summary display. EnvPanel adds the install buttons; this module is the
text-only fallback used by screens that don't need interactivity.
"""

from __future__ import annotations


def _short_docker_version(raw: str | None) -> str | None:
    # "Docker version 24.0.7, build afdd53b" → "24.0.7"
    if not raw:
        return None
    parts = raw.split()
    return parts[2].rstrip(",") if len(parts) >= 3 and parts[0].lower() == "docker" else raw


def _short_podman_version(raw: str | None) -> str | None:
    # "podman version 4.7.0" → "4.7.0"
    if not raw:
        return None
    parts = raw.split()
    return parts[-1] if parts else raw


def _short_terraform_version(raw: str | None) -> str | None:
    # "Terraform v1.7.0" → "v1.7.0"
    if not raw:
        return None
    parts = raw.split()
    if len(parts) >= 2 and parts[0].lower() == "terraform":
        return parts[1]
    return raw


def _short_az_version(raw: str | None) -> str | None:
    # First line of `az --version`: "azure-cli                         2.50.0"
    if not raw:
        return None
    parts = raw.split()
    return parts[-1] if parts else raw


def _short_gcloud_version(raw: str | None) -> str | None:
    # First line: "Google Cloud SDK 458.0.1"
    if not raw:
        return None
    parts = raw.split()
    return parts[-1] if parts else raw


def _short_aws_version(raw: str | None) -> str | None:
    # "aws-cli/2.15.0 Python/3.11.6 ..." → "2.15.0"
    if not raw:
        return None
    if raw.startswith("aws-cli/"):
        return raw.split()[0].removeprefix("aws-cli/")
    return raw


def _version_field(label: str, value: str | None) -> str:
    head = f"[bold bright_blue]{label}:[/] "
    return head + (f"[white]{value}[/]" if value else "")


def _presence_field(label: str, present: bool) -> str:
    head = f"[bold bright_blue]{label}:[/] "
    return head + ("[green]✓ installed[/]" if present else "")


def render_env_summary() -> str:
    """Plain-text env summary (no install controls). EnvPanel adds buttons inline."""
    from cabal.env_detect import detect_env
    from cabal._paths import GLOBAL_DIR, TARGET

    env = detect_env()
    pkg = env["pkg_manager"]
    pkg_str = f"[green]{pkg}[/]" if pkg else "[red]✗ none detected[/]"
    git_mark = "[green]✓[/]" if env["git"] else "[red]✗[/]"
    bash_mark = "[green]✓[/]" if env["bash"] else "[red]✗[/]"

    parts = [
        f"[bold bright_blue]OS:[/] {env['os']} {env['release']}    ",
        f"[bold bright_blue]Pkg:[/] {pkg_str}    ",
        f"[bold bright_blue]Python:[/] {env['python']}    ",
        _version_field("Node", env["node"]) + "    ",
        _version_field("npm", env["npm"]) + "    ",
        _version_field("Docker", _short_docker_version(env["docker"])) + "    ",
        f"[bold bright_blue]git/bash:[/] {git_mark}/{bash_mark}\n",
        _presence_field("Claude CLI", env["claude"]) + "    ",
        _presence_field("Gemini CLI", env["gemini"]) + "    ",
        _presence_field("Codex CLI", env["codex"]) + "    ",
        _presence_field("OpenCode", env["opencode"]) + "    ",
        _presence_field("gh", env["gh"]),
        f"\n[bold bright_blue]Source:[/] [cyan]{GLOBAL_DIR}[/]\n",
        f"[bold bright_blue]Target:[/] [cyan]{TARGET}[/] ",
        "[green](exists)[/]" if env["target_exists"] else "[yellow](will be created)[/]",
    ]
    return "".join(parts)
