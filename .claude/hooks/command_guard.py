#!/usr/bin/env python3
"""
PreToolUse guard: inspects Bash commands for prompt injection, hidden characters,
obfuscated execution, and destructive patterns before they run.

Exit 0  → allow
Exit 2  → block (prints JSON reason shown to Claude and user)
"""

import json
import re
import sys


DANGEROUS_UNICODE = {
    "​": "zero-width space",
    "‌": "zero-width non-joiner",
    "‍": "zero-width joiner",
    "‮": "right-to-left override (text direction reversal)",
    "‪": "left-to-right embedding",
    "‫": "right-to-left embedding",
    "‬": "pop directional formatting",
    " ": "line separator",
    " ": "paragraph separator",
    "﻿": "BOM / zero-width no-break space",
    "­": "soft hyphen (invisible)",
    "⁠": "word joiner (invisible)",
    "᠎": "Mongolian vowel separator (invisible)",
}

PROMPT_INJECTION = [
    (r"ignore\s+(previous|above|prior|all)\s+instructions", "ignore-instructions pattern"),
    (r"(system|assistant|human|user)\s*:\s*(?=\S)", "role-prefix injection"),
    (r"<\|im_start\|>|<\|im_end\|>", "ChatML token"),
    (r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", "Llama/Mistral instruction token"),
    (r"###\s*(Instruction|Response|Human|Assistant)\b", "instruction-marker injection"),
    (r"disregard\s+(your\s+)?(previous|prior|above|all)", "disregard-instructions pattern"),
    (r"IGNORE\s+AND\s+(PRINT|EXECUTE|RUN)", "explicit override injection"),
    (r"you\s+are\s+now\s+(?:in\s+)?(?:DAN|jailbreak|developer\s+mode)", "jailbreak pattern"),
]

DESTRUCTIVE = [
    (r"\brm\s+(?:-\S*\s+)*-\S*r\S*\s+/(?:\s|$)", "recursive delete from filesystem root"),
    (r"\brm\s+-rf\s+[~$\./]", "recursive force-delete from home/relative path"),
    (r"\bdd\s+.*if=/dev/(zero|random|urandom)\s+.*of=/dev/(sd|nvme|hd|vd)\w*(?!\d)",
     "full-disk wipe via dd"),
    (r":\(\)\s*\{.*:\s*\|\s*:.*&.*\}", "fork bomb"),
    (r">\s*/dev/(sd|nvme|hd|vd)[a-z](?!\d)", "direct overwrite of disk device"),
    (r"\bmkfs\.\w+\s+/dev/(sd|nvme|hd|vd)[a-z](?!\d)", "format entire disk"),
    (r"\bshred\b.*?/dev/(sd|nvme|hd|vd)", "shred disk device"),
    (r"\bchmod\s+-R\s+777\s+/(?:\s|$)", "chmod 777 on filesystem root"),
]

OBFUSCATED_EXEC = [
    (r"base64\s+-d.*\|\s*(ba)?sh", "base64-decode piped to shell"),
    (r"echo\s+[A-Za-z0-9+/=]{30,}\s*\|.*base64.*\|.*(sh|bash|zsh|exec)",
     "encoded payload piped to shell"),
    (r"\beval\s+\$\(", "eval with command substitution"),
    (r"\beval\s+`", "eval with backtick substitution"),
    (r"python[23]?\s+-c\s+[\"'].*exec.*base64", "Python eval of base64 payload"),
    (r"\$\(\s*curl\s+[^)]+\)\s*\|\s*(ba)?sh", "curl-pipe-to-shell"),
    (r"\$\(\s*wget\s+[^)]*-O\s*-[^)]*\)\s*\|\s*(ba)?sh", "wget-pipe-to-shell"),
    (r"\bcurl\s+-s[fSL]*\s+https?://\S+\s*\|\s*(ba)?sh", "curl-pipe-to-shell (direct)"),
    (r"\bwget\s+-q?O-\s+https?://\S+\s*\|\s*(ba)?sh", "wget-pipe-to-shell (direct)"),
    (r"\$\{[^}]*\$\{[^}]*\$\{", "triple-nested variable expansion (obfuscation)"),
    (r"\\x[0-9a-f]{2}(\\x[0-9a-f]{2}){4,}", "hex-encoded string (possible obfuscation)"),
]

ENV_HIJACK = [
    (r"export\s+PATH\s*=\s*[\"']?/tmp", "PATH hijack: prepending /tmp"),
    (r"export\s+PATH\s*=\s*[\"']?\./", "PATH hijack: prepending relative path"),
    (r"export\s+LD_PRELOAD\s*=", "LD_PRELOAD injection"),
    (r"export\s+LD_LIBRARY_PATH\s*=\s*(/tmp|\.)", "LD_LIBRARY_PATH pointing to /tmp or ."),
    (r"export\s+PYTHONPATH\s*=\s*(/tmp|\.(?!/dev))", "PYTHONPATH hijack"),
]


def scan(command: str) -> list[str]:
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

    for pattern, label in DESTRUCTIVE:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            issues.append(f"Destructive pattern: {label}")

    for pattern, label in OBFUSCATED_EXEC:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            issues.append(f"Obfuscated execution: {label}")

    for pattern, label in ENV_HIJACK:
        if re.search(pattern, command, re.IGNORECASE):
            issues.append(f"Environment hijack: {label}")

    return issues


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    issues = scan(command)
    if not issues:
        sys.exit(0)

    bullet_list = "\n".join(f"  • {i}" for i in issues)
    snippet = command[:400] + ("..." if len(command) > 400 else "")

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"[Command Guard] Blocked — suspicious content detected.\n\n"
            f"Issues:\n{bullet_list}\n\n"
            f"Command (truncated):\n  {snippet}\n\n"
            f"Inspect the source of this command before proceeding."
        )
    }))
    sys.exit(2)


if __name__ == "__main__":
    main()
