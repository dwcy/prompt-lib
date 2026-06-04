# > 250 LoC justified: self-contained cross-platform project launcher shipped as a single static file (no project deps); app config + multi-process supervision + arg parsing must co-locate.
"""Cross-platform project launcher.

One file, runs on Linux/macOS/Windows with only the Python 3 stdlib. Reads
`run.config.json` (a list of apps + their baked dev ports) sitting next to it;
if that file is missing it auto-detects the stack, picks a random port in the
conventional band for each app, and writes the config so ports stay stable.

Usage:
    ./run                 # run the default target (an app, or "all")
    ./run web             # run the app named "web"
    ./run all             # run every app concurrently, output prefixed
    ./run -p 3147         # override the port (single app only)
    ./run web -- --debug  # pass everything after -- to the app's command
    ./run --list          # show configured apps + their ports
"""

from __future__ import annotations

import json
import os
import random
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "run.config.json"

# Conventional dev-port bands per app type. A random port inside the band is
# baked at creation so two local projects don't both grab :3000 / :8000.
PORT_BANDS = {
    "web": (3000, 3999),
    "frontend": (3000, 3999),
    "backend": (8000, 8999),
    "api": (8000, 8999),
    "console": (0, 0),
    "worker": (0, 0),
}


def _pick_port(app_type: str) -> int:
    lo, hi = PORT_BANDS.get(app_type, (3000, 3999))
    if hi == 0:
        return 0
    return random.randint(lo + 1, hi)  # +1 keeps off the exact conventional base


