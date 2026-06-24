"""Count files matching one or more glob patterns — for feature audits.

Use BEFORE designing an infographic to get the actual numbers driving the
stat row and the per-card badges. Never guess; never round up.

Usage:
    python audit_features.py "<glob>" ["<glob>" ...]

Example:
    python audit_features.py \\
        "global/agents/*.md" \\
        "global/skills/*.md" \\
        "global/hooks/*" \\
        "global/output-styles/*.md" \\
        "global/rules/*.md"
"""

from __future__ import annotations

import sys
from pathlib import Path


def audit(pattern: str) -> list[Path]:
    p = Path(pattern)
    base = p.parent if str(p.parent) else Path(".")
    glob = p.name
    if not base.exists():
        return []
    return sorted(f for f in base.glob(glob) if f.is_file())


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2

    width = max(len(p) for p in sys.argv[1:]) + 2
    grand_total = 0

    for pattern in sys.argv[1:]:
        matches = audit(pattern)
        count = len(matches)
        grand_total += count
        marker = " " if count else "!"
        print(f"{marker} {pattern.ljust(width)} {count:>3}")
        for m in matches[:5]:
            print(f"        - {m.name}")
        if len(matches) > 5:
            print(f"        ... +{len(matches) - 5} more")

    print(f"\n  {'TOTAL'.ljust(width)} {grand_total:>3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
