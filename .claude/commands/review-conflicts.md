# Review Agent & Skill Conflicts

You are a configuration auditor for a Claude Code setup. Your job is to detect real conflicts, redundancies, and dead config across the user's agents, slash commands, hooks, memory, and settings — and surface them in a clear, actionable report.

---

## Step 1 — Collect all configuration

Read every file below. Do not skip any. Use parallel reads where possible.

**Settings & hooks**
- `~/.claude/settings.json`
- Every file under `~/.claude/hooks/`

**Slash commands**
- Every `.md` file under `~/.claude/commands/` (this file included — audit it too)

**Global instructions**
- `~/.claude/CLAUDE.md`
- Any files `@`-imported inside CLAUDE.md (e.g. `design.md`)

**Memory**

Derive the project memory path dynamically:
1. Get the current working directory (e.g. `C:\projects\my-app`)
2. Convert to a project slug: replace each path separator (`\` or `/`) with `--` and strip the drive colon (e.g. `C--projects--my-app`)
3. Read `~/.claude/projects/<slug>/memory/MEMORY.md`
4. Read every `.md` file linked from MEMORY.md

If no MEMORY.md exists for the current project, skip the memory section and note it in the report.

---

## Step 2 — Analyse for the following conflict types

### A. Hook conflicts
- **Dead hook**: a hook references a file that does not exist on disk.
- **Path format bug**: Windows paths using backslashes without quoting inside a JSON string command (Python, PowerShell, and shell all handle unquoted backslash-paths differently).
- **Duplicate matcher**: two `PreToolUse` or `PostToolUse` hooks match the same tool and could interfere or produce duplicate side-effects.
- **Missing tool coverage**: a hook exists in memory/docs as intended but is not wired into `settings.json`.

### B. Command vs hook overlap
- A slash command and a hook both handle the same threat or task but with different logic (e.g. prompt injection is screened by both `prompt-injection-guard.md` and `command_guard.py`). Flag whether the overlap is complementary or contradictory.
- A slash command describes a workflow that a hook already enforces automatically — user may not know the hook exists.

### C. Command vs command overlap
- Two slash commands produce the same output or cover the same domain.
- A slash command contradicts guidance in CLAUDE.md or a memory feedback entry (e.g. command says "always add XML doc comments" but memory says "no comments unless non-obvious").

### D. Memory conflicts
- Two memory entries give contradictory guidance on the same topic.
- A memory entry references a file path or function that no longer exists.
- A feedback memory entry conflicts with a slash command's conventions.

### E. MCP server redundancy
- Two MCP servers expose overlapping capabilities (e.g. two filesystem tools both covering `/projects`).

### F. Settings inconsistencies
- A hook type (e.g. `PreToolUse`) is wired up in `settings.json` but the corresponding script has a syntax error or wrong shebang for the platform.
- Model or channel settings that conflict with known project requirements in memory.

---

## Step 3 — Verify, don't assume

Before reporting a conflict:
- Confirm the file exists (a hook pointing to a missing script is a **Dead hook**, not just a warning).
- Read the actual logic of hook scripts to understand what they check — don't assume from the filename.
- If two items *could* conflict but probably don't in practice, mark them **Complementary** not **Conflict**.

---

## Step 4 — Report

Produce the report in this exact structure. Omit any section that has zero findings.

```
## Conflicts Report
Generated: <today's date>

### 🔴 Critical  (will cause errors or silent failures)
- **[category]** <item>: <what is wrong and why it matters>
  Fix: <exact change needed>

### 🟡 Redundant  (duplicate work, but nothing breaks)
- **[category]** <item>: <what overlaps and how>
  Recommendation: <keep / merge / remove one>

### 🟢 Complementary  (apparent overlap that is actually intentional layering)
- **[category]** <item A> + <item B>: <why they work together, not against each other>

### ℹ️ Minor  (organisational, cosmetic, or low-priority)
- <item>: <observation>

### ✅ Clean
<list the areas with no issues found>
```

Rules:
- Be specific — cite file names and line numbers where relevant.
- Never fabricate issues. If everything in a category is clean, say so under ✅ Clean.
- Do not suggest refactors or new features. Audit only.
- If a finding requires a one-line fix, include the exact fix inline under the finding.
