#!/usr/bin/env python3
"""
install-dev-tools.py
Checks versions, installs missing tools, upgrades stale ones.
  Windows : winget
  Linux   : dnf (Fedora / RHEL-family)
"""
import json
import platform
import shutil
import subprocess
import sys


RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[1;36m"
GREEN  = "\033[1;32m"
YELLOW = "\033[1;33m"
RED    = "\033[1;31m"
DIM    = "\033[2m"


def banner(text: str) -> None:
    print(f"\n{CYAN}── {text}{RESET}")


def ok(msg: str)   -> None: print(f"  {GREEN}✓  {msg}{RESET}")
def up(msg: str)   -> None: print(f"  {YELLOW}↑  {msg}{RESET}")
def miss(msg: str) -> None: print(f"  {DIM}·  {msg}{RESET}")
def cmd(parts: list) -> None: print(f"  {DIM}$ {' '.join(parts)}{RESET}")


def run(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    cmd(list(args))
    return subprocess.run(list(args), capture_output=True, text=True, check=check)


def run_visible(*args: str) -> None:
    cmd(list(args))
    subprocess.run(list(args))


# ── npm version helpers ────────────────────────────────────────────────────

def npm_installed(pkg: str) -> str | None:
    """Return installed global version of pkg, or None."""
    for mgr in ("pnpm", "npm"):
        if not shutil.which(mgr):
            continue
        r = subprocess.run(
            [mgr, "list", "-g", "--depth=0", "--json"],
            capture_output=True, text=True,
        )
        try:
            data = json.loads(r.stdout or "{}")
            ver = (data.get("dependencies") or data.get("devDependencies") or {}) \
                      .get(pkg, {}).get("version")
            if ver:
                return ver
        except json.JSONDecodeError:
            pass
    return None


def npm_latest(pkg: str) -> str | None:
    r = subprocess.run(["npm", "view", pkg, "version"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def cli_version(binary: str) -> str | None:
    if not shutil.which(binary):
        return None
    r = subprocess.run([binary, "--version"], capture_output=True, text=True)
    return r.stdout.strip().lstrip("v") if r.returncode == 0 else None


def npm_ensure(pkg: str, binary: str | None = None) -> None:
    """Install or upgrade a global npm package."""
    mgr = "pnpm" if shutil.which("pnpm") else "npm"
    installed = cli_version(binary) if binary else npm_installed(pkg)
    latest    = npm_latest(pkg)

    if installed and latest and installed == latest:
        ok(f"{pkg}  {installed}")
        return
    elif installed and latest:
        up(f"{pkg}  {installed} → {latest}")
    else:
        miss(f"{pkg}  {'not installed' if not installed else installed}")

    run_visible(mgr, "install", "-g", pkg)


# ── Windows / winget ───────────────────────────────────────────────────────

def winget_ensure(pkg_id: str, name: str) -> None:
    banner(name)
    check = subprocess.run(
        ["winget", "list", "--id", pkg_id, "--exact"],
        capture_output=True, text=True,
    )
    installed = pkg_id.lower() in check.stdout.lower()

    if installed:
        upgrade = subprocess.run(
            ["winget", "upgrade", "--id", pkg_id, "--exact"],
            capture_output=True, text=True,
        )
        has_upgrade = (
            pkg_id.lower() in upgrade.stdout.lower()
            and "No applicable upgrade" not in upgrade.stdout
        )
        if has_upgrade:
            up(f"{name} — upgrade available")
            run_visible(
                "winget", "upgrade", "--id", pkg_id, "--exact", "--silent",
                "--accept-source-agreements", "--accept-package-agreements",
            )
        else:
            ok(f"{name} — up to date")
    else:
        miss(f"{name} — not installed")
        run_visible(
            "winget", "install", "--id", pkg_id, "--exact", "--silent",
            "--accept-source-agreements", "--accept-package-agreements",
        )


# ── Linux / dnf ───────────────────────────────────────────────────────────

def dnf_ensure(*pkgs: str) -> None:
    run_visible("sudo", "dnf", "install", "-y", *pkgs)


# ── Entry point ────────────────────────────────────────────────────────────

system = platform.system()
print(f"\n{BOLD}Dev Tools Installer{RESET}  [{system}]")
print("─" * 42)

if system == "Windows":
    winget_ensure("Python.Python.3",    "Python (latest)")
    winget_ensure("Microsoft.DotNet.SDK.9", ".NET SDK 9")
    winget_ensure("OpenJS.NodeJS.LTS",  "Node.js LTS")
    winget_ensure("GitHub.cli",         "GitHub CLI")

elif system == "Linux":
    print(f"{DIM}Assuming Fedora / dnf{RESET}")
    banner("Python + pip")
    dnf_ensure("python3", "python3-pip", "python3-pipx")
    banner(".NET SDK 9")
    dnf_ensure("dotnet-sdk-9.0")
    banner("Node.js + npm")
    dnf_ensure("nodejs", "npm")
    banner("GitHub CLI")
    dnf_ensure("gh")

else:
    print(f"{RED}Unsupported platform: {system}{RESET}")
    sys.exit(1)

# pnpm must come first — subsequent packages prefer it
banner("pnpm  (preferred Node package manager)")
if not shutil.which("pnpm"):
    miss("pnpm not installed")
    run_visible("npm", "install", "-g", "pnpm")
else:
    npm_ensure("pnpm", binary="pnpm")

banner("Claude Code CLI")
npm_ensure("@anthropic-ai/claude-code", binary="claude")

banner("Gemini CLI")
npm_ensure("@google/gemini-cli", binary="gemini")

banner("Codex CLI")
npm_ensure("@openai/codex", binary="codex")

print(f"\n{GREEN}{BOLD}✓ Done.{RESET}  Restart your terminal to pick up PATH changes.\n")
