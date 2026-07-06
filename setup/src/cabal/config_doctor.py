# -*- coding: utf-8 -*-
"""Claude config health checks — detects silently-broken ~/.claude state (dead skills, BOMs, stale hook matchers)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from cabal import widget_cache
from cabal._paths import TARGET

# Bump when check logic changes so cached results from an older doctor re-run.
DOCTOR_VERSION = 1

# Tool names a PreToolUse/PostToolUse matcher can legitimately reference.
KNOWN_TOOLS = {
    "Agent", "Artifact", "AskUserQuestion", "Bash", "BashOutput", "Edit",
    "EnterPlanMode", "ExitPlanMode", "Glob", "Grep", "KillShell", "Monitor",
    "MultiEdit", "NotebookEdit", "PowerShell", "Read", "SendMessage", "Skill",
    "Task", "TaskCreate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
    "TaskUpdate", "TodoWrite", "WebFetch", "WebSearch", "Write",
}
# Old names that still parse but no longer match anything by themselves.
LEGACY_ONLY_TOOLS = {"Task"}

# Built-in slash commands / bundled skills a CLAUDE.md may reference.
BUILTIN_COMMANDS = {
    "add-dir", "agents", "batch", "bug", "claude-api", "clear", "code-review",
    "compact", "config", "context", "cost", "debug", "doctor", "export",
    "fast", "help", "hooks", "ide", "init", "install-github-app", "login",
    "logout", "loop", "mcp", "memory", "model", "output-style", "permissions",
    "plugin", "release-notes", "resume", "review", "rewind", "run",
    "run-skill-generator", "schedule", "security-review", "simplify",
    "skills", "statusline", "status", "terminal-setup", "todos", "upgrade",
    "usage", "verify", "vim",
}

_BOM = b"\xef\xbb\xbf"
_DESCRIPTION_LISTING_CAP = 1536
_USER_PATH_RE = re.compile(r"[A-Za-z]:\\+Users\\+([A-Za-z0-9._-]+)")
_SKILL_REF_RE = re.compile(r"`/([a-z][a-z0-9-]*)")
_HOOK_SCRIPT_RE = re.compile(r"hooks/([A-Za-z0-9_.-]+\.py)")


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" | "warning"
    category: str
    path: str
    message: str  # why it's unhealthy
    hint: str  # what to review / how to fix


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root.parent))
    except ValueError:
        return str(path)


def _frontmatter(text: str) -> dict[str, str] | None:
    """Naive single-line-value frontmatter parse; None when no --- block leads the file."""
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return None


def check_skills(skills_dir: Path, root: Path) -> list[Finding]:
    """Layout + frontmatter checks for one skills/ directory (personal or project)."""
    findings: list[Finding] = []
    if not skills_dir.is_dir():
        return findings
    for flat in sorted(skills_dir.glob("*.md")):
        findings.append(Finding(
            "error", "dead-flat-skill", _rel(flat, root),
            "Flat .md files directly under skills/ are never loaded by Claude Code.",
            f"Move it to skills/{flat.stem}/SKILL.md (or commands/{flat.name}), then redeploy.",
        ))
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            findings.append(Finding(
                "error", "missing-skill-md", _rel(skill_dir, root),
                "Skill directory has no SKILL.md, so the skill cannot load.",
                "Add a SKILL.md with frontmatter, or remove the directory.",
            ))
            continue
        findings.extend(_check_skill_md(skill_md, root))
    return findings


def _check_skill_md(skill_md: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    raw = skill_md.read_bytes()
    if raw.startswith(_BOM):
        findings.append(Finding(
            "error", "bom", _rel(skill_md, root),
            "File starts with a UTF-8 BOM, which breaks YAML frontmatter parsing "
            "(the skill loads with an empty description).",
            "Re-save the file as UTF-8 without BOM.",
        ))
    text = raw.lstrip(_BOM).decode("utf-8", errors="replace")
    fields = _frontmatter(text)
    if fields is None:
        findings.append(Finding(
            "warning", "no-frontmatter", _rel(skill_md, root),
            "No YAML frontmatter block — Claude has no description to match against.",
            "Add `---` frontmatter with at least a description field.",
        ))
        return findings
    description = fields.get("description", "")
    if not description:
        findings.append(Finding(
            "warning", "no-description", _rel(skill_md, root),
            "Frontmatter has no description, so the skill only triggers when typed as /name.",
            "Add a third-person description stating what the skill does and when to use it.",
        ))
    combined = len(description) + len(fields.get("when_to_use", ""))
    if combined > _DESCRIPTION_LISTING_CAP:
        findings.append(Finding(
            "warning", "description-too-long", _rel(skill_md, root),
            f"description + when_to_use is {combined} chars; the skill listing truncates "
            f"at {_DESCRIPTION_LISTING_CAP}, so trailing trigger keywords are invisible.",
            "Front-load the key use case and trim the description.",
        ))
    return findings


def check_agents(agents_dir: Path, root: Path) -> list[Finding]:
    """Frontmatter sanity for subagent definitions."""
    findings: list[Finding] = []
    if not agents_dir.is_dir():
        return findings
    for agent_md in sorted(agents_dir.glob("*.md")):
        raw = agent_md.read_bytes()
        if raw.startswith(_BOM):
            findings.append(Finding(
                "error", "bom", _rel(agent_md, root),
                "File starts with a UTF-8 BOM, which breaks YAML frontmatter parsing.",
                "Re-save the file as UTF-8 without BOM.",
            ))
        fields = _frontmatter(raw.lstrip(_BOM).decode("utf-8", errors="replace"))
        if fields is None or not fields.get("name") or not fields.get("description"):
            findings.append(Finding(
                "error", "agent-frontmatter", _rel(agent_md, root),
                "Subagent definitions require frontmatter with name and description; "
                "without them the agent is not registered.",
                "Add the missing frontmatter fields.",
            ))
    return findings


def check_hooks(settings_json: Path, hooks_dir: Path, root: Path) -> list[Finding]:
    """Hook wiring: referenced scripts exist; matchers reference tools that can still fire."""
    findings: list[Finding] = []
    if not settings_json.is_file():
        return findings
    try:
        settings = json.loads(settings_json.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return [Finding(
            "error", "settings-unparseable", _rel(settings_json, root),
            "settings.json is not valid JSON — no hooks or permissions load at all.",
            "Fix the JSON syntax (check for trailing commas or unquoted keys).",
        )]
    hooks = settings.get("hooks") or {}
    for event, groups in hooks.items():
        for group in groups if isinstance(groups, list) else []:
            findings.extend(_check_matcher(group.get("matcher"), event, settings_json, root))
            for hook in group.get("hooks") or []:
                command = hook.get("command", "")
                for script in _HOOK_SCRIPT_RE.findall(command):
                    if not (hooks_dir / script).is_file():
                        findings.append(Finding(
                            "error", "hook-script-missing", _rel(settings_json, root),
                            f"{event} hook references hooks/{script}, which does not exist — "
                            "the hook fails on every trigger.",
                            f"Restore {script} to {hooks_dir} or remove the hook entry.",
                        ))
    return findings


def _check_matcher(matcher: object, event: str, settings_json: Path, root: Path) -> list[Finding]:
    if not isinstance(matcher, str) or matcher in ("", "*") or not event.endswith("ToolUse"):
        return []
    segments = [s.strip() for s in matcher.split("|") if s.strip()]
    unknown = [s for s in segments if s not in KNOWN_TOOLS and not s.startswith("mcp__")]
    findings: list[Finding] = []
    if unknown:
        findings.append(Finding(
            "warning", "unknown-matcher-tool", _rel(settings_json, root),
            f'{event} matcher "{matcher}" references unknown tool(s) {unknown} — '
            "the hook may never fire.",
            "Check the current tool name in the Claude Code docs and update the matcher.",
        ))
    elif all(s in LEGACY_ONLY_TOOLS for s in segments):
        findings.append(Finding(
            "error", "legacy-matcher", _rel(settings_json, root),
            f'{event} matcher "{matcher}" only names legacy tools that no longer exist '
            "(Task was renamed to Agent) — the hook never fires.",
            'Widen the matcher, e.g. "Task|Agent".',
        ))
    return findings


def check_claude_md_refs(
    claude_md: Path, skill_sources: list[Path], root: Path
) -> list[Finding]:
    """`/skill-name` mentions in CLAUDE.md that resolve to nothing installed.

    skill_sources are skills/ or commands/ directories at any scope (personal
    and open-project) — a reference is dead only if no scope provides it.
    """
    if not claude_md.is_file():
        return []
    known = set(BUILTIN_COMMANDS)
    for source in skill_sources:
        if not source.is_dir():
            continue
        known.update(p.name for p in source.iterdir() if p.is_dir())
        known.update(p.stem for p in source.glob("*.md"))
    findings: list[Finding] = []
    text = claude_md.read_text(encoding="utf-8", errors="replace")
    for name in sorted(set(_SKILL_REF_RE.findall(text))):
        if name not in known:
            findings.append(Finding(
                "warning", "dead-skill-reference", _rel(claude_md, root),
                f"CLAUDE.md references `/{name}` but no such skill, command, or builtin "
                "is installed — sessions following that instruction hit a missing skill.",
                f"Install/restore the {name} skill or remove the reference.",
            ))
    return findings


def check_foreign_user_paths(dirs: list[Path], root: Path) -> list[Finding]:
    """Hardcoded C:\\Users\\<someone-else> paths break on this machine."""
    current_user = Path.home().name.lower()
    findings: list[Finding] = []
    for base in dirs:
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            users = {
                m.group(1)
                for m in _USER_PATH_RE.finditer(md.read_text(encoding="utf-8", errors="replace"))
                if m.group(1).lower() != current_user
            }
            if users:
                findings.append(Finding(
                    "warning", "foreign-user-path", _rel(md, root),
                    f"Hardcoded path(s) under C:\\Users\\{{{', '.join(sorted(users))}}} — "
                    "not this machine's user, so the referenced files won't be found.",
                    "Replace with ~/ or a path relative to the skill directory.",
                ))
    return findings


def run_doctor(target: Path = TARGET, project: Path | None = None) -> list[Finding]:
    """Run all checks against a deployed ~/.claude tree; errors first, then warnings.

    project (the currently open project, if any) contributes its .claude/skills
    and .claude/commands when resolving CLAUDE.md skill references.
    """
    skills = target / "skills"
    agents = target / "agents"
    skill_sources = [skills, target / "commands"]
    if project is not None:
        skill_sources += [project / ".claude" / "skills", project / ".claude" / "commands"]
    findings = [
        *check_skills(skills, target),
        *check_agents(agents, target),
        *check_hooks(target / "settings.json", target / "hooks", target),
        *check_claude_md_refs(target / "CLAUDE.md", skill_sources, target),
        *check_foreign_user_paths([skills, agents], target),
    ]
    findings.sort(key=lambda f: (f.severity != "error", f.path, f.category))
    return findings


def _checked_locations(target: Path, project: Path | None) -> list[Path]:
    dirs = [target / "skills", target / "agents", target / "hooks", target / "commands"]
    if project is not None:
        dirs += [project / ".claude" / "skills", project / ".claude" / "commands"]
    return dirs + [target / "settings.json", target / "CLAUDE.md"]


def tree_fingerprint(target: Path = TARGET, project: Path | None = None) -> str:
    """Cheap stat-based hash of every file the doctor looks at (path + mtime + size).

    No file contents are read, so this stays fast even on large trees; any
    deploy, edit, or deletion changes the fingerprint.
    """
    digest = hashlib.sha256(f"doctor-v{DOCTOR_VERSION}".encode())
    for location in _checked_locations(target, project):
        files = sorted(location.rglob("*")) if location.is_dir() else [location]
        for f in files:
            try:
                st = f.stat()
            except OSError:
                continue
            if f.is_file():
                digest.update(f"{f}|{st.st_mtime_ns}|{st.st_size}\n".encode())
    return digest.hexdigest()


def run_doctor_cached(
    target: Path = TARGET, project: Path | None = None
) -> tuple[list[Finding], bool]:
    """run_doctor, skipped when nothing changed since the last run.

    Returns (findings, from_cache). The cached result is reused only while the
    tree fingerprint matches; any change to the checked files re-runs the scan.
    """
    key = f"doctor:{target}"
    fingerprint = tree_fingerprint(target, project)
    payload = widget_cache.load_entry(key)
    if isinstance(payload, dict) and payload.get("fingerprint") == fingerprint:
        try:
            return [Finding(**f) for f in payload.get("findings", [])], True
        except TypeError:
            pass  # stale/foreign shape — fall through to a fresh scan
    findings = run_doctor(target, project)
    widget_cache.save_entry(
        key, {"fingerprint": fingerprint, "findings": [asdict(f) for f in findings]}
    )
    return findings, False
