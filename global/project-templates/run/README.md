# `run` launcher template

Cross-platform project launcher injected into the root of every new project (by `@init-project` and the cabal Init Project wizard).

## Files

| File | Role |
|---|---|
| `run` | POSIX shim — `exec`s `python3 run.py "$@"`. Needs the executable bit on macOS/Linux. |
| `run.cmd` | Windows shim — calls `python run.py %*` (falls back to `py -3`). |
| `run.py` | The launcher. **Static — identical in every project.** Stdlib only, no deps. |

`run.config.json` is **not** in this template — it is per-project. `run.py` self-generates it on first launch (auto-detecting the stack and baking a random dev port per app), or `@init-project` writes a precise one at creation.

## Contract

- `./run` — run the `default` target. `./run <app>` — one app. `./run all` — every app, output prefixed.
- `-p` / `--port <n>` — override the port (single app only; ignored with `all`).
- `<app> -- <args>` — everything after `--` is passed to the app's command.
- `--list` / `-h` — show configured apps and ports.

## Port bands (random at creation, off the bare default)

| type | band |
|---|---|
| `web` / `frontend` | 3001–3999 |
| `backend` / `api` | 8001–8999 |
| `console` / `worker` | 0 (no port) |

Port is injected via `portEnv` (e.g. `PORT`) or a `{port}` token inside `cmd`.

## Editing

Change `run.py` here, then deploy with the apply script so `~/.claude/project-templates/run/` updates. The two surfaces copy these files verbatim — keep `run.py` dependency-free and ASCII-only in printed output (Windows consoles are cp1252).
