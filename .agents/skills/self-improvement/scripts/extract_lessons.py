#!/usr/bin/env python3
"""
Helper for the self-improvement skill's memory files.

Subcommands:
  list <file>          List every entry's ID + title in the named memory file.
                       <file> is one of: lessons | mistakes | preferences | evals
                       Omit <file> to list all four.

  remove <file> <id>   Remove the entry with the given ID. Prints the removed
                       block to stderr so it can be pasted back if needed.

  validate             Check every memory file: every entry has an ID matching
                       the file's prefix, IDs are unique, the required fields
                       are present. Exit 1 on any malformed entry.

Memory file layout: a top-of-file preamble followed by `### <ID> — <Title>`
headings separated by `---` horizontal rules. Each heading is followed by a
bullet list of fields.

Direct Edit on the memory files is always allowed; this script is a convenience.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Force UTF-8 on Windows consoles so em-dashes in titles don't mojibake.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"

FILES = {
    "lessons":     ("lessons.md",     "L"),
    "mistakes":    ("mistakes.md",    "M"),
    "preferences": ("preferences.md", "P"),
    "evals":       ("evals.md",       "E"),
}

ID_RE = re.compile(r"^(?P<prefix>[LMPE])-(?P<date>\d{8})-(?P<seq>\d{2})$")
HEADING_RE = re.compile(r"^###\s+(?P<id>\S+)\s+—\s+(?P<title>.+?)\s*$")


@dataclass
class Entry:
    entry_id: str
    title: str
    body: str  # raw markdown including the heading line


def _read(file_key: str) -> tuple[Path, str, str]:
    if file_key not in FILES:
        raise SystemExit(f"unknown file '{file_key}'; expected one of {', '.join(FILES)}")
    filename, prefix = FILES[file_key]
    path = MEMORY_DIR / filename
    if not path.exists():
        raise SystemExit(f"missing memory file: {path}")
    return path, prefix, path.read_text(encoding="utf-8")


def _parse(text: str) -> list[Entry]:
    """Split the markdown into entries. Every line starting with `### <ID> — <title>`
    begins a new entry; the entry body runs until the next such heading or EOF.
    `---` separators between entries are tolerated but not required."""
    lines = text.splitlines()
    entries: list[Entry] = []
    current_lines: list[str] = []
    current_id: str | None = None
    current_title: str | None = None

    def flush() -> None:
        if current_id is not None:
            body = "\n".join(current_lines).strip()
            entries.append(Entry(entry_id=current_id, title=current_title or "", body=body))

    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m:
            flush()
            current_id = m["id"]
            current_title = m["title"]
            current_lines = [line]
        else:
            if current_id is not None:
                current_lines.append(line)
    flush()
    return entries


def cmd_list(args: argparse.Namespace) -> int:
    keys = [args.file] if args.file else list(FILES)
    for key in keys:
        path, prefix, text = _read(key)
        entries = _parse(text)
        print(f"# {key} ({path.name}) — {len(entries)} entries")
        for e in entries:
            print(f"  {e.entry_id}  {e.title}")
        if key != keys[-1]:
            print()
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    path, prefix, text = _read(args.file)
    entries = _parse(text)
    target = next((e for e in entries if e.entry_id == args.id), None)
    if target is None:
        print(f"no entry with id {args.id} in {path.name}", file=sys.stderr)
        return 1

    print(f"--- removed from {path.name} ---", file=sys.stderr)
    print(target.body, file=sys.stderr)
    print("--- end ---", file=sys.stderr)

    # Rebuild: take the preamble (everything before the first `### ` heading),
    # then concatenate the remaining entry bodies separated by a blank line.
    first_heading = next((i for i, ln in enumerate(text.splitlines()) if HEADING_RE.match(ln.strip())), None)
    if first_heading is None:
        print("file has no entries; nothing to do", file=sys.stderr)
        return 1
    preamble = "\n".join(text.splitlines()[:first_heading]).rstrip()
    keep = [e.body for e in entries if e.entry_id != args.id]
    new_text = preamble + "\n\n" + "\n\n".join(keep) + "\n"
    path.write_text(new_text, encoding="utf-8")
    print(f"removed {args.id} from {path.name}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    errors: list[str] = []
    for key, (filename, prefix) in FILES.items():
        path = MEMORY_DIR / filename
        if not path.exists():
            errors.append(f"{filename}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        entries = _parse(text)
        seen: set[str] = set()
        for e in entries:
            m = ID_RE.match(e.entry_id)
            if not m:
                errors.append(f"{filename}: malformed id '{e.entry_id}'")
                continue
            if m["prefix"] != prefix:
                errors.append(f"{filename}: id '{e.entry_id}' has wrong prefix (expected {prefix}-)")
            if e.entry_id in seen:
                errors.append(f"{filename}: duplicate id '{e.entry_id}'")
            seen.add(e.entry_id)

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print("all memory files valid")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list entries")
    p_list.add_argument("file", nargs="?", choices=FILES.keys())
    p_list.set_defaults(func=cmd_list)

    p_remove = sub.add_parser("remove", help="remove an entry by id")
    p_remove.add_argument("file", choices=FILES.keys())
    p_remove.add_argument("id")
    p_remove.set_defaults(func=cmd_remove)

    p_validate = sub.add_parser("validate", help="validate all memory files")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
