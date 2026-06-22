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

> **⛔ SPIKE FINDING (T001 — 2026-06-22): install FAILS on Windows; the planned one-click mechanism does not work as-is.**
>
> - PyPI `headroom-ai` 0.26.0 ships wheels **only** for `cp310-abi3` macOS-arm64, Linux-aarch64, and Linux-x86_64, plus an sdist. **There is no Windows wheel.**
> - On Windows, `uv tool install "headroom-ai[mcp]"` therefore falls back to building the sdist, which compiles a **Rust native extension** (`crates/headroom-py` via maturin). That build requires the **MSVC C++ build tools** (`link.exe` / Visual Studio Build Tools "Desktop development with C++") — Rust's own error emits: *"note: VS Code is a different product, and is not sufficient."*
> - On the target machine `rustc`/`cargo`/`cl`/MSVC `link` are absent, so the build fails (`maturin failed → cargo exit 101`). A user clicking **Install** in the cabal Tools view would hit this identical failure.
> - Implication: a clean "one-click `uv tool install`" on Windows is **not achievable** without first provisioning a heavyweight C++/Rust toolchain. This invalidates the as-written installer assumption and must be resolved before T004/T005 (see decision needed below).
> - Side effect: **T002 and T003 are blocked locally** — the MCP-serve invocation cannot be confirmed empirically and the proxy investigation cannot be run, because `headroom` will not install/run on this machine.

**Resolution (user decision 2026-06-22): auto-provision the toolchain.** On Windows the installer will, when `headroom` is absent and a build is required:
1. Ensure `uv` (`cabal.installers.uv.uv_install`).
2. Ensure a Rust toolchain — `winget install --id Rustlang.Rustup` (installs `rustup`, which provides `cargo`/`rustc` under `%USERPROFILE%\.cargo\bin`). Diagnostics confirmed neither `rustup` nor `cargo` is present, so Rust must be provisioned, not just PATH-fixed.
3. Ensure the MSVC C++ build tools — `winget install --id Microsoft.VisualStudio.2022.BuildTools` with the C++ workload (`--override "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --quiet --wait --norestart"`). `vswhere` found no VC.Tools component, so this is required for the maturin/cargo link step.
4. `uv tool install "headroom-ai[mcp]"` (now builds the native extension successfully).

This is heavyweight (multi-GB VS Build Tools download + a Rust compile) and the build can exceed `_common._run_install`'s 600 s cap, so the toolchain + build steps use their own longer timeouts. `headroom_status()` still keys off `shutil.which("headroom")`. macOS/Linux are unaffected — `cp310-abi3` wheels install with no toolchain.

### A3. MCP registration mechanism
- **Decision**: Add a `headroom` entry to `setup/mcp-templates.json` with `transport: stdio`, `default_enabled: false`, and register through the existing `claude_mcp_add_from_template` (which applies the Windows `cmd /s /c` wrapper automatically) — surfaced by `enumerate_mcp_servers` as a `template`-scope server until registered.
- **Rationale**: This is the canonical path every other managed MCP server already uses; no new registration code. `default_enabled: false` because compression is **manual/opt-in** (Claude must call the compress tool) and the server adds 3 tools to every session's budget — it should not be foisted on every machine.
- **Alternatives considered**: Headroom's own `headroom mcp install` self-registration — rejected as the primary path because it writes Claude config outside cabal's template machinery, bypassing the manager's scope/visibility model. (It may still be used inside the spike to *discover* the exact invocation it registers.)
- **CONFIRMED (docs — UNVERIFIED on this machine, T002)**: the stdio server is launched by **`headroom mcp serve`**. Headroom docs (`/docs/mcp`) state: *"Serve — stdio (default, called by Claude Code): `headroom mcp serve`"* (also `headroom mcp serve --debug`). Tools exposed: `headroom_compress`, `headroom_retrieve`, `headroom_stats`. So the template uses `command: "headroom"`, `args: ["mcp", "serve"]`. ⚠️ Not empirically verified because `headroom` will not install on this Windows machine (see finding above); re-confirm on a Linux/WSL box or after the toolchain is provisioned by inspecting what `headroom mcp install` writes to `~/.claude.json`.

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

**Findings (docs-based — UNVERIFIED on this machine, T003)**:
- Headroom's proxy works by env-var redirection: docs (`/docs/proxy`) show `ANTHROPIC_BASE_URL=http://localhost:8787 claude`. So `headroom wrap claude` / `headroom proxy` simply points the Claude CLI at a local Headroom proxy that forwards to Anthropic.
- The docs discuss **only API-key scenarios**. There is **zero** documentation about subscription/OAuth (Pro/Max, no `ANTHROPIC_API_KEY`) — no statement of support and no explicit disclaimer.
- Could not be run locally: `headroom` will not install on this Windows machine (no wheel + missing build toolchain), so no live wrapped session and no measured savings were obtained.

**Risks observed**:
- **Auth**: subscription Claude Code authenticates with short-lived OAuth bearer tokens against Anthropic's fixed endpoint. Routing that through a third-party local proxy means the proxy handles/forwards those tokens; whether OAuth survives the `ANTHROPIC_BASE_URL` redirect is undocumented and unverified.
- **Terms / attribution**: interposing an unofficial proxy on consumer-subscription traffic is a grey area (ToS, token/usage attribution). Not something to enable silently.
- **Compression requires request rewriting**: the proxy's value depends on mutating request bodies in flight, which is more invasive than passthrough and a larger correctness/safety surface on subscription traffic.

**Measured savings (if any)**: none obtained — install blocked on this machine.

**Verdict — SHELVE (docs-based, UNVERIFIED)**: Do not pursue the proxy/wrap path for prompt-lib's subscription-auth Claude Code at this time. It is undocumented for non-API-key auth, unverified here, and carries auth/ToS risk. The MCP-tool path (Stories 1–2) is the supported, in-scope integration. Re-evaluate ONLY if (a) Headroom documents subscription/OAuth support, and (b) it can be measured on a runnable (Linux/WSL or toolchain-provisioned) box. **No future work in this repo may assume the "4× usage" headline applies on subscription auth** until that re-evaluation happens.
