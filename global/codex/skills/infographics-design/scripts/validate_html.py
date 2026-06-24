"""Validate a single-file HTML infographic.

Checks:
    - Tag stack balance (every open tag has a matching close)
    - CSS brace count balance inside the <style> block
    - Gradient count budget (default: <=3)
    - Cell anatomy consistency (badge / sub / cell-foot occurrences match cell count)

Usage:
    python validate_html.py <path-to-html> [--gradients=N]
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class StackParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in VOID:
            return
        self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            self.errors.append(f"L{self.getpos()[0]}: </{tag}> with empty stack")
            return
        top, opened = self.stack[-1]
        if top != tag:
            self.errors.append(
                f"L{self.getpos()[0]}: expected </{top}> (opened L{opened}) got </{tag}>"
            )
            return
        self.stack.pop()


def report(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK " if ok else "FAIL"
    line = f"  [{mark}] {label}"
    if detail:
        line += f"  {detail}"
    print(line)


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2

    path = Path(sys.argv[1])
    gradient_budget = 3
    for arg in sys.argv[2:]:
        if arg.startswith("--gradients="):
            gradient_budget = int(arg.split("=", 1)[1])

    if not path.exists():
        sys.stderr.write(f"missing: {path}\n")
        return 1

    html = path.read_text(encoding="utf-8")
    print(f"Validating {path}  ({len(html):,} chars)")
    failures = 0

    # 1. Tag stack
    v = StackParser()
    v.feed(html)
    real_errors = [e for e in v.errors if "meta" not in e]
    report(
        "tag balance",
        not real_errors and not v.stack,
        f"errors={len(real_errors)} unclosed={[t for t,_ in v.stack][:5]}",
    )
    for e in real_errors[:5]:
        print(f"         - {e}")
    failures += int(bool(real_errors or v.stack))

    # 2. CSS braces
    m = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    if m:
        css = m.group(1)
        opens, closes = css.count("{"), css.count("}")
        report(
            "css braces",
            opens == closes,
            f"{opens} open / {closes} close",
        )
        failures += int(opens != closes)
    else:
        report("css braces", True, "no <style> block")

    # 3. Gradient budget
    grads = sum(html.count(g) for g in ("linear-gradient(", "conic-gradient(", "radial-gradient("))
    report(
        "gradient budget",
        grads <= gradient_budget,
        f"{grads} found, budget {gradient_budget}",
    )
    failures += int(grads > gradient_budget)

    # 4. Cell anatomy consistency — match only `cell` followed by space or quote
    # (so it doesn't also catch `cell-foot`).
    cells = len(re.findall(r'class="cell[\s"]', html))
    badges = html.count('class="badge')
    subs = len(re.findall(r'class="sub"', html))
    foots = html.count('class="cell-foot"')
    consistent = cells == badges == subs == foots and cells > 0
    report(
        "cell anatomy",
        consistent,
        f"cells={cells} badges={badges} subs={subs} foots={foots}",
    )
    failures += int(not consistent)

    print(f"\nResult: {'PASS' if failures == 0 else f'FAIL ({failures} check(s))'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