def _detect_apps(root: Path) -> list[dict]:
    """Best-effort stack detection. The creation flow normally writes a precise
    config; this is the fallback so `run.py` is useful even hand-copied."""
    apps: list[dict] = []

    def pm(d: Path) -> str:
        if (d / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (d / "bun.lockb").exists():
            return "bun"
        if (d / "yarn.lock").exists():
            return "yarn"
        return "npm"

    workspaces = (
        [p.parent for p in root.glob("*/package.json")]
        + [p.parent for p in root.glob("apps/*/package.json")]
        + [p.parent for p in root.glob("packages/*/package.json")]
    )
    if (root / "package.json").exists():
        workspaces.insert(0, root)

    for ws in dict.fromkeys(workspaces):
        rel = "." if ws == root else str(ws.relative_to(root)).replace("\\", "/")
        name = ws.name if ws != root else (root.name or "web")
        apps.append(
            {
                "name": name,
                "type": "web",
                "dir": rel,
                "cmd": [pm(ws), "run", "dev"],
                "portEnv": "PORT",
                "port": _pick_port("web"),
            }
        )

    for csproj in list(root.glob("*.csproj")) + list(root.glob("**/*.csproj"))[:1]:
        rel = str(csproj.relative_to(root)).replace("\\", "/")
        apps.append(
            {
                "name": csproj.stem,
                "type": "backend",
                "dir": ".",
                "cmd": [
                    "dotnet",
                    "run",
                    "--project",
                    rel,
                    "--urls",
                    "http://localhost:{port}",
                ],
                "portEnv": None,
                "port": _pick_port("backend"),
            }
        )
        break

    if not apps and (
        (root / "pyproject.toml").exists() or (root / "requirements.txt").exists()
    ):
        apps.append(
            {
                "name": root.name or "app",
                "type": "backend",
                "dir": ".",
                "cmd": ["python", "-m", "app", "--port", "{port}"],
                "portEnv": None,
                "port": _pick_port("backend"),
            }
        )

    if not apps:
        apps.append(
            {
                "name": "app",
                "type": "console",
                "dir": ".",
                "cmd": ["echo", "edit run.config.json to define how this project runs"],
                "portEnv": None,
                "port": 0,
            }
        )
    return apps


def _load_config(root: Path) -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    apps = _detect_apps(root)
    cfg = {"default": "all" if len(apps) > 1 else apps[0]["name"], "apps": apps}
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(
        f"run: wrote {CONFIG.name} ({len(apps)} app(s)) - review it and adjust commands."
    )
    return cfg


def _build(app: dict, port: int, extra: list[str]) -> tuple[list[str], dict, Path]:
    argv = [
        str(port) if a == "{port}" else a.replace("{port}", str(port))
        for a in app["cmd"]
    ]
    if extra:
        argv += extra
    exe = shutil.which(argv[0]) or argv[0]
    argv[0] = exe
    env = dict(os.environ)
    if app.get("portEnv") and port:
        env[app["portEnv"]] = str(port)
    cwd = (ROOT / app.get("dir", ".")).resolve()
    return argv, env, cwd


def _run_one(app: dict, port: int, extra: list[str]) -> int:
    argv, env, cwd = _build(app, port, extra)
    shown = f" :{port}" if port else ""
    print(
        f"run: starting {app['name']}{shown} -> {' '.join(app['cmd'])}  (cwd: {app.get('dir', '.')})"
    )
    try:
        return subprocess.run(argv, env=env, cwd=str(cwd)).returncode
    except FileNotFoundError:
        print(f"run: command not found: {argv[0]}", file=sys.stderr)
        return 127
    except KeyboardInterrupt:
        return 130


def _run_all(apps: list[dict], extra: list[str]) -> int:
    procs: list[tuple[str, subprocess.Popen]] = []
    for app in apps:
        argv, env, cwd = _build(app, app.get("port", 0), extra)
        try:
            p = subprocess.Popen(
                argv,
                env=env,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            print(
                f"run: command not found for {app['name']}: {argv[0]}", file=sys.stderr
            )
            continue
        procs.append((app["name"], p))

    def pump(name: str, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(f"[{name}] {line.rstrip()}")

    threads = [
        threading.Thread(target=pump, args=(n, p), daemon=True) for n, p in procs
    ]
    for t in threads:
        t.start()
    try:
        while any(p.poll() is None for _, p in procs):
            for t in threads:
                t.join(timeout=0.3)
    except KeyboardInterrupt:
        print("\nrun: stopping all apps...")
        for _, p in procs:
            p.terminate()
    return max((p.wait() for _, p in procs), default=0)


def _usage(cfg: dict) -> None:
    print(__doc__)
    print("Configured apps:")
    for a in cfg["apps"]:
        port = f":{a['port']}" if a.get("port") else "(no port)"
        print(f"  {a['name']:<16} {a['type']:<10} {port:<10} {' '.join(a['cmd'])}")
    print(f"\nDefault target: {cfg.get('default')}")


def main(argv: list[str]) -> int:
    cfg = _load_config(ROOT)
    apps = {a["name"]: a for a in cfg["apps"]}

    target, port_override, extra = cfg.get("default", "all"), None, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            extra = argv[i + 1 :]
            break
        elif a in ("-h", "--help", "--list"):
            _usage(cfg)
            return 0
        elif a in ("-p", "--port"):
            i += 1
            port_override = int(argv[i])
        elif a == "--app":
            i += 1
            target = argv[i]
        elif not a.startswith("-"):
            target = a
        else:
            print(f"run: unknown option {a}", file=sys.stderr)
            return 2
        i += 1

    if target == "all":
        if port_override is not None:
            print(
                "run: -p/--port is ignored with 'all' (set per-app ports in run.config.json)",
                file=sys.stderr,
            )
        return _run_all(cfg["apps"], extra)

    app = apps.get(target)
    if app is None:
        print(
            f"run: no app named '{target}'. Known: {', '.join(apps) or '(none)'}",
            file=sys.stderr,
        )
        return 2
    return _run_one(
        app, port_override if port_override is not None else app.get("port", 0), extra
    )


if __name__ == "__main__":
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, signal.default_int_handler)
    sys.exit(main(sys.argv[1:]))
