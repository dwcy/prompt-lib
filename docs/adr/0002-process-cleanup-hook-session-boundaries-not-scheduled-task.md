# 0002. Process-Cleanup Hook Triggers on Session Boundaries, Not a Scheduled Task

Date: 2026-07-12

## Status

Accepted

## Context

Claude Code / Claude Desktop sessions on Windows can leave orphaned helper processes behind (`node.exe`, `claude.exe`, `sh.exe`, `bash.exe`, and small unix helpers like `rg.exe`), eating RAM and disk I/O over time. Three loose PowerShell scripts already existed in `C:\projects\` to diagnose and clean these up, validated manually:

- `Claude-ProcessCheck.ps1` — report-only by default; `-Kill` terminates only orphans whose parent process is gone, with an explicit Claude-relatedness filter (command line matches `claude|anthropic|\.claude\|ripgrep`, or the process name is one of the known helper binaries) so a live, unrelated `node.exe` dev server is never touched.
- `Claude-ProcessCleanup.ps1` — a blunter 3-pass sweep with no relatedness filter; riskier to run unattended.
- `NodeProcess-Check.ps1` — pure diagnostic, never kills anything.

None of these were wired into any automation; cleanup only happened when manually invoked. The request was to run cleanup automatically, ideally "when things start to turn into syrup slow" — i.e., during a long working session as process buildup accumulates.

Claude Code's hook system (`global/hooks/` in this repo, deployed to `~/.claude/hooks/`) is strictly lifecycle-driven: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop` (per-turn), `SessionEnd`. There is no event for "a resource threshold was crossed" or any wall-clock timer. A hook can therefore observe the boundaries of a session, but not what happens *during* a single long session between those boundaries. The only mechanism capable of true mid-session, time-based automation is something external to Claude Code entirely — a Windows Scheduled Task running independently on an interval.

This tradeoff was surfaced explicitly and the user chose hook-only automation over adding a Scheduled Task, accepting that a single long session slowly turning to syrup mid-conversation will not be swept until that session ends.

## Decision

We will add `global/hooks/process_cleanup.py`, a Windows-only Python hook wired into both `SessionStart` and `SessionEnd` in `global/settings.json`. It shells out to a versioned copy of the validated engine script (`global/hooks/claude-process-check.ps1`) with `-Kill`, silently, under a timeout, and never fails the session (any error exits 0). Each run appends one line to `~/.claude/process_cleanup.log` (timestamp, event, orphans found/killed) for a forensic trail; `additionalContext` is only emitted on `SessionStart`, and only when something was actually killed, so a clean sweep produces no chat noise.

We will not add a Windows Scheduled Task for this feature. We will not use `Claude-ProcessCleanup.ps1` (no relatedness filter) or `NodeProcess-Check.ps1` (diagnostic-only, not designed for unattended killing) as the automated engine.

## Consequences

**Positive**

- Zero additional OS-level infrastructure — no Scheduled Task to register, maintain, or explain to a future reader of this machine's configuration.
- Cleanup is tied to Claude Code's own lifecycle: every fresh session starts with orphans from the previous session already swept, and every session close sweeps what it left behind.
- The automated engine (`claude-process-check.ps1 -Kill`) carries the Claude-relatedness filter and the explicit `node.exe` dev-server protection, so unattended silent killing does not risk a live dev server.
- Every run is logged, so silent auto-kill is still auditable after the fact.
- Versioning the engine script in this repo (`global/hooks/`) means it now deploys automatically through the existing hooks `Component` (`glob="*"`), with no manifest changes required.

**Negative**

- Does not solve the fullest form of the original request: a single long-running session that slowly accumulates orphans over hours will not be cleaned until that session ends. The "syrup slow mid-session" symptom is only partially addressed.
- Adds a Windows-only code path with no cross-platform equivalent; the hook silently no-ops on macOS/Linux.
- Two more subprocess calls (Python → PowerShell → `Get-CimInstance`) on every session start and end, bounded by a 20s timeout, adding minor latency to session boundaries.

**Neutral**

- `Claude-ProcessCleanup.ps1` and `NodeProcess-Check.ps1` remain untouched, loose manual-only tools in `C:\projects\`.
- The original loose `C:\projects\Claude-ProcessCheck.ps1` was copied, not moved, into the repo; whether to delete the loose original now that the repo copy is canonical is an open follow-up, not part of this decision.

## Alternatives Considered

**1. Windows Scheduled Task only (or in addition to the hook), running `-Kill` every 15–20 minutes.**
This is the only mechanism that provides genuine mid-session coverage, since it runs independently of Claude Code's lifecycle. Rejected (for now) in favor of the simpler hook-only approach — it adds external OS-level infrastructure and a second thing to maintain, for a symptom (long single sessions) judged less common than the session-boundary buildup the hook already addresses. Can be added later without touching the hook if mid-session slowness proves to still be a problem in practice.

**2. `Claude-ProcessCleanup.ps1` as the automated engine.**
Rejected. Its 3-pass sweep has no Claude-relatedness filter — any orphaned `node.exe` (including a non-Claude dev server that simply hasn't been touched in a while) would be killed. Unsafe to run silently and unattended.

**3. Dry-run/report-only automation, requiring manual review before killing.**
Rejected. This would not solve "syrup slow" automatically — the user would still have to notice the report and act on it, which is the exact manual-toil problem being solved. The engine script's existing safety filters were judged sufficient to run `-Kill` unattended.
