#!/usr/bin/env python3
"""
PreToolUse guard: inspects Bash commands for prompt injection, hidden characters,
obfuscated execution, and destructive patterns before they run.

Exit 0  -> allow
Exit 2  -> block (prints JSON reason shown to Claude and user)
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


# All keys use \u escapes; keep them visible in source reviews.
DANGEROUS_UNICODE = {
    "\u200b": "zero-width space",
    "\u200c": "zero-width non-joiner",
    "\u200d": "zero-width joiner",
    "\u202e": "right-to-left override (text direction reversal)",
    "\u202a": "left-to-right embedding",
    "\u202b": "right-to-left embedding",
    "\u202c": "pop directional formatting",
    "\u2028": "line separator",
    "\u2029": "paragraph separator",
    "\ufeff": "BOM / zero-width no-break space",
    "\u00ad": "soft hyphen (invisible)",
    "\u2060": "word joiner (invisible)",
    "\u180e": "Mongolian vowel separator (invisible)",
}

PROMPT_INJECTION = [
    (
        r"ignore\s+(previous|above|prior|all)\s+instructions",
        "ignore-instructions pattern",
    ),
    (r"(?im)^\s*(system|assistant|human|user)\s*:\s", "role-prefix injection"),
    (r"<\|im_start\|>|<\|im_end\|>", "ChatML token"),
    (r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", "Llama/Mistral instruction token"),
    (r"###\s*(Instruction|Response|Human|Assistant)\b", "instruction-marker injection"),
    (
        r"disregard\s+(your\s+)?(previous|prior|above|all)",
        "disregard-instructions pattern",
    ),
    (r"IGNORE\s+AND\s+(PRINT|EXECUTE|RUN)", "explicit override injection"),
    (
        r"you\s+are\s+now\s+(?:in\s+)?(?:DAN|jailbreak|developer\s+mode)",
        "jailbreak pattern",
    ),
]

DESTRUCTIVE = [
    (
        r"\brm\s+(?:-\S*\s+)*-\S*r\S*\s+/(?:\s|$)",
        "recursive delete from filesystem root",
    ),
    (r"\brm\s+-rf\s+[~$\./]", "recursive force-delete from home/relative path"),
    (
        r"\bdd\s+.*if=/dev/(zero|random|urandom)\s+.*of=/dev/(sd|nvme|hd|vd)\w*(?!\d)",
        "full-disk wipe via dd",
    ),
    (r":\(\)\s*\{.*:\s*\|\s*:.*&.*\}", "fork bomb"),
    (r">\s*/dev/(sd|nvme|hd|vd)[a-z](?!\d)", "direct overwrite of disk device"),
    (r"\bmkfs\.\w+\s+/dev/(sd|nvme|hd|vd)[a-z](?!\d)", "format entire disk"),
    (r"\bshred\b.*?/dev/(sd|nvme|hd|vd)", "shred disk device"),
    (r"\bchmod\s+-R\s+777\s+/(?:\s|$)", "chmod 777 on filesystem root"),
]

OBFUSCATED_EXEC = [
    (r"base64\s+-d.*\|\s*(ba)?sh", "base64-decode piped to shell"),
    (
        r"echo\s+[A-Za-z0-9+/=]{30,}\s*\|.*base64.*\|.*(sh|bash|zsh|exec)",
        "encoded payload piped to shell",
    ),
    (r"\beval\s+\$\(", "eval with command substitution"),
    (r"\beval\s+`", "eval with backtick substitution"),
    (r"python[23]?\s+-c\s+[\"'].*exec.*base64", "Python eval of base64 payload"),
    (r"\$\(\s*curl\s+[^)]+\)\s*\|\s*(ba)?sh", "curl-pipe-to-shell"),
    (r"\$\(\s*wget\s+[^)]*-O\s*-[^)]*\)\s*\|\s*(ba)?sh", "wget-pipe-to-shell"),
    (r"\bcurl\s+-s[fSL]*\s+https?://\S+\s*\|\s*(ba)?sh", "curl-pipe-to-shell (direct)"),
    (r"\bwget\s+-q?O-\s+https?://\S+\s*\|\s*(ba)?sh", "wget-pipe-to-shell (direct)"),
    (r"\$\{[^}]*\$\{[^}]*\$\{", "triple-nested variable expansion (obfuscation)"),
    (
        r"\\x[0-9a-f]{2}(\\x[0-9a-f]{2}){4,}",
        "hex-encoded string (possible obfuscation)",
    ),
]

ENV_HIJACK = [
    (r"export\s+PATH\s*=\s*[\"']?/tmp", "PATH hijack: prepending /tmp"),
    (r"export\s+PATH\s*=\s*[\"']?\./", "PATH hijack: prepending relative path"),
    (r"export\s+LD_PRELOAD\s*=", "LD_PRELOAD injection"),
    (
        r"export\s+LD_LIBRARY_PATH\s*=\s*(/tmp|\.)",
        "LD_LIBRARY_PATH pointing to /tmp or .",
    ),
    (r"export\s+PYTHONPATH\s*=\s*(/tmp|\.(?!/dev))", "PYTHONPATH hijack"),
]

# Windows / PowerShell patterns
DESTRUCTIVE_PS = [
    (
        r"Remove-Item\s+.*-Recurse.*-Force\s+[A-Za-z]:\\(?:\s|$)",
        "recursive force-delete from drive root",
    ),
    (
        r"Remove-Item\s+.*-Force.*-Recurse\s+[A-Za-z]:\\(?:\s|$)",
        "recursive force-delete from drive root",
    ),
    (r"\bFormat-Volume\b", "disk format (Format-Volume)"),
    (r"\bClear-Disk\b", "disk wipe (Clear-Disk)"),
    (r"\bchmod\s+-R\s+777\s+[A-Za-z]:\\", "chmod 777 on Windows drive root"),
]

ENV_HIJACK_PS = [
    (
        r'\$env:PATH\s*=\s*["\']?[A-Za-z]:\\[Tt]emp',
        "PATH hijack: prepending temp directory",
    ),
    (r'\$env:PATH\s*=\s*["\']?\.(?!\\)', "PATH hijack: prepending relative path"),
    (r"Set-Item\s+Env:PATH\s+.*[Tt]emp", "PATH hijack via Set-Item"),
    (r"\$env:LD_PRELOAD\s*=", "LD_PRELOAD injection"),
]

OBFUSCATED_EXEC_PS = [
    (
        r"\[System\.Convert\]::FromBase64String.*Invoke-Expression",
        "PowerShell base64-decode exec",
    ),
    (r"\bIEX\s*\(", "Invoke-Expression shorthand (IEX)"),
    (r"Invoke-Expression\s+\(?\s*\[System", "Invoke-Expression with .NET conversion"),
    (r"&\s*\(\s*\[scriptblock\]::Create", "scriptblock injection"),
]

FORBIDDEN_PACKAGE_MANAGER = re.compile(
    r"(?im)(?:^|[;&|]\s*|&&\s*|\|\|\s*)\s*(?:command\s+)?"
    r"(npm|npx|yarn)(?:\.(?:cmd|ps1|bat))?\b"
)

# `find ... -delete` / `-exec rm` is only flagged as destructive when it would
# touch files that aren't safely recoverable from git — see
# _find_delete_targets_are_versioned_and_clean() below.
FIND_DELETE_RE = re.compile(
    r"(?:^|[;&|`(])\s*find\b.*?(?:-delete\b|-exec\s+(?:/bin/)?rm\b)",
    re.IGNORECASE | re.DOTALL,
)

_CHAIN_METACHARS = re.compile(r"(?<!\\)[;&|`]|\$\(")

MAX_FIND_DELETE_TARGETS = 500


def _tool_executable(env_var: str, name: str, *win_git_relative: str) -> str:
    override = os.environ.get(env_var)
    if override:
        return override
    if sys.platform == "win32":
        for root in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ):
            candidate = Path(root).joinpath(*win_git_relative)
            if candidate.exists():
                return str(candidate)
    return name


GIT = _tool_executable("PROMPTLIB_GIT", "git", "Git", "cmd", "git.exe")
FIND = _tool_executable("PROMPTLIB_FIND", "find", "Git", "usr", "bin", "find.exe")


def _is_single_find_invocation(command: str) -> bool:
    stripped = command.strip()
    if not re.match(r"^find\b", stripped, re.IGNORECASE):
        return False
    return not _CHAIN_METACHARS.search(stripped)


def _find_listing_variant(command: str) -> str | None:
    """Swap the destructive action for -print, keeping every predicate
    identical, so the dry run matches exactly the same files the real
    command would touch."""
    stripped = command.strip()

    delete_swap = re.sub(r"-delete\b", "-print", stripped, count=1)
    if delete_swap != stripped:
        return delete_swap

    exec_swap = re.sub(
        r"-exec\s+(?:/bin/)?rm\b.*?(?:\\;|\+)",
        "-print",
        stripped,
        count=1,
        flags=re.DOTALL,
    )
    if exec_swap != stripped:
        return exec_swap

    return None


def _run(cmd: list[str], cwd: str, timeout: int = 10) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _find_delete_targets_are_versioned_and_clean(command: str, cwd: str) -> bool:
    """A find-delete is only safe to wave through when every file it would
    touch is already tracked AND identical to the last commit — genuinely
    recoverable via git, not just 'happens to live in a repo somewhere'.
    Any ambiguity (compound command, unparseable predicates, no git repo,
    an untracked or modified target) fails closed to "not safe"."""
    try:
        if not _is_single_find_invocation(command):
            return False

        listing_command = _find_listing_variant(command)
        if listing_command is None:
            return False

        try:
            tokens = shlex.split(listing_command)
        except ValueError:
            return False

        listing = _run([FIND, *tokens[1:]], cwd=cwd)
        if listing is None or listing.returncode != 0:
            return False

        targets = [line for line in listing.stdout.splitlines() if line.strip()]
        if not targets:
            return True  # nothing would actually be deleted
        if len(targets) > MAX_FIND_DELETE_TARGETS:
            return False

        in_repo = _run([GIT, "rev-parse", "--is-inside-work-tree"], cwd=cwd)
        if in_repo is None or in_repo.returncode != 0:
            return False

        tracked = _run([GIT, "ls-files", "--error-unmatch", "--", *targets], cwd=cwd)
        if tracked is None or tracked.returncode != 0:
            return False

        clean = _run([GIT, "diff", "--quiet", "HEAD", "--", *targets], cwd=cwd)
        if clean is None or clean.returncode != 0:
            return False

        return True
    except Exception:
        return False


def scan(command: str, tool_name: str = "Bash", cwd: str | None = None) -> list[str]:
    issues = []

    # Hidden Unicode
    for char, name in DANGEROUS_UNICODE.items():
        if char in command:
            issues.append(f"Hidden Unicode: {name} (U+{ord(char):04X})")

    # Bare control characters (allow tab, newline, carriage return)
    for ch in command:
        cp = ord(ch)
        if cp < 32 and ch not in "\t\n\r":
            issues.append(f"Control character in command: U+{cp:04X}")
            break

    for pattern, label in PROMPT_INJECTION:
        if re.search(pattern, command, re.IGNORECASE):
            issues.append(f"Prompt injection: {label}")

    obfuscated = OBFUSCATED_EXEC + (
        OBFUSCATED_EXEC_PS if tool_name == "PowerShell" else []
    )
    destructive = DESTRUCTIVE_PS if tool_name == "PowerShell" else DESTRUCTIVE
    env_hijack = ENV_HIJACK_PS if tool_name == "PowerShell" else ENV_HIJACK

    for pattern, label in obfuscated:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            issues.append(f"Obfuscated execution: {label}")

    for pattern, label in destructive:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            issues.append(f"Destructive pattern: {label}")

    for pattern, label in env_hijack:
        if re.search(pattern, command, re.IGNORECASE):
            issues.append(f"Environment hijack: {label}")

    if FORBIDDEN_PACKAGE_MANAGER.search(command):
        issues.append(
            "Package manager policy: npm, npx, and yarn are forbidden; use pnpm/pnpm dlx or bun/bunx"
        )

    if FIND_DELETE_RE.search(command):
        resolved_cwd = cwd or os.getcwd()
        if not _find_delete_targets_are_versioned_and_clean(command, resolved_cwd):
            issues.append(
                "Destructive pattern: find + delete/exec-rm targeting files that "
                "are not fully tracked and committed (untracked, modified, or "
                "unverifiable) — not safely recoverable"
            )

    return issues


def main():
    if should_skip("command_guard"):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in {"Bash", "PowerShell"}:
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    issues = scan(command, tool_name, cwd)
    if not issues:
        sys.exit(0)

    bullet_list = "\n".join(f"  - {i}" for i in issues)
    snippet = command[:400] + ("..." if len(command) > 400 else "")

    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    f"[Command Guard] Blocked - suspicious content detected.\n\n"
                    f"Issues:\n{bullet_list}\n\n"
                    f"Command (truncated):\n  {snippet}\n\n"
                    f"Inspect the source of this command before proceeding."
                ),
            }
        )
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
