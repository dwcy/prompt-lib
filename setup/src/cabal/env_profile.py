# -*- coding: utf-8 -*-
"""Shell-rc profile rewriter used by EnvScreen's Apply action on Unix."""

from __future__ import annotations

import re
from pathlib import Path


def update_profile(profile_path: str, keys: list[str], export_lines: list[str]) -> None:
    """Rewrite `profile_path` so its `# claude-code-env` block contains only `export_lines`.

    Removes any prior `export <KEY>=...` lines for the given `keys` and any stray
    `# claude-code-env` marker, then appends the marker + fresh exports. No-ops if
    the profile file does not exist.
    """
    path = Path(profile_path).expanduser()
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    pat = re.compile(r"^export (" + "|".join(re.escape(k) for k in keys) + r")=")
    kept = [l for l in lines if not pat.match(l) and l.strip() != "# claude-code-env"]
    with path.open("w", encoding="utf-8") as f:
        f.writelines(kept)
        f.write("# claude-code-env\n")
        for line in export_lines:
            f.write(line + "\n")
