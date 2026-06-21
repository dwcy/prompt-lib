# Research: Headroom as a Managed Tool

**Feature**: 009-headroom-tool | **Date**: 2026-06-21

This document holds (A) the resolved technical decisions for the managed-tool integration and (B) the investigate-only verdict on the transparent-proxy path (FR-009). Section B is the spec's research deliverable; its **Verdict** is filled empirically during the implementation Phase-0 spike and must not gate any shipped code (FR-010).

---

## A. Technical decisions

### A1. Headroom identity & maturity
- **Decision**: Treat Headroom as a real, actively-maintained third-party dependency worth managing.
- **Rationale**: Verified via GitHub API on 2026-06-21 — `chopratejas/headroom`, 44,072 stars, 3,068 forks, created 2026-01-07, last push same day, Apache-2.0, not archived, Python. Homepage `https://headroom-docs.vercel.app/docs`.
- **Alternatives considered**: Copy compression *patterns* into prompt-lib instead of managing the tool — rejected; reinventing a 44k-star compressor is out of scope and the user chose the "manage as a tool" path.

### A2. Install mechanism
- **Decision**: Install via `uv tool install` (auto-provisioning `uv` first), mirroring `setup/src/cabal/installers/specify.py`. Status via `shutil.which("headroom")` + `headroom --version`.
- **Rationale**: Headroom is a Python 3.10+ package distributed on PyPI as `headroom-ai`. `uv tool` gives an isolated, upgradeable global CLI exactly like the existing `specify` installer; `cabal.installers.uv.uv_install` already exists to bootstrap `uv`. Consistent with the repo's Python-CLI install convention; avoids `pipx`/`pip --user` PATH ambiguity.
- **Alternatives considered**: `pip install --user` (PATH/version-floor issues), winget (not packaged there), npm (the npm `headroom-ai` is the TS SDK, not the Python CLI). Rejected.
- **OPEN (confirm in spike)**: exact extra needed for the MCP server — `uv tool install "headroom-ai[mcp]"` vs `[all]` vs `--with`. `uv tool install` requires the extra on the package spec, not a post-install step; confirm the MCP server binary is present after install.

### A3. MCP registration mechanism
- **Decision**: Add a `headroom` entry to `setup/mcp-templates.json` with `transport: stdio`, `default_enabled: false`, and register through the existing `claude_mcp_add_from_template` (which applies the Windows `cmd /s /c` wrapper automatically) — surfaced by `enumerate_mcp_servers` as a `template`-scope server until registered.
- **Rationale**: This is the canonical path every other managed MCP server already uses; no new registration code. `default_enabled: false` because compression is **manual/opt-in** (Claude must call the compress tool) and the server adds 3 tools to every session's budget — it should not be foisted on every machine.
- **Alternatives considered**: Headroom's own `headroom mcp install` self-registration — rejected as the primary path because it writes Claude config outside cabal's template machinery, bypassing the manager's scope/visibility model. (It may still be used inside the spike to *discover* the exact invocation it registers.)
- **OPEN (confirm in spike)**: the exact stdio `command`/`args` the server runs. Plan assumes `command: "headroom"`, `args: ["mcp", "serve"]`. Confirm by inspecting what `headroom mcp install` writes to `~/.claude.json`, or `headroom mcp --help`.

### A4. Tool-registry wiring
- **Decision**: In `setup/src/cabal/tools.py`: import `headroom_install`/`headroom_status`; append a `Tool(key="headroom", ...)` to `TOOLS`; add `("headroom", "Headroom", headroom_install)` to `ENV_INSTALLERS`; add `"headroom"` to the `"AI CLIs"` group in `ENV_TOOL_GROUPS`. No `WINGET_IDS` entry.
- **Rationale**: Matches how `specify`, `skills`, `vercel-plugin`, and the AI CLIs are registered. No winget package exists, so it stays out of the winget outdated-check (best-effort "Latest" is acceptable for v1).
- **Alternatives considered**: A PyPI-latest outdated check (like the npm one for `claude`/`skills`) — deferred; not required for v1.

### A5. Scope boundaries
- **Decision**: No auto-compression nudge (hook/skill) and no `headroom learn` adoption in this feature.
- **Rationale**: Keeps 009 shippable and low-risk; both are larger design questions (the nudge changes session behavior; `headroom learn` overlaps the existing `self-improvement` skill and would trip Constitution Gate 5). Flagged for separate future specs.

---

## B. Proxy / wrap mode on subscription auth (investigate-only — FR-009)

**Question**: Does `headroom wrap claude` / `headroom proxy` transparently reduce interactive Claude Code token usage when Claude Code is authenticated via a **subscription/OAuth login (no `ANTHROPIC_API_KEY`)**, as on the target Windows machine?

**Why it matters**: Headroom's headline "4× your Claude Code usage" depends on the proxy intercepting API traffic. Subscription/OAuth traffic goes to a fixed Anthropic endpoint under OAuth; redirecting it through a local proxy is undocumented for this auth mode and may require an API key, may break OAuth, or may violate terms. We must not let any shipped behavior assume this works.

**Investigation steps (run in the implementation Phase-0 spike)**:
1. Determine whether `headroom wrap claude` sets `ANTHROPIC_BASE_URL` (or equivalent) and whether the Claude CLI honors it while using subscription/OAuth credentials.
2. Attempt a real wrapped session with no API key set; observe whether auth succeeds, fails, or silently falls back.
3. Check Headroom + Claude Code docs/terms for any statement on proxying subscription traffic and on token attribution.
4. If it runs, measure token/cost savings on one representative coding session; if it does not, record the exact failure.

**Findings**: _[pending — fill during implementation spike]_

**Risks observed**: _[pending]_

**Measured savings (if any)**: _[pending]_

**Verdict** (pursue / shelve / reject): _[pending — state explicitly so no future work re-assumes the headline savings apply on subscription auth]_
